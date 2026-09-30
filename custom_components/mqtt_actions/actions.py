"""Validation of user-authored action sequences."""

from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import script

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


class ActionsInvalid(ValueError):  # noqa: N818
    """Raised when an action sequence fails schema or deep validation."""


async def async_validate_actions(hass: HomeAssistant, raw: Any) -> list[ConfigType]:
    """
    Validate a raw action list and return the validated form used to build a Script.

    Callers must keep persisting the RAW list: the validated form holds Template objects that cannot be serialised.
    """
    try:
        validated = cv.SCRIPT_SCHEMA(raw)
        return await script.async_validate_actions_config(hass, validated)
    except (probatio.Invalid, HomeAssistantError) as err:
        raise ActionsInvalid(str(err)) from err


def validate_actions_structure(raw: Any) -> None:
    """
    Check the structure of a raw action list against the script schema and nothing else.

    Synchronous and instance independent: no service, device or entity is resolved, so a document from another
    instance is judged the same everywhere (D-06). The error text comes from the schema and may quote a value, so a
    caller logs the device name, never the message.
    """
    try:
        cv.SCRIPT_SCHEMA(raw)
    except (probatio.Invalid, HomeAssistantError) as err:
        raise ActionsInvalid(str(err)) from err


def _is_template(value: str) -> bool:
    """Return True when a string is a Jinja template, whose result cannot be judged statically."""
    return "{{" in value or "{%" in value


def _walk_device_ids(node: Any, found: dict[str, None]) -> None:
    """Collect every literal device_id value below a raw structure, preserving first-seen order."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "device_id":
                candidates = value if isinstance(value, list) else [value]
                for candidate in candidates:
                    if isinstance(candidate, str) and candidate and not _is_template(candidate):
                        found.setdefault(candidate)
            else:
                _walk_device_ids(value, found)
    elif isinstance(node, list):
        for item in node:
            _walk_device_ids(item, found)


def find_device_ids(raw: Any) -> list[str]:
    """
    Return the unique literal device_ids referenced anywhere in a raw action structure, first-seen first.

    Device ids are local to one Home Assistant instance, so sequences that use them do not work on other
    instances (D-10). Detection is static: a template that computes an id is not caught.
    """
    found: dict[str, None] = {}
    _walk_device_ids(raw, found)
    return list(found)
