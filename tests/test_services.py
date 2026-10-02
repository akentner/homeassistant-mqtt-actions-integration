"""The service layer: registration at setup, admin-only access, device resolution and the resync service (D-12)."""

import inspect
import json
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service import async_get_all_descriptions
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

import custom_components.mqtt_actions as integration
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    DOMAIN,
    EXPORT_DIRECTORY,
    RESYNC_MIN_INTERVAL_SECONDS,
    SERVICE_EXPORT_DEVICES,
    SERVICE_IMPORT_DEVICES,
    SERVICE_RESYNC,
    SUBENTRY_SELECT,
)
from custom_components.mqtt_actions.document import build_content, content_hash
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic
from tests.documents import document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.auth.models import User
    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on"}]


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Give every test of this module a temporary configuration directory, so export files never leave the test."""
    return hass_tmp_config_dir


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def _call(
    hass: HomeAssistant,
    service: str,
    data: dict[str, Any] | None = None,
    *,
    user: User | None = None,
    response: bool = False,
) -> Any:
    """Call a service of the domain the way the UI does: blocking, optionally as a user, optionally with a response."""
    context = Context(user_id=user.id) if user is not None else None
    result = await hass.services.async_call(
        DOMAIN, service, data or {}, blocking=True, context=context, return_response=response
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    return result


def _published_topics(mqtt_mock: Any) -> list[str]:
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list]


def _companion_id(hass: HomeAssistant, entry: MockConfigEntry, device_id: str) -> str:
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)
    assert device is not None
    return device.id


async def test_services_are_registered_at_setup_not_at_entry_setup(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-12: the services exist after the component setup, survive an unload, and the entry setup registers none."""
    assert not hass.services.has_service(DOMAIN, SERVICE_RESYNC)

    entry = await _setup(hass, make_hub_entry())
    assert hass.services.has_service(DOMAIN, SERVICE_RESYNC)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.services.has_service(DOMAIN, SERVICE_RESYNC)

    entry_setup = inspect.getsource(integration.async_setup_entry)
    assert "async_register" not in entry_setup
    assert "async_setup_services" not in entry_setup
    assert "async_setup_services" in inspect.getsource(integration.async_setup)


async def test_resync_service_republishes_in_the_phase_3_order(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-12: the service publishes document, discovery and `online`, never a clear, and answers resynced."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    device_id = sub["data"][CONF_DEVICE_ID]
    mqtt_mock.async_publish.reset_mock()

    result = await _call(hass, SERVICE_RESYNC, response=True)

    assert result == {"resynced": True}
    calls = mqtt_mock.async_publish.call_args_list
    topics = _published_topics(mqtt_mock)
    document = config_topic(BASE, device_id)
    discovery = discovery_topic("homeassistant", device_id)
    availability = availability_topic(BASE, entry.data[CONF_INSTANCE_ID])
    assert topics.index(document) < topics.index(discovery) < topics.index(availability)
    assert calls[topics.index(availability)].args[1] == "online"
    assert [call.args[0] for call in calls if call.args[1] in {"", b""}] == []


async def test_resync_service_is_admin_only(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    hass_read_only_user: User,
    hass_admin_user: User,
) -> None:
    """T-04-31: a read-only user is refused and nothing is published; the administrator succeeds."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    entry.runtime_data.clock = lambda: 1000.0
    mqtt_mock.async_publish.reset_mock()

    with pytest.raises(Unauthorized):
        await _call(hass, SERVICE_RESYNC, user=hass_read_only_user)
    assert _published_topics(mqtt_mock) == []

    assert await _call(hass, SERVICE_RESYNC, user=hass_admin_user, response=True) == {"resynced": True}
    assert _published_topics(mqtt_mock) != []


async def test_resync_service_throttled_raises_a_translated_error(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-35: a second call inside the cooldown raises resync_throttled and publishes nothing."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    now = [1000.0]
    entry.runtime_data.clock = lambda: now[0]

    await _call(hass, SERVICE_RESYNC)
    now[0] += RESYNC_MIN_INTERVAL_SECONDS - 1
    mqtt_mock.async_publish.reset_mock()

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, SERVICE_RESYNC)
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "resync_throttled"
    assert _published_topics(mqtt_mock) == []

    now[0] += 2
    assert await _call(hass, SERVICE_RESYNC, response=True) == {"resynced": True}


async def test_service_without_a_loaded_entry_raises_not_loaded(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """With the entry unloaded the handler finds no manager and says so in a translated error."""
    entry = await _setup(hass, make_hub_entry())
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, SERVICE_RESYNC)
    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "not_loaded"


async def test_resolve_device_maps_the_companion_device_to_the_uuid(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """The registry id of a companion device resolves to its uuid; hub, unknown and foreign devices are refused."""
    # Imported here so that a missing module fails this test only and not the collection of the whole file
    from custom_components.mqtt_actions.services import resolve_device

    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    entry = await _setup(hass, make_hub_entry([sub]))
    manager: Manager = entry.runtime_data
    owned_id = sub["data"][CONF_DEVICE_ID]
    foreign = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    async_fire_mqtt_message(hass, config_topic(BASE, foreign.device_id), document_payload(foreign), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert foreign.device_id in manager.mirrors

    assert resolve_device(hass, manager, _companion_id(hass, entry, owned_id)) == owned_id
    assert resolve_device(hass, manager, _companion_id(hass, entry, owned_id), owned_only=True) == owned_id
    assert resolve_device(hass, manager, _companion_id(hass, entry, foreign.device_id)) == foreign.device_id

    # A mirror is not an owned device
    with pytest.raises(ServiceValidationError):
        resolve_device(hass, manager, _companion_id(hass, entry, foreign.device_id), owned_only=True)

    # The hub device carries the entry id as its identifier value and is never a device of the manager
    hub = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert hub is not None
    with pytest.raises(ServiceValidationError) as hub_error:
        resolve_device(hass, manager, hub.id)
    assert hub_error.value.translation_key == "not_a_device"

    with pytest.raises(ServiceValidationError) as unknown_error:
        resolve_device(hass, manager, "no-such-registry-id")
    assert unknown_error.value.translation_key == "unknown_device"

    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    stranger = dr.async_get(hass).async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("other", "thing")}, name="Thing"
    )
    with pytest.raises(ServiceValidationError) as stranger_error:
        resolve_device(hass, manager, stranger.id)
    assert stranger_error.value.translation_key == "not_a_device"


def _export_dir(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(EXPORT_DIRECTORY))


async def test_export_returns_all_owned_devices_as_a_response(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """D-11: without fields the response holds the content of every owned device and no file name."""
    lamp = make_switch_subentry("Lamp", on=ON_ACTIONS, run_on_startup=True)
    scene = make_select_subentry("Scene", [("a", "A", ON_ACTIONS), ("b", "B", [])])
    await _setup(hass, make_hub_entry([lamp, scene]))

    result = await _call(hass, SERVICE_EXPORT_DEVICES, response=True)

    assert result["file"] is None
    document = result["export"]
    assert (document["format"], document["export_version"]) == ("mqtt_actions_export", 1)
    assert {item["name"] for item in document["devices"]} == {"Lamp", "Scene"}
    for item in document["devices"]:
        assert {"device_id", "owner", "rev", "hash"}.isdisjoint(item)
    assert not _export_dir(hass).exists()


async def test_export_selection_by_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """With the registry id of one companion device only that device is exported; two ids export two."""
    subs = [make_switch_subentry(name, on=ON_ACTIONS) for name in ("One", "Two", "Three")]
    entry = await _setup(hass, make_hub_entry(subs))
    ids = [_companion_id(hass, entry, sub["data"][CONF_DEVICE_ID]) for sub in subs]

    one = await _call(hass, SERVICE_EXPORT_DEVICES, {"device_id": [ids[1]]}, response=True)
    assert [item["name"] for item in one["export"]["devices"]] == ["Two"]

    two = await _call(hass, SERVICE_EXPORT_DEVICES, {"device_id": [ids[0], ids[2]]}, response=True)
    assert [item["name"] for item in two["export"]["devices"]] == ["One", "Three"]


async def test_export_refuses_a_mirror_and_the_hub_device(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """A mirror is never exported, and neither is the hub device; nothing is written."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    foreign = make_spec(name="Foreign lamp", on=ON_ACTIONS)
    async_fire_mqtt_message(hass, config_topic(BASE, foreign.device_id), document_payload(foreign), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    mirror_id = _companion_id(hass, entry, foreign.device_id)
    hub = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, entry.entry_id), entry.entry_id)
    assert hub is not None

    with pytest.raises(ServiceValidationError) as mirror_error:
        await _call(hass, SERVICE_EXPORT_DEVICES, {"device_id": [mirror_id], "file_name": "backup.json"}, response=True)
    assert mirror_error.value.translation_key == "export_not_owned"

    with pytest.raises(ServiceValidationError) as hub_error:
        await _call(hass, SERVICE_EXPORT_DEVICES, {"device_id": [hub.id], "file_name": "backup.json"}, response=True)
    assert hub_error.value.translation_key == "not_a_device"

    assert not _export_dir(hass).exists()


async def test_export_writes_a_file_in_the_private_directory(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-11, A7: the file sits in <config>/mqtt_actions/, is private and holds what the response holds."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))

    result = await _call(hass, SERVICE_EXPORT_DEVICES, {"file_name": "backup.json"}, response=True)

    assert result["file"] == "mqtt_actions/backup.json"
    path = _export_dir(hass) / "backup.json"
    assert path.is_file()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert json.loads(path.read_text(encoding="utf-8")) == result["export"]


async def test_export_is_admin_only(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    hass_read_only_user: User,
) -> None:
    """T-04-31: a read-only user cannot export and nothing is written."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))

    with pytest.raises(Unauthorized):
        await _call(hass, SERVICE_EXPORT_DEVICES, {"file_name": "backup.json"}, user=hass_read_only_user, response=True)

    assert not _export_dir(hass).exists()


@pytest.mark.parametrize("name", ["../x.json", "a/b.json", ".hidden.json", "x.txt", "", "x" * 65 + ".json"])
async def test_export_bad_file_name_is_rejected(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable, name: str
) -> None:
    """T-04-32: a bad name is a translated validation error and writes nothing."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, SERVICE_EXPORT_DEVICES, {"file_name": name}, response=True)

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "bad_file_name"
    assert not _export_dir(hass).exists()


def _plant_symlink(hass: HomeAssistant) -> Path:
    """Prepare an export directory with `link.json` pointing at another file, and return that file."""
    other = Path(hass.config.path("precious.txt"))
    other.write_text("precious", encoding="utf-8")
    _export_dir(hass).mkdir(mode=0o700)
    (_export_dir(hass) / "link.json").symlink_to(other)
    return other


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


async def test_export_write_failure_is_a_translated_error(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """T-04-32: a symlink as target is refused with a translated error and the linked file is untouched."""
    await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    other = _plant_symlink(hass)

    with pytest.raises(HomeAssistantError) as raised:
        await _call(hass, SERVICE_EXPORT_DEVICES, {"file_name": "link.json"}, response=True)

    assert raised.value.translation_key == "export_write_failed"
    assert _read(other) == "precious"


async def test_services_yaml_describes_both_services(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """services.yaml loads and describes the export fields: a device selector of this integration and a text field."""
    await _setup(hass, make_hub_entry())

    descriptions = (await async_get_all_descriptions(hass))[DOMAIN]

    assert SERVICE_RESYNC in descriptions
    fields = descriptions[SERVICE_EXPORT_DEVICES]["fields"]
    assert fields[CONF_DEVICE_ID]["selector"] == {"device": {"integration": DOMAIN, "multiple": True}}
    assert "text" in fields["file_name"]["selector"]


# --- import (D-11) ---------------------------------------------------------------------------------------------


def _export_of(*contents: dict[str, Any]) -> dict[str, Any]:
    return {"format": "mqtt_actions_export", "export_version": 1, "devices": list(contents)}


def _item(name: str, **overrides: Any) -> dict[str, Any]:
    """Return the shared content of a Switch as an export item, the way the export service would write it."""
    return {**build_content(make_spec(name=name, on=ON_ACTIONS)), **overrides}


def _published_documents(mqtt_mock: Any, device_id: str) -> list[dict[str, Any]]:
    topic = config_topic(BASE, device_id)
    return [json.loads(call.args[1]) for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


async def test_import_creates_owned_devices_that_publish(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    """D-11: two items become two owned devices with new ids, published like devices made in the UI."""
    entry = await _setup(hass, make_hub_entry())
    manager: Manager = entry.runtime_data
    document = _export_of(
        _item("Lamp"),
        build_content(make_spec(SUBENTRY_SELECT, name="Scene", options=[("a", "A", ON_ACTIONS), ("b", "B", [])])),
    )
    mqtt_mock.async_publish.reset_mock()

    result = await _call(hass, SERVICE_IMPORT_DEVICES, {"data": document}, response=True)

    imported = result["imported"]
    assert [(row["index"], row["name"]) for row in imported] == [(1, "Lamp"), (2, "Scene")]
    new_ids = [row["uuid"] for row in imported]
    assert len(set(new_ids)) == 2
    assert {sub.title for sub in entry.subentries.values()} == {"Lamp", "Scene"}
    assert {sub.unique_id for sub in entry.subentries.values()} == set(new_ids)
    assert set(manager.devices) == set(new_ids)
    for new_id in new_ids:
        documents = _published_documents(mqtt_mock, new_id)
        assert documents
        assert documents[-1]["owner"] == entry.data[CONF_INSTANCE_ID]
        assert documents[-1]["rev"] == 1
        assert documents[-1]["device_id"] == new_id
        assert discovery_topic("homeassistant", new_id) in _published_topics(mqtt_mock)


async def test_export_import_round_trip(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    make_select_subentry: Callable,
) -> None:
    """Exporting the owned devices and importing the response restores equal content under different ids."""
    lamp = make_switch_subentry("Lamp", on=ON_ACTIONS, run_on_startup=True, run_mode="restart")
    scene = make_select_subentry("Scene", [("a", "A", ON_ACTIONS), ("b", "B", [])], breaker_max_runs=9)
    entry = await _setup(hass, make_hub_entry([lamp, scene]))
    manager: Manager = entry.runtime_data
    originals = {device_id: content_hash(build_content(device.spec)) for device_id, device in manager.devices.items()}
    exported = await _call(hass, SERVICE_EXPORT_DEVICES, response=True)

    result = await _call(hass, SERVICE_IMPORT_DEVICES, {"data": exported["export"]}, response=True)

    new_ids = [row["uuid"] for row in result["imported"]]
    assert set(new_ids).isdisjoint(originals)
    assert set(manager.devices) == set(originals) | set(new_ids)
    restored = {new_id: content_hash(build_content(manager.devices[new_id].spec)) for new_id in new_ids}
    assert sorted(restored.values()) == sorted(originals.values())


async def test_import_is_admin_only(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, hass_read_only_user: User, hass_admin_user: User
) -> None:
    """T-04-40: a read-only user is refused and nothing is created; the administrator may import."""
    entry = await _setup(hass, make_hub_entry())

    with pytest.raises(Unauthorized):
        await _call(
            hass, SERVICE_IMPORT_DEVICES, {"data": _export_of(_item("Lamp"))}, user=hass_read_only_user, response=True
        )
    assert len(entry.subentries) == 0

    result = await _call(
        hass, SERVICE_IMPORT_DEVICES, {"data": _export_of(_item("Lamp"))}, user=hass_admin_user, response=True
    )
    assert len(result["imported"]) == 1
    assert len(entry.subentries) == 1
