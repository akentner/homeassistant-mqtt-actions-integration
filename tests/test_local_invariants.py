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
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.helpers.json import json_dumps
from pytest_homeassistant_custom_component.common import async_fire_time_changed, async_mock_service

from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_DISCOVERY_EXPORT,
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
from custom_components.mqtt_actions.manager import async_remove_all_devices
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY, spec_from_data
from custom_components.mqtt_actions.portability import subentry_payload
from custom_components.mqtt_actions.topics import config_topic, discovery_topic
from tests.fake_broker import FakeBroker, FakeGateway

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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
