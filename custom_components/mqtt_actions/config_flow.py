"""Config flow: hub entry, switch device subentries and select device subentries."""

import copy
import json
import uuid
from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentry,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .actions import ActionsInvalid, async_validate_actions, find_device_ids
from .const import (
    CONF_ACTIONS,
    CONF_BASE_TOPIC,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DELETE_DEVICES_ON_REMOVE,
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_INSTANCE_ID,
    CONF_INSTANCE_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_OPTIONS,
    CONF_RUN_MODE,
    CONF_RUN_ON_STARTUP,
    CONF_STATE_VALUE,
    DEFAULT_BASE_TOPIC,
    DEFAULT_BREAKER_MAX_RUNS,
    DEFAULT_BREAKER_WINDOW,
    DOMAIN,
    MAX_OPTIONS,
    MIN_OPTIONS,
    RUN_MODE_RESTART,
    RUN_MODE_SERIAL,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from .document import escape_markdown
from .model import invalid_name, validate_breaker, validate_option
from .topics import InvalidBaseTopic, validate_base_topic

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

CONF_NAME = "name"

# Validation error text shown in the form is capped; the submitted action data is never echoed (T-01-09)
MAX_FLOW_ERROR_LENGTH = 200

# Field of the option chooser steps
CONF_OPTION = "option"

# Settings every device stores, in the order they are read back from a draft
SETTINGS_KEYS: tuple[str, ...] = (CONF_RUN_ON_STARTUP, CONF_RUN_MODE, CONF_BREAKER_MAX_RUNS, CONF_BREAKER_WINDOW)

# Action fields in check order, with the label shown in the invalid_actions error
ACTION_FIELDS: tuple[tuple[str, str], ...] = (
    (CONF_ON_CHANGE_TO_ON, "onChangeToOn"),
    (CONF_ON_CHANGE_TO_OFF, "onChangeToOff"),
)


class MqttActionsConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Hub flow: one entry per Home Assistant instance, requires MQTT (D-11).

    There is deliberately no reconfigure step: the base topic is baked into retained broker messages (D-01). What
    happens to the devices when the hub is removed is chosen in the options flow beforehand, because Home Assistant
    offers no hook or dialog during the removal itself (D-11).
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
            elif invalid_name(instance_name):
                # The same rule the parser applies: a longer name would make every document of this instance unreadable
                errors[CONF_INSTANCE_NAME] = "instance_name_invalid"
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HubOptionsFlow:  # noqa: ARG004
        """Return the options flow of the hub: the keep-or-delete choice for its removal (D-11)."""
        return HubOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:  # noqa: ARG003
        """Return the subentry types this integration supports."""
        return {SUBENTRY_SWITCH: SwitchSubentryFlow, SUBENTRY_SELECT: SelectSubentryFlow}


class HubOptionsFlow(OptionsFlow):
    """
    Choose what removing the hub does to the devices on the broker (D-11).

    A plain options flow, not a reload-on-change one: saving the option triggers the update listener, whose reconcile
    finds nothing to do. Nothing is published here; the choice is only read when the entry is removed.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the delete choice, off by default, and store it."""
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_DELETE_DEVICES_ON_REMOVE: bool(user_input.get(CONF_DELETE_DEVICES_ON_REMOVE, False))}
            )
        schema = probatio.Schema(
            {probatio.Optional(CONF_DELETE_DEVICES_ON_REMOVE, default=False): selector.BooleanSelector()}
        )
        stored = bool(self.config_entry.options.get(CONF_DELETE_DEVICES_ON_REMOVE, False))
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, {CONF_DELETE_DEVICES_ON_REMOVE: stored}),
        )


class _DeviceSubentryFlow(ConfigSubentryFlow):
    """Shared parts of the device flows: action checking with warn-then-confirm and the run mode and breaker fields."""

    def __init__(self) -> None:
        """Initialise the per-flow fingerprint used for warn-then-confirm (D-10)."""
        super().__init__()
        self._confirmed_fingerprint: str | None = None

    async def _async_check_actions(
        self, entries: Sequence[tuple[str, Any]], fingerprint_source: Any
    ) -> tuple[dict[str, str], dict[str, str]]:
        """
        Return (errors, placeholders) for labelled action lists: invalid actions first, then the device_id warning.

        `entries` holds (label, raw actions) pairs; the label names the offending list and the action data is never
        echoed (T-02-22). The warning is shown once per distinct `fingerprint_source`, so an identical resubmit saves.
        """
        for label, raw_actions in entries:
            try:
                await async_validate_actions(self.hass, raw_actions)
            except ActionsInvalid as err:
                # A base error always renders as a form alert; the action selector may not show field errors
                return {"base": "invalid_actions"}, {"field": label, "error": str(err)[:MAX_FLOW_ERROR_LENGTH]}

        device_ids = find_device_ids([raw_actions for _label, raw_actions in entries])
        if device_ids:
            fingerprint = json.dumps(fingerprint_source, sort_keys=True, default=str)
            if fingerprint != self._confirmed_fingerprint:
                self._confirmed_fingerprint = fingerprint
                return {"base": "device_id_warning"}, {"device_ids": ", ".join(device_ids)}
        return {}, {}

    def _online_instance_count(self) -> int:
        """Return the number of other instances currently online; 0 while the hub entry is not loaded."""
        entry = self._get_entry()
        if entry.state is not ConfigEntryState.LOADED:
            return 0
        return int(entry.runtime_data.online_instance_count())

    async def async_step_delete_device(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """
        Ask whether the device really goes, on every connected instance and not only on this one (D-16, SYN-06).

        This is the only door to `delete_confirmed`: a menu accepts only its own options, so the removal cannot be
        reached without passing here. The generic Home Assistant delete cannot be vetoed and ends in the same removal.
        """
        return self.async_show_menu(
            step_id="delete_device",
            menu_options=["delete_confirmed", "keep_device"],
            description_placeholders={
                "name": escape_markdown(self._get_reconfigure_subentry().title),
                "count": str(self._online_instance_count()),
            },
        )

    async def async_step_delete_confirmed(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """Remove the subentry; the reconcile that follows clears the broker topics in the delete order (D-16)."""
        self.hass.config_entries.async_remove_subentry(self._get_entry(), self._get_reconfigure_subentry().subentry_id)
        return self.async_abort(reason="device_deleted")

    @staticmethod
    def _settings_fields() -> dict[Any, Any]:
        """Return the schema entries every device shares: startup flag, run mode and circuit breaker limits."""
        return {
            probatio.Optional(CONF_RUN_ON_STARTUP, default=False): selector.BooleanSelector(),
            probatio.Optional(CONF_RUN_MODE, default=RUN_MODE_SERIAL): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[RUN_MODE_SERIAL, RUN_MODE_RESTART],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_RUN_MODE,
                )
            ),
            # No min and max here: an out-of-range value must come back as a translated error on the field, and the
            # selector would reject it as invalid data before the flow sees it. validate_breaker owns the ranges.
            probatio.Optional(CONF_BREAKER_MAX_RUNS, default=DEFAULT_BREAKER_MAX_RUNS): selector.NumberSelector(
                selector.NumberSelectorConfig(step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            probatio.Optional(CONF_BREAKER_WINDOW, default=DEFAULT_BREAKER_WINDOW): selector.NumberSelector(
                selector.NumberSelectorConfig(step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s")
            ),
        }

    @staticmethod
    def _validate_settings(user_input: Mapping[str, Any]) -> dict[str, str]:
        """Return the range errors of the breaker fields of a submitted settings form."""
        return validate_breaker(
            user_input.get(CONF_BREAKER_MAX_RUNS, DEFAULT_BREAKER_MAX_RUNS),
            user_input.get(CONF_BREAKER_WINDOW, DEFAULT_BREAKER_WINDOW),
        )

    @staticmethod
    def _coerce_settings(user_input: Mapping[str, Any]) -> dict[str, Any]:
        """Return the settings to store; the number selector returns floats and ints are stored (T-02-21)."""
        return {
            CONF_RUN_ON_STARTUP: bool(user_input.get(CONF_RUN_ON_STARTUP, False)),
            CONF_RUN_MODE: user_input.get(CONF_RUN_MODE, RUN_MODE_SERIAL),
            CONF_BREAKER_MAX_RUNS: int(user_input.get(CONF_BREAKER_MAX_RUNS, DEFAULT_BREAKER_MAX_RUNS)),
            CONF_BREAKER_WINDOW: int(user_input.get(CONF_BREAKER_WINDOW, DEFAULT_BREAKER_WINDOW)),
        }


class SwitchSubentryFlow(_DeviceSubentryFlow):
    """Create or reconfigure a switch device; the device id is a fresh uuid4 that never changes (D-03)."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Ask for a name and the two action lists."""
        return await self._async_handle_form("user", user_input, None)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """
        Offer to edit or delete an existing switch (D-16).

        The presence of this step is what makes Home Assistant offer reconfigure.
        """
        return self.async_show_menu(step_id="reconfigure", menu_options=["edit_device", "delete_device"])

    async def async_step_edit_device(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Edit name, actions and startup flag of an existing switch; the device id stays."""
        return await self._async_handle_form("edit_device", user_input, self._get_reconfigure_subentry())

    async def async_step_keep_device(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """Leave the device alone and go back to the reconfigure menu."""
        return await self.async_step_reconfigure()

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
            elif invalid_name(name):
                errors[CONF_NAME] = "name_invalid"
            errors.update(self._validate_settings(user_input))
            if not errors:
                errors, placeholders = await self._async_check_actions(
                    [(label, user_input.get(field, [])) for field, label in ACTION_FIELDS], user_input
                )
            if not errors:
                # Store the RAW selector output, never the validated form (Template objects)
                data: dict[str, Any] = {
                    CONF_ON_CHANGE_TO_ON: user_input.get(CONF_ON_CHANGE_TO_ON, []),
                    CONF_ON_CHANGE_TO_OFF: user_input.get(CONF_ON_CHANGE_TO_OFF, []),
                    **self._coerce_settings(user_input),
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
                **self._settings_fields(),
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
            CONF_RUN_MODE: subentry.data.get(CONF_RUN_MODE, RUN_MODE_SERIAL),
            CONF_BREAKER_MAX_RUNS: subentry.data.get(CONF_BREAKER_MAX_RUNS, DEFAULT_BREAKER_MAX_RUNS),
            CONF_BREAKER_WINDOW: subentry.data.get(CONF_BREAKER_WINDOW, DEFAULT_BREAKER_WINDOW),
        }


class SelectSubentryFlow(_DeviceSubentryFlow):
    """
    Create a select device as a menu loop over an in-memory draft (D-01).

    Nothing is stored before Done, and a menu cannot show errors, so invalid states are made unreachable instead: Done
    is hidden until there are two options and Add is hidden at the cap. Validation lives in the form steps (D-04).
    """

    def __init__(self) -> None:
        """Start with an empty draft; the settings step fills the name and the shared settings."""
        super().__init__()
        self._draft: dict[str, Any] = {CONF_OPTIONS: []}
        # StateValue of the option the edit or remove steps work on; the StateValue is the option's identity (D-03)
        self._selected: str | None = None

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """
        Load the stored device into a private draft and open the menu.

        The presence of this step is what makes Home Assistant offer reconfigure. The draft is a deep copy: stored data
        is never mutated, which would change configuration without an update listener call (T-02-24).
        """
        subentry = self._get_reconfigure_subentry()
        data = subentry.data
        self._draft = {
            CONF_NAME: subentry.title,
            CONF_RUN_ON_STARTUP: data.get(CONF_RUN_ON_STARTUP, False),
            CONF_RUN_MODE: data.get(CONF_RUN_MODE, RUN_MODE_SERIAL),
            CONF_BREAKER_MAX_RUNS: data.get(CONF_BREAKER_MAX_RUNS, DEFAULT_BREAKER_MAX_RUNS),
            CONF_BREAKER_WINDOW: data.get(CONF_BREAKER_WINDOW, DEFAULT_BREAKER_WINDOW),
            CONF_OPTIONS: copy.deepcopy(list(data.get(CONF_OPTIONS, []))),
        }
        return await self.async_step_menu()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Ask for the name and the settings of the device, then open the menu."""
        return await self._async_settings_form("user", user_input)

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Edit the name and the settings from the menu."""
        return await self._async_settings_form("settings", user_input)

    async def _async_settings_form(self, step_id: str, user_input: dict[str, Any] | None) -> SubentryFlowResult:
        """Show or process the settings form; it is the first step and can be reopened from the menu."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            elif invalid_name(name):
                errors[CONF_NAME] = "name_invalid"
            errors.update(self._validate_settings(user_input))
            if not errors:
                self._draft.update({CONF_NAME: name, **self._coerce_settings(user_input)})
                return await self.async_step_menu()

        schema = probatio.Schema({probatio.Required(CONF_NAME): str, **self._settings_fields()})
        suggested = user_input if user_input is not None else self._draft_settings()
        if suggested is not None:
            schema = self.add_suggested_values_to_schema(schema, suggested)
        return self.async_show_form(step_id=step_id, data_schema=schema, errors=errors)

    def _draft_settings(self) -> dict[str, Any] | None:
        """Return the form values of the draft, or None while the settings were never submitted."""
        if CONF_NAME not in self._draft:
            return None
        return {key: self._draft[key] for key in (CONF_NAME, *SETTINGS_KEYS)}

    async def async_step_menu(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """Show the menu of the draft; the entries offered depend on how many options exist."""
        options: list[dict[str, Any]] = self._draft[CONF_OPTIONS]
        menu_options: list[str] = []
        if len(options) < MAX_OPTIONS:
            menu_options.append("add_option")
        if options:
            menu_options.append("edit_option")
        if len(options) > MIN_OPTIONS:
            menu_options.append("remove_option")
        menu_options.append("settings")
        if len(options) >= MIN_OPTIONS:
            menu_options.append("done")
        # Deleting needs a stored device, so only the reconfigure menu offers it (D-16)
        if self.source == SOURCE_RECONFIGURE:
            menu_options.append("delete_device")
        return self.async_show_menu(
            step_id="menu",
            menu_options=menu_options,
            description_placeholders={
                "name": self._draft[CONF_NAME],
                "count": str(len(options)),
                "options": "\n".join(
                    f"- {option[CONF_FRIENDLY_NAME]} ({option[CONF_STATE_VALUE]})" for option in options
                ),
            },
        )

    async def async_step_add_option(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add an option at the end of the list (D-05)."""
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        options: list[dict[str, Any]] = self._draft[CONF_OPTIONS]

        if user_input is not None:
            errors = validate_option(user_input[CONF_STATE_VALUE], user_input[CONF_FRIENDLY_NAME], self._others())
            if not errors:
                friendly_name = user_input[CONF_FRIENDLY_NAME].strip()
                errors, placeholders = await self._async_check_actions(
                    [(friendly_name, user_input.get(CONF_ACTIONS, []))], user_input
                )
            if not errors:
                # Store the RAW selector output, never the validated form (Template objects)
                options.append(
                    {
                        CONF_STATE_VALUE: user_input[CONF_STATE_VALUE],
                        CONF_FRIENDLY_NAME: friendly_name,
                        CONF_ACTIONS: user_input.get(CONF_ACTIONS, []),
                    }
                )
                return await self.async_step_menu()

        schema = probatio.Schema(
            {
                probatio.Required(CONF_STATE_VALUE): str,
                probatio.Required(CONF_FRIENDLY_NAME): str,
                probatio.Optional(CONF_ACTIONS, default=[]): selector.ActionSelector(),
            }
        )
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="add_option", data_schema=schema, errors=errors, description_placeholders=placeholders
        )

    def _others(self, *, skip: str | None = None) -> list[tuple[str, str]]:
        """Return the (StateValue, friendly name) pairs of the draft's options, leaving out the option `skip`."""
        return [
            (option[CONF_STATE_VALUE], option[CONF_FRIENDLY_NAME])
            for option in self._draft[CONF_OPTIONS]
            if option[CONF_STATE_VALUE] != skip
        ]

    def _selected_option(self) -> dict[str, Any] | None:
        """Return the draft option the edit or remove steps work on, or None when it is gone."""
        return next(
            (option for option in self._draft[CONF_OPTIONS] if option[CONF_STATE_VALUE] == self._selected), None
        )

    def _chooser_schema(self) -> probatio.Schema:
        """Return the schema of the option chooser: the value is the StateValue, the label the friendly name."""
        return probatio.Schema(
            {
                probatio.Required(CONF_OPTION): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=option[CONF_STATE_VALUE], label=option[CONF_FRIENDLY_NAME])
                            for option in self._draft[CONF_OPTIONS]
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )

    async def async_step_edit_option(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Choose the option to edit."""
        if user_input is None:
            return self.async_show_form(step_id="edit_option", data_schema=self._chooser_schema())
        self._selected = user_input[CONF_OPTION]
        return await self.async_step_edit_option_details()

    async def async_step_edit_option_details(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Edit the friendly name and the actions of the chosen option; the StateValue is locked (D-03)."""
        option = self._selected_option()
        if option is None:
            return await self.async_step_menu()

        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None:
            errors = validate_option(
                option[CONF_STATE_VALUE],
                user_input[CONF_FRIENDLY_NAME],
                self._others(skip=option[CONF_STATE_VALUE]),
                editing=True,
            )
            if not errors:
                friendly_name = user_input[CONF_FRIENDLY_NAME].strip()
                errors, placeholders = await self._async_check_actions(
                    [(friendly_name, user_input.get(CONF_ACTIONS, []))], user_input
                )
            if not errors:
                option[CONF_FRIENDLY_NAME] = friendly_name
                option[CONF_ACTIONS] = user_input.get(CONF_ACTIONS, [])
                return await self.async_step_menu()

        # There is deliberately no StateValue field in this schema
        schema = probatio.Schema(
            {
                probatio.Required(CONF_FRIENDLY_NAME): str,
                probatio.Optional(CONF_ACTIONS, default=[]): selector.ActionSelector(),
            }
        )
        suggested = (
            user_input
            if user_input is not None
            else {CONF_FRIENDLY_NAME: option[CONF_FRIENDLY_NAME], CONF_ACTIONS: option[CONF_ACTIONS]}
        )
        return self.async_show_form(
            step_id="edit_option_details",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders={**placeholders, "state_value": option[CONF_STATE_VALUE]},
        )

    async def async_step_remove_option(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Choose the option to remove; the removal itself needs a confirmation (D-02)."""
        if len(self._draft[CONF_OPTIONS]) <= MIN_OPTIONS:
            return await self.async_step_menu()
        if user_input is None:
            return self.async_show_form(step_id="remove_option", data_schema=self._chooser_schema())
        self._selected = user_input[CONF_OPTION]
        return await self.async_step_remove_confirm()

    async def async_step_remove_confirm(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """Ask whether the chosen option really goes."""
        option = self._selected_option()
        if option is None:
            return await self.async_step_menu()
        return self.async_show_menu(
            step_id="remove_confirm",
            menu_options=["remove_confirmed", "keep_option"],
            description_placeholders={
                "friendly_name": option[CONF_FRIENDLY_NAME],
                "state_value": option[CONF_STATE_VALUE],
            },
        )

    async def async_step_remove_confirmed(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """Remove the confirmed option from the draft, unless that would leave fewer than the minimum."""
        option = self._selected_option()
        if option is not None and len(self._draft[CONF_OPTIONS]) > MIN_OPTIONS:
            self._draft[CONF_OPTIONS].remove(option)
        self._selected = None
        return await self.async_step_menu()

    async def async_step_keep_option(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """Leave the option alone and go back to the menu."""
        self._selected = None
        return await self.async_step_menu()

    async def async_step_keep_device(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:  # noqa: ARG002
        """Leave the device alone and go back to the menu with the draft as it was."""
        return await self.async_step_menu()

    async def async_step_done(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Store the device once: create it with a fresh uuid4 device id, or replace the stored data (D-03)."""
        if len(self._draft[CONF_OPTIONS]) < MIN_OPTIONS:
            return await self.async_step_menu(user_input)
        if self.source == SOURCE_RECONFIGURE:
            subentry = self._get_reconfigure_subentry()
            # Replace, do not merge; re-inject the immutable device id
            return self.async_update_and_abort(
                self._get_entry(),
                subentry,
                title=self._draft[CONF_NAME],
                data={**self._device_data(), CONF_DEVICE_ID: subentry.data[CONF_DEVICE_ID]},
            )
        device_id = str(uuid.uuid4())
        return self.async_create_entry(
            title=self._draft[CONF_NAME],
            unique_id=device_id,
            data={CONF_DEVICE_ID: device_id, **self._device_data()},
        )

    def _device_data(self) -> dict[str, Any]:
        """Return the settings and options of the draft as they are stored; deep-copied so the draft stays private."""
        return {
            **{key: self._draft[key] for key in SETTINGS_KEYS},
            CONF_OPTIONS: copy.deepcopy(self._draft[CONF_OPTIONS]),
        }
