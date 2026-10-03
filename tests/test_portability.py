"""Export document and the private export file: no ids in the content, a bare file name, 0700 and 0600 (D-11)."""

import json
import os
import stat
import uuid
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.mqtt_actions import portability
from custom_components.mqtt_actions.const import (
    CONF_DEVICE_ID,
    EXPORT_DIRECTORY,
    EXPORT_FORMAT,
    EXPORT_VERSION,
    MAX_ACTION_DEPTH,
    MAX_DOCUMENT_BYTES,
    MAX_IMPORT_BYTES,
    MAX_IMPORT_DEVICES,
    SUBENTRY_SELECT,
    SUBENTRY_SWITCH,
)
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


# --- import: envelope and preparation (D-11) --------------------------------------------------------------------------

OWNER = "instance-local"
OWNER_NAME = "Local instance"


def _envelope(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {"format": EXPORT_FORMAT, "export_version": EXPORT_VERSION, "devices": []}
    document.update(overrides)
    return document


def test_parse_export_accepts_the_export_envelope() -> None:
    """D-11: format, version and a devices list give the item list; anything else is a fixed reason code."""
    items = [build_content(make_spec(name="Lamp", on=SWITCH_ACTIONS))]
    assert portability.parse_export(_envelope(devices=items)) == items
    assert portability.parse_export(_envelope()) == []

    for broken in (
        [],
        "text",
        None,
        _envelope(format="something_else"),
        {"export_version": 1, "devices": []},
        _envelope(devices="not a list"),
        _envelope(devices={"a": 1}),
        _envelope(export_version="1"),
        _envelope(export_version=True),
        _envelope(export_version=0),
    ):
        with pytest.raises(PortabilityError) as raised:
            portability.parse_export(broken)
        assert raised.value.reason == "bad_format"
        assert raised.value.index is None

    with pytest.raises(PortabilityError) as too_new:
        portability.parse_export(_envelope(export_version=EXPORT_VERSION + 1))
    assert too_new.value.reason == "too_new"


def test_prepare_import_assigns_new_ids_and_owner() -> None:
    """Every item gets a fresh uuid4 and the shared content of the item, nothing else."""
    switch = make_spec(name="Lamp", on=SWITCH_ACTIONS, run_on_startup=True, run_mode="restart", breaker_max_runs=7)
    select = make_spec(
        SUBENTRY_SELECT,
        name="Scene",
        options=[("a", "First", SWITCH_ACTIONS), ("b", "Second", [])],
        breaker_window=30,
    )
    items = [build_content(switch), build_content(select)]

    prepared = portability.prepare_import(items, owner=OWNER, owner_name=OWNER_NAME)

    assert [device.index for device in prepared] == [1, 2]
    assert [(device.kind, device.name) for device in prepared] == [
        (SUBENTRY_SWITCH, "Lamp"),
        (SUBENTRY_SELECT, "Scene"),
    ]
    ids = [device.device_id for device in prepared]
    assert len(set(ids)) == 2
    assert switch.device_id not in ids
    assert all(uuid.UUID(device_id).version == 4 for device_id in ids)
    for device, item in zip(prepared, items, strict=True):
        expected = {key: value for key, value in item.items() if key not in {"kind", "name"}}
        assert device.data == {**expected, CONF_DEVICE_ID: device.device_id}
        assert device.spec.device_id == device.device_id
    first, second = prepared
    assert (first.spec.run_on_startup, first.spec.run_mode, first.spec.breaker_max_runs) == (True, "restart", 7)
    assert second.spec.breaker_window == 30
    assert [trigger.value for trigger in second.spec.triggers.values()] == ["a", "b"]


def test_forged_bookkeeping_keys_are_ignored() -> None:
    """T-04-36: owner, ids, rev, hash and schema version inside an item never reach the new device."""
    forged = {
        **build_content(make_spec(name="Lamp", on=SWITCH_ACTIONS)),
        "owner": "someone-else",
        "owner_name": "Someone else",
        "device_id": "forged-id",
        "rev": 99,
        "hash": "f" * 64,
        "schema_version": 99,
    }

    (device,) = portability.prepare_import([forged], owner=OWNER, owner_name=OWNER_NAME)

    assert device.device_id != "forged-id"
    assert uuid.UUID(device.device_id).version == 4
    assert device.data[CONF_DEVICE_ID] == device.device_id
    assert {"owner", "owner_name", "rev", "hash", "schema_version"}.isdisjoint(device.data)
    assert "forged-id" not in json.dumps(device.data)
    assert "someone-else" not in json.dumps(device.data)


def test_subentry_payload_drops_kind_and_name_and_adds_the_device_id() -> None:
    """The shared helper that the adoption plan reuses."""
    content = build_content(make_spec(name="Lamp", on=SWITCH_ACTIONS))

    payload = portability.subentry_payload(content, "new-id")

    assert payload == {**{k: v for k, v in content.items() if k not in {"kind", "name"}}, CONF_DEVICE_ID: "new-id"}
    assert "kind" in content
    assert "name" in content


# --- import: hostile input, denied services and the private file (D-11, T-04-36 to T-04-38) ---------------------


def _valid_item(name: str = "Lamp") -> dict[str, Any]:
    return build_content(make_spec(name=name, on=SWITCH_ACTIONS))


def _item_with(**changes: Any) -> dict[str, Any]:
    return {**_valid_item("Second"), **changes}


def _nested(depth: int) -> list[dict[str, Any]]:
    """Return an action list whose nesting is deeper than `depth` container levels."""
    actions: list[dict[str, Any]] = [{"action": "test.on"}]
    for _ in range(depth):
        actions = [{"if": [], "then": actions}]
    return actions


def _run(value: Any) -> list[portability.PreparedDevice]:
    """Run the whole pure pipeline of an import: text parser, envelope, preparation."""
    if isinstance(value, str):
        value = portability.parse_import_text(value)
    items = portability.parse_export(value)
    return portability.prepare_import(items, owner=OWNER, owner_name=OWNER_NAME)


def _doc(*devices: Any) -> dict[str, Any]:
    return _envelope(devices=list(devices))


HOSTILE = [
    pytest.param("{this is not json", "not_json", None, id="not-json"),
    pytest.param("", "not_json", None, id="empty-text"),
    pytest.param([_valid_item()], "bad_format", None, id="json-list"),
    pytest.param(_doc(_valid_item(), "a string"), "invalid_device", 2, id="item-not-a-dict"),
    pytest.param(_doc(_valid_item(), _item_with(kind="timer")), "invalid_device", 2, id="unknown-kind"),
    pytest.param(_doc(_item_with(kind=["switch"])), "invalid_device", 1, id="unhashable-kind"),
    pytest.param(
        _doc(_valid_item(), _item_with(kind=SUBENTRY_SELECT, options="none")),
        "invalid_device",
        2,
        id="select-no-options",
    ),
    pytest.param(
        _doc(_valid_item(), _item_with(on_change_to_on=[{"bogus": 1}])), "invalid_actions", 2, id="bad-action-structure"
    ),
    pytest.param(
        _doc(_item_with(on_change_to_on=_nested(MAX_ACTION_DEPTH))), "invalid_device", 1, id="nested-too-deep"
    ),
    pytest.param(
        _doc(_valid_item(), _item_with(name="x" * (MAX_DOCUMENT_BYTES + 1))), "too_large", 2, id="item-too-large"
    ),
    pytest.param(_doc(*[_valid_item()] * (MAX_IMPORT_DEVICES + 1)), "too_many", None, id="too-many-items"),
    pytest.param(_doc(_item_with(run_mode="sideways")), "invalid_device", 1, id="bad-run-mode"),
    pytest.param(_doc(_item_with(breaker_window=float("nan"))), "invalid_device", 1, id="nan"),
]


@pytest.mark.parametrize(("value", "reason", "index"), HOSTILE)
def test_parse_and_prepare_reject_hostile_input(value: Any, reason: str, index: int | None) -> None:
    """T-04-36, T-04-38: hostile input is refused with a fixed reason code and the position of the offending item."""
    with pytest.raises(PortabilityError) as raised:
        _run(value)

    assert raised.value.reason == reason
    assert raised.value.index == index
    assert str(raised.value) == reason


def test_the_maximum_number_of_items_is_accepted() -> None:
    """The cap is inclusive: exactly MAX_IMPORT_DEVICES items parse."""
    items = portability.parse_export(_doc(*[_valid_item()] * MAX_IMPORT_DEVICES))
    assert len(items) == MAX_IMPORT_DEVICES


@pytest.mark.parametrize(
    "actions",
    [
        [{"action": "shell_command.run"}],
        [{"action": "homeassistant.restart"}],
        [
            {
                "choose": [
                    {
                        "conditions": [{"condition": "state", "entity_id": "light.lamp", "state": "on"}],
                        "sequence": [{"action": "python_script.run"}],
                    }
                ]
            }
        ],
    ],
    ids=["denied-domain", "denied-service", "nested-in-choose"],
)
def test_denied_services_are_rejected(actions: list[dict[str, Any]]) -> None:
    """T-04-36: an item that statically calls a denied service is refused, also when nested in a choose."""
    with pytest.raises(PortabilityError) as raised:
        _run(_doc(_valid_item(), _item_with(on_change_to_off=actions)))

    assert raised.value.reason == "denied_service"
    assert raised.value.index == 2


def test_a_templated_service_name_is_accepted() -> None:
    """Imports are owned, and a template cannot be judged statically, so it is not refused."""
    (device,) = _run(_doc(_item_with(on_change_to_on=[{"action": "{{ 'shell_' ~ 'command.run' }}"}])))
    assert device.name == "Second"


def test_parse_import_text_returns_the_value() -> None:
    assert portability.parse_import_text('{"a": [1, 2]}') == {"a": [1, 2]}


def _write_import_file(directory: Path, name: str, content: bytes) -> Path:
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return path


def test_read_import_reads_a_regular_file(tmp_path: Path) -> None:
    """A regular file below mqtt_actions/ is read as text."""
    _write_import_file(tmp_path / EXPORT_DIRECTORY, "backup.json", '{"é": 1}'.encode())

    assert portability.read_import(tmp_path, "backup.json") == '{"é": 1}'


@pytest.mark.parametrize("name", ["../x.json", "a/b.json", ".hidden.json", "x.txt", "", "x\n.json"])
def test_read_import_refuses_a_bad_name(tmp_path: Path, name: str) -> None:
    """T-04-37: only a bare name of the fixed pattern reaches the disk."""
    with pytest.raises(PortabilityError) as raised:
        portability.read_import(tmp_path, name)
    assert raised.value.reason == "bad_file_name"


def test_read_import_refuses_what_is_not_a_plain_file(tmp_path: Path) -> None:
    """T-04-37: a missing file or directory, a directory in place of a file, a symlink and bad UTF-8 are unreadable."""
    directory = tmp_path / EXPORT_DIRECTORY

    # No directory at all
    with pytest.raises(PortabilityError) as no_directory:
        portability.read_import(tmp_path, "backup.json")
    assert no_directory.value.reason == "file_unreadable"

    _write_import_file(directory, "plain.json", b"{}")
    (directory / "dir.json").mkdir()
    other = tmp_path / "other.json"
    other.write_text("{}", encoding="utf-8")
    (directory / "link.json").symlink_to(other)
    _write_import_file(directory, "binary.json", b"\xff\xfe{}")

    for name in ("missing.json", "dir.json", "link.json", "binary.json"):
        with pytest.raises(PortabilityError) as raised:
            portability.read_import(tmp_path, name)
        assert raised.value.reason == "file_unreadable", name
    assert portability.read_import(tmp_path, "plain.json") == "{}"


def test_read_import_refuses_a_symlinked_directory(tmp_path: Path) -> None:
    """The private directory must be a real directory, as for the export."""
    elsewhere = tmp_path / "elsewhere"
    _write_import_file(elsewhere, "backup.json", b"{}")
    config = tmp_path / "config"
    config.mkdir()
    (config / EXPORT_DIRECTORY).symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(PortabilityError) as raised:
        portability.read_import(config, "backup.json")
    assert raised.value.reason == "file_unreadable"


def test_read_import_refuses_a_file_above_the_cap_before_reading(tmp_path: Path) -> None:
    """T-04-38: the size is checked on the opened file; the cap itself is still accepted."""
    directory = tmp_path / EXPORT_DIRECTORY
    path = _write_import_file(directory, "big.json", b"")
    os.truncate(path, MAX_IMPORT_BYTES + 1)

    with pytest.raises(PortabilityError) as raised:
        portability.read_import(tmp_path, "big.json")
    assert raised.value.reason == "too_large"

    os.truncate(path, MAX_IMPORT_BYTES)
    assert len(portability.read_import(tmp_path, "big.json")) == MAX_IMPORT_BYTES
