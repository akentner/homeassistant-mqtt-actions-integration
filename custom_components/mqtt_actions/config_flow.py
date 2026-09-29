"""Config flow: hub entry and switch device subentries."""

import uuid
from typing import Any

import probatio
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

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

CONF_NAME = "name"


class MqttActionsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Hub flow: one entry per Home Assistant instance, requires MQTT (D-11)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the base topic and the instance name; the instance id is generated (D-11)."""
        if not self.hass.config_entries.async_entries("mqtt"):
            return self.async_abort(reason="mqtt_required")
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_INSTANCE_NAME],
                data={
                    CONF_BASE_TOPIC: user_input[CONF_BASE_TOPIC],
                    CONF_INSTANCE_NAME: user_input[CONF_INSTANCE_NAME],
                    CONF_INSTANCE_ID: str(uuid.uuid4()),
                },
            )
        schema = probatio.Schema(
            {
                probatio.Required(CONF_BASE_TOPIC, default=DEFAULT_BASE_TOPIC): str,
                probatio.Required(CONF_INSTANCE_NAME, default=self.hass.config.location_name): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:  # noqa: ARG003
        """Return the subentry types this integration supports."""
        return {SUBENTRY_SWITCH: SwitchSubentryFlow}


class SwitchSubentryFlow(ConfigSubentryFlow):
    """Create a switch device; the device id is a fresh uuid4 that never changes (D-03)."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Ask for a name and the two action lists."""
        if user_input is not None:
            device_id = str(uuid.uuid4())
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                unique_id=device_id,
                data={
                    CONF_DEVICE_ID: device_id,
                    # Store the RAW selector output, never the validated form
                    CONF_ON_CHANGE_TO_ON: user_input.get(CONF_ON_CHANGE_TO_ON, []),
                    CONF_ON_CHANGE_TO_OFF: user_input.get(CONF_ON_CHANGE_TO_OFF, []),
                    CONF_RUN_ON_STARTUP: False,
                },
            )
        schema = probatio.Schema(
            {
                probatio.Required(CONF_NAME): str,
                probatio.Optional(CONF_ON_CHANGE_TO_ON, default=[]): selector.ActionSelector(),
                probatio.Optional(CONF_ON_CHANGE_TO_OFF, default=[]): selector.ActionSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
