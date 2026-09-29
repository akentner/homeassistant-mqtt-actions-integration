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
