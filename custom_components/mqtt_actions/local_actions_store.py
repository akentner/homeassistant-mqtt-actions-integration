"""
The separate Store of the local actions of mirrors (D-07, D-22).

Its own key and version, so a save of the main Store, including one by an older release, never reads or rewrites it.
Parsing and migration are the HA-free functions of `local_actions`; this module only adapts them to the HA Store.
"""

import asyncio
from pathlib import Path
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


class LocalActionsStoreUnreadableError(HomeAssistantError):
    """Raised when stored local actions exist but cannot be read; nothing is rewritten and every save is refused."""


class LocalActionsStore(Store[dict[str, Any]]):
    """
    The HA Store of the local action records of one instance.

    The snapshot is replaced only by a successful load or save, and every record handed out carries its own copy of
    the actions. A payload this release cannot read fails the load and turns every later save into an error, so it is
    never overwritten (T-11-09): a newer major version, a payload that is not a mapping with a record list, and a
    missing file beside a `.corrupt.` copy of the same key, which Home Assistant leaves after a file it could not parse
    (D-07). Rows this release cannot parse and top-level keys other than the record list, for example of a newer
    minor format, are kept from the last successful load and written back after the records on every save; they are
    never records (D-07, WR-03). Loading never rewrites the Store except through the migration hook (D-22). Removal
    deletes the file and the corrupt copies of its own key only, and forgets the kept rows (D-08).
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
        # Rows and top-level keys of the last successful load that this release cannot read; written back on every save
        self._preserved: tuple[Any, ...] = ()
        self._extra: dict[str, Any] = {}
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

    @property
    def preserved_device_ids(self) -> frozenset[str]:
        """Return the device ids named by kept rows: the non-blank string `device_id` of each kept mapping row."""
        return frozenset(
            device_id
            for row in self._preserved
            if isinstance(row, dict) and isinstance(device_id := row.get("device_id"), str) and device_id.strip()
        )

    async def async_load_records(self) -> tuple[LocalActionRecord, ...]:
        """
        Load and parse the records; rows this release cannot parse are kept aside, never applied, and logged by count.

        Raises the Store's UnsupportedStorageVersionError for a newer major version, LocalActionsStoreVersionError for
        any other unreadable version, and LocalActionsStoreUnreadableError for a payload without a record list or for a
        missing file beside a corrupt copy of this key. The Store is then left unloaded and refuses every save. Null
        data and a missing file without such a copy load as no records.
        """
        async with self._lock:
            self._loaded = False
            self._records = ()
            self._preserved = ()
            self._extra = {}
            stored = await self.async_load()
            if stored is None:
                # Core moves a file it cannot parse aside and returns None, the same as for a missing file (WR-03)
                if await self.hass.async_add_executor_job(self._corrupt_copies):
                    msg = f"The local actions Store {self.key} has a corrupt copy beside a missing file"
                    raise LocalActionsStoreUnreadableError(msg)
                records: tuple[LocalActionRecord, ...] = ()
            else:
                parsed = parse_local_actions_payload(stored)
                if not parsed.shape_valid:
                    # Left unloaded on purpose: a later save would replace records this release cannot read (WR-03)
                    msg = f"The local actions Store {self.key} holds no record list"
                    raise LocalActionsStoreUnreadableError(msg)
                if parsed.preserved:
                    LOGGER.warning(
                        "Kept %d local action records of %s that this version cannot read; they are not applied",
                        len(parsed.preserved),
                        self.key,
                    )
                if duplicates := parsed.dropped - len(parsed.preserved):
                    LOGGER.warning("Dropped %d duplicate local action records from %s", duplicates, self.key)
                records = parsed.records
                self._preserved = parsed.preserved
                self._extra = parsed.extra
            self._records = records
            self._loaded = True
            return copy_local_records(records)

    async def async_save_records(self, records: Iterable[LocalActionRecord]) -> tuple[LocalActionRecord, ...]:
        """
        Save the complete record set at once and return copies of it; raise LocalActionsStoreError.

        Only a written payload replaces the snapshot: on any failure the previous records stay, in memory and on disk.
        The rows and keys of the last load that this release cannot read are written back after the records (WR-03).
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
                await self.async_save(local_actions_payload(snapshot, preserved=self._preserved, extra=self._extra))
            except Exception as err:  # noqa: BLE001 - any failure of the write is reported the same way
                error: Exception | None = err
            else:
                error = self._write_error
            self._write_error = None
            if error is not None:
                msg = f"The local actions of {self.key} could not be saved"
                raise LocalActionsStoreError(msg) from error
            self._records = snapshot
            return copy_local_records(snapshot)

    async def async_close(self) -> None:
        """
        Refuse every later save until the next load; called when the Manager stops (T-11-28).

        A save already running finishes first, because both take the lock. After that a late callback of a stopped
        Manager cannot write, so a hub removal that deletes the file cannot see it come back.
        """
        async with self._lock:
            self._loaded = False

    async def async_remove_records(self) -> None:
        """
        Remove this Store's file and its corrupt copies; forget its records and kept rows. Raise LocalActionsStoreError.

        Only the copies of this key go; no other key is touched. Allowed even after a refused load: removing is the
        user's explicit choice (D-08). A later save writes a new file.
        """
        async with self._lock:
            try:
                await self.async_remove()
                await self.hass.async_add_executor_job(self._remove_corrupt_copies)
            except Exception as err:
                msg = f"The local actions of {self.key} could not be removed"
                raise LocalActionsStoreError(msg) from err
            self._records = ()
            self._preserved = ()
            self._extra = {}
            self._loaded = True

    def _corrupt_copies(self) -> list[Path]:
        """
        Return the copies Home Assistant left of this key's file, named `<file>.corrupt.<time>`; run in an executor.

        A missing storage folder has none.
        """
        path = Path(self.path)
        prefix = f"{path.name}.corrupt."
        try:
            return [entry for entry in path.parent.iterdir() if entry.name.startswith(prefix)]
        except FileNotFoundError:
            return []

    def _remove_corrupt_copies(self) -> None:
        """Delete every corrupt copy of this key; run in an executor, any OSError reaches the caller."""
        for corrupt in self._corrupt_copies():
            corrupt.unlink(missing_ok=True)
