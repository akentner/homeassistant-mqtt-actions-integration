"""Execution of configured action sequences: one Script per device, failures surfaced in the log and Repairs."""

import copy
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.script import Script
from homeassistant.helpers.trace import trace_get
from homeassistant.util import dt as dt_util

from .actions import ActionsInvalid, async_validate_actions
from .const import (
    DOMAIN,
    ISSUE_ACTION_FAILED_PREFIX,
    ISSUE_DENIED_CALL_PREFIX,
    LOGGER,
    MAX_ISSUE_ERROR_LENGTH,
    MAX_LOGGED_PAYLOAD_LENGTH,
    RUN_MODE_SERIAL,
    SERIAL_QUEUE_LIMIT,
    TRIGGER_SETUP,
)
from .document import DocumentRejectedError, analyze_actions, escape_markdown
from .local_actions import BranchOutcome, effective_policy, reduce_local_outcome, summarize_trace
from .trust import DeniedServiceCallError, guard_actions

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .local_actions import EffectivePolicy, EffectiveTriggerPlan
    from .model import DeviceSpec, TriggerSpec


def _branch_sequence(plan: EffectiveTriggerPlan) -> list[dict[str, Any]]:
    """Return the raw dispatch sequence of one effective plan, from copies; both branches become one `parallel`."""
    owner = copy.deepcopy(plan.owner_actions)
    local = copy.deepcopy(plan.local_actions)
    if owner is not None and local is not None:
        return [{"parallel": [{"sequence": owner}, {"sequence": local}]}]
    sequence = owner if owner is not None else local
    return sequence if sequence is not None else []


def _replace_at(node: Any, parts: list[str], replace: Callable[[Any], Any]) -> Any:
    """Return a copy of a validated tree with the node at a config path replaced; the containers on the path are new."""
    if not parts:
        return replace(node)
    head, rest = parts[0], parts[1:]
    if isinstance(node, list):
        index = int(head)
        return [*node[:index], _replace_at(node[index], rest, replace), *node[index + 1 :]]
    return {**node, head: _replace_at(node[head], rest, replace)}


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
        # Devices whose current Script was built restricted (mirrors); their broker-supplied text is escaped in issues
        self._restricted: set[str] = set()
        # device id -> trigger key -> the effective plan its current Script was built with; only customized mirrors
        self._plans: dict[str, dict[str, EffectiveTriggerPlan]] = {}
        # device id -> number of runner-initiated stops; a run that overlaps one never proves a local success
        self._stops: dict[str, int] = {}
        # Receives one BranchOutcome per run of a trigger with a local branch, after both branches settled
        self.on_local_outcome: Callable[[BranchOutcome], None] | None = None

    async def async_build_device(self, spec: DeviceSpec, *, restricted: bool = False) -> None:
        """
        Build the one Script of the device and replace the previous one.

        A restricted build is for a mirror (D-03, D-05): a trigger with a statically denied service is not runnable and
        the service-name templates of the others are guarded, so a name that resolves to a denied service stops the run.
        Owned devices are built unrestricted.

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
                if restricted:
                    self._refuse_denied(trigger)
                await async_validate_actions(self._hass, trigger.actions)
            except ActionsInvalid as err:
                self._report_setup_error(spec, trigger.label, err, restricted=restricted)
                continue
            runnable.append(trigger)
        script = await self._async_build_script(spec, runnable, restricted=restricted) if runnable else None
        previous = self._scripts.pop(spec.device_id, None)
        self._plans.pop(spec.device_id, None)
        if script is None:
            self._runnable.pop(spec.device_id, None)
            self._restricted.discard(spec.device_id)
        else:
            self._scripts[spec.device_id] = script
            self._runnable[spec.device_id] = frozenset(trigger.key for trigger in runnable)
            if restricted:
                self._restricted.add(spec.device_id)
            else:
                self._restricted.discard(spec.device_id)
        if previous is not None:
            await previous.async_unload()

    async def async_build_effective(
        self, spec: DeviceSpec, plans: Sequence[EffectiveTriggerPlan], *, policy: EffectivePolicy | None = None
    ) -> None:
        """
        Build the one Script of a mirror from the effective plans of its triggers and replace the previous one.

        Without any local customization this is exactly today's mirror build: the restricted dispatcher when the owner
        actions are eligible, no Script otherwise (D-21). With one, every trigger's owner and local actions are
        validated on their own, so an invalid branch never removes the other (D-01). The static denylist and the
        GuardedTemplate apply to the owner actions only, after the final validation; trusted local actions keep
        owned-device trust (D-02, T-11-05). Both branches of a trigger run as one native `parallel`, owner first,
        inside the single device Script; there is no second Script and no step is patched.

        `policy` is the device-wide snapshot for the Script mode and queue bound; by default the owner's settings when
        its exact hash is approved, the fixed safe local policy otherwise (D-03).
        """
        if all(plan.customization is None for plan in plans):
            if any(plan.owner_eligible for plan in plans):
                await self.async_build_device(spec, restricted=True)
            else:
                await self.async_unload(spec.device_id)
            return
        built: list[EffectiveTriggerPlan] = []
        for plan in plans:
            checked = await self._async_check_branches(spec, plan)
            if checked.runnable:
                built.append(checked.at_dispatch(f"0/choose/{len(built)}/sequence"))
        policy = policy or effective_policy(spec, plans[0].approval)
        script = await self._async_build_effective_script(spec, built, policy) if built else None
        previous = self._scripts.pop(spec.device_id, None)
        if script is None:
            self._runnable.pop(spec.device_id, None)
            self._plans.pop(spec.device_id, None)
            self._restricted.discard(spec.device_id)
        else:
            self._scripts[spec.device_id] = script
            self._runnable[spec.device_id] = frozenset(plan.trigger_key for plan in built)
            self._plans[spec.device_id] = {plan.trigger_key: plan for plan in built}
            self._restricted.add(spec.device_id)
        if previous is not None:
            await previous.async_unload()

    async def _async_check_branches(self, spec: DeviceSpec, plan: EffectiveTriggerPlan) -> EffectiveTriggerPlan:
        """Validate the owner and the local actions of one trigger separately; drop a branch that fails."""
        owner = plan.owner_eligible
        if plan.owner_actions is not None:
            try:
                self._refuse_denied_actions(plan.owner_actions)
                await async_validate_actions(self._hass, plan.owner_actions)
            except ActionsInvalid as err:
                self._report_setup_error(spec, plan.label, err, restricted=True)
                owner = False
        local = plan.local_eligible
        if plan.local_actions is not None:
            try:
                await async_validate_actions(self._hass, plan.local_actions)
            except ActionsInvalid as err:
                # Local actions are validated when they are saved; this only catches what changed since then
                LOGGER.error(
                    "Invalid local actions for %s of device %s: %s",
                    plan.label,
                    spec.name,
                    str(err)[:MAX_ISSUE_ERROR_LENGTH],
                )
                local = False
        return plan.restricted_to(owner=owner, local=local)

    async def _async_build_effective_script(
        self, spec: DeviceSpec, built: list[EffectiveTriggerPlan], policy: EffectivePolicy
    ) -> Script | None:
        """Assemble the dispatcher of the effective plans, validate it, guard the owner subtrees, build the Script."""
        # Only the hashed hex key enters a template, never option names or user text (T-02-07)
        sequence = [
            {
                "choose": [
                    {
                        "conditions": [
                            {
                                "condition": "template",
                                "value_template": f"{{{{ trigger_key == '{plan.trigger_key}' }}}}",
                            }
                        ],
                        "sequence": _branch_sequence(plan),
                    }
                    for plan in built
                ]
            }
        ]
        try:
            validated = await async_validate_actions(self._hass, sequence)
        except ActionsInvalid as err:
            self._report_setup_error(spec, TRIGGER_SETUP, err, restricted=True)
            return None
        for plan in built:
            if plan.owner_path is not None:
                validated = _replace_at(validated, plan.owner_path.split("/"), guard_actions)
        return Script(
            self._hass,
            validated,
            spec.name,
            DOMAIN,
            script_mode="queued" if policy.run_mode == RUN_MODE_SERIAL else "restart",
            max_runs=policy.queue_limit,
            max_exceeded="WARNING",
            logger=LOGGER,
        )

    def plan_for(self, device_id: str, key: str) -> EffectiveTriggerPlan | None:
        """Return the effective plan the device Script was built with for a trigger, or None."""
        return self._plans.get(device_id, {}).get(key)

    @staticmethod
    def _refuse_denied(trigger: TriggerSpec) -> None:
        """Raise ActionsInvalid naming the denied services of a trigger; a tree that cannot be walked is refused too."""
        ActionRunner._refuse_denied_actions(trigger.actions)

    @staticmethod
    def _refuse_denied_actions(actions: list[dict[str, Any]]) -> None:
        """Raise ActionsInvalid naming the denied services of owner actions; a tree that cannot be walked too."""
        try:
            denied = analyze_actions(actions).denied
        except DocumentRejectedError as err:
            msg = f"the actions cannot be checked ({err.reason})"
            raise ActionsInvalid(msg) from err
        if denied:
            msg = f"service {', '.join(denied)[: MAX_LOGGED_PAYLOAD_LENGTH * 2]} is not allowed for mirrored actions"
            raise ActionsInvalid(msg)

    async def _async_build_script(
        self, spec: DeviceSpec, runnable: list[TriggerSpec], *, restricted: bool
    ) -> Script | None:
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
            self._report_setup_error(spec, TRIGGER_SETUP, err, restricted=restricted)
            return None
        if restricted:
            validated = guard_actions(validated)
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

    def _report_setup_error(self, spec: DeviceSpec, label: str, err: ActionsInvalid, *, restricted: bool) -> None:
        """Log invalid stored actions and show them in Repairs under trigger setup."""
        error = str(err)[:MAX_ISSUE_ERROR_LENGTH]
        LOGGER.error("Invalid actions for %s of device %s: %s", label, spec.name, error)
        self.report_failure(spec.device_id, spec.name, TRIGGER_SETUP, error, escape=restricted)

    def can_run(self, device_id: str, key: str) -> bool:
        """Return True when the trigger of the device is part of the device's Script."""
        return key in self._runnable.get(device_id, frozenset())

    def script_for(self, device_id: str, key: str) -> Script | None:
        """Return the Script of the device when the trigger can run, or None."""
        return self._scripts.get(device_id) if self.can_run(device_id, key) else None

    def script_count(self, device_id: str) -> int:
        """Return the number of Scripts the runner owns for a device: 1 or 0."""
        return 1 if device_id in self._scripts else 0

    def enqueue(  # noqa: PLR0913
        self,
        device_id: str,
        device_name: str,
        trigger_label: str,
        trigger_key: str,
        run_variables: dict[str, Any],
        *,
        test: bool = False,
    ) -> None:
        """
        Start a run of the device's Script in a background task tied to the config entry lifecycle.

        Every run gets the run variables `trigger_key` and `test`; `test` is True for a run started by a test button.

        A change of a trigger without actions never reaches this method, so it cannot cancel a running restart run
        (A5). Reconfiguring a device unloads its previous Script, which stops the in-flight run of that Script; that
        run ends as a cancelled task without an issue.
        """
        if (script := self.script_for(device_id, trigger_key)) is None:
            return
        generation = self._generation.get(device_id, 0) + 1
        self._generation[device_id] = generation
        plan = self.plan_for(device_id, trigger_key)
        self._entry.async_create_background_task(
            self._hass,
            self._async_run(
                device_id,
                device_name,
                trigger_label,
                script=script,
                generation=generation,
                run_variables={**run_variables, "trigger_key": trigger_key, "test": test},
                restricted=device_id in self._restricted,
                local_plan=plan if plan is not None and plan.local_path is not None else None,
                stops=self._stops.get(device_id, 0),
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
        restricted: bool,
        local_plan: EffectiveTriggerPlan | None = None,
        stops: int = 0,
    ) -> None:
        """
        Run the device's Script once; the Script mode queues or restarts.

        The failure issue is cleared only by a run that returned a result (a dropped run returns None) and is still
        the latest one enqueued for the device (a superseded run must not hide a failure, A10).

        A restart-cancelled or unloaded run ends as a cancelled task: CancelledError is a BaseException and is never
        caught here, so it creates neither an issue nor an error log (D-11).

        A service name that resolved to a denied service stops the run of a restricted Script (D-05); it is logged with
        device, trigger and service name and shown in Repairs, never with action data.

        A run of a trigger with a local branch gets a fresh task-local trace collector; after the run it is reduced
        to one bounded BranchOutcome and cleared (D-18, D-19, T-11-08). Other runs are unchanged.
        """
        if self._scripts.get(device_id) is not script:
            return  # The device was unloaded or rebuilt before this run started
        trace = trace_get() if local_plan is not None else None
        # Set once the run returned a result or raised; a dropped run (None) or a cancelled task proves nothing
        ran = False
        try:
            result = await script.async_run(run_variables, Context())
        except DeniedServiceCallError as err:
            ran = True
            LOGGER.warning(
                "Actions for %s of device %s were stopped: the service %s is not allowed for mirrored actions",
                trigger_label,
                device_name,
                err.service[:MAX_LOGGED_PAYLOAD_LENGTH],
            )
            self.report_denied(device_id, device_name, trigger_label, err.service)
        except Exception as err:  # noqa: BLE001
            ran = True
            # Only device and trigger names are logged, never the action data (T-01-10)
            LOGGER.exception("Actions for %s of device %s failed", trigger_label, device_name)
            self.report_failure(device_id, device_name, trigger_label, str(err), escape=restricted)
        else:
            ran = result is not None
            if result is not None and self._generation.get(device_id) == generation:
                self.clear_issue(device_id)
        finally:
            # Also on cancellation: a local error recorded before a restart or unload is still a local failure
            if trace is not None and local_plan is not None:
                proven = (
                    ran
                    and self._scripts.get(device_id) is script
                    and self._generation.get(device_id) == generation
                    and self._stops.get(device_id, 0) == stops
                    and not self._hass.is_stopping
                )
                self._deliver_local_outcome(local_plan, trace, generation=generation, proven=proven)

    def _deliver_local_outcome(
        self, plan: EffectiveTriggerPlan, trace: dict[str, Any], *, generation: int, proven: bool
    ) -> None:
        """Reduce the run's trace to one BranchOutcome, discard the trace and hand the outcome to the listener."""
        steps = summarize_trace(trace)
        trace.clear()
        status, error = reduce_local_outcome(plan, steps, proven=proven)
        if self.on_local_outcome is not None:
            self.on_local_outcome(
                BranchOutcome(plan.device_id, plan.trigger_key, plan.label, status, error, generation)
            )

    def report_failure(
        self, device_id: str, device_name: str, trigger: str, error: str, *, escape: bool = False
    ) -> None:
        """
        Create or update the one Repairs issue of a device; a dismissed issue stays dismissed (D-08, D-09).

        `escape` is set for a mirror, whose names and error text come from the broker and reach a markdown text.
        """
        error = error[:MAX_ISSUE_ERROR_LENGTH]
        if escape:
            device_name, trigger, error = escape_markdown(device_name), escape_markdown(trigger), escape_markdown(error)
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
                "error": error,
            },
        )

    def report_denied(self, device_id: str, device_name: str, trigger: str, service: str) -> None:
        """Show that a run was stopped because a templated service name resolved to a denied service (D-05)."""
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            f"{ISSUE_DENIED_CALL_PREFIX}{device_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key="denied_service_call",
            translation_placeholders={
                "device": escape_markdown(device_name),
                "trigger": escape_markdown(trigger),
                "service": escape_markdown(service[:MAX_LOGGED_PAYLOAD_LENGTH]),
            },
        )

    def clear_issue(self, device_id: str) -> None:
        """Delete the Repairs issue of a device, for example because its actions were just reconfigured."""
        ir.async_delete_issue(self._hass, DOMAIN, f"{ISSUE_ACTION_FAILED_PREFIX}{device_id}")

    async def async_stop_runs(self, device_id: str) -> None:
        """Stop the running and queued runs of a device; its Script stays usable for later runs."""
        self._stops[device_id] = self._stops.get(device_id, 0) + 1
        if (script := self._scripts.get(device_id)) is not None:
            await script.async_stop()

    async def async_unload_all(self) -> None:
        """Unload every Script that is still registered, including those of a device that never finished starting."""
        for device_id in list(self._scripts):
            await self.async_unload(device_id)

    async def async_unload(self, device_id: str, *, remove_issue: bool = False) -> None:
        """Unload the Script of a device, stopping its running and queued runs; a removed device loses its issue."""
        self._runnable.pop(device_id, None)
        self._generation.pop(device_id, None)
        self._restricted.discard(device_id)
        self._plans.pop(device_id, None)
        if (script := self._scripts.pop(device_id, None)) is not None:
            await script.async_unload()
        if remove_issue:
            self.clear_issue(device_id)
