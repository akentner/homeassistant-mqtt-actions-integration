"""Execution of configured action sequences: serialised per device, failures surfaced in the log and Repairs."""

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script import Script
from homeassistant.util import dt as dt_util

from .actions import ActionsInvalid, async_validate_actions
from .const import DOMAIN, ISSUE_ACTION_FAILED_PREFIX, LOGGER, MAX_ISSUE_ERROR_LENGTH, TRIGGER_SETUP

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .model import DeviceSpec


class ActionRunner:
    """Builds Scripts from device specs and runs them first-in first-out per device in background tasks."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the runner."""
        self._hass = hass
        self._entry = entry
        self._locks: dict[str, asyncio.Lock] = {}
        # device id -> trigger key -> Script; a trigger without actions or with invalid actions has no entry
        self._scripts: dict[str, dict[str, Script]] = {}

    async def async_build_device(self, spec: DeviceSpec) -> None:
        """
        Build one Script per trigger with actions and replace the Scripts of the device.

        Invalid stored actions are logged and shown in Repairs (trigger setup); that trigger then has no Script while
        the others and the baseline tracking keep working. Reconfiguring the device rebuilds it. The previous Scripts
        are unloaded only after the new ones exist, and queued runs of a retired Script are skipped.
        """
        scripts: dict[str, Script] = {}
        for trigger in spec.triggers.values():
            if not trigger.actions:
                continue
            try:
                sequence = await async_validate_actions(self._hass, trigger.actions)
            except ActionsInvalid as err:
                error = str(err)[:MAX_ISSUE_ERROR_LENGTH]
                LOGGER.error("Invalid actions for %s of device %s: %s", trigger.label, spec.name, error)
                self.report_failure(spec.device_id, spec.name, TRIGGER_SETUP, error)
                continue
            scripts[trigger.key] = Script(
                self._hass, sequence, f"{spec.name} {trigger.label}", DOMAIN, script_mode="single", logger=LOGGER
            )
        previous = self._scripts.get(spec.device_id, {})
        self._scripts[spec.device_id] = scripts
        for script in previous.values():
            await script.async_unload()

    def can_run(self, device_id: str, key: str) -> bool:
        """Return True when the trigger of the device has a Script to run."""
        return key in self._scripts.get(device_id, {})

    def script_for(self, device_id: str, key: str) -> Script | None:
        """Return the Script of a trigger, or None when the trigger has none."""
        return self._scripts.get(device_id, {}).get(key)

    def script_count(self, device_id: str) -> int:
        """Return the number of Scripts the runner owns for a device."""
        return len(self._scripts.get(device_id, {}))

    def enqueue(
        self,
        device_id: str,
        device_name: str,
        trigger_label: str,
        trigger_key: str,
        run_variables: dict[str, Any],
    ) -> None:
        """Queue a run of the trigger's Script in a background task tied to the config entry lifecycle."""
        if (script := self.script_for(device_id, trigger_key)) is None:
            return
        self._entry.async_create_background_task(
            self._hass,
            self._async_run(
                device_id,
                device_name,
                trigger_label,
                trigger_key=trigger_key,
                script=script,
                run_variables=run_variables,
            ),
            name=f"{DOMAIN} {script.name}",
        )

    async def _async_run(  # noqa: PLR0913
        self,
        device_id: str,
        device_name: str,
        trigger_label: str,
        *,
        trigger_key: str,
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
            if self.script_for(device_id, trigger_key) is not script:
                return  # The device was unloaded or rebuilt while this run was queued
            try:
                await script.async_run(run_variables, Context())
            except Exception as err:  # noqa: BLE001
                # Only device and trigger names are logged, never the action data (T-01-10)
                LOGGER.exception("Actions for %s of device %s failed", trigger_label, device_name)
                self.report_failure(device_id, device_name, trigger_label, str(err))
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

    async def async_unload_all(self) -> None:
        """Unload every Script that is still registered, including those of a device that never finished starting."""
        for device_id in list(self._scripts):
            await self.async_unload(device_id)

    async def async_unload(self, device_id: str, *, remove_issue: bool = False) -> None:
        """Unload the scripts of a device; a removed device also loses its Repairs issue."""
        for script in self._scripts.pop(device_id, {}).values():
            await script.async_unload()
        self._locks.pop(device_id, None)
        if remove_issue:
            self.clear_issue(device_id)
