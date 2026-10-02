"""
Export and import of owned devices as a document and as a private file (SYN-08, D-11).

Almost pure module: the only Home Assistant import is the JSON parser of core, through `document`. The document carries
the shared content of each device and never an identity or a bookkeeping value, because an import always assigns new
ids:

    {"format": "mqtt_actions_export", "export_version": 1, "devices": [<content>, ...]}

`format` and `export_version` let a later reader tell versions apart; a user keeps these files as backups, so both are a
contract once released. The file lives only in `<config>/mqtt_actions/`: never in `www`, which Home Assistant serves
without authentication, and never at a path the user chooses. The user gives a bare name matching a fixed pattern. The
directory is 0700, the file 0600, a symlink is refused and the file is replaced atomically. The functions that touch
the disk block and belong into the executor.

An import is the most security-relevant way text becomes devices: every item becomes a throw-away document and runs
through `parse_document`, the same strict path as a document received from the broker, then the structure check of the
script schema and the static denylist. Nothing of the item that is bookkeeping survives: the new device gets a new
uuid, this instance as owner and revision 1. Rejections carry a fixed reason code and a position, never content.
"""

import contextlib
import os
import re
import stat
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from homeassistant.util.json import json_loads

from .actions import ActionsInvalid, validate_spec_structure
from .const import (
    CONF_DEVICE_ID,
    EXPORT_DIRECTORY,
    EXPORT_FORMAT,
    EXPORT_VERSION,
    MAX_IMPORT_BYTES,
    MAX_IMPORT_DEVICES,
    SCHEMA_VERSION,
)
from .document import (
    DocumentRejectedError,
    RejectReason,
    analyze_spec,
    build_content,
    parse_document,
    serialize_document,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .model import DeviceSpec

# A letter or digit first, then letters, digits, dot, dash and underscore up to 64 characters in all, then `.json`;
# always a full match, so a trailing newline, a separator or a second extension never passes
FILE_NAME_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\.json")
# Reason codes of a PortabilityError
REASON_BAD_FILE_NAME: Final = "bad_file_name"
REASON_SYMLINK: Final = "symlink"
REASON_NOT_A_DIRECTORY: Final = "not_a_directory"
REASON_DIRECTORY_NOT_PRIVATE: Final = "directory_not_private"
# Reason codes of a rejected import; each is also the key of a placeholder value in the translated error
REASON_BAD_FORMAT: Final = "bad_format"
REASON_TOO_NEW: Final = "too_new"
REASON_INVALID_DEVICE: Final = "invalid_device"
REASON_INVALID_ACTIONS: Final = "invalid_actions"
REASON_DENIED_SERVICE: Final = "denied_service"
REASON_TOO_LARGE: Final = "too_large"
REASON_TOO_MANY: Final = "too_many"
REASON_NOT_JSON: Final = "not_json"
# Reason code of an import file that cannot be read; the service gives it a message of its own
REASON_FILE_UNREADABLE: Final = "file_unreadable"
# The keys of the content that identify the device kind and name; they are the title and type of a subentry, not data
NON_DATA_KEYS: Final = frozenset({"kind", "name"})
DIRECTORY_MODE = 0o700
FILE_MODE = 0o600


class PortabilityError(ValueError):
    """
    An export file cannot be written or an import is refused.

    `reason` is a short code and `index` the 1-based position of the offending item (None when the whole file is
    meant); the text is the code and never carries user content.
    """

    def __init__(self, reason: str, index: int | None = None) -> None:
        """Remember the code and the position and use the code as the message."""
        super().__init__(reason)
        self.reason = reason
        self.index = index


def build_export(specs: Iterable[DeviceSpec]) -> dict[str, Any]:
    """Return the export document of the given specs: the shared content of each, no id, owner, rev or hash."""
    return {
        "format": EXPORT_FORMAT,
        "export_version": EXPORT_VERSION,
        "devices": [build_content(spec) for spec in specs],
    }


def export_file_path(config_dir: Path, name: str) -> Path:
    """Return the path of an export file below the private directory, or raise for any name that is not a bare name."""
    if not FILE_NAME_PATTERN.fullmatch(name):
        raise PortabilityError(REASON_BAD_FILE_NAME)
    return config_dir / EXPORT_DIRECTORY / name


def _ensure_private_directory(directory: Path) -> None:
    """Create the export directory with 0700, or close a too open one of ours; a symlink or a foreign one is refused."""
    with contextlib.suppress(FileExistsError):
        directory.mkdir(mode=DIRECTORY_MODE)
    # lstat does not follow a link: a symlinked directory would send the file somewhere else
    status = directory.lstat()
    if stat.S_ISLNK(status.st_mode):
        raise PortabilityError(REASON_SYMLINK)
    if not stat.S_ISDIR(status.st_mode):
        raise PortabilityError(REASON_NOT_A_DIRECTORY)
    if stat.S_IMODE(status.st_mode) != DIRECTORY_MODE:
        if status.st_uid != os.getuid():
            raise PortabilityError(REASON_DIRECTORY_NOT_PRIVATE)
        directory.chmod(DIRECTORY_MODE)


def write_export(config_dir: Path, name: str, text: str) -> Path:
    """
    Write the text to the export file and return its path; blocking, so call it in the executor.

    The text goes to a temporary file in the same directory, created with 0600 by `mkstemp`, is flushed to disk and
    then replaces the target with `os.replace`, so a reader never sees half a file and the temporary file never stays.
    `os.replace` swaps the directory entry and never writes through a link, but a symlink as target is refused anyway,
    because it can only mean someone prepared the directory.
    """
    target = export_file_path(config_dir, name)
    directory = target.parent
    _ensure_private_directory(directory)
    if target.is_symlink():
        raise PortabilityError(REASON_SYMLINK)
    descriptor, temporary = tempfile.mkstemp(dir=directory, prefix=".export-", suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).chmod(FILE_MODE)
        Path(temporary).replace(target)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(temporary).unlink()
        raise
    return target


# --- import (D-11) ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreparedDevice:
    """A validated import item: the new device with its new id, the subentry data and the spec built from it."""

    index: int
    device_id: str
    kind: str
    name: str
    data: dict[str, Any]
    spec: DeviceSpec


def parse_export(value: Any) -> list[Any]:
    """Check the envelope of an export and return its item list; raise PortabilityError with a fixed reason code."""
    if not isinstance(value, dict) or value.get("format") != EXPORT_FORMAT:
        raise PortabilityError(REASON_BAD_FORMAT)
    version = value.get("export_version")
    if type(version) is not int or version < 1:
        raise PortabilityError(REASON_BAD_FORMAT)
    if version > EXPORT_VERSION:
        raise PortabilityError(REASON_TOO_NEW)
    devices = value.get("devices")
    if not isinstance(devices, list):
        raise PortabilityError(REASON_BAD_FORMAT)
    if len(devices) > MAX_IMPORT_DEVICES:
        raise PortabilityError(REASON_TOO_MANY)
    return devices


def parse_import_text(text: str) -> Any:
    """Return the JSON value of the text of an import file, or raise PortabilityError with `not_json`."""
    try:
        return json_loads(text)
    except ValueError as err:
        raise PortabilityError(REASON_NOT_JSON) from err


def read_import(config_dir: Path, name: str) -> str:
    """
    Return the text of an import file in the private export directory; blocking, so call it in the executor.

    Only a bare name of the fixed pattern is accepted, the directory must be a real directory and the file is opened
    without following a link, so a planted symlink never leads out of the directory. The opened file must be a regular
    file; its size is checked on the descriptor before anything is read and the read itself is bounded, so a huge file
    never reaches memory (T-04-37, T-04-38). The text must be strict UTF-8. Every refusal that is not a bad name or a
    size is `file_unreadable`, whatever the cause, so the error never tells a probe which file exists.
    """
    path = export_file_path(config_dir, name)
    if path.parent.is_symlink():
        raise PortabilityError(REASON_FILE_UNREADABLE)
    # O_NONBLOCK keeps a FIFO planted under the name from blocking the open; the regular-file check refuses it after
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
    except OSError as err:
        raise PortabilityError(REASON_FILE_UNREADABLE) from err
    try:
        with os.fdopen(descriptor, "rb") as handle:
            status = os.fstat(handle.fileno())
            if not stat.S_ISREG(status.st_mode):
                raise PortabilityError(REASON_FILE_UNREADABLE)
            if status.st_size > MAX_IMPORT_BYTES:
                raise PortabilityError(REASON_TOO_LARGE)
            raw = handle.read(MAX_IMPORT_BYTES + 1)
    except OSError as err:
        raise PortabilityError(REASON_FILE_UNREADABLE) from err
    if len(raw) > MAX_IMPORT_BYTES:
        # The file grew between the size check and the read
        raise PortabilityError(REASON_TOO_LARGE)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as err:
        raise PortabilityError(REASON_FILE_UNREADABLE) from err


def subentry_payload(content: dict[str, Any], device_id: str) -> dict[str, Any]:
    """Return the subentry data of shared content: no kind and no name (they are type and title), plus the device id."""
    payload = {key: value for key, value in content.items() if key not in NON_DATA_KEYS}
    payload[CONF_DEVICE_ID] = device_id
    return payload


def _prepare_item(index: int, item: Any, *, owner: str, owner_name: str) -> PreparedDevice:
    """
    Turn one item into a new owned device through the strict path of a document from the broker.

    The throw-away document is the item overlaid with the bookkeeping of this instance, so a forged owner, device id,
    rev, hash or schema version of the item loses. The checks follow the order of a received document: size, depth and
    field rules by `parse_document`, the structure of the actions, then the static denylist.
    """
    if not isinstance(item, dict):
        raise PortabilityError(REASON_INVALID_DEVICE, index)
    device_id = str(uuid.uuid4())
    document = {
        **item,
        "schema_version": SCHEMA_VERSION,
        CONF_DEVICE_ID: device_id,
        "owner": owner,
        "owner_name": owner_name,
        "rev": 1,
    }
    document.pop("hash", None)
    try:
        payload = serialize_document(document)
    except (TypeError, ValueError) as err:
        # Mixed key types, NaN and the like: the item is not plain JSON
        raise PortabilityError(REASON_INVALID_DEVICE, index) from err
    try:
        parsed = parse_document(device_id, payload)
    except DocumentRejectedError as err:
        reason = REASON_TOO_LARGE if err.reason is RejectReason.TOO_LARGE else REASON_INVALID_DEVICE
        raise PortabilityError(reason, index) from err
    try:
        validate_spec_structure(parsed.spec)
    except ActionsInvalid as err:
        raise PortabilityError(REASON_INVALID_ACTIONS, index) from err
    try:
        denied = analyze_spec(parsed.spec).denied
    except DocumentRejectedError as err:
        raise PortabilityError(REASON_INVALID_DEVICE, index) from err
    if denied:
        raise PortabilityError(REASON_DENIED_SERVICE, index)
    return PreparedDevice(
        index=index,
        device_id=device_id,
        kind=parsed.spec.kind,
        name=parsed.spec.name,
        data=subentry_payload(parsed.content, device_id),
        spec=parsed.spec,
    )


def prepare_import(items: Iterable[Any], *, owner: str, owner_name: str) -> list[PreparedDevice]:
    """
    Validate every item and return the new devices; the first flaw raises PortabilityError with its 1-based position.

    Nothing is created here, so a caller creates devices only after the whole list passed.
    """
    return [_prepare_item(index, item, owner=owner, owner_name=owner_name) for index, item in enumerate(items, start=1)]
