"""Execution of configured action sequences: one Script per device, failures surfaced in the log and Repairs."""

from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script import Script
from homeassistant.util import dt as dt_util

from .actions import ActionsInvalid, async_validate_actions
from .const import (
    DOMAIN,
    ISSUE_ACTION_FAILED_PREFIX,
    LOGGER,
    MAX_ISSUE_ERROR_LENGTH,
    RUN_MODE_SERIAL,
    SERIAL_QUEUE_LIMIT,
    TRIGGER_SETUP,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .model import DeviceSpec, TriggerSpec


class ActionRunner:
    """Builds one Script per device and runs it in background tasks; the Script mode decides queue or restart."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the runner."""
        self._hass = hass
        self._entry = entry
        # device id -> the one Script of the device; absent when no trigger of the device can run
        self._scripts: dict[str, Script] = {}
        # device id -> keys of the triggers whose actions are part of that Script
        self._runnable: dict[str, frozenset[str]] = {}
        # device id -> number of runs enqueued so far; a run may clear the failure issue only while it is the latest
        self._generation: dict[str, int] = {}

    async def async_build_device(self, spec: DeviceSpec) -> None:
        """
        Build the one Script of the device and replace the previous one.

        Every trigger's actions are validated on their own; invalid ones are logged and shown in Repairs (trigger
        setup) and that trigger is left out while the others and the baseline tracking keep working. The runnable
        triggers become the branches of one `choose` that dispatches on the run variable `trigger_key`, so serial
        ordering and restart cancellation hold across all triggers of the device (D-10, D-11). Reconfiguring the
        device rebuilds it; the previous Script is unloaded only after the new one is registered.
        """
        runnable: list[TriggerSpec] = []
        for trigger in spec.triggers.values():
            if not trigger.actions:
                continue
            try:
                await async_validate_actions(self._hass, trigger.actions)
            except ActionsInvalid as err:
                self._report_setup_error(spec, trigger.label, err)
                continue
            runnable.append(trigger)
        script = await self._async_build_script(spec, runnable) if runnable else None
        previous = self._scripts.pop(spec.device_id, None)
        if script is None:
            self._runnable.pop(spec.device_id, None)
        else:
            self._scripts[spec.device_id] = script
            self._runnable[spec.device_id] = frozenset(trigger.key for trigger in runnable)
        if previous is not None:
            await previous.async_unload()

    async def _async_build_script(self, spec: DeviceSpec, runnable: list[TriggerSpec]) -> Script | None:
        """Assemble and validate the combined sequence and build the Script; None when the assembly is invalid."""
        # Only the hashed hex key enters a template, never option names or user text (T-02-07)
        sequence = [
            {
                "choose": [
                    {
                        "conditions": [
                            {"condition": "template", "value_template": f"{{{{ trigger_key == '{trigger.key}' }}}}"}
                        ],
                        "sequence": trigger.actions,
                    }
                    for trigger in runnable
                ]
            }
        ]
        try:
            validated = await async_validate_actions(self._hass, sequence)
        except ActionsInvalid as err:
            self._report_setup_error(spec, TRIGGER_SETUP, err)
            return None
        return Script(
            self._hass,
            validated,
            spec.name,
            DOMAIN,
            script_mode="queued" if spec.run_mode == RUN_MODE_SERIAL else "restart",
            max_runs=SERIAL_QUEUE_LIMIT,
            max_exceeded="WARNING",
            logger=LOGGER,
        )

    def _report_setup_error(self, spec: DeviceSpec, label: str, err: ActionsInvalid) -> None:
        """Log invalid stored actions and show them in Repairs under trigger setup."""
        error = str(err)[:MAX_ISSUE_ERROR_LENGTH]
        LOGGER.error("Invalid actions for %s of device %s: %s", label, spec.name, error)
        self.report_failure(spec.device_id, spec.name, TRIGGER_SETUP, error)

    def can_run(self, device_id: str, key: str) -> bool:
        """Return True when the trigger of the device is part of the device's Script."""
        return key in self._runnable.get(device_id, frozenset())

    def script_for(self, device_id: str, key: str) -> Script | None:
        """Return the Script of the device when the trigger can run, or None."""
        return self._scripts.get(device_id) if self.can_run(device_id, key) else None

    def script_count(self, device_id: str) -> int:
        """Return the number of Scripts the runner owns for a device: 1 or 0."""
        return 1 if device_id in self._scripts else 0

    def enqueue(
        self,
        device_id: str,
        device_name: str,
        trigger_label: str,
        trigger_key: str,
        run_variables: dict[str, Any],
    ) -> None:
        """
        Start a run of the device's Script in a background task tied to the config entry lifecycle.

        A change of a trigger without actions never reaches this method, so it cannot cancel a running restart run
        (A5). Reconfiguring a device unloads its previous Script, which stops the in-flight run of that Script; that
        run ends as a cancelled task without an issue.
        """
        if (script := self.script_for(device_id, trigger_key)) is None:
            return
        generation = self._generation.get(device_id, 0) + 1
        self._generation[device_id] = generation
        self._entry.async_create_background_task(
            self._hass,
            self._async_run(
                device_id,
                device_name,
                trigger_label,
                script=script,
                generation=generation,
                run_variables={**run_variables, "trigger_key": trigger_key},
            ),
            name=f"{DOMAIN} {script.name}",
        )

    async def _async_run(  # noqa: PLR0913
        self,
        device_id: str,
        device_name: str,
        trigger_label: str,
        *,
        script: Script,
        generation: int,
        run_variables: dict[str, Any],
    ) -> None:
        """
        Run the device's Script once; the Script mode queues or restarts.

        The failure issue is cleared only by a run that returned a result (a dropped run returns None) and is still
        the latest one enqueued for the device (a superseded run must not hide a failure, A10).

        A restart-cancelled or unloaded run ends as a cancelled task: CancelledError is a BaseException and is never
        caught here, so it creates neither an issue nor an error log (D-11).
        """
        if self._scripts.get(device_id) is not script:
            return  # The device was unloaded or rebuilt before this run started
        try:
            result = await script.async_run(run_variables, Context())
        except Exception as err:  # noqa: BLE001
            # Only device and trigger names are logged, never the action data (T-01-10)
            LOGGER.exception("Actions for %s of device %s failed", trigger_label, device_name)
            self.report_failure(device_id, device_name, trigger_label, str(err))
        else:
            if result is not None and self._generation.get(device_id) == generation:
                self.clear_issue(device_id)

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
        """Unload the Script of a device, stopping its running and queued runs; a removed device loses its issue."""
        self._runnable.pop(device_id, None)
        self._generation.pop(device_id, None)
        if (script := self._scripts.pop(device_id, None)) is not None:
            await script.async_unload()
        if remove_issue:
            self.clear_issue(device_id)
