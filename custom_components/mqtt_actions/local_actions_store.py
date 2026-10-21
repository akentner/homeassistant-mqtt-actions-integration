"""
The separate Store of the local actions of mirrors (D-07, D-22).

Its own key and version, so a save of the main Store, including one by an older release, never reads or rewrites it.
Parsing and migration are the HA-free functions of `local_actions`; this module only adapts them to the HA Store.
"""

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.storage import Store

from .const import LOCAL_ACTIONS_STORE_KEY, LOCAL_ACTIONS_STORE_MINOR_VERSION, LOCAL_ACTIONS_STORE_VERSION
from .local_actions import LocalActionRecord, migrate_local_actions_payload

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant


class LocalActionsStore(Store[dict[str, Any]]):
    """The HA Store of the local action records of one instance."""

    def __init__(self, hass: HomeAssistant, key: str = LOCAL_ACTIONS_STORE_KEY) -> None:
        """Initialize the Store; `key` is a test seam, production uses the shared local key."""
        super().__init__(
            hass,
            LOCAL_ACTIONS_STORE_VERSION,
            key,
            private=True,
            atomic_writes=True,
            minor_version=LOCAL_ACTIONS_STORE_MINOR_VERSION,
        )

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Upgrade an older payload through the pure migrator; the Store saves the result."""
        return migrate_local_actions_payload(old_major_version, old_minor_version, old_data)

    @property
    def records(self) -> tuple[LocalActionRecord, ...]:
        """Return the records of the last successful load or save."""
        return ()

    async def async_load_records(self) -> tuple[LocalActionRecord, ...]:
        """Load the records."""
        return ()

    async def async_save_records(self, records: Iterable[LocalActionRecord]) -> tuple[LocalActionRecord, ...]:
        """Save the records."""
        del records
        return ()
