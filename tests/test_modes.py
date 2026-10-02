"""Run, observe and disabled per owned device: select entity, gate and persistence (SYN-09, D-13, D-14, D-15)."""

import logging
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message, async_mock_service

from custom_components.mqtt_actions import topics
from custom_components.mqtt_actions.const import CONF_DEVICE_ID, DOMAIN, STORE_KEY
from custom_components.mqtt_actions.document import build_content, build_document

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

ON_ACTIONS = [{"action": "test.on"}]
OFF_ACTIONS = [{"action": "test.off"}]
MAX_RUNS = 3
WINDOW = 3600


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _device_id(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


async def _fire(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payload: str, *, retain: bool) -> None:
    """Deliver one state message to the device topic and let the run finish."""
    async_fire_mqtt_message(hass, topics.state_topic(entry.data["base_topic"], device_id), payload, retain=retain)
    await hass.async_block_till_done(wait_background_tasks=True)


def _mode_entity_id(hass: HomeAssistant, device_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{device_id}_mode")


async def _select_mode(hass: HomeAssistant, device_id: str, mode: str) -> None:
    """Set the mode through the select service, the way a user does."""
    entity_id = _mode_entity_id(hass, device_id)
    assert entity_id is not None
    await hass.services.async_call("select", "select_option", {"entity_id": entity_id, "option": mode}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


def _switch(make_switch_subentry: Callable, name: str = "Lamp", **kwargs: Any) -> ConfigSubentryData:
    """A switch with both actions and the test breaker limits (3 runs in 3600 seconds)."""
    return make_switch_subentry(
        name, on=ON_ACTIONS, off=OFF_ACTIONS, breaker_max_runs=MAX_RUNS, breaker_window=WINDOW, **kwargs
    )


async def test_owned_device_has_a_companion_device_under_its_subentry(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-13: the select sits on a companion device of the subentry; the discovery device is a different one."""
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)

    device_registry = dr.async_get(hass)
    companion = device_registry.async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)
    assert companion is not None
    (subentry,) = entry.subentries.values()
    assert companion.config_entry_id == entry.entry_id
    assert companion.config_subentry_id == subentry.subentry_id
    assert companion.manufacturer == "MQTT Actions"
    assert companion.model == "Switch device"
    assert companion.name == "Lamp"

    for mqtt_entry in hass.config_entries.async_entries("mqtt"):
        discovery = device_registry.async_get_device_by_identifier(
            ("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry.entry_id
        )
        assert discovery is None or discovery.id != companion.id

    entity_id = _mode_entity_id(hass, device_id)
    assert entity_id is not None
    registered = er.async_get(hass).async_get(entity_id)
    assert registered is not None
    assert registered.platform == DOMAIN
    assert registered.device_id == companion.id
    assert registered.entity_category is EntityCategory.CONFIG
    assert hass.states.get(entity_id).state == "run"
    assert hass.states.get(entity_id).attributes["options"] == ["run", "observe", "disabled"]


async def test_select_device_companion_model(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_select_subentry: Callable
) -> None:
    """D-13: a Select device gets its own model text on the companion device."""
    sub = make_select_subentry("Mode", [("a", "Alpha", ON_ACTIONS), ("b", "Bravo", OFF_ACTIONS)])
    entry = await _setup(hass, make_hub_entry([sub]))
    companion = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, _device_id(sub)), entry.entry_id)
    assert companion is not None
    assert companion.model == "Select device"


async def test_observe_logs_and_runs_nothing_but_tracks_the_baseline(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-14: observe tracks the baseline, logs the suppressed run and never counts toward the breaker."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)
    device = entry.runtime_data.devices[device_id]

    await _select_mode(hass, device_id, "observe")
    caplog.set_level(logging.INFO)
    await _fire(hass, entry, device_id, "ON", retain=False)

    assert on_calls == []
    assert device.tracker.last_acted == "ON"
    lines = [record.getMessage() for record in caplog.records if "observe" in record.getMessage().lower()]
    assert len(lines) == 1
    assert "'Lamp'" in lines[0]
    assert "'onChangeToOn'" in lines[0]

    # More edges than the breaker allows: none of them is a run, so nothing trips
    for payload in ["OFF", "ON", "OFF", "ON", "OFF", "ON"][: MAX_RUNS + 3]:
        await _fire(hass, entry, device_id, payload, retain=False)
    assert on_calls == []
    assert off_calls == []
    assert device.breaker.tripped is False

    await _select_mode(hass, device_id, "run")
    await _fire(hass, entry, device_id, "OFF", retain=False)
    assert len(off_calls) == 1
    assert device.breaker.tripped is False


async def test_mode_change_never_publishes(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-21: choosing a mode is local; nothing goes to the broker and the document stays as it was."""
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)
    manager = entry.runtime_data
    revision = manager.revision(device_id)
    mqtt_mock.async_publish.reset_mock()

    for mode in ("observe", "disabled", "run"):
        await _select_mode(hass, device_id, mode)

    assert mqtt_mock.async_publish.call_args_list == []
    assert manager.revision(device_id) == revision


async def test_modes_are_not_part_of_the_document(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-21: the content, the document and the hash hold no mode, and a mode change leaves the hash alone."""
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)
    spec = entry.runtime_data.devices[device_id].spec

    def _snapshot() -> tuple[dict[str, Any], dict[str, Any]]:
        return build_content(spec), build_document(spec, owner="owner", owner_name="Owner", rev=1)

    content_before, document_before = _snapshot()
    await _select_mode(hass, device_id, "observe")
    content_after, document_after = _snapshot()

    assert content_before == content_after
    assert document_before["hash"] == document_after["hash"]
    for text in (str(content_after), str(document_after)):
        assert "observe" not in text
        assert "disabled" not in text
    assert not {"mode", "device_mode", "instance_mode"} & set(document_after)


async def test_mode_persists_across_restart(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-14: the mode is saved in the Store and still gates after the entry was unloaded and set up again."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)

    await _select_mode(hass, device_id, "observe")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass_storage[STORE_KEY]["data"]["device_modes"] == {device_id: "observe"}

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.LOADED
    entity_id = _mode_entity_id(hass, device_id)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "observe"

    await _fire(hass, entry, device_id, "ON", retain=False)
    assert on_calls == []


def test_is_mode_and_most_restrictive() -> None:
    """The three words are the only modes; the most restrictive one wins and no argument means run."""
    from custom_components.mqtt_actions.modes import is_mode, most_restrictive

    words = ("run", "observe", "disabled")
    assert [is_mode(word) for word in words] == [True, True, True]
    for value in (True, False, 0, 1, None, "", "Run", "paused", b"run", ["run"]):
        assert is_mode(value) is False

    assert most_restrictive() == "run"
    rank = {word: index for index, word in enumerate(words)}
    for first in words:
        for second in words:
            assert most_restrictive(first, second) == max(first, second, key=rank.__getitem__)
    assert most_restrictive("run", "observe", "disabled", "run") == "disabled"
    assert most_restrictive("observe") == "observe"


async def _press(hass: HomeAssistant, entry: MockConfigEntry, device_id: str, payload: str) -> None:
    """Deliver one message to the test topic of a device the way the broker forwards a button press."""
    async_fire_mqtt_message(hass, topics.test_topic(entry.data["base_topic"], device_id), payload, retain=False)
    await hass.async_block_till_done(wait_background_tasks=True)


def _instance_mode_entity_id(hass: HomeAssistant, entry: MockConfigEntry) -> str | None:
    return er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_instance_mode")


async def _select_instance_mode(hass: HomeAssistant, entry: MockConfigEntry, mode: str) -> None:
    entity_id = _instance_mode_entity_id(hass, entry)
    assert entity_id is not None
    await hass.services.async_call("select", "select_option", {"entity_id": entity_id, "option": mode}, blocking=True)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_disabled_ignores_state_and_leaves_the_baseline(
    hass: HomeAssistant,
    mqtt_mock: Any,
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-14: a disabled device does not process the message at all, so the baseline stays where it was."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)
    device = entry.runtime_data.devices[device_id]
    await _fire(hass, entry, device_id, "ON", retain=False)
    assert (len(on_calls), device.tracker.last_acted) == (1, "ON")

    await _select_mode(hass, device_id, "disabled")
    caplog.clear()
    caplog.set_level(logging.DEBUG, logger="custom_components.mqtt_actions")
    await _fire(hass, entry, device_id, "OFF", retain=False)
    await _fire(hass, entry, device_id, "no such payload", retain=False)

    assert off_calls == []
    assert len(on_calls) == 1
    assert device.tracker.last_acted == "ON"
    assert [record for record in caplog.records if "payload" in record.getMessage().lower()] == []


async def test_test_topic_respects_the_mode(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-19: a press on the test topic runs in run mode only, so the mode cannot be bypassed through a button."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)

    await _press(hass, entry, device_id, "ON")
    assert len(on_calls) == 1

    for mode in ("observe", "disabled"):
        await _select_mode(hass, device_id, mode)
        await _press(hass, entry, device_id, "ON")
        assert len(on_calls) == 1

    await _select_mode(hass, device_id, "run")
    await _press(hass, entry, device_id, "ON")
    assert len(on_calls) == 2


@pytest.mark.parametrize(
    ("instance_mode", "device_mode", "expected"),
    [
        ("run", "run", "run"),
        ("run", "observe", "observe"),
        ("run", "disabled", "disabled"),
        ("observe", "run", "observe"),
        ("observe", "observe", "observe"),
        ("observe", "disabled", "disabled"),
        ("disabled", "run", "disabled"),
        ("disabled", "observe", "disabled"),
        ("disabled", "disabled", "disabled"),
    ],
)
async def test_effective_mode_is_the_most_restrictive(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    instance_mode: str,
    device_mode: str,
    expected: str,
) -> None:
    """Post-research: the hub mode and the device mode combine to the more restrictive of the two."""
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)
    manager = entry.runtime_data

    await manager.async_set_instance_mode(instance_mode)
    await manager.async_set_device_mode(device_id, device_mode)

    assert manager.effective_mode(device_id) == expected
    assert manager.instance_mode == instance_mode
    assert manager.device_mode(device_id) == device_mode


async def test_set_mode_rejects_bad_input(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A word that is no mode and an id that is neither owned nor mirrored are refused and change nothing."""
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = _device_id(sub)
    manager = entry.runtime_data

    with pytest.raises(ValueError, match="mode"):
        await manager.async_set_device_mode(device_id, "paused")
    with pytest.raises(ValueError, match="mode"):
        await manager.async_set_instance_mode("paused")
    with pytest.raises(ValueError, match="device"):
        await manager.async_set_device_mode("no-such-device", "observe")

    assert manager.device_mode(device_id) == "run"
    assert manager.instance_mode == "run"


async def test_hub_mode_select_sets_the_whole_instance(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The hub select sets the mode of the instance; leaving disabled re-baselines what the hub had disabled."""
    on_calls = async_mock_service(hass, "test", "on")
    off_calls = async_mock_service(hass, "test", "off")
    lamp = _switch(make_switch_subentry, "Lamp")
    fan = _switch(make_switch_subentry, "Fan")
    entry = await _setup(hass, make_hub_entry([lamp, fan]))
    manager = entry.runtime_data
    lamp_id, fan_id = _device_id(lamp), _device_id(fan)

    hub = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    entity_id = _instance_mode_entity_id(hass, entry)
    assert hub is not None
    assert entity_id is not None
    registered = er.async_get(hass).async_get(entity_id)
    assert registered is not None
    assert registered.device_id == hub.id
    assert registered.entity_category is EntityCategory.CONFIG
    assert hass.states.get(entity_id).state == "run"
    assert hass.states.get(entity_id).attributes["options"] == ["run", "observe", "disabled"]

    # The fan is disabled on its own and has a baseline
    await _fire(hass, entry, fan_id, "ON", retain=False)
    await _select_mode(hass, fan_id, "disabled")
    assert len(on_calls) == 1

    await _select_instance_mode(hass, entry, "observe")
    assert hass.states.get(entity_id).state == "observe"
    await _fire(hass, entry, lamp_id, "ON", retain=False)
    assert len(on_calls) == 1
    assert manager.devices[lamp_id].tracker.last_acted == "ON"

    await _select_instance_mode(hass, entry, "disabled")
    await _fire(hass, entry, lamp_id, "OFF", retain=False)
    assert off_calls == []
    assert manager.devices[lamp_id].tracker.last_acted == "ON"

    await _select_instance_mode(hass, entry, "run")
    # The lamp left disabled: no baseline, no startup window. The fan is still disabled on its own and was not touched.
    assert manager.devices[lamp_id].tracker.last_acted is None
    assert manager.devices[lamp_id].tracker.startup_pending is False
    assert manager.devices[fan_id].tracker.last_acted == "ON"
    await _fire(hass, entry, fan_id, "OFF", retain=False)
    assert off_calls == []
    assert manager.devices[fan_id].tracker.last_acted == "ON"
    await _fire(hass, entry, lamp_id, "OFF", retain=False)
    assert len(off_calls) == 1


async def test_hub_mode_persists_across_restart(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-14: the instance mode is saved under instance_mode and restored by the next start."""
    on_calls = async_mock_service(hass, "test", "on")
    sub = _switch(make_switch_subentry)
    entry = await _setup(hass, make_hub_entry([sub]))

    await _select_instance_mode(hass, entry, "observe")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass_storage[STORE_KEY]["data"]["instance_mode"] == "observe"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    entity_id = _instance_mode_entity_id(hass, entry)
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "observe"
    await _fire(hass, entry, _device_id(sub), "ON", retain=False)
    assert on_calls == []
