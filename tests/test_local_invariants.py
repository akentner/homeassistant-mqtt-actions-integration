"""
Owner bytes and broker traffic never carry local actions (D-04, D-21, T-11-01).

Written before any Phase 11 production code, on purpose: the separate local-actions Store is seeded with unique markers
in action data, templates, targets, labels and StateValues, and every artifact an owner authorizes or a broker carries
is compared with the owner-only baseline built from the subentry data alone. Today no production code reads that Store,
so these tests are green and characterize the existing wire paths; from Plan 11-05 on the Manager loads the Store, and
the same assertions then prove that loading it changes no owner byte and no publication.

The seeded keys follow the Plan 11-04 contract: the production key `mqtt_actions.local_actions` plus the per-instance
`Instance.local_store_key` once the factory injects one. Each instance is stopped, seeded and started again, so a save
on the way down cannot overwrite the seed and every start loads it.

The publication oracle reads the complete `FakeGateway.published` history of every instance, retained and transient
alike, plus the retained broker state. A local action that deliberately calls `mqtt.publish` is execution data the user
authored, not serialization of overlay configuration by the integration: such a call goes to the Home Assistant service
registry (a mock here), never through the gateway, so it is outside this oracle by construction.
"""

import json
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from homeassistant.helpers.json import json_dumps
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.mqtt_actions import retrigger as retrigger_module
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_DISCOVERY_EXPORT,
    CONF_ON_CHANGE_TO_ON,
    DEFAULT_EXPORT_PREFIX,
    PRUNE_GRACE_SECONDS,
    STORE_KEY,
    STORE_MIRRORS,
    STORE_VERSION,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
from custom_components.mqtt_actions.diagnostics import async_get_config_entry_diagnostics
from custom_components.mqtt_actions.discovery import build_export
from custom_components.mqtt_actions.document import (
    actions_hash,
    build_content,
    build_document,
    canonical_json,
    serialize_document,
)
from custom_components.mqtt_actions.local_actions import local_trigger_identity
from custom_components.mqtt_actions.manager import AdoptionError, async_remove_all_devices, async_remove_local_state
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY, spec_from_data
from custom_components.mqtt_actions.mqtt_gateway import IncomingMessage
from custom_components.mqtt_actions.portability import subentry_payload
from custom_components.mqtt_actions.topics import config_topic, discovery_topic
from tests.fake_broker import FakeBroker, FakeGateway

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.model import DeviceSpec
    from tests.fake_broker import Instance

pytestmark = pytest.mark.multi_instance

BASE = "mqtt_actions"
# Literal on purpose: Plan 11-04 declares LOCAL_ACTIONS_STORE_KEY with this value, and the test must not depend on it
LOCAL_STORE_KEY = "mqtt_actions.local_actions"
LOCAL_STORE_VERSION = 1
MODE_ADDITIVE = "additive"
MODE_REPLACEMENT = "replacement"

# Markers: none of them may appear in any owner artifact or any publication, in any letter case
M_DATA = "LOCAL_SENTINEL_DATA_7f3a"
M_TEMPLATE = "LOCAL_SENTINEL_TEMPLATE_9c1e"
M_TARGET = "light.local_sentinel_target_4b2d"
M_LABEL = "LOCAL SENTINEL LABEL 5e8b"
M_ORPHAN = "localsentinelorphan0d6c"
M_TOPIC = "local_sentinel_topic_2a91/publish"
MARKERS = (M_DATA, M_TEMPLATE, M_TARGET, M_LABEL, M_ORPHAN, M_TOPIC)

OWNER_ON = [{"action": "test.owner_on"}]
OWNER_OFF = [{"action": "test.owner_off"}]
OWNER_COZY = [{"action": "test.owner_cozy"}]
SERVICES = (("test", "owner_on"), ("test", "owner_off"), ("test", "owner_cozy"), ("test", "local_sentinel"))


def _local_actions() -> list[dict[str, Any]]:
    """Return a trusted local sequence whose data, template, target and authored publish all carry markers."""
    return [
        {
            "action": "test.local_sentinel",
            "target": {"entity_id": M_TARGET},
            "data": {"message": M_DATA, "rendered": "{{ '" + M_TEMPLATE + "' }}"},
        },
        # Authored by the user: a deliberate service call, never a publish of the integration (see the module text)
        {"action": "mqtt.publish", "data": {"topic": M_TOPIC, "payload": M_DATA}},
    ]


def _record(device_id: str, kind: str, state_value: str, mode: str, actions: list[dict[str, Any]]) -> dict[str, Any]:
    """Return one v1 local record: identity (device id, kind, StateValue), last label, mode and raw actions."""
    return {
        "device_id": device_id,
        "kind": kind,
        "state_value": state_value,
        "label": M_LABEL,
        "mode": mode,
        "actions": actions,
    }


def _sentinel_records(lamp_id: str, mode_id: str) -> list[dict[str, Any]]:
    """Return active, muted, orphaned and kind-mismatched records for a Switch and a Select, all full of markers."""
    return [
        _record(lamp_id, SUBENTRY_SWITCH, "ON", MODE_ADDITIVE, _local_actions()),
        _record(lamp_id, SUBENTRY_SWITCH, "OFF", MODE_REPLACEMENT, _local_actions()),
        # Same StateValue under the other kind: must never attach to the Switch
        _record(lamp_id, SUBENTRY_SELECT, "ON", MODE_ADDITIVE, _local_actions()),
        _record(mode_id, SUBENTRY_SELECT, "cozy", MODE_ADDITIVE, _local_actions()),
        # Empty replacement: a deliberate local mute of the option
        _record(mode_id, SUBENTRY_SELECT, "bright", MODE_REPLACEMENT, []),
        # The owner has no such option: an orphan that stays inactive
        _record(mode_id, SUBENTRY_SELECT, M_ORPHAN, MODE_REPLACEMENT, _local_actions()),
    ]


def _local_store_keys(instances: Iterable[Instance]) -> set[str]:
    """Return the production local key plus every injected per-instance key (Plan 11-04 adds `local_store_key`)."""
    keys = {LOCAL_STORE_KEY}
    for instance in instances:
        if (key := getattr(instance, "local_store_key", None)) is not None:
            keys.add(key)
    return keys


def _seed_local_store(hass_storage: dict[str, Any], instances: Iterable[Instance], records: list[dict]) -> None:
    """Write the records as an HA Store v1 envelope under every local key the instances may read."""
    for key in _local_store_keys(instances):
        hass_storage[key] = {
            "version": LOCAL_STORE_VERSION,
            "minor_version": 1,
            "key": key,
            "data": {"records": json.loads(json.dumps(records))},
        }


async def _settle(*instances: Instance) -> None:
    """Let every instance finish the messages and background tasks the broker delivered."""
    for _ in range(2):
        for instance in instances:
            await instance.hass.async_block_till_done(wait_background_tasks=True)


async def _restart_seeded(hass_storage: dict[str, Any], records: list[dict], *instances: Instance) -> None:
    """Stop each instance, seed its local Store and start it again, so the start (and nothing else) reads the seed."""
    for instance in instances:
        await instance.stop()
        _seed_local_store(hass_storage, [instance], records)
        await instance.start()
    await _settle(*instances)


def _register_services(*instances: Instance) -> dict[str, dict[str, list]]:
    """Register every owner and local service, and a mock `mqtt.publish`, on each instance; return the call lists."""
    calls: dict[str, dict[str, list]] = {}
    for instance in instances:
        calls[instance.name] = {
            f"{domain}.{service}": async_mock_service(instance.hass, domain, service) for domain, service in SERVICES
        }
        calls[instance.name]["mqtt.publish"] = async_mock_service(instance.hass, "mqtt", "publish")
    return calls


def _baseline_spec(sub: ConfigSubentryData) -> DeviceSpec:
    """Return the owner-only spec of a subentry, built from its data alone and never from a running manager."""
    return spec_from_data(sub["subentry_type"], sub["title"], dict(sub["data"]))


def _device_id(sub: ConfigSubentryData) -> str:
    return sub["data"][CONF_DEVICE_ID]


def _subentries(
    make_switch_subentry: Callable, make_select_subentry: Callable
) -> tuple[ConfigSubentryData, ConfigSubentryData]:
    lamp = make_switch_subentry("Lamp", on=OWNER_ON, off=OWNER_OFF)
    mode = make_select_subentry("Mode", [("cozy", "Cozy", OWNER_COZY), ("bright", "Bright", [])])
    return lamp, mode


async def _seeded_pair(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> tuple[Instance, Instance, ConfigSubentryData, ConfigSubentryData, dict[str, dict[str, list]]]:
    """Start owner alpha of a Switch and a Select and follower beta; both restart with the sentinel local Store."""
    lamp, mode = _subentries(make_switch_subentry, make_select_subentry)
    alpha = await make_instance("alpha", hass=hass, subentries=[lamp, mode])
    beta = await make_instance("beta")
    calls = _register_services(alpha, beta)
    await _settle(alpha, beta)
    records = _sentinel_records(_device_id(lamp), _device_id(mode))
    await _restart_seeded(hass_storage, records, alpha, beta)
    assert {_device_id(lamp), _device_id(mode)} <= beta.manager.mirrors.keys()
    return alpha, beta, lamp, mode, calls


async def _approve_all(instance: Instance) -> None:
    """Approve the current hash of every mirror of an instance that has actions to approve."""
    for device_id, device in list(instance.manager.mirrors.items()):
        assert device.mirror is not None
        if str(instance.manager.approval_state(device_id)) == "pending":
            assert await instance.manager.async_approve(device_id, device.mirror.actions_hash) is True


def _expected_document(spec: DeviceSpec, owner: Instance, **bookkeeping: Any) -> str:
    """Return the wire bytes of the owner-only document of a spec, with the owner's bookkeeping."""
    return serialize_document(
        build_document(spec, owner=owner.manager.instance_id, owner_name=owner.name, **bookkeeping)
    )


def _leaks(gateways: Iterable[FakeGateway], retained: dict[str, str] | None = None) -> list[tuple[str, str, str]]:
    """
    Return (marker, topic, payload prefix) for every publication that carries a marker, in any letter case.

    Every tuple of every gateway's history counts, retained or not; the retained broker state is scanned as well.
    """
    entries = [(topic, payload) for gateway in gateways for topic, payload, _retain in gateway.published]
    entries.extend((retained or {}).items())
    return [
        (marker, topic, payload[:80])
        for topic, payload in entries
        for marker in MARKERS
        if marker.lower() in topic.lower() or marker.lower() in payload.lower()
    ]


# --- owner hash and document bytes ----------------------------------------------------------------------------------


async def test_owner_hash_and_document_bytes_equal_the_owner_only_baseline(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-04: with the sentinel Store loaded, every actions hash, document and cached payload is the owner-only one."""
    alpha, beta, lamp, mode, _calls = await _seeded_pair(
        hass, hass_storage, make_instance, make_switch_subentry, make_select_subentry
    )
    await _approve_all(beta)
    await _settle(alpha, beta)
    await beta.manager.async_save_now()

    for sub in (lamp, mode):
        spec = _baseline_spec(sub)
        device_id = spec.device_id
        expected_hash = actions_hash(spec)
        expected = _expected_document(
            spec, alpha, rev=alpha.manager.revision(device_id), native=alpha.manager.is_native(device_id)
        )
        mirror = beta.manager.mirrors[device_id]
        assert mirror.mirror is not None
        # The approval is bound to the owner-only hash, and the running specs are not mutated by an overlay
        assert mirror.mirror.actions_hash == expected_hash
        assert actions_hash(mirror.spec) == expected_hash
        assert actions_hash(alpha.manager.devices[device_id].spec) == expected_hash
        assert beta.manager._approvals.get(device_id, expected_hash) == expected_hash
        # Byte equality of the wire document: every publish, the retained copy and the follower's cached payload
        sent = [
            payload for topic, payload, _retain in alpha.gateway.published if topic == config_topic(BASE, device_id)
        ]
        assert sent, f"the owner never published the document of {sub['title']}"
        assert set(sent) == {expected}
        assert fake_broker.retained[config_topic(BASE, device_id)] == expected
        assert mirror.mirror.payload == expected
        stored = hass_storage[beta.store_key]["data"][STORE_MIRRORS][device_id]
        assert stored == expected


async def test_owner_hash_survives_a_restart_with_the_local_store(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-04: an approval made with the sentinel Store present still matches after a restart; the hash never moved."""
    alpha, beta, lamp, mode, _calls = await _seeded_pair(
        hass, hass_storage, make_instance, make_switch_subentry, make_select_subentry
    )
    await _approve_all(beta)
    approvals = dict(beta.manager._approvals)
    assert approvals == {sub["data"][CONF_DEVICE_ID]: actions_hash(_baseline_spec(sub)) for sub in (lamp, mode)}
    records = _sentinel_records(_device_id(lamp), _device_id(mode))

    await _restart_seeded(hass_storage, records, beta)
    await _settle(alpha, beta)

    for sub in (lamp, mode):
        assert str(beta.manager.approval_state(_device_id(sub))) == "approved"
    assert beta.manager._approvals == approvals


# --- adoption subentry bytes ----------------------------------------------------------------------------------------


async def test_adoption_subentry_and_adopted_document_bytes_equal_the_owner_only_baseline(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-04, D-05: the adopted subentry holds the owner content exactly, and the adopter publishes owner bytes only."""
    alpha, beta, lamp, mode, _calls = await _seeded_pair(
        hass, hass_storage, make_instance, make_switch_subentry, make_select_subentry
    )
    await _approve_all(beta)
    await alpha.stop()
    await _settle(alpha, beta)

    for sub in (lamp, mode):
        spec = _baseline_spec(sub)
        device_id = spec.device_id
        published_before = len(beta.gateway.published)

        assert await beta.manager.async_adopt(device_id, force=True) == "alpha"
        await _settle(alpha, beta)

        (subentry,) = [item for item in beta.entry.subentries.values() if item.unique_id == device_id]
        expected_data = subentry_payload(build_content(spec), device_id)
        assert canonical_json(dict(subentry.data)) == canonical_json(expected_data)
        assert dict(subentry.data) == expected_data
        assert (subentry.subentry_type, subentry.title) == (spec.kind, spec.name)
        sent = [
            payload
            for topic, payload, _retain in beta.gateway.published[published_before:]
            if topic == config_topic(BASE, device_id)
        ]
        assert sent, f"the adopter never published the document of {sub['title']}"
        rev = json.loads(sent[-1])["rev"]
        expected = _expected_document(
            spec,
            beta,
            rev=rev,
            transferred_from=(alpha.manager.instance_id,),
            native=beta.manager.is_native(device_id),
        )
        assert sent[-1] == expected
        assert actions_hash(beta.manager.devices[device_id].spec) == actions_hash(spec)
    assert _leaks([alpha.gateway, beta.gateway]) == []


# --- export publication bytes ---------------------------------------------------------------------------------------


async def test_export_publication_bytes_equal_the_owner_only_baseline(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-04: the discovery export of native owned devices is the owner-only payload with the sentinel Store loaded."""
    lamp, mode = _subentries(make_switch_subentry, make_select_subentry)
    alpha_key = f"{STORE_KEY}.alpha"
    hass_storage[alpha_key] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": alpha_key,
        "data": {"native": {"instance": True, "pending": [], "devices": []}},
    }
    alpha = await make_instance("alpha", hass=hass, subentries=[lamp, mode])
    _register_services(alpha)
    alpha.hass.config_entries.async_update_entry(alpha.entry, options={CONF_DISCOVERY_EXPORT: True})
    await alpha.manager.async_reconcile()
    await _settle(alpha)
    published_before = len(alpha.gateway.published)

    await _restart_seeded(hass_storage, _sentinel_records(_device_id(lamp), _device_id(mode)), alpha)

    for sub in (lamp, mode):
        spec = _baseline_spec(sub)
        assert alpha.manager.is_native(spec.device_id), "premise: only a native owned device has an export"
        topic = discovery_topic(DEFAULT_EXPORT_PREFIX, spec.device_id)
        expected = json_dumps(
            build_export(
                spec=spec, base_topic=BASE, instance_id=alpha.manager.instance_id, sw_version=alpha.manager.version
            )
        )
        sent = [payload for published, payload, _retain in alpha.gateway.published if published == topic]
        after_restart = [item for item in alpha.gateway.published[published_before:] if item[0] == topic]
        assert after_restart, f"the seeded start never published the export of {sub['title']}"
        assert set(sent) == {expected}
        assert fake_broker.retained[topic] == expected
    assert _leaks([alpha.gateway], fake_broker.retained) == []


# --- diagnostics ----------------------------------------------------------------------------------------------------


async def test_diagnostics_hash_rows_carry_no_local_content(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-04: the diagnostics of owner and follower show owner content hashes only and no marker of the local Store."""
    alpha, beta, lamp, mode, _calls = await _seeded_pair(
        hass, hass_storage, make_instance, make_switch_subentry, make_select_subentry
    )
    await _approve_all(beta)

    for instance in (alpha, beta):
        result = await async_get_config_entry_diagnostics(instance.hass, instance.entry)
        text = json.dumps(result)
        assert [marker for marker in MARKERS if marker.lower() in text.lower()] == []
        hashes = {row["uuid"]: row["hash"] for row in result["devices"]}
        for sub in (lamp, mode):
            spec = _baseline_spec(sub)
            assert hashes[spec.device_id] == json.loads(_expected_document(spec, alpha, rev=1))["hash"]


# --- every publication ----------------------------------------------------------------------------------------------


async def test_publication_oracle_sees_markers_in_transient_and_retained_publishes(hass: HomeAssistant) -> None:
    """The oracle is not vacuous: a marker in a transient payload, a retained payload or a topic is reported."""
    gateway = FakeGateway(FakeBroker(), hass)
    await gateway.async_publish("mqtt_actions/v1/clean", "nothing here", retain=False)
    assert _leaks([gateway]) == []

    await gateway.async_publish("mqtt_actions/v1/acks/x", json.dumps({"reason": M_DATA}), retain=False)
    await gateway.async_publish("mqtt_actions/v1/devices/x/config", json.dumps({"a": M_LABEL.lower()}), retain=True)
    await gateway.async_publish(f"mqtt_actions/{M_TOPIC}", "", retain=True)

    found = {(marker, topic) for marker, topic, _payload in _leaks([gateway])}
    assert found == {
        (M_DATA, "mqtt_actions/v1/acks/x"),
        (M_LABEL, "mqtt_actions/v1/devices/x/config"),
        (M_TOPIC, f"mqtt_actions/{M_TOPIC}"),
    }
    assert _leaks([], {"t": M_TEMPLATE}) == [(M_TEMPLATE, "t", M_TEMPLATE)]


async def _remove_owned(instance: Instance, device_id: str) -> None:
    """Delete one owned device of an instance, which publishes its clears and its tombstone."""
    (subentry,) = [item for item in instance.entry.subentries.values() if item.unique_id == device_id]
    instance.hass.config_entries.async_remove_subentry(instance.entry, subentry.subentry_id)
    await instance.manager.async_reconcile()


async def test_no_publication_carries_local_content_across_the_lifecycle(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """
    D-04, D-21: every integration publish of owner and follower stays free of markers through the whole lifecycle.

    Startup, approval refresh, state edges, test presses, re-triggers both ways, reconnect, resync, a prune after a
    missed deletion, a live tombstone and both hub removals; then the complete history of both gateways is scanned.
    """
    alpha, beta, lamp, mode, calls = await _seeded_pair(
        hass, hass_storage, make_instance, make_switch_subentry, make_select_subentry
    )
    lamp_id, mode_id = _device_id(lamp), _device_id(mode)
    await _approve_all(beta)
    await alpha.manager.presence.async_publish_heartbeat()
    await beta.manager.presence.async_publish_heartbeat()
    await _settle(alpha, beta)

    # State edges on both kinds; the owner runs its approved actions on the follower too
    for device_id, value in ((lamp_id, "OFF"), (lamp_id, "ON"), (mode_id, "bright"), (mode_id, "cozy")):
        await alpha.manager.async_send_state(device_id, value)
        await _settle(alpha, beta)
    assert len(calls["beta"]["test.owner_on"]) >= 1, "premise: the approved follower ran a state edge"

    # Test presses on both instances
    for instance in (alpha, beta):
        await instance.manager.async_press_test(lamp_id, SWITCH_ON_KEY)
        await instance.manager.async_press_test(lamp_id, SWITCH_OFF_KEY)
    await _settle(alpha, beta)

    # Re-triggers in both directions: requests and acknowledgements are transient publishes
    beta_result = await beta.manager.retrigger.async_retrigger(lamp_id)
    alpha_result = await alpha.manager.retrigger.async_retrigger(mode_id)
    await _settle(alpha, beta)
    assert {entry["status"] for entry in beta_result["instances"]} == {"executed"}
    assert {entry["status"] for entry in alpha_result["instances"]} == {"executed"}

    # Reconnect and resync republish everything both instances own
    alpha.gateway.reconnect()
    beta.gateway.reconnect()
    await _settle(alpha, beta)
    assert await alpha.manager.async_resync() is True
    assert await beta.manager.async_resync() is True
    await _settle(alpha, beta)

    # Prune: the follower misses the deletion of the Select and prunes it once the online owner lacks the document
    await beta.stop()
    await _remove_owned(alpha, mode_id)
    await _settle(alpha)
    await beta.start()
    await _settle(alpha, beta)
    freezer.tick(timedelta(seconds=PRUNE_GRACE_SECONDS + 1))
    async_fire_time_changed(alpha.hass)
    await _settle(alpha, beta)
    assert mode_id not in beta.manager.mirrors

    # Tombstone: the owner deletes the Switch while the follower listens
    await _remove_owned(alpha, lamp_id)
    await _settle(alpha, beta)
    assert lamp_id not in beta.manager.mirrors

    # Both hub removals with deletion
    for instance in (beta, alpha):
        await instance.stop()
        await async_remove_all_devices(
            instance.hass, instance.entry, gateway=instance.gateway, store_key=instance.store_key
        )
    await _settle(alpha, beta)

    history = [*alpha.gateway.published, *beta.gateway.published]
    assert any(retain for _topic, _payload, retain in history)
    assert any(not retain for _topic, _payload, retain in history)
    assert _leaks([alpha.gateway, beta.gateway], fake_broker.retained) == []
    # The authored local publish never reaches the gateway, whatever ran: no gateway topic is the authored one
    assert all(M_TOPIC not in topic for topic, _payload, _retain in history)


# --- the complete lifecycle table (Plan 11-10) -----------------------------------------------------------------------

# Every transition a local record can live through; the oracle below runs each one and scans what it published
REQUIRED_TRANSITIONS = (
    "startup_with_local_store",
    "local_edit",
    "local_remove",
    "owner_approval",
    "owner_content_change",
    "state_change",
    "native_test_button",
    "legacy_test_topic",
    "retrigger",
    "reconnect",
    "resync",
    "transient_prune",
    "reattach",
    "tombstone_after_prune",
    "adoption_failure",
    "adoption_success",
    "hub_removal_keep",
    "hub_removal_delete",
)

# The transitions that stay on this instance: they publish nothing, not even a clean message
SILENT_TRANSITIONS = frozenset(
    {
        "local_edit",
        "local_remove",
        "owner_approval",
        "native_test_button",
        "legacy_test_topic",
        "adoption_failure",
        "hub_removal_keep",
    }
)


@dataclass
class _Lifecycle:
    """The owner alpha of Lamp, Mode and Spare, the follower beta with the sentinel Store, and the shared harness."""

    alpha: Instance
    beta: Instance
    lamp: ConfigSubentryData
    mode: ConfigSubentryData
    spare: ConfigSubentryData
    broker: FakeBroker
    storage: dict[str, Any]
    freezer: FrozenDateTimeFactory
    clock: list[float]

    @property
    def lamp_id(self) -> str:
        return _device_id(self.lamp)

    @property
    def mode_id(self) -> str:
        return _device_id(self.mode)

    @property
    def spare_id(self) -> str:
        return _device_id(self.spare)

    def records_of(self, device_id: str) -> int:
        """Return how many local records beta keeps for a device, from its running manager."""
        counts = self.beta.manager.local_action_counts_by_device().get(device_id)
        return 0 if counts is None else counts.records

    def tick(self) -> None:
        """Advance the owner's manager clock past every per-call interval (resync, re-trigger)."""
        self.clock[0] += 60


async def _prune_on_beta(ctx: _Lifecycle, device_id: str) -> None:
    """
    Prune one mirror on beta while its owner is online: beta restarts, the retained document is gone, the grace ends.

    The broker loses the document silently (no live message), as after a lost retained store; the owner stays online.
    """
    await ctx.beta.stop()
    ctx.broker.retained.pop(config_topic(BASE, device_id))
    await ctx.beta.start()
    await _settle(ctx.alpha, ctx.beta)
    ctx.freezer.tick(timedelta(seconds=PRUNE_GRACE_SECONDS + 1))
    for instance in (ctx.alpha, ctx.beta):
        async_fire_time_changed(instance.hass)
    await _settle(ctx.alpha, ctx.beta)
    assert device_id not in ctx.beta.manager.mirrors, "premise: the online owner lacks the document, so beta prunes"


async def _step_startup(ctx: _Lifecycle) -> None:
    for device_id in (ctx.lamp_id, ctx.mode_id, ctx.spare_id):
        assert device_id in ctx.beta.manager.mirrors
    assert ctx.records_of(ctx.lamp_id) == 3, "premise: the sentinel Store loaded at the start"


async def _step_local_edit(ctx: _Lifecycle) -> None:
    lamp_on = local_trigger_identity(ctx.lamp_id, SUBENTRY_SWITCH, "ON")
    await ctx.beta.manager.async_set_local_action(lamp_on, MODE_REPLACEMENT, _local_actions())
    await ctx.beta.manager.async_set_local_action(
        local_trigger_identity(ctx.spare_id, SUBENTRY_SWITCH, "ON"), MODE_ADDITIVE, _local_actions()
    )
    assert ctx.records_of(ctx.spare_id) == 1


async def _step_local_remove(ctx: _Lifecycle) -> None:
    await ctx.beta.manager.async_remove_local_action(local_trigger_identity(ctx.lamp_id, SUBENTRY_SWITCH, "OFF"))
    assert ctx.records_of(ctx.lamp_id) == 2


async def _step_owner_approval(ctx: _Lifecycle) -> None:
    await _approve_all(ctx.beta)
    for device_id in (ctx.lamp_id, ctx.mode_id, ctx.spare_id):
        assert str(ctx.beta.manager.approval_state(device_id)) == "approved"


async def _step_owner_content_change(ctx: _Lifecycle) -> None:
    subentry = next(item for item in ctx.alpha.entry.subentries.values() if item.unique_id == ctx.lamp_id)
    ctx.alpha.hass.config_entries.async_update_subentry(
        ctx.alpha.entry, subentry, data={**subentry.data, CONF_ON_CHANGE_TO_ON: [*OWNER_ON, *OWNER_COZY]}
    )
    await ctx.alpha.manager.async_reconcile()
    await _settle(ctx.alpha, ctx.beta)
    assert str(ctx.beta.manager.approval_state(ctx.lamp_id)) == "pending", "premise: new owner actions need approval"
    assert ctx.records_of(ctx.lamp_id) == 2, "an owner content change keeps the local records"
    await _approve_all(ctx.beta)


async def _step_state_change(ctx: _Lifecycle) -> None:
    for device_id, value in ((ctx.lamp_id, "OFF"), (ctx.lamp_id, "ON"), (ctx.mode_id, "bright"), (ctx.mode_id, "cozy")):
        await ctx.alpha.manager.async_send_state(device_id, value)
        await _settle(ctx.alpha, ctx.beta)


async def _step_native_test_button(ctx: _Lifecycle) -> None:
    for instance in (ctx.alpha, ctx.beta):
        await instance.manager.async_press_test(ctx.lamp_id, SWITCH_ON_KEY)
        await instance.manager.async_press_test(ctx.lamp_id, SWITCH_OFF_KEY)


async def _step_legacy_test_topic(ctx: _Lifecycle) -> None:
    for payload in ("ON", "OFF"):
        ctx.beta.manager.test_message_handler(ctx.lamp_id)(IncomingMessage(payload=payload, retain=False))


async def _step_retrigger(ctx: _Lifecycle) -> None:
    ctx.tick()
    beta_result = await ctx.beta.manager.retrigger.async_retrigger(ctx.lamp_id, "ON")
    alpha_result = await ctx.alpha.manager.retrigger.async_retrigger(ctx.mode_id, "cozy")
    assert {entry["status"] for entry in beta_result["instances"]} == {"executed"}
    assert {entry["status"] for entry in alpha_result["instances"]} == {"executed"}


async def _step_reconnect(ctx: _Lifecycle) -> None:
    ctx.alpha.gateway.reconnect()
    ctx.beta.gateway.reconnect()


async def _step_resync(ctx: _Lifecycle) -> None:
    ctx.tick()
    assert await ctx.alpha.manager.async_resync() is True
    assert await ctx.beta.manager.async_resync() is True


async def _step_transient_prune(ctx: _Lifecycle) -> None:
    before = ctx.storage[ctx.beta.local_store_key]["data"]
    await _prune_on_beta(ctx, ctx.mode_id)
    assert ctx.storage[ctx.beta.local_store_key]["data"] == before, "a prune never changes the local Store"
    listed = {device.device_id: device for device in ctx.beta.manager.local_action_devices()}
    assert listed[ctx.mode_id].mirrored is False
    assert listed[ctx.mode_id].records == 3


async def _step_reattach(ctx: _Lifecycle) -> None:
    ctx.tick()
    assert await ctx.alpha.manager.async_resync() is True
    await _settle(ctx.alpha, ctx.beta)
    assert ctx.mode_id in ctx.beta.manager.mirrors, "premise: the owner's republish brings the mirror back"
    counts = ctx.beta.manager.local_action_counts_by_device()[ctx.mode_id]
    # cozy and bright attach again; the orphan option stays inactive
    assert (counts.records, counts.active, counts.inactive) == (3, 2, 1)


async def _step_tombstone_after_prune(ctx: _Lifecycle) -> None:
    await _prune_on_beta(ctx, ctx.lamp_id)
    assert ctx.records_of(ctx.lamp_id) == 2, "premise: the prune kept the records"
    await _remove_owned(ctx.alpha, ctx.lamp_id)
    await _settle(ctx.alpha, ctx.beta)
    assert ctx.records_of(ctx.lamp_id) == 0, "the tombstone after a prune still deletes the records"
    stored = ctx.storage[ctx.beta.local_store_key]["data"]["records"]
    assert [row for row in stored if row["device_id"] == ctx.lamp_id] == []


async def _step_adoption_failure(ctx: _Lifecycle) -> None:
    before = json.dumps(ctx.storage[ctx.beta.local_store_key]["data"], sort_keys=True)
    with pytest.raises(AdoptionError) as refused:
        await ctx.beta.manager.async_adopt_device(ctx.spare_id)
    assert refused.value.reason == "owner_not_offline"
    with (
        patch.object(ctx.beta.hass.config_entries, "async_add_subentry", side_effect=RuntimeError("boom")),
        pytest.raises(RuntimeError),
    ):
        await ctx.beta.manager.async_adopt_device(ctx.spare_id, force=True)
    await _settle(ctx.alpha, ctx.beta)
    assert ctx.spare_id in ctx.beta.manager.mirrors
    assert json.dumps(ctx.storage[ctx.beta.local_store_key]["data"], sort_keys=True) == before
    assert ctx.records_of(ctx.spare_id) == 1


async def _step_adoption_success(ctx: _Lifecycle) -> None:
    await ctx.alpha.stop()
    await _settle(ctx.alpha, ctx.beta)
    result = await ctx.beta.manager.async_adopt_device(ctx.spare_id, force=True)
    assert result.local_actions_discarded == 1
    assert ctx.spare_id in ctx.beta.manager.devices
    assert ctx.records_of(ctx.spare_id) == 0


async def _step_hub_removal_keep(ctx: _Lifecycle) -> None:
    alpha = ctx.alpha
    await async_remove_local_state(
        alpha.hass, alpha.entry, store_key=alpha.store_key, local_store_key=alpha.local_store_key
    )
    assert alpha.local_store_key not in ctx.storage


async def _step_hub_removal_delete(ctx: _Lifecycle) -> None:
    beta = ctx.beta
    await beta.stop()
    await async_remove_all_devices(
        beta.hass, beta.entry, gateway=beta.gateway, store_key=beta.store_key, local_store_key=beta.local_store_key
    )
    assert beta.local_store_key not in ctx.storage


LIFECYCLE: tuple[tuple[str, Callable[[_Lifecycle], Awaitable[None]]], ...] = (
    ("startup_with_local_store", _step_startup),
    ("local_edit", _step_local_edit),
    ("local_remove", _step_local_remove),
    ("owner_approval", _step_owner_approval),
    ("owner_content_change", _step_owner_content_change),
    ("state_change", _step_state_change),
    ("native_test_button", _step_native_test_button),
    ("legacy_test_topic", _step_legacy_test_topic),
    ("retrigger", _step_retrigger),
    ("reconnect", _step_reconnect),
    ("resync", _step_resync),
    ("transient_prune", _step_transient_prune),
    ("reattach", _step_reattach),
    ("tombstone_after_prune", _step_tombstone_after_prune),
    ("adoption_failure", _step_adoption_failure),
    ("adoption_success", _step_adoption_success),
    ("hub_removal_keep", _step_hub_removal_keep),
    ("hub_removal_delete", _step_hub_removal_delete),
)


def _step_leaks(entries: Iterable[tuple[str, str, bool]]) -> list[tuple[str, str]]:
    """Return (marker, topic) for every publication of one transition that carries a marker, in any letter case."""
    return [
        (marker, topic)
        for topic, payload, _retain in entries
        for marker in MARKERS
        if marker.lower() in topic.lower() or marker.lower() in payload.lower()
    ]


def _ack_words(gateways: Iterable[FakeGateway]) -> tuple[set[str], set[str]]:
    """Return every status and reason word of every re-trigger answer the gateways published."""
    statuses: set[str] = set()
    reasons: set[str] = set()
    for gateway in gateways:
        for topic, payload, _retain in gateway.published:
            if topic.endswith("/acks"):
                answer = json.loads(payload)
                statuses.add(answer["status"])
                if "reason" in answer:
                    reasons.add(answer["reason"])
    return statuses, reasons


async def test_every_lifecycle_transition_publishes_no_local_content(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    fake_broker: FakeBroker,
    make_instance: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
    freezer: FrozenDateTimeFactory,
) -> None:
    """
    D-04, D-05, D-21, T-11-32: each named transition of a local record is run, and none publishes local content.

    The table names every transition the plan requires; each step's publications of both gateways are scanned on their
    own, so a leak names its transition, and the complete history plus the retained state is scanned at the end. The
    re-trigger answers use only the existing status and reason words.
    """
    lamp, mode = _subentries(make_switch_subentry, make_select_subentry)
    spare = make_switch_subentry("Spare", on=OWNER_ON)
    alpha = await make_instance("alpha", hass=hass, subentries=[lamp, mode, spare])
    beta = await make_instance("beta")
    _register_services(alpha, beta)
    await _settle(alpha, beta)
    clock = [1000.0]
    ctx = _Lifecycle(alpha, beta, lamp, mode, spare, fake_broker, hass_storage, freezer, clock)
    alpha.manager.clock = lambda: clock[0]
    await _restart_seeded(hass_storage, _sentinel_records(_device_id(lamp), _device_id(mode)), alpha, beta)
    alpha.manager.clock = lambda: clock[0]
    for instance in (alpha, beta):
        await instance.manager.presence.async_publish_heartbeat()
    await _settle(alpha, beta)

    assert tuple(name for name, _step in LIFECYCLE) == REQUIRED_TRANSITIONS
    leaks: dict[str, list[tuple[str, str]]] = {}
    published: dict[str, int] = {}
    seen = dict.fromkeys((alpha.gateway, beta.gateway), 0)
    for name, step in LIFECYCLE:
        await step(ctx)
        await _settle(alpha, beta)
        entries = [entry for gateway, count in seen.items() for entry in gateway.published[count:]]
        seen = {gateway: len(gateway.published) for gateway in seen}
        published[name] = len(entries)
        leaks[name] = _step_leaks(entries)

    assert leaks == {name: [] for name in REQUIRED_TRANSITIONS}, f"publications per transition: {published}"
    # Local-only transitions publish nothing at all; every other one did publish, so its scan was not vacuous
    assert {name for name, count in published.items() if count == 0} == SILENT_TRANSITIONS, published
    history = [*alpha.gateway.published, *beta.gateway.published]
    assert any(retain for _topic, _payload, retain in history)
    assert any(not retain for _topic, _payload, retain in history)
    assert _leaks([alpha.gateway, beta.gateway], fake_broker.retained) == []
    assert all(M_TOPIC not in topic for topic, _payload, _retain in history)
    statuses, reasons = _ack_words([alpha.gateway, beta.gateway])
    assert statuses, "premise: the re-trigger answers were published"
    assert statuses <= frozenset(retrigger_module._STATUS_WORDS)
    assert reasons <= frozenset(retrigger_module._REASON_WORDS)
