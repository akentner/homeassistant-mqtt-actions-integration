"""The roster sensor of the hub device: how many instances are online (OPS-03, D-06)."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .const import MAX_TRACKED_INSTANCES, SIGNAL_ROSTER_UPDATED
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
    # The list can be long and changes with every heartbeat; it is never written to the recorder (T-04-16)
    _unrecorded_attributes = frozenset({"instances"})

    def __init__(self, manager: Manager) -> None:
        """Initialize the sensor; its unique id is bound to the config entry."""
        super().__init__(manager)
        self._attr_unique_id = f"{manager.entry.entry_id}_roster"

    @property
    def native_value(self) -> int:
        """Return how many instances are online, this one included."""
        return self._manager.presence.online_count()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return every known instance, this one first, as rows of five keys; capped at the cap plus this instance.

        The texts come from validated heartbeats or from this instance's own configuration, and nothing here is rendered
        as markdown, so they need no escaping (T-04-18).
        """
        rows = self._manager.presence.rows()[: MAX_TRACKED_INSTANCES + 1]
        return {
            "instances": [{key: row[key] for key in ("name", "id", "version", "last_seen", "online")} for row in rows]
        }


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry[Manager],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the roster sensor of the running manager."""
    async_add_entities([RosterSensor(entry.runtime_data)])
