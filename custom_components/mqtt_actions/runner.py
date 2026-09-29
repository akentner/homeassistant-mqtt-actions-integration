"""Execution of configured action sequences: serialised per device, failures surfaced in the log and Repairs."""

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script import Script
from homeassistant.util import dt as dt_util

from .actions import async_validate_actions
from .const import DOMAIN, ISSUE_ACTION_FAILED_PREFIX, LOGGER, MAX_ISSUE_ERROR_LENGTH

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


class ActionRunner:
    """Builds Scripts from raw action lists and runs them first-in first-out per device in background tasks."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the runner."""
        self._hass = hass
        self._entry = entry
        self._locks: dict[str, asyncio.Lock] = {}
        self._scripts: dict[str, list[Script]] = {}

    async def async_build_script(self, device_id: str, name: str, raw: list[dict[str, Any]]) -> Script | None:
        """Validate a raw action list and build a Script owned by the device; an empty list yields None."""
        if not raw:
            return None
        sequence = await async_validate_actions(self._hass, raw)
        script = Script(self._hass, sequence, name, DOMAIN, script_mode="single", logger=LOGGER)
        self._scripts.setdefault(device_id, []).append(script)
        return script

    def enqueue(
        self,
        device_id: str,
        device_name: str,
        trigger: str,
        script: Script,
        run_variables: dict[str, Any],
    ) -> None:
        """Queue a run in a background task tied to the config entry lifecycle."""
        self._entry.async_create_background_task(
            self._hass,
            self._async_run(device_id, device_name, trigger, script, run_variables),
            name=f"{DOMAIN} {script.name}",
        )

    async def _async_run(
        self,
        device_id: str,
        device_name: str,
        trigger: str,
        script: Script,
        run_variables: dict[str, Any],
    ) -> None:
        """
        Run a script once the device's earlier runs are done.

        Script mode single would silently drop an overlapping run, so the per-device lock (first-in first-out) is what
        guarantees that no change is lost or reordered.
        """
        lock = self._locks.setdefault(device_id, asyncio.Lock())
        async with lock:
            if script not in self._scripts.get(device_id, ()):
                return  # The device was unloaded while this run was queued
            try:
                await script.async_run(run_variables, Context())
            except Exception as err:  # noqa: BLE001
                # Only device and trigger names are logged, never the action data (T-01-10)
                LOGGER.exception("Actions for %s of device %s failed", trigger, device_name)
                self.report_failure(device_id, device_name, trigger, str(err))
            else:
                ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}")

    def report_failure(self, device_id: str, device_name: str, trigger: str, error: str) -> None:
        """Create or update the one Repairs issue of a device; a dismissed issue stays dismissed (D-08, D-09)."""
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="action_failed",
            translation_placeholders={
                "device": device_name,
                "trigger": trigger,
                "time": dt_util.now().replace(microsecond=0).isoformat(),
                "error": error[:MAX_ISSUE_ERROR_LENGTH],
            },
        )

    def clear_issue(self, device_id: str) -> None:
        """Delete the Repairs issue of a device, for example because its actions were just reconfigured."""
        ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}")

    async def async_retire_scripts(self, device_id: str, *, keep: list[Script]) -> None:
        """Unload the Scripts of a device that are not in keep; queued runs of a retired Script are skipped."""
        retained: list[Script] = []
        for script in self._scripts.get(device_id, []):
            if script in keep:
                retained.append(script)
            else:
                await script.async_unload()
        self._scripts[device_id] = retained

    async def async_unload_all(self) -> None:
        """Unload every Script that is still registered, including those of a device that never finished starting."""
        for device_id in list(self._scripts):
            await self.async_unload(device_id)

    async def async_unload(self, device_id: str, *, remove_issue: bool = False) -> None:
        """Unload the scripts of a device; a removed device also loses its Repairs issue."""
        for script in self._scripts.pop(device_id, []):
            await script.async_unload()
        self._locks.pop(device_id, None)
        if remove_issue:
            self.clear_issue(device_id)
