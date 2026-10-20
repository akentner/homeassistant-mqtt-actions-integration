"""
Pins of the installed Core parallel and trace semantics that local actions on mirrors rely on (D-01, D-02, D-18-D-20).

D-01 runs owner and local actions of one trigger as two branches of a native `parallel` inside the one device Script.
These tests run that shape against the installed Home Assistant (Core 2026.9.4 when written), never against a mock, and
promote the research probe (`11-parallel-probe.py`) into permanent, loud contracts. They always run and carry
no marker: a Core bump that changes one of them turns CI red, and the failure message says what changed. D-20 applies
then: stop and return to the owner before any sequential fallback.

Every outcome is read from observable service callbacks and from the task-local trace paths of each branch, never from
the outer return value or exception alone: the outer result hides a local error behind an owner stop, reports only
the first of two branch errors, and is a normal result for a cancelled run. The test-local reference reducer below
classifies a run for the local branch: any trace error at or below the local branch path is a local failure, also a
continued one; success needs the local completion callback and a clean local subtree; everything else (stop, abort,
drop, cancellation, supersession, a different trigger, an owner-only run) is no local success.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.core import Context, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.script import Script
from homeassistant.helpers.template import Template
from homeassistant.helpers.trace import trace_get

from custom_components.mqtt_actions.actions import async_validate_actions
from custom_components.mqtt_actions.trust import DeniedServiceCallError, GuardedTemplate, guard_actions

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

CORE = "Home Assistant Core 2026.9.4"
HINT = (
    f"{CORE} native parallel semantics changed (homeassistant/helpers/script.py: _async_parallel_step, "
    "_async_run_script, stop/continue_on_error handling, or helpers/trace.py paths). D-20: stop and return to the "
    "owner before any sequential fallback; adapt the Phase 11 branch reducer only on purpose."
)
OWNER = "0/parallel/0"
LOCAL = "0/parallel/1"
OWNER_STEP = f"{OWNER}/sequence/0"
LOCAL_STEP = f"{LOCAL}/sequence/0"

FAILURE = "local_failure"
SUCCESS = "local_success"
NO_SUCCESS = "no_local_success"

LOCAL_DONE = {"action": "probe.local_done"}
AFTER = {"action": "probe.after"}


class Probe:
    """Services that record what ran, in order; `hold` waits for `gate` and records a cancellation."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.events: list[str] = []
        self.gate = asyncio.Event()
        for name in ("owner", "local", "local_done", "after", "owner_after"):
            hass.services.async_register("probe", name, self._record)
        hass.services.async_register("probe", "fail", self._fail)
        hass.services.async_register("probe", "fail_local", self._fail)
        hass.services.async_register("probe", "finish", self._finish)
        hass.services.async_register("probe", "hold", self._hold)
        hass.services.async_register("probe", "response", self._response, supports_response=SupportsResponse.ONLY)
        # A trusted local call to a service the owner side must never reach
        hass.services.async_register("mqtt", "publish", self._record)

    async def _record(self, call: ServiceCall) -> None:
        self.events.append(f"{call.domain}.{call.service}")

    async def _fail(self, call: ServiceCall) -> None:
        self.events.append(f"probe.{call.service}")
        msg = "OWNER_FAILURE" if call.service == "fail" else "LOCAL_FAILURE"
        raise HomeAssistantError(msg)

    async def _finish(self, _call: ServiceCall) -> None:
        await asyncio.sleep(0.02)
        self.events.append("local_finished")

    async def _hold(self, _call: ServiceCall) -> None:
        self.events.append("hold_start")
        try:
            await self.gate.wait()
        except asyncio.CancelledError:
            self.events.append("hold_cancelled")
            raise
        self.events.append("hold_end")

    async def _response(self, call: ServiceCall) -> dict[str, Any]:
        return {"answer": call.data["answer"]}


async def _parallel(
    hass: HomeAssistant,
    owner: list[dict[str, Any]],
    local: list[dict[str, Any]],
    *,
    mode: str = "queued",
    max_runs: int = 10,
    guard_owner: bool = False,
) -> Script:
    """Build the D-01 shape: one Script, owner and local as the two parallel branches, then a following action."""
    validated = await async_validate_actions(
        hass, [{"parallel": [{"sequence": owner}, {"sequence": local}]}, {"action": "probe.after"}]
    )
    if guard_owner:
        # Owner-only restriction after validation, as the runner applies it; the local subtree is left as validated
        validated[0]["parallel"][0]["sequence"] = guard_actions(validated[0]["parallel"][0]["sequence"])
    return Script(hass, validated, "phase 11 pin", "probe", script_mode=mode, max_runs=max_runs, max_exceeded="WARNING")


def _errors(trace: dict[str, Any]) -> dict[str, list[str]]:
    """Return the trace errors by path; paths without an error are left out."""
    found: dict[str, list[str]] = {}
    for path, elements in trace.items():
        errors = [element.as_dict()["error"] for element in elements if element.as_dict().get("error")]
        if errors:
            found[path] = errors
    return found


def _under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(f"{prefix}/")


def _branch_errors(trace: dict[str, Any], prefix: str) -> dict[str, list[str]]:
    return {path: errors for path, errors in _errors(trace).items() if _under(path, prefix)}


def _reached(trace: dict[str, Any], prefix: str) -> bool:
    return any(_under(path, prefix) for path in trace)


def local_outcome(trace: dict[str, Any], *, local_completed: bool, prefix: str = LOCAL) -> str:
    """Reference reducer: any local trace error is a failure; success needs completion and a clean local subtree."""
    if _branch_errors(trace, prefix):
        return FAILURE
    if local_completed and _reached(trace, prefix):
        return SUCCESS
    return NO_SUCCESS


async def _run(script: Script) -> tuple[Any, BaseException | None]:
    """Run once in this task and return (result, exception); the trace collector of the test sees every step."""
    try:
        return await script.async_run({}, Context()), None
    except Exception as err:  # noqa: BLE001
        return None, err


async def _turns(count: int = 25) -> None:
    for _ in range(count):
        await asyncio.sleep(0)


# --- the ten research cases -------------------------------------------------------------------------------------------


async def test_owner_failure_lets_the_delayed_local_branch_finish(hass: HomeAssistant) -> None:
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(hass, [{"action": "probe.fail"}], [{"action": "probe.finish"}, LOCAL_DONE])

    result, err = await _run(script)

    assert result is None, HINT
    assert isinstance(err, HomeAssistantError), HINT
    assert str(err) == "OWNER_FAILURE", HINT
    assert probe.events == ["probe.fail", "local_finished", "probe.local_done"], HINT
    assert _branch_errors(trace, OWNER) == {OWNER_STEP: ["OWNER_FAILURE"]}, HINT
    assert _branch_errors(trace, LOCAL) == {}, HINT
    assert local_outcome(trace, local_completed="probe.local_done" in probe.events) == SUCCESS, HINT
    await script.async_unload()


async def test_both_failures_run_and_only_the_first_branch_error_is_raised(hass: HomeAssistant) -> None:
    """The outer exception names the owner only; the local failure is visible in the local trace path alone."""
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(hass, [{"action": "probe.fail"}], [{"action": "probe.fail_local"}, LOCAL_DONE])

    _result, err = await _run(script)

    assert str(err) == "OWNER_FAILURE", HINT
    assert probe.events == ["probe.fail", "probe.fail_local"], HINT
    assert _branch_errors(trace, OWNER) == {OWNER_STEP: ["OWNER_FAILURE"]}, HINT
    assert _branch_errors(trace, LOCAL) == {LOCAL_STEP: ["LOCAL_FAILURE"]}, HINT
    assert local_outcome(trace, local_completed=False) == FAILURE, HINT
    await script.async_unload()


async def test_normal_stop_ends_the_whole_run_after_the_sibling_settles(hass: HomeAssistant) -> None:
    """A stop is not branch-local: the sibling finishes, the following action never runs; no local success."""
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(hass, [{"stop": "normal stop"}], [{"action": "probe.finish"}])

    result, err = await _run(script)

    assert err is None, HINT
    assert result is not None, HINT
    assert probe.events == ["local_finished"], HINT
    assert "probe.after" not in probe.events, HINT
    assert _errors(trace) == {}, HINT
    assert local_outcome(trace, local_completed=False) == NO_SUCCESS, HINT
    await script.async_unload()


async def test_error_stop_returns_a_result_and_records_the_error_only_in_the_trace(hass: HomeAssistant) -> None:
    """A non-None result is no evidence of success: the error stop lives in the owner trace path."""
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(hass, [{"stop": "error stop", "error": True}], [{"action": "probe.finish"}])

    result, err = await _run(script)

    assert err is None, HINT
    assert result is not None, HINT
    assert probe.events == ["local_finished"], HINT
    assert _branch_errors(trace, OWNER) == {OWNER_STEP: ["error stop"]}, HINT
    assert _branch_errors(trace, LOCAL) == {}, HINT
    await script.async_unload()


async def test_continue_on_error_keeps_the_authored_continuation_and_the_trace_error(hass: HomeAssistant) -> None:
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(
        hass,
        [{"action": "probe.fail", "continue_on_error": True}, {"action": "probe.owner_after"}],
        [{"action": "probe.finish"}, LOCAL_DONE],
    )

    result, err = await _run(script)

    assert err is None, HINT
    assert result is not None, HINT
    assert probe.events == ["probe.fail", "probe.owner_after", "local_finished", "probe.local_done", "probe.after"], (
        HINT
    )
    assert _branch_errors(trace, OWNER) == {OWNER_STEP: ["OWNER_FAILURE"]}, HINT
    assert local_outcome(trace, local_completed=True) == SUCCESS, HINT
    await script.async_unload()


async def test_stop_response_comes_from_the_stopping_branch(hass: HomeAssistant) -> None:
    """The outer service response is the owner's stop response; responses are no per-branch result channel."""
    probe = Probe(hass)
    script = await _parallel(
        hass,
        [{"variables": {"answer": {"branch": "owner"}}}, {"stop": "response", "response_variable": "answer"}],
        [{"action": "probe.finish"}],
    )

    result, err = await _run(script)

    assert err is None, HINT
    assert result.service_response == {"branch": "owner"}, HINT
    assert probe.events == ["local_finished"], HINT
    await script.async_unload()


async def test_distinct_response_variables_are_both_visible_after_the_parallel(hass: HomeAssistant) -> None:
    Probe(hass)
    script = await _parallel(
        hass,
        [{"action": "probe.response", "data": {"answer": "owner"}, "response_variable": "owner_reply"}],
        [{"action": "probe.response", "data": {"answer": "local"}, "response_variable": "local_reply"}],
    )

    result, err = await _run(script)

    assert err is None, HINT
    assert result.variables["owner_reply"] == {"answer": "owner"}, HINT
    assert result.variables["local_reply"] == {"answer": "local"}, HINT
    await script.async_unload()


async def test_same_response_variable_is_one_shared_name_without_isolation(hass: HomeAssistant) -> None:
    """Both branches assign one name: a single value survives, so the branches share one namespace."""
    Probe(hass)
    script = await _parallel(
        hass,
        [{"action": "probe.response", "data": {"answer": "owner"}, "response_variable": "reply"}],
        [{"action": "probe.response", "data": {"answer": "local"}, "response_variable": "reply"}],
    )

    result, err = await _run(script)

    assert err is None, HINT
    # No promise which branch wins: ordering between branches is not a supported coordination mechanism
    assert result.variables["reply"] in ({"answer": "owner"}, {"answer": "local"}), HINT
    assert not {"owner_reply", "local_reply"} & set(result.variables), HINT
    await script.async_unload()


async def test_owner_stop_masks_a_local_error_from_the_outer_result(hass: HomeAssistant) -> None:
    """No outer exception at all: the local failure is visible only in the local trace path."""
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(hass, [{"stop": "normal stop"}], [{"action": "probe.fail_local"}, LOCAL_DONE])

    result, err = await _run(script)

    assert err is None, HINT
    assert result is not None, HINT
    assert probe.events == ["probe.fail_local"], HINT
    assert _branch_errors(trace, OWNER) == {}, HINT
    assert _branch_errors(trace, LOCAL) == {LOCAL_STEP: ["LOCAL_FAILURE"]}, HINT
    assert local_outcome(trace, local_completed=False) == FAILURE, HINT
    await script.async_unload()


def _templates(node: Any) -> list[Template]:
    """Return every Template in a validated tree."""
    if isinstance(node, Template):
        return [node]
    if isinstance(node, dict):
        return [template for value in node.values() for template in _templates(value)]
    if isinstance(node, list):
        return [template for item in node for template in _templates(item)]
    return []


async def test_owner_only_guard_denies_the_owner_and_leaves_the_identical_local_call_unwrapped(
    hass: HomeAssistant,
) -> None:
    """D-02: the guard wraps the owner subtree only; the same templated local call runs, the denial is not continued."""
    probe = Probe(hass)
    trace = trace_get()
    templated = "{{ 'mqtt.publish' }}"
    script = await _parallel(
        hass,
        [{"action": templated, "continue_on_error": True}],
        [{"action": templated}, LOCAL_DONE],
        guard_owner=True,
    )
    owner_tree = script.sequence[0]["parallel"][0]["sequence"]
    local_tree = script.sequence[0]["parallel"][1]["sequence"]
    assert any(isinstance(item, GuardedTemplate) for item in _templates(owner_tree)), HINT
    assert _templates(local_tree), HINT
    assert not any(isinstance(item, GuardedTemplate) for item in _templates(local_tree)), HINT

    _result, err = await _run(script)

    assert isinstance(err, DeniedServiceCallError), HINT
    assert probe.events == ["mqtt.publish", "probe.local_done"], HINT
    denied = "service mqtt.publish is not allowed for mirrored actions"
    assert _branch_errors(trace, OWNER) == {OWNER_STEP: [denied]}, HINT
    assert local_outcome(trace, local_completed=True) == SUCCESS, HINT
    await script.async_unload()


# --- further D-19 cases: continued and nested errors, aborts and runs that never complete ---------------------------


async def test_continued_local_error_is_a_local_failure_despite_completion(hass: HomeAssistant) -> None:
    """The local branch continues and completes, the outer run succeeds, yet the continued error is reportable."""
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(
        hass, [{"action": "probe.owner"}], [{"action": "probe.fail_local", "continue_on_error": True}, LOCAL_DONE]
    )

    result, err = await _run(script)

    assert err is None, HINT
    assert result is not None, HINT
    assert probe.events == ["probe.owner", "probe.fail_local", "probe.local_done", "probe.after"], HINT
    assert _branch_errors(trace, LOCAL) == {LOCAL_STEP: ["LOCAL_FAILURE"]}, HINT
    assert local_outcome(trace, local_completed=True) == FAILURE, HINT
    await script.async_unload()


async def test_nested_continued_local_errors_stay_reportable_at_their_nested_paths(hass: HomeAssistant) -> None:
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(
        hass,
        [{"action": "probe.owner"}],
        [
            {"sequence": [{"action": "probe.fail_local", "continue_on_error": True}]},
            {
                "choose": [
                    {
                        "conditions": [{"condition": "template", "value_template": "{{ true }}"}],
                        "sequence": [{"action": "probe.fail_local", "continue_on_error": True}],
                    }
                ]
            },
            LOCAL_DONE,
        ],
    )

    result, err = await _run(script)

    assert err is None, HINT
    assert result is not None, HINT
    expected = ["probe.owner", "probe.fail_local", "probe.fail_local", "probe.local_done", "probe.after"]
    assert probe.events == expected, HINT
    assert _branch_errors(trace, LOCAL) == {
        f"{LOCAL}/sequence/0/sequence/0": ["LOCAL_FAILURE"],
        f"{LOCAL}/sequence/1/choose/0/sequence/0": ["LOCAL_FAILURE"],
    }, HINT
    assert _branch_errors(trace, OWNER) == {}, HINT
    assert local_outcome(trace, local_completed=True) == FAILURE, HINT
    await script.async_unload()


async def test_nested_uncaught_local_error_is_forwarded_and_stops_the_local_branch(hass: HomeAssistant) -> None:
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(
        hass, [{"action": "probe.owner"}], [{"sequence": [{"action": "probe.fail_local"}]}, LOCAL_DONE]
    )

    _result, err = await _run(script)

    assert str(err) == "LOCAL_FAILURE", HINT
    assert probe.events == ["probe.owner", "probe.fail_local"], HINT
    assert f"{LOCAL}/sequence/0/sequence/0" in _branch_errors(trace, LOCAL), HINT
    assert local_outcome(trace, local_completed=False) == FAILURE, HINT
    await script.async_unload()


async def test_condition_abort_ends_only_the_local_branch_without_an_error(hass: HomeAssistant) -> None:
    """A false condition ends the rest of its branch; the outer run continues; no error and no local success."""
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(
        hass,
        [{"action": "probe.owner"}],
        [{"condition": "template", "value_template": "{{ false }}"}, {"action": "probe.local"}, LOCAL_DONE],
    )

    result, err = await _run(script)

    assert err is None, HINT
    assert result is not None, HINT
    assert probe.events == ["probe.owner", "probe.after"], HINT
    assert _errors(trace) == {}, HINT
    assert _reached(trace, LOCAL), HINT
    assert local_outcome(trace, local_completed=False) == NO_SUCCESS, HINT
    await script.async_unload()


async def _held_run(hass: HomeAssistant, script: Script) -> asyncio.Task:
    """Start one run whose local branch waits in `probe.hold`, and let it reach the hold."""
    task = hass.async_create_task(script.async_run({}, Context()))
    await _turns()
    return task


async def test_cancelled_run_returns_a_result_but_no_local_success(hass: HomeAssistant) -> None:
    """Stopping the Script cancels the held local branch; the run still returns a normal result."""
    probe = Probe(hass)
    trace = trace_get()
    script = await _parallel(hass, [{"action": "probe.owner"}], [{"action": "probe.hold"}, LOCAL_DONE])
    task = await _held_run(hass, script)
    assert probe.events == ["probe.owner", "hold_start"], HINT

    await script.async_stop()
    result = await task

    assert result is not None, HINT
    assert probe.events == ["probe.owner", "hold_start", "hold_cancelled"], HINT
    assert _errors(trace) == {}, HINT
    assert local_outcome(trace, local_completed=False) == NO_SUCCESS, HINT
    await script.async_unload()


async def test_queued_overflow_drops_the_run_before_any_branch_starts(hass: HomeAssistant) -> None:
    probe = Probe(hass)
    script = await _parallel(hass, [{"action": "probe.owner"}], [{"action": "probe.hold"}, LOCAL_DONE], max_runs=1)
    task = await _held_run(hass, script)

    dropped = await script.async_run({}, Context())

    assert dropped is None, HINT
    assert probe.events == ["probe.owner", "hold_start"], HINT
    probe.gate.set()
    assert await task is not None, HINT
    # Only the admitted run completed its local branch; the dropped one never reached a branch
    assert probe.events.count("probe.owner") == 1, HINT
    assert probe.events.count("probe.local_done") == 1, HINT
    await script.async_unload()


async def test_rebuild_unload_cancels_the_running_local_branch(hass: HomeAssistant) -> None:
    """Replacing the device Script unloads the old one: its held local branch is cancelled and never completes."""
    probe = Probe(hass)
    trace = trace_get()
    old = await _parallel(hass, [{"action": "probe.owner"}], [{"action": "probe.hold"}, LOCAL_DONE])
    task = await _held_run(hass, old)
    new = await _parallel(hass, [{"action": "probe.owner"}], [{"action": "probe.local"}, LOCAL_DONE])

    await old.async_unload()
    result = await task

    assert result is not None, HINT
    assert probe.events == ["probe.owner", "hold_start", "hold_cancelled"], HINT
    assert local_outcome(trace, local_completed=False) == NO_SUCCESS, HINT
    _result, err = await _run(new)
    assert err is None, HINT
    assert probe.events[3:] == ["probe.owner", "probe.local", "probe.local_done", "probe.after"], HINT
    await new.async_unload()


async def test_restart_supersedes_the_running_local_branch(hass: HomeAssistant) -> None:
    """In restart mode a new run cancels the held one; only the second run completes its local branch."""
    probe = Probe(hass)
    script = await _parallel(hass, [{"action": "probe.owner"}], [{"action": "probe.hold"}, LOCAL_DONE], mode="restart")
    first = await _held_run(hass, script)
    second = await _held_run(hass, script)

    probe.gate.set()
    results = await asyncio.gather(first, second)

    assert all(result is not None for result in results), HINT
    assert probe.events == [
        "probe.owner",
        "hold_start",
        "hold_cancelled",
        "probe.owner",
        "hold_start",
        "hold_end",
        "probe.local_done",
        "probe.after",
    ], HINT
    await script.async_unload()


async def test_different_trigger_and_owner_only_runs_never_reach_the_local_branch(hass: HomeAssistant) -> None:
    """In the per-device choose dispatcher, a run of another trigger or an owner-only trigger has no local path."""
    probe = Probe(hass)
    validated = await async_validate_actions(
        hass,
        [
            {
                "choose": [
                    {
                        "conditions": [{"condition": "template", "value_template": "{{ trigger_key == 'a' }}"}],
                        "sequence": [
                            {"parallel": [{"sequence": [{"action": "probe.owner"}]}, {"sequence": [LOCAL_DONE]}]}
                        ],
                    },
                    {
                        "conditions": [{"condition": "template", "value_template": "{{ trigger_key == 'b' }}"}],
                        "sequence": [{"action": "probe.owner"}],
                    },
                ]
            }
        ],
    )
    script = Script(hass, validated, "phase 11 dispatcher pin", "probe", script_mode="queued", max_runs=10)
    local_prefix = "0/choose/0/sequence/0/parallel/1"

    trace = trace_get()
    await script.async_run({"trigger_key": "b"}, Context())
    assert probe.events == ["probe.owner"], HINT
    assert not _reached(trace, local_prefix), HINT
    assert local_outcome(trace, local_completed=False, prefix=local_prefix) == NO_SUCCESS, HINT

    trace = trace_get()
    await script.async_run({"trigger_key": "a"}, Context())
    assert probe.events[1:] == ["probe.owner", "probe.local_done"], HINT
    assert _reached(trace, local_prefix), HINT
    assert local_outcome(trace, local_completed=True, prefix=local_prefix) == SUCCESS, HINT
    await script.async_unload()
