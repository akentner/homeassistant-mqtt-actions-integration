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
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector
from homeassistant.helpers.translation import async_get_translations

from .actions import ActionsInvalid, async_validate_actions, find_device_ids
from .const import (
    CONF_ACTIONS,
    CONF_BASE_TOPIC,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DELETE_DEVICES_ON_REMOVE,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_EXPORT,
    CONF_EXPORT_PREFIX,
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
    DEFAULT_EXPORT_PREFIX,
    DOMAIN,
    MAX_OPTIONS,
    MIN_OPTIONS,
    RUN_MODE_RESTART,
    RUN_MODE_SERIAL,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from .document import escape_markdown
from .local_actions import LocalActionMode
from .local_actions_store import LocalActionsStore
from .manager import (
    LOCAL_ACTION_INVALID_ACTIONS,
    LOCAL_ACTION_INVALID_MODE,
    LOCAL_ACTION_NOT_RUNNING,
    LOCAL_ACTION_SAVE_FAILED,
    LOCAL_ACTION_STALE_TARGET,
    LocalActionDevice,
    LocalActionError,
    LocalActionTrigger,
    Manager,
    async_local_action_device_count,
)
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

# Fields and section of the local actions editor of the hub options (D-06, D-13)
CONF_DEVICE = "device"
CONF_TRIGGER = "trigger"
CONF_LOCAL_SECTION = "local_actions"
CONF_LOCAL_MODE = "mode"
CONF_LOCAL_ACTIONS = "actions"
# Translation keys of the mode selector and of the direct markers of a trigger label (D-16)
LOCAL_MODE_TRANSLATION_KEY = "local_mode"
LOCAL_STATUS_TRANSLATION_KEY = "local_trigger_status"
LOCAL_STATUS_MARKERS: tuple[str, ...] = ("additive", "replacement", "muted", "orphan", "kind_mismatch", "no_mirror")
# Separator between the identifying part of a picker label and its markers
LABEL_SEPARATOR = " — "

# Why the Manager refused a local edit (LocalActionError.reason) -> base error of the editor
LOCAL_ERRORS: dict[str, str] = {
    LOCAL_ACTION_NOT_RUNNING: "not_loaded",
    LOCAL_ACTION_STALE_TARGET: "stale_target",
    LOCAL_ACTION_INVALID_MODE: "invalid_mode",
    LOCAL_ACTION_INVALID_ACTIONS: "invalid_local_actions",
    LOCAL_ACTION_SAVE_FAILED: "save_failed",
}

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
                # A leftover local Store of an earlier, removed hub must not reach the new one (D-08, D-02, G-03)
                await LocalActionsStore(self.hass).async_remove_records()
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
        """Return the options flow of the hub: the keep-or-delete choice (D-11) and the discovery export (D-03)."""
        return HubOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:  # noqa: ARG003
        """Return the subentry types this integration supports."""
        return {SUBENTRY_SWITCH: SwitchSubentryFlow, SUBENTRY_SELECT: SelectSubentryFlow}


class HubOptionsFlow(OptionsFlow):
    """
    Hub options: a menu of the hub settings and the local actions of mirrored devices (D-06).

    The settings are what removing the hub does to the devices (D-11) and the optional MQTT Discovery export (D-03).
    Only submitted keys are stored, so an omitted export key means the default: off, and the default prefix.

    The local actions editor is a thin client of the Manager (T-11-24): device, then trigger, then mode and actions.
    Each confirmed save or removal goes to the Manager at once, which validates, rechecks the target and stores it in
    its own Store; the flow never writes a local customization into the entry options or a subentry. A draft lives
    only in this flow, so leaving it, or closing the dialog, drops nothing but the unsaved edit (D-13).
    """

    def __init__(self) -> None:
        """Start without a chosen device, trigger or draft."""
        super().__init__()
        self._local_device: LocalActionDevice | None = None
        self._local_target: LocalActionTrigger | None = None
        # The submitted but not yet saved mode and actions of the chosen trigger
        self._local_draft: dict[str, Any] | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  # noqa: ARG002
        """Offer the hub settings and the local actions of mirrored devices."""
        return self.async_show_menu(step_id="init", menu_options=["settings", "local_actions"])

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """
        Show the delete choice, the export switch and the export prefix, and store what is submitted.

        The description warns how many devices lose their local actions when the hub is removed, in either removal
        mode (D-08); the count is read again each time the form is shown.
        """
        errors: dict[str, str] = {}
        if user_input is not None:
            options: dict[str, Any] = {
                CONF_DELETE_DEVICES_ON_REMOVE: bool(user_input.get(CONF_DELETE_DEVICES_ON_REMOVE, False))
            }
            if CONF_DISCOVERY_EXPORT in user_input:
                options[CONF_DISCOVERY_EXPORT] = bool(user_input[CONF_DISCOVERY_EXPORT])
            if CONF_EXPORT_PREFIX in user_input:
                prefix = str(user_input[CONF_EXPORT_PREFIX]).strip()
                try:
                    validate_base_topic(prefix)
                except InvalidBaseTopic:
                    errors[CONF_EXPORT_PREFIX] = "invalid_export_prefix"
                options[CONF_EXPORT_PREFIX] = prefix
            if not errors:
                return self.async_create_entry(data=options)
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_DELETE_DEVICES_ON_REMOVE, default=False): selector.BooleanSelector(),
                probatio.Optional(CONF_DISCOVERY_EXPORT): selector.BooleanSelector(),
                probatio.Optional(CONF_EXPORT_PREFIX): selector.TextSelector(),
            }
        )
        stored = self.config_entry.options
        suggested = {
            CONF_DELETE_DEVICES_ON_REMOVE: bool(stored.get(CONF_DELETE_DEVICES_ON_REMOVE, False)),
            CONF_DISCOVERY_EXPORT: bool(stored.get(CONF_DISCOVERY_EXPORT, False)),
            CONF_EXPORT_PREFIX: str(stored.get(CONF_EXPORT_PREFIX, DEFAULT_EXPORT_PREFIX)),
        }
        if user_input is not None:
            # A refused submit shows what the user typed, not the stored values
            suggested.update(user_input)
        local_devices = await async_local_action_device_count(self.hass, self.config_entry)
        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders={"local_action_device_count": str(local_devices)},
        )

    # --- local actions of mirrored devices (D-06, D-11 to D-16) -------------------------------------------------

    def _local_manager(self) -> Manager | None:
        """Return the Manager of the hub while it is loaded, else None; read at every step, never kept."""
        entry = self.config_entry
        if entry.state is not ConfigEntryState.LOADED:
            return None
        return entry.runtime_data

    async def async_step_local_actions(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose the device: every current mirror, then devices known only from saved local records (D-12)."""
        if (manager := self._local_manager()) is None:
            return self.async_abort(reason="not_loaded")
        devices = manager.local_action_devices()
        if not devices:
            return self.async_abort(reason="no_local_devices")
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = next((device for device in devices if device.device_id == user_input[CONF_DEVICE]), None)
            if chosen is not None:
                self._local_device = chosen
                return await self.async_step_local_actions_device()
            errors["base"] = "stale_target"
        texts = await self._local_texts()
        schema = probatio.Schema(
            {
                probatio.Required(CONF_DEVICE): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=device.device_id, label=self._device_label(device, texts))
                            for device in devices
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="local_actions", data_schema=schema, errors=errors)

    async def async_step_local_actions_device(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """
        Choose the trigger of the device; the labels name it and show its local mode directly (D-11, D-16).

        The value of an option is the stable identity (kind and StateValue), never the shown text. Returning here
        drops any unsaved draft (D-13).
        """
        if (manager := self._local_manager()) is None:
            return self.async_abort(reason="not_loaded")
        if self._local_device is None:
            return await self.async_step_local_actions()
        # Read again: the device may have gained or lost its mirror since it was chosen
        device_id = self._local_device.device_id
        self._local_device = next(
            (device for device in manager.local_action_devices() if device.device_id == device_id), None
        )
        rows = manager.local_action_triggers(device_id) if self._local_device is not None else ()
        if not rows:
            return await self.async_step_local_actions()
        self._local_target = None
        self._local_draft = None
        errors: dict[str, str] = {}
        if user_input is not None:
            chosen = next((row for row in rows if _trigger_value(row) == user_input[CONF_TRIGGER]), None)
            if chosen is not None:
                self._local_target = chosen
                if chosen.record is None:
                    return await self.async_step_local_actions_edit()
                return await self.async_step_local_actions_trigger()
            errors["base"] = "stale_target"
        return await self._async_show_trigger_picker(rows, errors)

    async def _async_show_trigger_picker(
        self, rows: Sequence[LocalActionTrigger], errors: dict[str, str]
    ) -> ConfigFlowResult:
        """Show the trigger selection of the chosen device with the given errors."""
        texts = await self._local_texts()
        schema = probatio.Schema(
            {
                probatio.Required(CONF_TRIGGER): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=_trigger_value(row), label=self._trigger_label(row, texts))
                            for row in rows
                        ],
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="local_actions_device",
            data_schema=schema,
            errors=errors,
            description_placeholders={"device": escape_markdown(self._local_device_name())},
        )

    async def async_step_local_actions_trigger(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:  # noqa: ARG002
        """Offer what can be done with a trigger that already has a saved local customization."""
        if self._local_target is None:
            return await self.async_step_local_actions_device()
        return self.async_show_menu(
            step_id="local_actions_trigger",
            menu_options=["local_actions_edit", "local_actions_confirm_remove", "local_actions_device"],
            description_placeholders=self._target_placeholders(),
        )

    async def async_step_local_actions_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """
        Edit the mode and the local actions of the chosen trigger; a new customization starts additive (D-15).

        A submit is saved through the Manager at once and returns to the trigger selection (D-13). The Manager owns
        validation and the target recheck; a refusal shows a base error and keeps the submitted values.
        """
        if self._local_target is None:
            return await self.async_step_local_actions_device()
        if user_input is None:
            return self._show_local_editor(self._local_values())
        values = user_input.get(CONF_LOCAL_SECTION) or {}
        self._local_draft = {
            CONF_LOCAL_MODE: values.get(CONF_LOCAL_MODE, str(LocalActionMode.ADDITIVE)),
            CONF_LOCAL_ACTIONS: copy.deepcopy(values.get(CONF_LOCAL_ACTIONS) or []),
        }
        if (
            self._local_draft[CONF_LOCAL_MODE] == LocalActionMode.REPLACEMENT
            and not self._local_draft[CONF_LOCAL_ACTIONS]
        ):
            # Instead of with no actions mutes the trigger here; that needs its own confirmation (D-15)
            return await self.async_step_local_actions_confirm_mute()
        return await self._async_save_local(self._local_draft[CONF_LOCAL_MODE], self._local_draft[CONF_LOCAL_ACTIONS])

    async def async_step_local_actions_confirm_mute(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """
        Ask before an empty replacement is saved: the trigger then runs no action at all on this instance (D-15).

        This is not the removal: removing restores the owner actions, muting suppresses them here. Going back to the
        editor keeps the draft; going back to the triggers drops it. Nothing is saved before the confirmation.
        """
        if self._local_target is None or self._local_draft is None:
            return await self.async_step_local_actions_device()
        return self.async_show_menu(
            step_id="local_actions_confirm_mute",
            menu_options=["local_actions_mute_confirmed", "local_actions_edit", "local_actions_device"],
            description_placeholders=self._target_placeholders(),
        )

    async def async_step_local_actions_mute_confirmed(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Save the confirmed mute: a replacement without local actions."""
        if self._local_target is None or self._local_draft is None:
            return await self.async_step_local_actions_device()
        return await self._async_save_local(str(LocalActionMode.REPLACEMENT), [])

    async def async_step_local_actions_confirm_remove(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Ask before the local customization is removed; this restores the owner actions, subject to approval."""
        if self._local_target is None or self._local_target.record is None:
            return await self.async_step_local_actions_device()
        return self.async_show_menu(
            step_id="local_actions_confirm_remove",
            menu_options=["local_actions_remove_confirmed", "local_actions_device"],
            description_placeholders=self._target_placeholders(),
        )

    async def async_step_local_actions_remove_confirmed(
        self,
        user_input: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Remove the local customization through the Manager and return to the trigger selection."""
        target = self._local_target
        if target is None:
            return await self.async_step_local_actions_device()
        if (manager := self._local_manager()) is None:
            return self.async_abort(reason="not_loaded")
        try:
            await manager.async_remove_local_action(target.identity)
        except LocalActionError as err:
            rows = manager.local_action_triggers(target.identity.device_id)
            if not rows:
                return await self.async_step_local_actions()
            self._local_target = None
            error = LOCAL_ERRORS.get(err.reason, LOCAL_ERRORS[LOCAL_ACTION_SAVE_FAILED])
            return await self._async_show_trigger_picker(rows, {"base": error})
        return await self.async_step_local_actions_device()

    async def _async_save_local(self, mode: str, actions: list[dict[str, Any]]) -> ConfigFlowResult:
        """Save the draft through the Manager; back to the trigger selection, or the editor with a base error."""
        target = self._local_target
        manager = self._local_manager()
        if target is None:
            return await self.async_step_local_actions_device()
        placeholders: dict[str, str] = {}
        if manager is None:
            errors = {"base": LOCAL_ERRORS[LOCAL_ACTION_NOT_RUNNING]}
        else:
            try:
                await manager.async_set_local_action(target.identity, mode, actions)
            except LocalActionError as err:
                errors = {"base": LOCAL_ERRORS.get(err.reason, LOCAL_ERRORS[LOCAL_ACTION_SAVE_FAILED])}
                if err.reason == LOCAL_ACTION_INVALID_ACTIONS:
                    # The validation message, capped; the submitted action data is never echoed (T-01-09)
                    placeholders["error"] = str(err.__cause__ or err)[:MAX_FLOW_ERROR_LENGTH]
            else:
                return await self.async_step_local_actions_device()
        return self._show_local_editor(self._local_values(), errors, placeholders)

    def _local_values(self) -> dict[str, Any]:
        """Return the editor values: the unsaved draft, else the saved record, else a new additive customization."""
        if self._local_draft is not None:
            return self._local_draft
        record = self._local_target.record if self._local_target is not None else None
        if record is not None:
            return {CONF_LOCAL_MODE: str(record.mode), CONF_LOCAL_ACTIONS: record.copy_actions()}
        return {CONF_LOCAL_MODE: str(LocalActionMode.ADDITIVE), CONF_LOCAL_ACTIONS: []}

    def _show_local_editor(
        self,
        values: Mapping[str, Any],
        errors: dict[str, str] | None = None,
        placeholders: Mapping[str, str] | None = None,
    ) -> ConfigFlowResult:
        """
        Show the editor: one expanded section with the mode and the action selector (11-02 frontend smoke).

        The section stays expanded, because a collapsed one folds again after a base error; the guidance for the
        action list lives in the section description, because the action selector shows no field description.
        """
        fields = probatio.Schema(
            {
                probatio.Required(CONF_LOCAL_MODE, default=str(LocalActionMode.ADDITIVE)): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[str(LocalActionMode.ADDITIVE), str(LocalActionMode.REPLACEMENT)],
                        mode=selector.SelectSelectorMode.LIST,
                        translation_key=LOCAL_MODE_TRANSLATION_KEY,
                    )
                ),
                probatio.Optional(CONF_LOCAL_ACTIONS, default=[]): selector.ActionSelector(),
            }
        )
        schema = probatio.Schema({probatio.Required(CONF_LOCAL_SECTION): section(fields, {"collapsed": False})})
        return self.async_show_form(
            step_id="local_actions_edit",
            data_schema=self.add_suggested_values_to_schema(schema, {CONF_LOCAL_SECTION: dict(values)}),
            errors=errors or {},
            description_placeholders={**self._target_placeholders(), **(placeholders or {})},
        )

    def _local_device_name(self) -> str:
        """Return the name of the chosen device; a device known only from records shows its id."""
        device = self._local_device
        if device is None:
            return ""
        return device.name or device.device_id

    def _target_placeholders(self) -> dict[str, str]:
        """Return the escaped device name, trigger label and StateValue; all come from the broker (T-11-26)."""
        target = self._local_target
        return {
            "device": escape_markdown(self._local_device_name()),
            "trigger": escape_markdown(target.label if target is not None else ""),
            "state_value": escape_markdown(target.state_value if target is not None else ""),
        }

    async def _local_texts(self) -> dict[str, str]:
        """
        Return the translated markers of the picker labels, in the language of this instance.

        A selector option label is plain text the frontend does not translate, so the markers are looked up here.
        """
        translations = await async_get_translations(self.hass, self.hass.config.language, "selector", [DOMAIN])
        prefix = f"component.{DOMAIN}.selector.{LOCAL_STATUS_TRANSLATION_KEY}.options."
        return {marker: translations.get(prefix + marker, marker) for marker in LOCAL_STATUS_MARKERS}

    @staticmethod
    def _device_label(device: LocalActionDevice, texts: Mapping[str, str]) -> str:
        """Return the label of a device: its name, or its id and a marker while only saved records know it."""
        if device.mirrored:
            return device.name or device.device_id
        return LABEL_SEPARATOR.join((device.device_id, texts["no_mirror"]))

    def _trigger_label(self, row: LocalActionTrigger, texts: Mapping[str, str]) -> str:
        """
        Return friendly name and StateValue of a trigger, then its direct markers (D-11, D-12, D-16).

        The first marker is the local mode: additional, instead of the owner actions, or muted for an empty
        replacement. An inactive record adds why it is inactive: its option is gone from the owner, it was saved for
        the other device kind, or the device is not mirrored right now. An inactive record never runs.
        """
        name = row.label
        # A Switch trigger is named by its StateValue; showing it twice adds nothing
        if row.label != row.state_value:
            name = f"{row.label} ({row.state_value})"
        markers: list[str] = []
        if row.record is not None:
            if row.record.mode is LocalActionMode.REPLACEMENT and not row.record.actions:
                markers.append(texts["muted"])
            else:
                markers.append(texts[str(row.record.mode)])
        if not row.present:
            device = self._local_device
            if device is None or not device.mirrored:
                markers.append(texts["no_mirror"])
            elif row.identity.kind != device.kind:
                markers.append(texts["kind_mismatch"])
            else:
                markers.append(texts["orphan"])
        return LABEL_SEPARATOR.join((name, *markers))


def _trigger_value(row: LocalActionTrigger) -> str:
    """Return the option value of a trigger row: its stable identity within the device, never the shown text."""
    return json.dumps([row.identity.kind, row.identity.state_value])


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
                "name": escape_markdown(self._draft[CONF_NAME]),
                "count": str(len(options)),
                "options": "\n".join(
                    f"- {escape_markdown(option[CONF_FRIENDLY_NAME])} ({escape_markdown(option[CONF_STATE_VALUE])})"
                    for option in options
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
            description_placeholders={**placeholders, "state_value": escape_markdown(option[CONF_STATE_VALUE])},
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
                "friendly_name": escape_markdown(option[CONF_FRIENDLY_NAME]),
                "state_value": escape_markdown(option[CONF_STATE_VALUE]),
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
