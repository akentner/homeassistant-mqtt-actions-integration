"""The resync button of the hub device: republish everything this instance owns (DSC-04, D-12)."""

from typing import TYPE_CHECKING

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import LOGGER
from .entities import MqttActionsEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .manager import Manager


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


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: ConfigEntry[Manager],
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the resync button of the running manager."""
    async_add_entities([ResyncButton(entry.runtime_data)])
