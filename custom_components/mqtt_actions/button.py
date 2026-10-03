"""
The buttons: resync, the native test buttons and the restore button of native Select devices.

New test buttons are diagnostic and disabled by default; an existing registry entry keeps its category and its state.
"""

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, LOGGER, SIGNAL_DEVICES_CHANGED, SUBENTRY_SELECT
from .entities import MqttActionsEntity, NativeDeviceEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .manager import Manager
    from .model import TriggerSpec


class ResyncButton(MqttActionsEntity, ButtonEntity):
    """Republishes the config documents, the discovery and `online` through the order of Phase 3."""

    _attr_translation_key = "resync"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager: Manager) -> None:
        """Initialize the button; its unique id is bound to the config entry."""
        super().__init__(manager)
        self._attr_unique_id = f"{manager.entry.entry_id}_resync"

    async def async_press(self) -> None:
        """Resync; a press inside the cooldown or on a stopped manager does nothing (T-04-15)."""
        if not await self._manager.async_resync():
            LOGGER.debug("The resync was ignored because it is throttled or the manager is not running")


def _test_button_unique_id(device_id: str, key: str) -> str:
    """Return the unique id of the test button of a trigger; the value the discovery button had."""
    return f"{device_id}_test_{key}"


def _test_button_category(registry: er.EntityRegistry, device_id: str, key: str) -> EntityCategory | None:
    """
    Return the category a test button is added with: its own for an existing registry entry, else diagnostic.

    Home Assistant writes the category of an entity to an existing registry entry at every add, but applies the
    enabled default only when the entry is created. An existing entry therefore has to hand its own category back to
    stay untouched; only a new entry gets the diagnostic category (P-05).
    """
    entity_id = registry.async_get_entity_id("button", DOMAIN, _test_button_unique_id(device_id, key))
    if entity_id is not None and (existing := registry.async_get(entity_id)) is not None:
        return existing.entity_category
    return EntityCategory.DIAGNOSTIC


class DeviceTestButton(NativeDeviceEntity, ButtonEntity):
    """
    Runs the actions of one trigger locally, through the same mode gate as the test topic (MIG-03).

    A press publishes nothing and never touches the state or the baseline: no test topic round trip exists for a native
    device. A new button is diagnostic and disabled by default; an existing registry entry keeps both (Q-01).
    """

    _attr_entity_registry_enabled_default = False

    def __init__(
        self, manager: Manager, device_id: str, trigger: TriggerSpec, entity_category: EntityCategory | None
    ) -> None:
        """Initialize the button of one trigger; its unique id derives from the immutable StateValue."""
        super().__init__(manager, device_id)
        self._attr_entity_category = entity_category
        self._trigger_key = trigger.key
        self._attr_unique_id = _test_button_unique_id(device_id, trigger.key)
        self._attr_name = f"Test {trigger.friendly_name}"

    @callback
    def _on_signal(self) -> None:
        """Follow a renamed option, then write the state again."""
        device = self._manager.device(self._device_id)
        if device is not None and (trigger := device.spec.triggers.get(self._trigger_key)) is not None:
            self._attr_name = f"Test {trigger.friendly_name}"
        super()._on_signal()

    async def async_press(self) -> None:
        """Run the actions of the trigger once."""
        await self._manager.async_press_test(self._device_id, self._trigger_key)


def _restore_button_unique_id(device_id: str) -> str:
    """Return the unique id of the restore button of a Select device."""
    return f"{device_id}_restore_previous"


class RestorePreviousButton(NativeDeviceEntity, ButtonEntity):
    """Publishes the StateValue that was shown before the current one, exactly like choosing that option."""

    _attr_translation_key = "restore_previous"
    _entity_id_part = "restore"

    def __init__(self, manager: Manager, device_id: str) -> None:
        """Initialize the button of one Select device."""
        super().__init__(manager, device_id)
        self._attr_unique_id = _restore_button_unique_id(device_id)

    async def async_press(self) -> None:
        """Restore the previous state; a press without a known previous state does nothing."""
        if not await self._manager.async_restore_previous(self._device_id):
            LOGGER.debug("The restore was ignored because no previous state is known")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[Manager],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the resync button and the test button of every trigger of every native device or mirror, now and later."""
    manager = entry.runtime_data
    async_add_entities([ResyncButton(manager)])
    added: set[tuple[str, str]] = set()

    @callback
    def _sync_test_buttons() -> None:
        expected = {
            (device_id, key): trigger
            for device_id, device in [*manager.devices.items(), *manager.mirrors.items()]
            if manager.is_native(device_id)
            for key, trigger in device.spec.triggers.items()
        }
        # A removed option leaves no unavailable button behind: its registry entry goes; a native button needs no
        # tombstone, unlike the discovery button
        registry = er.async_get(hass)
        for device_id, key in sorted(added - expected.keys()):
            if entity_id := registry.async_get_entity_id("button", DOMAIN, _test_button_unique_id(device_id, key)):
                registry.async_remove(entity_id)
        added.intersection_update(expected)
        for device_id in sorted({device_id for device_id, _key in expected.keys() - added}):
            new = [(pair, trigger) for pair, trigger in expected.items() if pair[0] == device_id and pair not in added]
            added.update(pair for pair, _trigger in new)
            async_add_entities(
                [
                    DeviceTestButton(manager, device_id, trigger, _test_button_category(registry, device_id, key))
                    for (_device_id, key), trigger in new
                ],
                config_subentry_id=manager.subentry_id_of(device_id),
            )

    added_restore: set[str] = set()

    @callback
    def _add_restore_buttons() -> None:
        qualifying = {
            device_id
            for device_id, device in [*manager.devices.items(), *manager.mirrors.items()]
            if device.spec.kind == SUBENTRY_SELECT and manager.is_native(device_id)
        }
        added_restore.intersection_update(qualifying)
        for device_id in sorted(qualifying - added_restore):
            added_restore.add(device_id)
            async_add_entities(
                [RestorePreviousButton(manager, device_id)], config_subentry_id=manager.subentry_id_of(device_id)
            )

    _sync_test_buttons()
    _add_restore_buttons()
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICES_CHANGED.format(entry.entry_id), _sync_test_buttons)
    )
    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_DEVICES_CHANGED.format(entry.entry_id), _add_restore_buttons)
    )
