"""
Two followers keep different local actions for the same owner mirrors (D-02 to D-04, MIR-02, MIR-06, MIR-09 to MIR-11).

One owner publishes a Switch, a Select with an option without actions and a Switch without any actions. Two followers
on the same fake broker save different additive, replacement and muting records for those triggers, approve different
devices and leave the others pending. Each follower must run only the effective actions of its own records on every
entry point (state change, test button, re-trigger), keep the owner's approval exact and its safe policy while
pending, and send nothing to the broker that the other instances could see: every shared document, hash and retained
topic stays byte-identical, and no local service name reaches any publication.

Every local service name carries `sentinel` plus the follower's name, so a leak into the other instance shows as a
call and a leak onto the wire shows in the publication scan.
"""

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.mqtt_actions import retrigger as retrigger_module
from custom_components.mqtt_actions.const import CONF_DEVICE_ID, SUBENTRY_SELECT, SUBENTRY_SWITCH
from custom_components.mqtt_actions.document import actions_hash
from custom_components.mqtt_actions.local_actions import (
    LOCAL_SAFE_POLICY,
    EffectivePolicy,
    LocalActionMode,
    local_trigger_identity,
)
from custom_components.mqtt_actions.manager import LocalActionError
from custom_components.mqtt_actions.model import spec_from_data, trigger_key
from custom_components.mqtt_actions.topics import config_topic

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant

    from tests.fake_broker import FakeBroker, Instance

pytestmark = pytest.mark.multi_instance

BASE = "mqtt_actions"
ADDITIVE = LocalActionMode.ADDITIVE
REPLACEMENT = LocalActionMode.REPLACEMENT

OWNER_SERVICES = ("owner_on", "owner_off", "owner_cozy")
# Every local service names its follower; "sentinel" is what the publication scan looks for
BETA_SERVICES = ("beta_sentinel_lamp_on", "beta_sentinel_cozy", "beta_sentinel_bare_on")
GAMMA_SERVICES = ("gamma_sentinel_lamp_on", "gamma_sentinel_lamp_off", "gamma_sentinel_bright")
ALL_SERVICES = (*OWNER_SERVICES, *BETA_SERVICES, *GAMMA_SERVICES)
LEAK_MARKERS = ("sentinel", "beta_", "gamma_")

# Owner settings that differ from the safe local policy, so a follower that trusts them too early is visible
LAMP_SETTINGS = {"run_mode": "restart", "breaker_max_runs": 20, "breaker_window": 60}
MODE_SETTINGS = {"breaker_max_runs": 30, "breaker_window": 60}


def _local(service: str) -> list[dict[str, Any]]:
    return [{"action": f"test.{service}", "data": {"source": service}}]


@dataclass
class Scenario:
    """The owner, both followers, the three owner subentries and the service calls of every instance."""

    alpha: Instance
    beta: Instance
    gamma: Instance
    lamp: ConfigSubentryData
    mode: ConfigSubentryData
    bare: ConfigSubentryData
    calls: dict[str, dict[str, list]]

    @property
    def instances(self) -> tuple[Instance, Instance, Instance]:
        return self.alpha, self.beta, self.gamma

    @property
    def followers(self) -> tuple[Instance, Instance]:
        return self.beta, self.gamma

    def ids(self) -> tuple[str, str, str]:
        return tuple(sub["data"][CONF_DEVICE_ID] for sub in (self.lamp, self.mode, self.bare))  # type: ignore[return-value]

    def ran(self) -> dict[str, list[str]]:
        """Return the services each instance ran since the last call, sorted, and forget them."""
        result: dict[str, list[str]] = {}
        for name, services in self.calls.items():
            result[name] = sorted(service for service, served in services.items() for _ in served)
            for served in services.values():
                served.clear()
        return result


async def _settle(*instances: Instance) -> None:
    for _ in range(3):
        for instance in instances:
            await instance.hass.async_block_till_done(wait_background_tasks=True)


def _baseline_hash(sub: ConfigSubentryData) -> str:
    """Return the owner-only actions hash of a subentry, built from its data alone."""
    return actions_hash(spec_from_data(sub["subentry_type"], sub["title"], dict(sub["data"])))


# The local choices of each follower: (device, kind, StateValue) -> (mode, actions)
def _beta_records(lamp_id: str, mode_id: str, bare_id: str) -> dict[tuple[str, str, str], tuple[Any, list]]:
    return {
        (lamp_id, SUBENTRY_SWITCH, "ON"): (ADDITIVE, _local("beta_sentinel_lamp_on")),
        # Muted on beta only
        (lamp_id, SUBENTRY_SWITCH, "OFF"): (REPLACEMENT, []),
        (mode_id, SUBENTRY_SELECT, "cozy"): (REPLACEMENT, _local("beta_sentinel_cozy")),
        # The owner's document has no actions at all
        (bare_id, SUBENTRY_SWITCH, "ON"): (ADDITIVE, _local("beta_sentinel_bare_on")),
    }


def _gamma_records(lamp_id: str, mode_id: str, _bare_id: str) -> dict[tuple[str, str, str], tuple[Any, list]]:
    return {
        (lamp_id, SUBENTRY_SWITCH, "ON"): (REPLACEMENT, _local("gamma_sentinel_lamp_on")),
        (lamp_id, SUBENTRY_SWITCH, "OFF"): (ADDITIVE, _local("gamma_sentinel_lamp_off")),
        # The owner's option has no actions
        (mode_id, SUBENTRY_SELECT, "bright"): (ADDITIVE, _local("gamma_sentinel_bright")),
    }


async def _started(
    hass: HomeAssistant,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> Scenario:
    """Start owner alpha and followers beta and gamma; approve the Lamp on beta and the Mode on gamma only."""
    lamp = make_switch_subentry(
        "Lamp", on=[{"action": "test.owner_on"}], off=[{"action": "test.owner_off"}], **LAMP_SETTINGS
    )
    mode = make_select_subentry(
        "Mode", [("cozy", "Cozy", [{"action": "test.owner_cozy"}]), ("bright", "Bright", [])], **MODE_SETTINGS
    )
    bare = make_switch_subentry("Bare")
    alpha = await make_instance("alpha", hass=hass, subentries=[lamp, mode, bare])
    beta = await make_instance("beta")
    gamma = await make_instance("gamma")
    calls = {
        instance.name: {service: async_mock_service(instance.hass, "test", service) for service in ALL_SERVICES}
        for instance in (alpha, beta, gamma)
    }
    scenario = Scenario(alpha, beta, gamma, lamp, mode, bare, calls)
    await _settle(*scenario.instances)
    lamp_id, mode_id, bare_id = scenario.ids()
    for follower in scenario.followers:
        assert {lamp_id, mode_id, bare_id} <= follower.manager.mirrors.keys(), f"premise: {follower.name} mirrors all"
    assert await beta.manager.async_approve(lamp_id, _baseline_hash(lamp))
    assert await gamma.manager.async_approve(mode_id, _baseline_hash(mode))
    await _settle(*scenario.instances)
    return scenario


async def _save_records(scenario: Scenario) -> None:
    """Save the different local records of beta and gamma through the production edit path."""
    for follower, records in ((scenario.beta, _beta_records), (scenario.gamma, _gamma_records)):
        for (device_id, kind, value), (mode_word, actions) in records(*scenario.ids()).items():
            await follower.manager.async_set_local_action(
                local_trigger_identity(device_id, kind, value), mode_word, actions
            )
    await _settle(*scenario.instances)


async def _scenario(
    hass: HomeAssistant,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> Scenario:
    """
    Start the three instances, save the records and prime every state topic.

    Nothing has run yet when this returns: the state topics only carry a primed value whose runs were discarded.
    """
    scenario = await _started(hass, make_instance, make_switch_subentry, make_select_subentry)
    await _save_records(scenario)
    lamp_id, mode_id, bare_id = scenario.ids()
    # A first value on every state topic, so each measured change below is a real edge on every instance
    for device_id, value in ((lamp_id, "OFF"), (mode_id, "bright"), (bare_id, "OFF")):
        await scenario.alpha.manager.async_send_state(device_id, value)
        await _settle(*scenario.instances)
    scenario.ran()
    return scenario


# What each instance runs for one trigger, on every entry point: owner alpha runs its own actions, each follower its
# effective plan (approved owner branch, additive or replacement local branch, mute)
EXPECTED_RUNS: dict[tuple[str, str], dict[str, list[str]]] = {
    ("lamp", "ON"): {
        "alpha": ["owner_on"],
        "beta": ["beta_sentinel_lamp_on", "owner_on"],  # approved + additive
        "gamma": ["gamma_sentinel_lamp_on"],  # pending + replacement
    },
    ("lamp", "OFF"): {
        "alpha": ["owner_off"],
        "beta": [],  # approved + mute
        "gamma": ["gamma_sentinel_lamp_off"],  # pending + additive: the owner branch stays out
    },
    ("mode", "cozy"): {
        "alpha": ["owner_cozy"],
        "beta": ["beta_sentinel_cozy"],  # pending + replacement
        "gamma": ["owner_cozy"],  # approved, no record
    },
    ("mode", "bright"): {
        "alpha": [],
        "beta": [],  # pending, no record, empty owner option
        "gamma": ["gamma_sentinel_bright"],  # approved + additive on an empty owner option
    },
    ("bare", "ON"): {
        "alpha": [],
        "beta": ["beta_sentinel_bare_on"],  # owner without actions + additive
        "gamma": [],
    },
    ("bare", "OFF"): {"alpha": [], "beta": [], "gamma": []},
}

# The re-trigger answer of each instance to a request of alpha: only the existing status and reason words
EXPECTED_ANSWERS: dict[tuple[str, str], dict[str, tuple[str, str | None]]] = {
    ("lamp", "ON"): {"alpha": ("executed", None), "beta": ("executed", None), "gamma": ("executed", None)},
    ("lamp", "OFF"): {"alpha": ("executed", None), "beta": ("error", "no_actions"), "gamma": ("executed", None)},
    ("mode", "cozy"): {"alpha": ("executed", None), "beta": ("executed", None), "gamma": ("executed", None)},
    ("mode", "bright"): {
        "alpha": ("error", "no_actions"),
        "beta": ("not_approved", None),
        "gamma": ("executed", None),
    },
    ("bare", "ON"): {"alpha": ("error", "no_actions"), "beta": ("executed", None), "gamma": ("error", "no_actions")},
    ("bare", "OFF"): {
        "alpha": ("error", "no_actions"),
        "beta": ("error", "no_actions"),
        "gamma": ("error", "no_actions"),
    },
}


def _device_of(scenario: Scenario, name: str) -> str:
    return dict(zip(("lamp", "mode", "bare"), scenario.ids(), strict=True))[name]


def _leaks(scenario: Scenario, fake_broker: FakeBroker) -> list[tuple[str, str]]:
    """Return (topic, payload prefix) of every publication or retained message that names a local service."""
    entries = [(topic, payload) for instance in scenario.instances for topic, payload, _ in instance.gateway.published]
    entries.extend(fake_broker.retained.items())
    return [
        (topic, payload[:80])
        for topic, payload in entries
        if any(marker in topic.lower() or marker in payload.lower() for marker in LEAK_MARKERS)
    ]


def _shared_retained(fake_broker: FakeBroker) -> dict[str, str]:
    """Return the retained documents and discovery messages: everything retained except the state topics."""
    return {topic: payload for topic, payload in fake_broker.retained.items() if not topic.endswith("/state")}


# --- isolation of the saved records, approval, policy and shared bytes -----------------------------------------------


async def test_followers_save_separate_records_and_publish_nothing(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-02, D-04, T-11-30: each follower's records live only in its own Store; saving them publishes nothing."""
    scenario = await _started(hass, make_instance, make_switch_subentry, make_select_subentry)
    alpha = scenario.alpha
    shared_before = _shared_retained(fake_broker)
    published_before = [len(instance.gateway.published) for instance in scenario.instances]

    await _save_records(scenario)

    assert [len(instance.gateway.published) for instance in scenario.instances] == published_before
    assert _shared_retained(fake_broker) == shared_before
    keys = [instance.local_store_key for instance in scenario.instances]
    assert len(set(keys)) == len(keys), f"two instances share a local Store key: {keys}"
    stored = {
        follower.name: json.dumps(hass_storage.get(follower.local_store_key, {}).get("data", {}).get("records"))
        for follower in scenario.followers
    }
    assert all(service in stored["beta"] for service in BETA_SERVICES)
    assert not any(service in stored["beta"] for service in GAMMA_SERVICES), "beta's Store holds gamma's records"
    assert all(service in stored["gamma"] for service in GAMMA_SERVICES)
    assert not any(service in stored["gamma"] for service in BETA_SERVICES), "gamma's Store holds beta's records"
    assert hass_storage.get(alpha.local_store_key, {}).get("data", {}).get("records", []) == []
    counts = {instance.name: instance.manager.local_action_counts().records for instance in scenario.instances}
    assert counts == {"alpha": 0, "beta": 4, "gamma": 3}
    # The owner cannot customize its own devices: local actions belong to mirrors
    with pytest.raises(LocalActionError):
        await alpha.manager.async_set_local_action(
            local_trigger_identity(scenario.ids()[0], SUBENTRY_SWITCH, "ON"), ADDITIVE, _local("beta_sentinel_lamp_on")
        )
    assert _leaks(scenario, fake_broker) == []


async def test_followers_keep_exact_approvals_and_safe_policies_on_identical_shared_bytes(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-03, D-04, T-11-31: owner approval stays exact per follower, pending mirrors run safe, documents are equal."""
    scenario = await _scenario(hass, make_instance, make_switch_subentry, make_select_subentry)
    _alpha, beta, gamma = scenario.instances
    lamp_id, mode_id, bare_id = scenario.ids()

    approvals = {
        follower.name: {device_id: str(follower.manager.approval_state(device_id)) for device_id in scenario.ids()}
        for follower in scenario.followers
    }
    assert approvals == {
        "beta": {lamp_id: "approved", mode_id: "pending", bare_id: "no_actions"},
        "gamma": {lamp_id: "pending", mode_id: "approved", bare_id: "no_actions"},
    }
    assert beta.manager._approvals == {lamp_id: _baseline_hash(scenario.lamp)}
    assert gamma.manager._approvals == {mode_id: _baseline_hash(scenario.mode)}

    # The owner's settings govern only an exactly approved mirror; every other one runs on the safe local policy
    lamp_policy = EffectivePolicy(
        run_on_startup=False, run_mode="restart", breaker_max_runs=20, breaker_window=60, queue_limit=10
    )
    mode_policy = EffectivePolicy(
        run_on_startup=False, run_mode="serial", breaker_max_runs=30, breaker_window=60, queue_limit=10
    )
    policies = {
        follower.name: {device_id: follower.manager.device(device_id).policy for device_id in scenario.ids()}
        for follower in scenario.followers
    }
    assert policies == {
        "beta": {lamp_id: lamp_policy, mode_id: LOCAL_SAFE_POLICY, bare_id: LOCAL_SAFE_POLICY},
        "gamma": {lamp_id: LOCAL_SAFE_POLICY, mode_id: mode_policy, bare_id: LOCAL_SAFE_POLICY},
    }
    for follower in scenario.followers:
        for device_id in scenario.ids():
            breaker = follower.manager.device(device_id).breaker
            expected = policies[follower.name][device_id]
            assert (breaker.max_runs, breaker.window) == (expected.breaker_max_runs, expected.breaker_window)

    # Both followers hold the same owner document and hash for every mirror, equal to the retained bytes
    for sub in (scenario.lamp, scenario.mode, scenario.bare):
        device_id = sub["data"][CONF_DEVICE_ID]
        retained = fake_broker.retained[config_topic(BASE, device_id)]
        for follower in scenario.followers:
            info = follower.manager.mirrors[device_id].mirror
            assert info is not None
            assert info.actions_hash == _baseline_hash(sub)
            assert actions_hash(follower.manager.mirrors[device_id].spec) == _baseline_hash(sub)
            assert info.payload == retained
    assert _leaks(scenario, fake_broker) == []


# --- every entry point runs each follower's own effective actions ----------------------------------------------------


async def test_state_changes_run_only_each_followers_own_local_actions(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-02, D-03, MIR-02: one state change on the shared topic runs a different effective plan on each follower."""
    scenario = await _scenario(hass, make_instance, make_switch_subentry, make_select_subentry)
    shared_before = _shared_retained(fake_broker)

    runs: dict[tuple[str, str], dict[str, list[str]]] = {}
    for device, value in EXPECTED_RUNS:
        await scenario.alpha.manager.async_send_state(_device_of(scenario, device), value)
        await _settle(*scenario.instances)
        runs[device, value] = scenario.ran()

    assert runs == EXPECTED_RUNS
    assert _shared_retained(fake_broker) == shared_before
    assert _leaks(scenario, fake_broker) == []
    for follower in scenario.followers:
        assert not any(device.breaker.tripped for device in follower.manager.mirrors.values())


async def test_test_buttons_run_only_each_followers_own_local_actions(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """MIR-10: a test press on each instance runs what a state change runs there, and publishes nothing shared."""
    scenario = await _scenario(hass, make_instance, make_switch_subentry, make_select_subentry)
    shared_before = _shared_retained(fake_broker)
    published_before = [len(instance.gateway.published) for instance in scenario.instances]

    runs: dict[tuple[str, str], dict[str, list[str]]] = {}
    for device, value in EXPECTED_RUNS:
        for instance in scenario.instances:
            await instance.manager.async_press_test(_device_of(scenario, device), trigger_key(value))
        await _settle(*scenario.instances)
        runs[device, value] = scenario.ran()

    assert runs == EXPECTED_RUNS
    assert [len(instance.gateway.published) for instance in scenario.instances] == published_before
    assert _shared_retained(fake_broker) == shared_before
    assert _leaks(scenario, fake_broker) == []


async def test_retrigger_runs_each_followers_own_local_actions_with_the_existing_answer_words(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """MIR-10, D-03: one request of the owner runs each follower's plan; the answers use only the existing words."""
    scenario = await _scenario(hass, make_instance, make_switch_subentry, make_select_subentry)
    for instance in scenario.instances:
        await instance.manager.presence.async_publish_heartbeat()
    await _settle(*scenario.instances)
    shared_before = _shared_retained(fake_broker)
    # The requester's interval per device runs on the manager clock; each request below is a new interval.
    # Every receiver limits requests per device on its manager clock, too
    now = [1000.0]
    for instance in scenario.instances:
        instance.manager.clock = lambda: now[0]

    runs: dict[tuple[str, str], dict[str, list[str]]] = {}
    answers: dict[tuple[str, str], dict[str, tuple[str, str | None]]] = {}
    for device, value in EXPECTED_RUNS:
        now[0] += 60
        result = await scenario.alpha.manager.retrigger.async_retrigger(_device_of(scenario, device), value)
        await _settle(*scenario.instances)
        runs[device, value] = scenario.ran()
        answers[device, value] = {
            entry["instance_name"]: (entry["status"], entry.get("reason")) for entry in result["instances"]
        }

    assert answers == EXPECTED_ANSWERS
    assert runs == EXPECTED_RUNS
    statuses = {status for answer in answers.values() for status, _ in answer.values()}
    reasons = {reason for answer in answers.values() for _, reason in answer.values()} - {None}
    assert statuses <= frozenset(retrigger_module._STATUS_WORDS)
    assert reasons <= frozenset(retrigger_module._REASON_WORDS)
    assert _shared_retained(fake_broker) == shared_before
    assert _leaks(scenario, fake_broker) == []


async def test_follower_restarts_reload_only_their_own_records(
    hass: HomeAssistant,
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """MIR-06, T-11-30: after a restart both followers load and run only their own plans; the Stores did not mix."""
    scenario = await _scenario(hass, make_instance, make_switch_subentry, make_select_subentry)
    # Beta first: gamma saved last, so a shared Store key would hand gamma's records to the restarted beta
    for follower in scenario.followers:
        await follower.restart()
    await _settle(*scenario.instances)
    scenario.ran()

    runs: dict[tuple[str, str], dict[str, list[str]]] = {}
    for device, value in (("lamp", "ON"), ("lamp", "OFF"), ("mode", "cozy"), ("mode", "bright")):
        await scenario.alpha.manager.async_send_state(_device_of(scenario, device), value)
        await _settle(*scenario.instances)
        runs[device, value] = scenario.ran()

    assert runs == {key: EXPECTED_RUNS[key] for key in runs}
    assert scenario.gamma.manager.local_action_counts().records == 3
    assert scenario.beta.manager.local_action_counts().records == 4
    assert _leaks(scenario, fake_broker) == []
