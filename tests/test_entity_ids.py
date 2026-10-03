"""Short English entity ids of newly created entities, whatever the UI language is (quick 261003-sfb)."""

from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.core import valid_entity_id
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.mqtt_actions.const import CONF_DEVICE_ID, DOMAIN, STORE_KEY, STORE_VERSION
from custom_components.mqtt_actions.model import SWITCH_OFF_KEY, SWITCH_ON_KEY, trigger_key

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.config_entries import ConfigSubentryData
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

AREA_NAME = "Küche"
KITCHEN_OPTIONS = [("kitchen_on", "Küche an", [{"action": "test.on"}]), ("off", "Aus", [{"action": "test.off"}])]

# The ids the German UI language produced before this change, used as pre-registered old ids
OLD_RESTORE_ID = "button.kuche_modus_kuche_vorherigen_zustand_wiederherstellen"


async def prepare(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    entry: MockConfigEntry,
    *,
    language: str,
    area: bool,
) -> dict[str, str]:
    """
    Add the entry natively with the given language, WITHOUT setting it up; return the device registry id per device id.

    The language has to be set before the entry is set up, because the entity platform loads its translations then.
    With `area` every device of a subentry is registered in the area "Küche", so Home Assistant adds the area part.
    """
    hass.config.language = language
    hass_storage[STORE_KEY] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": STORE_KEY,
        "data": {"native": {"instance": True, "pending": [], "devices": []}},
    }
    entry.add_to_hass(hass)
    devices: dict[str, str] = {}
    area_id = ar.async_get(hass).async_create(AREA_NAME).id if area else None
    for subentry_id, subentry in entry.subentries.items():
        device_id = subentry.data[CONF_DEVICE_ID]
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry_id,
            identifiers={(DOMAIN, device_id)},
            name=subentry.title,
        )
        if area_id is not None:
            dr.async_get(hass).async_update_device(device.id, area_id=area_id)
        devices[device_id] = device.id
    return devices


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the prepared entry up and wait for the background tasks."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


def device_id_of(subentry: ConfigSubentryData) -> str:
    return subentry["data"][CONF_DEVICE_ID]


def entity_id(hass: HomeAssistant, domain: str, unique_id: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, unique_id)


def pre_register(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    devices: dict[str, str],
    domain: str,
    unique_id: str,
    old_entity_id: str,
    device_id: str | None = None,
) -> er.RegistryEntry:
    """Register an entry with its old entity id verbatim, the way an earlier run left it in the registry."""
    object_id = old_entity_id.split(".", 1)[1]
    return er.async_get(hass).async_get_or_create(
        domain,
        DOMAIN,
        unique_id,
        config_entry=entry,
        device_id=devices.get(device_id) if device_id else None,
        suggested_object_id=object_id,
    )


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize("area", [False, True])
async def test_a_new_restore_button_gets_a_short_english_id(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
    language: str,
    area: bool,
) -> None:
    """The id part is `_restore` in every language, after the area and device parts; the name stays translated."""
    subentry = make_select_subentry("Modus Küche", KITCHEN_OPTIONS)
    entry = make_hub_entry([subentry])
    await prepare(hass, hass_storage, entry, language=language, area=area)
    await setup(hass, entry)

    device_id = device_id_of(subentry)
    registered_id = entity_id(hass, "button", f"{device_id}_restore_previous")
    assert registered_id == ("button.kuche_modus_kuche_restore" if area else "button.modus_kuche_restore")
    registered = er.async_get(hass).async_get(registered_id)
    assert registered is not None
    assert registered.original_name == (
        "Vorherigen Zustand wiederherstellen" if language == "de" else "Restore previous state"
    )
    assert hass.states.get(registered_id) is not None
    # Pressing without a known previous state raises nothing and publishes nothing
    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call("button", "press", {"entity_id": registered_id}, blocking=True)
    mqtt_mock.async_publish.assert_not_called()


async def test_an_existing_restore_button_keeps_its_old_german_id(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """
    An entry registered before keeps its entity id and registry id; only a new one gets the English part.

    This guard passes before the change as well: Home Assistant never renames an existing registry entry.
    """
    kitchen = make_select_subentry("Modus Küche", KITCHEN_OPTIONS)
    bath = make_select_subentry("Modus Bad", KITCHEN_OPTIONS)
    entry = make_hub_entry([kitchen, bath])
    devices = await prepare(hass, hass_storage, entry, language="de", area=True)
    kitchen_id = device_id_of(kitchen)
    old = pre_register(
        hass, entry, devices, "button", f"{kitchen_id}_restore_previous", OLD_RESTORE_ID, device_id=kitchen_id
    )
    assert old.entity_id == OLD_RESTORE_ID

    await setup(hass, entry)

    after = er.async_get(hass).async_get(OLD_RESTORE_ID)
    assert after is not None
    assert after.id == old.id
    assert after.unique_id == f"{kitchen_id}_restore_previous"
    assert hass.states.get(OLD_RESTORE_ID) is not None
    bath_id = entity_id(hass, "button", f"{device_id_of(bath)}_restore_previous")
    assert bath_id == "button.kuche_modus_bad_restore"


def registered_ids(hass: HomeAssistant, entry: MockConfigEntry) -> dict[tuple[str, str], str]:
    """Return the entity id of every registry entry of the config entry, by (domain, unique id)."""
    registry = er.async_get(hass)
    return {
        (registered.domain, registered.unique_id): registered.entity_id
        for registered in er.async_entries_for_config_entry(registry, entry.entry_id)
    }


@pytest.mark.parametrize("language", ["en", "de"])
@pytest.mark.parametrize("area", [False, True])
async def test_every_new_entity_gets_its_english_id_part(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
    make_switch_subentry: Callable,
    language: str,
    area: bool,
) -> None:
    """The ids of all entities of an instance, in en and de, with and without an area part."""
    select = make_select_subentry("Modus Küche", KITCHEN_OPTIONS)
    switch = make_switch_subentry("Lampe", on=[{"action": "test.on"}], off=[{"action": "test.off"}])
    entry = make_hub_entry([select, switch])
    await prepare(hass, hass_storage, entry, language=language, area=area)
    await setup(hass, entry)

    select_prefix = "kuche_modus_kuche" if area else "modus_kuche"
    switch_prefix = "kuche_lampe" if area else "lampe"
    sid, wid = device_id_of(select), device_id_of(switch)
    hub = entry.entry_id
    assert registered_ids(hass, entry) == {
        ("select", sid): f"select.{select_prefix}",
        ("select", f"{sid}_mode"): f"select.{select_prefix}_mode",
        ("button", f"{sid}_restore_previous"): f"button.{select_prefix}_restore",
        ("button", f"{sid}_test_{trigger_key('kitchen_on')}"): f"button.{select_prefix}_test_kitchen_on",
        ("button", f"{sid}_test_{trigger_key('off')}"): f"button.{select_prefix}_test_off",
        ("switch", wid): f"switch.{switch_prefix}",
        ("select", f"{wid}_mode"): f"select.{switch_prefix}_mode",
        ("button", f"{wid}_test_{SWITCH_ON_KEY}"): f"button.{switch_prefix}_test_on",
        ("button", f"{wid}_test_{SWITCH_OFF_KEY}"): f"button.{switch_prefix}_test_off",
        ("button", f"{hub}_resync"): "button.test_instance_resync",
        ("sensor", f"{hub}_roster"): "sensor.test_instance_instances",
        ("select", f"{hub}_instance_mode"): "select.test_instance_instance_mode",
    }
    resync = er.async_get(hass).async_get("button.test_instance_resync")
    assert resync is not None
    assert resync.original_name == ("Neu synchronisieren" if language == "de" else "Resync")


async def test_every_existing_entity_keeps_its_old_german_id(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """Entries of every kind registered before keep entity id and registry id; the unregistered test button is new."""
    select = make_select_subentry("Modus Küche", KITCHEN_OPTIONS)
    entry = make_hub_entry([select])
    devices = await prepare(hass, hass_storage, entry, language="de", area=True)
    sid, hub = device_id_of(select), entry.entry_id
    old_ids = {
        ("button", f"{hub}_resync", None): "button.test_instance_neu_synchronisieren",
        ("sensor", f"{hub}_roster", None): "sensor.test_instance_verbundene_instanzen",
        ("select", f"{hub}_instance_mode", None): "select.test_instance_instanzmodus",
        ("select", f"{sid}_mode", sid): "select.kuche_modus_kuche_modus",
        ("button", f"{sid}_restore_previous", sid): OLD_RESTORE_ID,
        ("button", f"{sid}_test_{trigger_key('kitchen_on')}", sid): "button.kuche_modus_kuche_test_kuche_an",
    }
    before = {
        key: pre_register(hass, entry, devices, key[0], key[1], old_id, device_id=key[2])
        for key, old_id in old_ids.items()
    }
    for key, old_id in old_ids.items():
        assert before[key].entity_id == old_id

    await setup(hass, entry)

    registry = er.async_get(hass)
    for key, old_id in old_ids.items():
        after = registry.async_get(old_id)
        assert after is not None, old_id
        assert (after.id, after.unique_id) == (before[key].id, key[1])
        assert entity_id(hass, key[0], key[1]) == old_id
    assert entity_id(hass, "button", f"{sid}_test_{trigger_key('off')}") == "button.kuche_modus_kuche_test_off"


async def test_a_hostile_state_value_gives_a_valid_test_button_id(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_select_subentry: Callable,
) -> None:
    """T-261003-07: a StateValue with spaces, slashes, dots, colons and an umlaut cannot produce an invalid id."""
    value = "Ä b/c.d:e  ü/../9"
    select = make_select_subentry("Modus", [(value, "Hostile", [{"action": "test.on"}]), ("off", "Aus", [])])
    entry = make_hub_entry([select])
    await prepare(hass, hass_storage, entry, language="de", area=False)
    await setup(hass, entry)

    registered_id = entity_id(hass, "button", f"{device_id_of(select)}_test_{trigger_key(value)}")
    assert registered_id is not None
    assert valid_entity_id(registered_id)
    assert registered_id.startswith("button.")
    assert len(registered_id) <= 255
    # The part comes from the StateValue and not from the friendly name
    assert registered_id.startswith("button.modus_test_")
    assert "_c_d_e_" in registered_id
