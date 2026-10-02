"""
Export of owned devices as a document and as a private file (SYN-08, D-11).

Pure module: no Home Assistant import. The document carries the shared content of each device and never an identity
or a bookkeeping value, because an import always assigns new ids:

    {"format": "mqtt_actions_export", "export_version": 1, "devices": [<content>, ...]}

`format` and `export_version` let a later reader tell versions apart; a user keeps these files as backups, so both are a
contract once released. The file lives only in `<config>/mqtt_actions/`: never in `www`, which Home Assistant serves
without authentication, and never at a path the user chooses. The user gives a bare name matching a fixed pattern. The
directory is 0700, the file 0600, a symlink is refused and the file is replaced atomically. The functions that touch
the disk block and belong into the executor.
"""

import contextlib
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from .const import EXPORT_DIRECTORY, EXPORT_FORMAT, EXPORT_VERSION
from .document import build_content

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
DIRECTORY_MODE = 0o700
FILE_MODE = 0o600


class PortabilityError(ValueError):
    """An export file cannot be written; `reason` is a short code and the text never carries user content."""

    def __init__(self, reason: str) -> None:
        """Remember the code and use it as the message."""
        super().__init__(reason)
        self.reason = reason


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
