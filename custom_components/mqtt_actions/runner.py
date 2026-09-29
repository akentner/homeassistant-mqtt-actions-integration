"""Execution of configured action sequences."""

from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers.script import Script

from .actions import async_validate_actions
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class ActionRunner:
    """Builds Scripts from raw action lists and runs them in background tasks."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the runner."""
        self._hass = hass
        self._entry = entry

    async def async_build_script(self, name: str, raw: list[dict[str, Any]]) -> Script | None:
        """Validate a raw action list and build a Script; an empty list yields None."""
        if not raw:
            return None
        sequence = await async_validate_actions(self._hass, raw)
        return Script(self._hass, sequence, name, DOMAIN, script_mode="single", logger=LOGGER)

    def enqueue(self, script: Script, run_variables: dict[str, Any]) -> None:
        """Run a script in a background task tied to the config entry lifecycle."""
        self._entry.async_create_background_task(
            self._hass,
            self._async_run(script, run_variables),
            name=f"{DOMAIN} {script.name}",
        )

    async def _async_run(self, script: Script, run_variables: dict[str, Any]) -> None:
        """Run a script and log any failure; surfacing in Repairs follows in a later plan."""
        try:
            await script.async_run(run_variables, Context())
        except Exception:  # noqa: BLE001
            LOGGER.exception("Actions of %s failed", script.name)
