"""What the core-prefix discovery topic of a device holds: the pure classifier and the sync verdicts (D-02, D-03)."""

import asyncio
import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import pytest
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_fire_time_changed

from custom_components.mqtt_actions import sync as sync_module
from custom_components.mqtt_actions.const import CONF_DEVICE_ID, MAX_DOCUMENT_BYTES, SUBENTRY_SELECT
from custom_components.mqtt_actions.discovery import (
    DiscoveryContent,
    build_discovery,
    build_export,
    classify_discovery,
)
from custom_components.mqtt_actions.mqtt_gateway import MqttGateway
from custom_components.mqtt_actions.topics import discovery_topic, discovery_wildcard
from tests.documents import FOREIGN_OWNER, make_spec
from tests.test_native_start import _legacy_mirror, _manager, _restart, _seed_native
from tests.test_takeover import MIGRATE_PAYLOAD, PREFIX

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.mqtt_actions.model import DeviceSpec

BASE = "mqtt_actions"
INSTANCE = "instance-local"
SPEC = make_spec(name="Lamp")
SELECT_SPEC = make_spec(SUBENTRY_SELECT, name="Mode")


def _legacy(spec: DeviceSpec = SPEC, *, retired: tuple[str, ...] = ()) -> dict[str, Any]:
    return build_discovery(spec=spec, base_topic=BASE, instance_id=INSTANCE, sw_version="1.0.1", retired=retired)


def _export(spec: DeviceSpec = SPEC) -> dict[str, Any]:
    return build_export(spec=spec, base_topic=BASE, instance_id=INSTANCE, sw_version="1.0.1")


def _changed(payload: dict[str, Any], change: Callable[[dict[str, Any]], None]) -> str:
    """Return the payload after a change, as wire text; the payload passed in is a fresh copy."""
    change(payload)
    return json.dumps(payload)


def _set_button_unique_id(payload: dict[str, Any]) -> None:
    key = next(key for key in payload["components"] if key.startswith("test_"))
    payload["components"][key]["unique_id"] = "another-device_test_on"


def _abbreviate(payload: dict[str, Any]) -> None:
    payload["dev"] = payload.pop("device")
    payload["cmps"] = payload.pop("components")


def _drop_buttons(payload: dict[str, Any]) -> None:
    payload["components"] = {"switch": payload["components"]["switch"]}


def _oversized() -> str:
    payload = _legacy()
    payload["padding"] = "x" * MAX_DOCUMENT_BYTES
    return json.dumps(payload)


@pytest.mark.parametrize(
    ("spec", "payload", "expected"),
    [
        pytest.param(SPEC, json.dumps(_legacy()), DiscoveryContent.LEGACY, id="legacy_switch"),
        pytest.param(SELECT_SPEC, json.dumps(_legacy(SELECT_SPEC)), DiscoveryContent.LEGACY, id="legacy_select"),
        pytest.param(
            SPEC, json.dumps(_legacy(retired=("test_old",))), DiscoveryContent.LEGACY, id="legacy_with_tombstones"
        ),
        pytest.param(
            SELECT_SPEC,
            json.dumps(_legacy(SELECT_SPEC, retired=("test_c",))),
            DiscoveryContent.LEGACY,
            id="legacy_select_with_tombstones",
        ),
        pytest.param(SPEC, json.dumps(_export()), DiscoveryContent.EXPORT, id="export_switch"),
        pytest.param(SELECT_SPEC, json.dumps(_export(SELECT_SPEC)), DiscoveryContent.EXPORT, id="export_select"),
        pytest.param(SPEC, "", DiscoveryContent.EMPTY, id="empty"),
        pytest.param(SPEC, MIGRATE_PAYLOAD, None, id="migrate_payload"),
        pytest.param(SPEC, "{not json", DiscoveryContent.UNKNOWN, id="invalid_json"),
        pytest.param(SPEC, json.dumps([_legacy()]), DiscoveryContent.UNKNOWN, id="json_list"),
        pytest.param(SPEC, _oversized(), DiscoveryContent.UNKNOWN, id="oversized"),
        pytest.param(
            SPEC,
            _changed(_legacy(), lambda p: p["device"].update(identifiers=["mqtt_actions_another-device"])),
            DiscoveryContent.UNKNOWN,
            id="foreign_identifier",
        ),
        pytest.param(SPEC, _changed(_legacy(), _abbreviate), DiscoveryContent.UNKNOWN, id="abbreviated_keys"),
        pytest.param(
            SPEC,
            _changed(_legacy(), lambda p: p["components"].update(select=dict(p["components"]["switch"]))),
            DiscoveryContent.UNKNOWN,
            id="two_main_components",
        ),
        pytest.param(
            SPEC,
            _changed(_legacy(), lambda p: p["components"].update(light={"platform": "button"})),
            DiscoveryContent.UNKNOWN,
            id="non_button_extra_key",
        ),
        pytest.param(
            SPEC, _changed(_legacy(), _set_button_unique_id), DiscoveryContent.UNKNOWN, id="button_foreign_unique_id"
        ),
        pytest.param(
            SPEC,
            _changed(_legacy(), lambda p: p["components"]["switch"].update(unique_id="another-device")),
            DiscoveryContent.UNKNOWN,
            id="main_component_foreign_unique_id",
        ),
        pytest.param(SPEC, _changed(_legacy(), _drop_buttons), DiscoveryContent.UNKNOWN, id="main_without_buttons"),
    ],
)
def test_classify_discovery(spec: DeviceSpec, payload: str, expected: DiscoveryContent | None) -> None:
    """T-09.1-03: only the exact legacy and export shapes of this device id count; everything else keeps the rows."""
    assert classify_discovery(spec.device_id, payload) is expected


# --- the sync verdicts ---------------------------------------------------------------------------------------------


async def _owned(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> tuple[MockConfigEntry, DeviceSpec]:
    """Set up a native owner of one switch; native, so an empty discovery payload does not start the legacy heal."""
    _seed_native(hass_storage, pending=[])
    sub = make_switch_subentry("Lamp")
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry, make_spec(device_id=sub["data"][CONF_DEVICE_ID], name="Lamp")


async def _mirrored(hass: HomeAssistant, make_hub_entry: Callable) -> tuple[MockConfigEntry, DeviceSpec]:
    """Set up a follower with a mirror of a foreign device."""
    spec = make_spec(name="Foreign lamp")
    entry, _topic = await _legacy_mirror(hass, make_hub_entry, spec)
    return entry, spec


async def _held(
    held: str,
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> tuple[MockConfigEntry, DeviceSpec]:
    if held == "owned":
        return await _owned(hass, hass_storage, make_hub_entry, make_switch_subentry)
    return await _mirrored(hass, make_hub_entry)


async def _send(hass: HomeAssistant, device_id: str, payload: str) -> None:
    async_fire_mqtt_message(hass, discovery_topic(PREFIX, device_id), payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


def _foreign_legacy(spec: DeviceSpec) -> str:
    return json.dumps(build_discovery(spec=spec, base_topic=BASE, instance_id=FOREIGN_OWNER, sw_version="1.2.3"))


@pytest.mark.parametrize("held", ["owned", "mirrored"])
async def test_the_sync_records_the_latest_verdict_for_a_held_id_and_ignores_the_migrate_payload(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    held: str,
) -> None:
    """The latest message wins; the live migrate payload leaves the retained content as it was."""
    entry, spec = await _held(held, hass, hass_storage, make_hub_entry, make_switch_subentry)
    sync = _manager(entry).sync

    await _send(hass, spec.device_id, _foreign_legacy(spec))
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.LEGACY
    await _send(hass, spec.device_id, MIGRATE_PAYLOAD)
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.LEGACY
    await _send(hass, spec.device_id, "")
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.EMPTY
    await _send(hass, spec.device_id, json.dumps(_export(spec)))
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.EXPORT


async def test_the_sync_records_nothing_for_an_id_it_does_not_hold_and_reads_unknown_for_an_unseen_id(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-09.1-04: only held ids are recorded, and an id without any message seen is UNKNOWN."""
    entry, spec = await _owned(hass, hass_storage, make_hub_entry, make_switch_subentry)
    sync = _manager(entry).sync
    stranger = make_spec(name="Stranger")

    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    await _send(hass, stranger.device_id, _foreign_legacy(stranger))

    assert sync.discovery_content(stranger.device_id) is DiscoveryContent.UNKNOWN
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN


async def test_the_sync_forgets_every_verdict_on_a_reconnect(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """After a reconnect the broker replays what is retained; until then nothing is known about the topic."""
    entry, spec = await _owned(hass, hass_storage, make_hub_entry, make_switch_subentry)
    sync = _manager(entry).sync
    await _send(hass, spec.device_id, _foreign_legacy(spec))
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.LEGACY

    sync.on_reconnect()

    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN


# --- the settle: when an unseen topic counts as empty (D-03) --------------------------------------------------------

GRACE = 2.0


class _Settle:
    """Capture the settle watch of the sync and drive it and the manager clock by hand."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.watches: list[tuple[str, int]] = []
        self._on_done: list[Callable[[], None]] = []
        self.now = 100.0
        watches, on_dones = self.watches, self._on_done

        def _watch(_gateway: MqttGateway, topic: str, qos: int, on_done: Callable[[], None]) -> Callable[[], None]:
            watches.append((topic, qos))
            on_dones.append(on_done)
            return lambda: None

        monkeypatch.setattr(sync_module, "DISCOVERY_SETTLE_GRACE_SECONDS", GRACE)
        monkeypatch.setattr(MqttGateway, "async_on_subscribed", _watch)

    def use_clock_of(self, entry: MockConfigEntry) -> None:
        _manager(entry).clock = lambda: self.now

    def settle(self) -> None:
        """Report the most recent watch as done, as core does after the SUBACK."""
        self._on_done[-1]()


@pytest.fixture
def settle(monkeypatch: pytest.MonkeyPatch) -> _Settle:
    return _Settle(monkeypatch)


async def test_an_unseen_owned_id_is_empty_only_once_the_grace_after_the_settle_has_passed(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    settle: _Settle,
) -> None:
    """D-03: UNKNOWN before the settle and inside the grace, EMPTY from the end of the grace on."""
    entry, spec = await _owned(hass, hass_storage, make_hub_entry, make_switch_subentry)
    settle.use_clock_of(entry)
    sync = _manager(entry).sync
    assert settle.watches == [(discovery_wildcard(PREFIX), 1)]

    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    settle.now += 60
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    settle.settle()
    settle.now += 1.9
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    settle.now += 0.1
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.EMPTY


async def test_a_recorded_verdict_wins_over_the_settle(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    settle: _Settle,
) -> None:
    """D-02: a topic seen to hold the legacy payload stays LEGACY after the settle and the grace."""
    entry, spec = await _owned(hass, hass_storage, make_hub_entry, make_switch_subentry)
    settle.use_clock_of(entry)
    await _send(hass, spec.device_id, _foreign_legacy(spec))
    settle.settle()
    settle.now += 10 * GRACE

    assert _manager(entry).sync.discovery_content(spec.device_id) is DiscoveryContent.LEGACY


async def test_a_mirror_created_after_the_subscription_stays_unknown_until_a_message_for_it_arrives(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, settle: _Settle
) -> None:
    """D-03: the retained message of a mirror created later was dropped, so its unseen topic is never empty."""
    entry, spec = await _mirrored(hass, make_hub_entry)
    settle.use_clock_of(entry)
    sync = _manager(entry).sync
    settle.settle()
    settle.now += 10 * GRACE

    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    await _send(hass, spec.device_id, "")
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.EMPTY


async def test_a_mirror_held_when_the_subscription_was_made_is_in_scope(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, settle: _Settle
) -> None:
    """D-03: after a restart the mirror is held at subscribe time, so its unseen topic is empty after the grace."""
    entry, spec = await _mirrored(hass, make_hub_entry)
    await _restart(hass, entry)
    assert spec.device_id in _manager(entry).mirrors
    settle.use_clock_of(entry)
    settle.settle()
    settle.now += GRACE

    assert _manager(entry).sync.discovery_content(spec.device_id) is DiscoveryContent.EMPTY


async def test_a_reconnect_makes_every_unseen_id_unknown_until_the_next_settle(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    settle: _Settle,
) -> None:
    """D-03: the reconnect resets the settle; the resubscribe settles again and the grace starts over."""
    entry, spec = await _owned(hass, hass_storage, make_hub_entry, make_switch_subentry)
    settle.use_clock_of(entry)
    sync = _manager(entry).sync
    settle.settle()
    settle.now += GRACE
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.EMPTY

    sync.on_reconnect()

    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    settle.now += 10 * GRACE
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    settle.settle()
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.UNKNOWN
    settle.now += GRACE
    assert sync.discovery_content(spec.device_id) is DiscoveryContent.EMPTY


# --- the gateway wrapper over core's subscribe-done signal -----------------------------------------------------------

WATCHED = "mqtt_actions_test/settle/+/config"


async def _subscribe_and_let_the_debouncer_run(
    hass: HomeAssistant, gateway: MqttGateway, freezer: Any, mqtt_client_mock: Any
) -> None:
    """Subscribe, move the clock past the subscribe cooldown and wait until core subscribed the topic and signalled."""
    await gateway.async_subscribe(WATCHED, lambda _msg: None, 1)
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    # Core subscribes the queued topics one by one, each after its acknowledgement, in a task hass does not wait for
    for _turn in range(2000):
        if any(call.args[0] == WATCHED for call in mqtt_client_mock.subscribe.call_args_list):
            break
        await asyncio.sleep(0)
    assert any(call.args[0] == WATCHED for call in mqtt_client_mock.subscribe.call_args_list)
    # The acknowledgement, the dispatcher task and core's call_soon of the signal
    for _turn in range(50):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


async def test_the_gateway_calls_back_once_the_subscription_is_done(
    hass: HomeAssistant, mqtt_mock: Any, mqtt_client_mock: Any, freezer: Any
) -> None:
    """The wrapper forwards core's signal for the topic and qos after the subscribe debouncer has run."""
    gateway = MqttGateway(hass)
    calls: list[None] = []
    gateway.async_on_subscribed(WATCHED, 1, lambda: calls.append(None))

    await _subscribe_and_let_the_debouncer_run(hass, gateway, freezer, mqtt_client_mock)

    assert len(calls) == 1


async def test_the_gateway_never_calls_back_for_another_qos(
    hass: HomeAssistant, mqtt_mock: Any, mqtt_client_mock: Any, freezer: Any
) -> None:
    """A watch for qos 2 on a qos 1 subscription never settles, so EMPTY is never inferred."""
    gateway = MqttGateway(hass)
    calls: list[None] = []
    gateway.async_on_subscribed(WATCHED, 2, lambda: calls.append(None))

    await _subscribe_and_let_the_debouncer_run(hass, gateway, freezer, mqtt_client_mock)

    assert calls == []


async def test_the_gateway_does_not_call_back_after_the_watch_was_stopped(
    hass: HomeAssistant, mqtt_mock: Any, mqtt_client_mock: Any, freezer: Any
) -> None:
    """The stop callback ends the watch before the debouncer runs."""
    gateway = MqttGateway(hass)
    calls: list[None] = []
    stop = gateway.async_on_subscribed(WATCHED, 1, lambda: calls.append(None))
    stop()

    await _subscribe_and_let_the_debouncer_run(hass, gateway, freezer, mqtt_client_mock)

    assert calls == []


async def test_the_gateway_calls_back_when_another_subscriber_raised_the_qos_of_the_filter(
    hass: HomeAssistant, mqtt_mock: Any, mqtt_client_mock: Any, freezer: Any
) -> None:
    """
    WR-01 (review): core signals the highest qos of all subscribers to a filter, so a qos 1 watch settles at qos 2.

    Core MQTT discovery subscribes the device wildcard at the user's discovery qos; with 2 the filter is subscribed at
    2, and a watch that only matched qos 1 would never settle, so an unseen topic would never read as empty.
    """
    gateway = MqttGateway(hass)
    calls: list[None] = []
    gateway.async_on_subscribed(WATCHED, 1, lambda: calls.append(None))
    await gateway.async_subscribe(WATCHED, lambda _msg: None, 2)

    await _subscribe_and_let_the_debouncer_run(hass, gateway, freezer, mqtt_client_mock)

    assert any(call.args == (WATCHED, 2) for call in mqtt_client_mock.subscribe.call_args_list)
    assert len(calls) == 1
