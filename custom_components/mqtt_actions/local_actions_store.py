"""
The separate Store of the local actions of mirrors (D-07, D-22).

Its own key and version, so a save of the main Store, including one by an older release, never reads or rewrites it.
Parsing and migration are the HA-free functions of `local_actions`; this module only adapts them to the HA Store.
"""

import asyncio
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import LOCAL_ACTIONS_STORE_KEY, LOCAL_ACTIONS_STORE_MINOR_VERSION, LOCAL_ACTIONS_STORE_VERSION, LOGGER
from .local_actions import (
    LocalActionRecord,
    copy_local_records,
    local_actions_payload,
    migrate_local_actions_payload,
    parse_local_actions_payload,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.core import HomeAssistant


class LocalActionsStoreError(HomeAssistantError):
    """Raised when the local actions cannot be saved; the previous durable and in-memory snapshot stays."""


class LocalActionsStore(Store[dict[str, Any]]):
    """
    The HA Store of the local action records of one instance.

    The snapshot is replaced only by a successful load or save, and every record handed out carries its own copy of
    the actions. A payload of a newer major version fails the load and turns every later save into an error, so it is
    never overwritten (T-11-09). Loading never rewrites the Store except through the migration hook (D-22).
    """

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
        self._records: tuple[LocalActionRecord, ...] = ()
        self._loaded = False
        self._lock = asyncio.Lock()
        # The base Store logs a failed write and returns normally; the override below keeps the error for the caller
        self._write_error: Exception | None = None

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Upgrade an older payload through the pure migrator; the Store saves the result."""
        return migrate_local_actions_payload(old_major_version, old_minor_version, old_data)

    async def _async_write_data(self, data: dict[str, Any]) -> None:
        """Write through the base Store and remember a failure, which the base Store would only log."""
        try:
            await super()._async_write_data(data)
        except Exception as err:
            self._write_error = err
            raise

    @property
    def records(self) -> tuple[LocalActionRecord, ...]:
        """Return copies of the records of the last successful load or save."""
        return copy_local_records(self._records)

    async def async_load_records(self) -> tuple[LocalActionRecord, ...]:
        """
        Load and parse the records; malformed rows are dropped one by one and logged by count only.

        Raises the Store's UnsupportedStorageVersionError for a newer major version, and LocalActionsStoreVersionError
        for any other unreadable one; the Store is then left unloaded and refuses every save.
        """
        async with self._lock:
            self._loaded = False
            self._records = ()
            stored = await self.async_load()
            if stored is None:
                records: tuple[LocalActionRecord, ...] = ()
            else:
                parsed = parse_local_actions_payload(stored)
                if not parsed.shape_valid:
                    LOGGER.warning("The local actions Store %s holds no record list; no local actions loaded", self.key)
                elif parsed.dropped:
                    LOGGER.warning("Dropped %d malformed local action records from %s", parsed.dropped, self.key)
                records = parsed.records
            self._records = records
            self._loaded = True
            return copy_local_records(records)

    async def async_save_records(self, records: Iterable[LocalActionRecord]) -> tuple[LocalActionRecord, ...]:
        """
        Save the complete record set at once and return copies of it; raise LocalActionsStoreError.

        Only a written payload replaces the snapshot: on any failure the previous records stay, in memory and on disk.
        """
        snapshot = copy_local_records(records)
        if len({record.identity for record in snapshot}) != len(snapshot):
            msg = "Two local action records share one trigger identity; nothing was saved"
            raise LocalActionsStoreError(msg)
        async with self._lock:
            if not self._loaded:
                msg = f"The local actions of {self.key} are not loaded; nothing was saved"
                raise LocalActionsStoreError(msg)
            self._write_error = None
            try:
                await self.async_save(local_actions_payload(snapshot))
            except Exception as err:
                msg = f"The local actions of {self.key} could not be saved"
                raise LocalActionsStoreError(msg) from err
            if (error := self._write_error) is not None:
                self._write_error = None
                msg = f"The local actions of {self.key} could not be saved"
                raise LocalActionsStoreError(msg) from error
            self._records = snapshot
            return copy_local_records(snapshot)

    async def async_remove_records(self) -> None:
        """Remove the Store file."""
