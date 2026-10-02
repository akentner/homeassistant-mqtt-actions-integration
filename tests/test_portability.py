"""Export document and the private export file: no ids in the content, a bare file name, 0700 and 0600 (D-11)."""

import json
import stat
from typing import TYPE_CHECKING

import pytest

from custom_components.mqtt_actions.const import EXPORT_DIRECTORY, EXPORT_FORMAT, EXPORT_VERSION, SUBENTRY_SELECT
from custom_components.mqtt_actions.document import build_content
from custom_components.mqtt_actions.portability import PortabilityError, build_export, export_file_path, write_export
from tests.documents import make_spec

if TYPE_CHECKING:
    from pathlib import Path

SWITCH_ACTIONS = [{"action": "test.on", "target": {"entity_id": "light.lamp"}}]
FORBIDDEN_KEYS = {"device_id", "owner", "owner_name", "rev", "hash", "schema_version"}


def test_build_export_has_format_version_and_content_only() -> None:
    """D-11: the document names its format and version, and each device is exactly its shared content."""
    switch = make_spec(name="Lamp", on=SWITCH_ACTIONS, run_on_startup=True)
    select = make_spec(
        SUBENTRY_SELECT,
        name="Scene",
        options=[("c", "Third", []), ("a", "First", SWITCH_ACTIONS), ("b", "Second", [])],
    )

    document = build_export([switch, select])

    assert document["format"] == EXPORT_FORMAT == "mqtt_actions_export"
    assert document["export_version"] == EXPORT_VERSION == 1
    assert set(document) == {"format", "export_version", "devices"}
    first, second = document["devices"]
    assert first == build_content(switch)
    assert second == build_content(select)
    for item in document["devices"]:
        assert FORBIDDEN_KEYS.isdisjoint(item)
    assert [option["state_value"] for option in second["options"]] == ["c", "a", "b"]
    # The document is plain JSON
    assert json.loads(json.dumps(document)) == document


def test_build_export_of_nothing_is_an_empty_list() -> None:
    """An instance without owned devices exports an empty, valid document."""
    assert build_export([])["devices"] == []


@pytest.mark.parametrize("name", ["backup.json", "a-b_c.1.json", "A.json", f"{'a' * 64}.json", f"{'a' * 62}.b.json"])
def test_export_file_name_accepts(name: str, tmp_path: Path) -> None:
    """Names made of letters, digits, dot, dash and underscore with the json extension are accepted."""
    assert export_file_path(tmp_path, name) == tmp_path / EXPORT_DIRECTORY / name


@pytest.mark.parametrize(
    "name",
    [
        "",
        ".json",
        "../x.json",
        "a/b.json",
        "a\\b.json",
        "/etc/passwd.json",
        ".hidden.json",
        "x.txt",
        "x.json.exe",
        "x.json\n",
        "x\x00.json",
        "ä.json",
        "x y.json",
        f"{'a' * 65}.json",
    ],
)
def test_export_file_name_rules(name: str, tmp_path: Path) -> None:
    """T-04-32: separators, parent references, hidden names, other extensions and long names are rejected."""
    with pytest.raises(PortabilityError) as raised:
        export_file_path(tmp_path, name)
    assert raised.value.reason == "bad_file_name"


def test_write_export_creates_a_private_file(tmp_path: Path) -> None:
    """T-04-33: the directory is 0700, the file 0600, an existing file is replaced and no temporary file stays."""
    path = write_export(tmp_path, "backup.json", '{"first": true}')

    directory = tmp_path / EXPORT_DIRECTORY
    assert path == directory / "backup.json"
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert path.read_text(encoding="utf-8") == '{"first": true}'

    # An existing file is replaced and keeps the private mode; a too open directory of ours is closed again
    directory.chmod(0o755)
    write_export(tmp_path, "backup.json", '{"second": true}')
    assert path.read_text(encoding="utf-8") == '{"second": true}'
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert [p.name for p in directory.iterdir()] == ["backup.json"]


def test_write_export_refuses_a_symlink(tmp_path: Path) -> None:
    """T-04-32: a name that is a symlink to another file is refused and the other file is unchanged."""
    other = tmp_path / "other.txt"
    other.write_text("precious", encoding="utf-8")
    directory = tmp_path / EXPORT_DIRECTORY
    directory.mkdir(mode=0o700)
    (directory / "link.json").symlink_to(other)

    with pytest.raises(PortabilityError) as raised:
        write_export(tmp_path, "link.json", "overwritten")

    assert raised.value.reason == "symlink"
    assert other.read_text(encoding="utf-8") == "precious"
    assert [p.name for p in directory.iterdir()] == ["link.json"]


def test_write_export_refuses_a_symlinked_directory(tmp_path: Path) -> None:
    """A directory that is a symlink would send the file elsewhere, so it is refused as well."""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    config = tmp_path / "config"
    config.mkdir()
    (config / EXPORT_DIRECTORY).symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(PortabilityError) as raised:
        write_export(config, "backup.json", "x")

    assert raised.value.reason == "symlink"
    assert list(elsewhere.iterdir()) == []
