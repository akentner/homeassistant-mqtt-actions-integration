"""Config flow: hub entry and switch device subentries."""

import json
import uuid
from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .actions import ActionsInvalid, async_validate_actions, find_device_ids
from .const import (
    CONF_BASE_TOPIC,
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_RUN_ON_STARTUP,
    DEFAULT_BASE_TOPIC,
    DOMAIN,
    SUBENTRY_SWITCH,
)
from .topics import InvalidBaseTopic, validate_base_topic

if TYPE_CHECKING:
    from collections.abc import Mapping

CONF_NAME = "name"

# Validation error text shown in the form is capped; the submitted action data is never echoed (T-01-09)
MAX_FLOW_ERROR_LENGTH = 200

# Action fields in check order, with the label shown in the invalid_actions error
ACTION_FIELDS: tuple[tuple[str, str], ...] = (
    (CONF_ON_CHANGE_TO_ON, "onChangeToOn"),
    (CONF_ON_CHANGE_TO_OFF, "onChangeToOff"),
)


class MqttActionsConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Hub flow: one entry per Home Assistant instance, requires MQTT (D-11).

    There is deliberately no reconfigure step: the base topic is baked into retained broker messages (D-01).
    """

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the base topic and the instance name; the instance id is generated (D-11)."""
        if not self.hass.config_entries.async_entries("mqtt"):
            return self.async_abort(reason="mqtt_required")

        errors: dict[str, str] = {}
        if user_input is not None:
            base_topic = user_input[CONF_BASE_TOPIC].strip()
            instance_name = user_input[CONF_INSTANCE_NAME].strip()
            try:
                validate_base_topic(base_topic)
            except InvalidBaseTopic:
                errors[CONF_BASE_TOPIC] = "invalid_base_topic"
            if not instance_name:
                errors[CONF_INSTANCE_NAME] = "instance_name_required"
            if not errors:
                return self.async_create_entry(
                    title=instance_name,
                    data={
                        CONF_BASE_TOPIC: base_topic,
                        CONF_INSTANCE_NAME: instance_name,
                        CONF_INSTANCE_ID: str(uuid.uuid4()),
                    },
                )

        schema = probatio.Schema(
            {
                probatio.Required(CONF_BASE_TOPIC, default=DEFAULT_BASE_TOPIC): str,
                probatio.Required(CONF_INSTANCE_NAME, default=self.hass.config.location_name): str,
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:  # noqa: ARG003
        """Return the subentry types this integration supports."""
        return {SUBENTRY_SWITCH: SwitchSubentryFlow}


class SwitchSubentryFlow(ConfigSubentryFlow):
    """Create or reconfigure a switch device; the device id is a fresh uuid4 that never changes (D-03)."""

    def __init__(self) -> None:
        """Initialise the per-flow fingerprint used for warn-then-confirm (D-10)."""
        super().__init__()
        self._confirmed_fingerprint: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Ask for a name and the two action lists."""
        return await self._async_handle_form("user", user_input, None)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Edit name, actions and startup flag of an existing switch; the device id stays."""
        return await self._async_handle_form("reconfigure", user_input, self._get_reconfigure_subentry())

    async def _async_handle_form(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        subentry: ConfigSubentry | None,
    ) -> SubentryFlowResult:
        """Validate and store the form; shared by create and reconfigure."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                errors, placeholders = await self._async_check_actions(user_input)
            if not errors:
                # Store the RAW selector output, never the validated form (Template objects)
                data: dict[str, Any] = {
                    CONF_ON_CHANGE_TO_ON: user_input.get(CONF_ON_CHANGE_TO_ON, []),
                    CONF_ON_CHANGE_TO_OFF: user_input.get(CONF_ON_CHANGE_TO_OFF, []),
                    CONF_RUN_ON_STARTUP: user_input.get(CONF_RUN_ON_STARTUP, False),
                }
                if subentry is None:
                    device_id = str(uuid.uuid4())
                    return self.async_create_entry(
                        title=name,
                        unique_id=device_id,
                        data={CONF_DEVICE_ID: device_id, **data},
                    )
                # Replace, do not merge, so a cleared list stays cleared; re-inject the immutable device id
                return self.async_update_and_abort(
                    self._get_entry(),
                    subentry,
                    title=name,
                    data={**data, CONF_DEVICE_ID: subentry.data[CONF_DEVICE_ID]},
                )

        schema = probatio.Schema(
            {
                probatio.Required(CONF_NAME): str,
                probatio.Optional(CONF_ON_CHANGE_TO_ON, default=[]): selector.ActionSelector(),
                probatio.Optional(CONF_ON_CHANGE_TO_OFF, default=[]): selector.ActionSelector(),
                probatio.Optional(CONF_RUN_ON_STARTUP, default=False): selector.BooleanSelector(),
            }
        )
        suggested = user_input if user_input is not None else self._prefill(subentry)
        if suggested is not None:
            schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def _async_check_actions(self, user_input: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
        """Return (errors, placeholders) for the action lists: invalid actions first, then the device_id warning."""
        for field, label in ACTION_FIELDS:
            try:
                await async_validate_actions(self.hass, user_input.get(field, []))
            except ActionsInvalid as err:
                # A base error always renders as a form alert; the action selector may not show field errors
                return {"base": "invalid_actions"}, {"field": label, "error": str(err)[:MAX_FLOW_ERROR_LENGTH]}

        device_ids = find_device_ids([user_input.get(field, []) for field, _ in ACTION_FIELDS])
        if device_ids:
            fingerprint = json.dumps(user_input, sort_keys=True, default=str)
            if fingerprint != self._confirmed_fingerprint:
                self._confirmed_fingerprint = fingerprint
                return {"base": "device_id_warning"}, {"device_ids": ", ".join(device_ids)}
        return {}, {}

    @staticmethod
    def _prefill(subentry: ConfigSubentry | None) -> dict[str, Any] | None:
        """Return the form values of an existing subentry, or None when creating."""
        if subentry is None:
            return None
        return {
            CONF_NAME: subentry.title,
            CONF_ON_CHANGE_TO_ON: subentry.data.get(CONF_ON_CHANGE_TO_ON, []),
            CONF_ON_CHANGE_TO_OFF: subentry.data.get(CONF_ON_CHANGE_TO_OFF, []),
            CONF_RUN_ON_STARTUP: subentry.data.get(CONF_RUN_ON_STARTUP, False),
        }
