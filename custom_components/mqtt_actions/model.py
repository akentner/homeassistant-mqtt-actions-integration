"""Pure device model: one DeviceSpec per subentry, built from stored data. No Home Assistant imports at runtime."""

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .const import (
    CONF_ACTIONS,
    CONF_BREAKER_MAX_RUNS,
    CONF_BREAKER_WINDOW,
    CONF_DEVICE_ID,
    CONF_FRIENDLY_NAME,
    CONF_ON_CHANGE_TO_OFF,
    CONF_ON_CHANGE_TO_ON,
    CONF_OPTIONS,
    CONF_RUN_MODE,
    CONF_RUN_ON_STARTUP,
    CONF_STATE_VALUE,
    DEFAULT_BREAKER_MAX_RUNS,
    DEFAULT_BREAKER_WINDOW,
    PAYLOAD_OFF,
    PAYLOAD_ON,
    RUN_MODE_RESTART,
    RUN_MODE_SERIAL,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
    TRIGGER_OFF,
    TRIGGER_ON,
)
from .state import SWITCH_ACCEPTED

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigSubentry


def trigger_key(value: str) -> str:
    """
    Return the stable key of a trigger, derived from its StateValue (case-insensitive).

    The key is never stored: StateValue is immutable after creation, so the key survives renames of the friendly name.
    It contains no spaces, which core MQTT discovery requires of component keys.
    """
    return hashlib.sha256(value.lower().encode()).hexdigest()[:12]


SWITCH_ON_KEY = trigger_key(PAYLOAD_ON)
SWITCH_OFF_KEY = trigger_key(PAYLOAD_OFF)


@dataclass(frozen=True, slots=True)
class TriggerSpec:
    """One thing a device can react to: the Switch's ON or OFF, or one Select option."""

    value: str
    key: str
    label: str
    friendly_name: str
    actions: list[dict[str, Any]]


@dataclass(frozen=True, slots=True)
class DeviceSpec:
    """Everything the runtime needs to know about one device, independent of how it is stored."""

    kind: str
    device_id: str
    name: str
    run_on_startup: bool
    run_mode: str
    breaker_max_runs: int
    breaker_window: int
    accepted: Mapping[str, str]
    triggers: dict[str, TriggerSpec]


def _actions(raw: Any) -> list[dict[str, Any]]:
    """Return stored actions as a list; anything else is treated as no actions."""
    return raw if isinstance(raw, list) else []


def _switch_triggers(data: Mapping[str, Any]) -> dict[str, TriggerSpec]:
    """Return the ON and OFF triggers of a Switch."""
    return {
        SWITCH_ON_KEY: TriggerSpec(
            PAYLOAD_ON, SWITCH_ON_KEY, TRIGGER_ON, PAYLOAD_ON, _actions(data.get(CONF_ON_CHANGE_TO_ON))
        ),
        SWITCH_OFF_KEY: TriggerSpec(
            PAYLOAD_OFF, SWITCH_OFF_KEY, TRIGGER_OFF, PAYLOAD_OFF, _actions(data.get(CONF_ON_CHANGE_TO_OFF))
        ),
    }


def _select_triggers(data: Mapping[str, Any]) -> dict[str, TriggerSpec]:
    """Return one trigger per stored option in stored order (D-05)."""
    options = data.get(CONF_OPTIONS, [])
    triggers: dict[str, TriggerSpec] = {}
    for option in options if isinstance(options, list) else []:
        value = option[CONF_STATE_VALUE]
        friendly = option[CONF_FRIENDLY_NAME]
        key = trigger_key(value)
        triggers[key] = TriggerSpec(value, key, friendly, friendly, _actions(option.get(CONF_ACTIONS)))
    return triggers


def spec_from_data(subentry_type: str, title: str, data: Mapping[str, Any]) -> DeviceSpec:
    """Build the spec of a device from stored subentry data; keys added after Phase 1 fall back to defaults (D-10)."""
    if subentry_type == SUBENTRY_SELECT:
        triggers = _select_triggers(data)
        accepted: Mapping[str, str] = {trigger.value.lower(): trigger.value for trigger in triggers.values()}
    else:
        triggers = _switch_triggers(data)
        accepted = SWITCH_ACCEPTED
    return DeviceSpec(
        kind=SUBENTRY_SELECT if subentry_type == SUBENTRY_SELECT else SUBENTRY_SWITCH,
        device_id=data[CONF_DEVICE_ID],
        name=title,
        run_on_startup=bool(data.get(CONF_RUN_ON_STARTUP, False)),
        run_mode=RUN_MODE_RESTART if data.get(CONF_RUN_MODE) == RUN_MODE_RESTART else RUN_MODE_SERIAL,
        breaker_max_runs=data.get(CONF_BREAKER_MAX_RUNS, DEFAULT_BREAKER_MAX_RUNS),
        breaker_window=data.get(CONF_BREAKER_WINDOW, DEFAULT_BREAKER_WINDOW),
        accepted=accepted,
        triggers=triggers,
    )


def spec_from_subentry(subentry: ConfigSubentry) -> DeviceSpec:
    """Build the spec of a device from its config subentry."""
    return spec_from_data(subentry.subentry_type, subentry.title, subentry.data)
