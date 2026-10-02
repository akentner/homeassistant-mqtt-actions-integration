"""The roster sensor of the hub device: how many instances are online (OPS-03, D-06)."""

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .const import SIGNAL_ROSTER_UPDATED
from .entities import MqttActionsEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .manager import Manager


class RosterSensor(MqttActionsEntity, SensorEntity):
    """The number of online instances including this one; follows the roster."""

    _attr_translation_key = "instances_online"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _signals = (SIGNAL_ROSTER_UPDATED,)

    def __init__(self, manager: Manager) -> None:
        """Initialize the sensor; its unique id is bound to the config entry."""
        super().__init__(manager)
        self._attr_unique_id = f"{manager.entry.entry_id}_roster"

    @property
    def native_value(self) -> int:
        """Return how many instances are online, this one included."""
        return self._manager.presence.online_count()


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry[Manager],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the roster sensor of the running manager."""
    async_add_entities([RosterSensor(entry.runtime_data)])
