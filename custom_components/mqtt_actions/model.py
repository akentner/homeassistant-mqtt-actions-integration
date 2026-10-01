"""Pure device model: one DeviceSpec per subentry, built from stored data. No Home Assistant imports at runtime."""

import hashlib
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .const import (
    BREAKER_MAX_RUNS_LIMIT,
    BREAKER_WINDOW_LIMIT,
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
    MAX_TEXT_LENGTH,
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
    from collections.abc import Mapping, Sequence

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


def _encodable(text: str) -> bool:
    """Return True when a string survives UTF-8 encoding; a lone surrogate would make json_dumps raise."""
    try:
        text.encode()
    except UnicodeEncodeError:
        return False
    return True


def _valid_option(option: Any) -> bool:
    """Return True for a stored option a spec can be built from (T-02-04); UI hygiene rules belong to the flow."""
    if not isinstance(option, dict):
        return False
    value = option.get(CONF_STATE_VALUE)
    friendly = option.get(CONF_FRIENDLY_NAME)
    return (
        isinstance(value, str)
        and isinstance(friendly, str)
        and bool(value)
        and bool(friendly)
        and value == value.strip()
        and _encodable(value)
        and _encodable(friendly)
    )


def _select_triggers(data: Mapping[str, Any]) -> dict[str, TriggerSpec]:
    """
    Return one trigger per stored option in stored order (D-05).

    Stored data never crashes the loader: malformed options are dropped, and among StateValues that are equal ignoring
    case the first one wins.
    """
    options = data.get(CONF_OPTIONS, [])
    triggers: dict[str, TriggerSpec] = {}
    seen: set[str] = set()
    for option in options if isinstance(options, list) else []:
        if not _valid_option(option) or option[CONF_STATE_VALUE].lower() in seen:
            continue
        value = option[CONF_STATE_VALUE]
        friendly = option[CONF_FRIENDLY_NAME]
        seen.add(value.lower())
        key = trigger_key(value)
        triggers[key] = TriggerSpec(value, key, friendly, friendly, _actions(option.get(CONF_ACTIONS)))
    return triggers


def _count(value: Any, default: int) -> int:
    """Return a stored breaker setting as an int: an int (not a bool) or an integral float of at least 1."""
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 1:
        return value
    return default


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
        breaker_max_runs=_count(data.get(CONF_BREAKER_MAX_RUNS), DEFAULT_BREAKER_MAX_RUNS),
        breaker_window=_count(data.get(CONF_BREAKER_WINDOW), DEFAULT_BREAKER_WINDOW),
        accepted=accepted,
        triggers=triggers,
    )


def spec_from_subentry(subentry: ConfigSubentry) -> DeviceSpec:
    """Build the spec of a device from its config subentry."""
    return spec_from_data(subentry.subentry_type, subentry.title, subentry.data)


def _invalid_text(text: str) -> bool:
    """Return True for text the UI rejects: not printable (also catches lone surrogates) or over the length cap."""
    return not text.isprintable() or len(text) > MAX_TEXT_LENGTH


def invalid_name(text: str) -> bool:
    """Return True for a device or instance name the document parser would reject (unprintable or over the cap)."""
    return _invalid_text(text)


def validate_option(
    state_value: str,
    friendly_name: str,
    others: Sequence[tuple[str, str]],
    *,
    editing: bool = False,
) -> dict[str, str]:
    """
    Return the errors of a Select option typed in the UI as a map from field name to error key; empty when valid.

    `others` holds the (StateValue, friendly name) pairs of the other options of the device. While `editing`, the
    StateValue is locked (D-03) and not checked. The rules follow D-04 plus what core MQTT select does with the values:
    it strips the rendered friendly name and turns the entity unknown for the name "none" (T-02-19).
    """
    errors: dict[str, str] = {}
    if not editing:
        if not state_value.strip():
            errors[CONF_STATE_VALUE] = "state_value_required"
        elif state_value != state_value.strip() or _invalid_text(state_value):
            errors[CONF_STATE_VALUE] = "state_value_invalid"
        elif state_value.lower() in {other_value.lower() for other_value, _ in others}:
            errors[CONF_STATE_VALUE] = "state_value_duplicate"

    friendly = friendly_name.strip()
    if not friendly:
        errors[CONF_FRIENDLY_NAME] = "friendly_name_required"
    elif _invalid_text(friendly):
        errors[CONF_FRIENDLY_NAME] = "friendly_name_invalid"
    elif friendly.lower() == "none":
        errors[CONF_FRIENDLY_NAME] = "friendly_name_reserved"
    elif friendly.lower() in {other_name.strip().lower() for _, other_name in others}:
        errors[CONF_FRIENDLY_NAME] = "friendly_name_duplicate"
    return errors


def _in_range(value: float, limit: int) -> bool:
    """Return True for a whole number from 1 to `limit`; the number selector delivers floats."""
    return float(value).is_integer() and 1 <= value <= limit


def validate_breaker(max_runs: float, window: float) -> dict[str, str]:
    """Return the range errors of the breaker settings as a map from field name to error key (T-02-21)."""
    errors: dict[str, str] = {}
    if not _in_range(max_runs, BREAKER_MAX_RUNS_LIMIT):
        errors[CONF_BREAKER_MAX_RUNS] = "breaker_max_runs_range"
    if not _in_range(window, BREAKER_WINDOW_LIMIT):
        errors[CONF_BREAKER_WINDOW] = "breaker_window_range"
    return errors
