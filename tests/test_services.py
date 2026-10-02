"""The service layer: registration at setup, admin-only access, device resolution and the resync service (D-12)."""

import inspect
from typing import TYPE_CHECKING, Any

import pytest
from homeassistant.core import Context
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_mqtt_message

import custom_components.mqtt_actions as integration
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    CONF_INSTANCE_ID,
    DOMAIN,
    RESYNC_MIN_INTERVAL_SECONDS,
    SERVICE_EXPORT_DEVICES,
    SERVICE_RESYNC,
)
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic
from tests.documents import document_payload, make_spec

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.auth.models import User
    from homeassistant.core import HomeAssistant

    from custom_components.mqtt_actions.manager import Manager

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on"}]


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


def test_export_service_name_is_a_constant() -> None:
    """The export service name is part of the user-facing contract."""
    assert SERVICE_EXPORT_DEVICES == "export_devices"
