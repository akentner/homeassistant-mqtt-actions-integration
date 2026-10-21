"""Hub removal keeps every device on the broker by default and deletes everywhere only on an explicit option (D-11)."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import probatio
import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_fire_mqtt_message

from custom_components.mqtt_actions import manager as manager_module
from custom_components.mqtt_actions.config_flow import MqttActionsConfigFlow
from custom_components.mqtt_actions.const import (
    CONF_DELETE_DEVICES_ON_REMOVE,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_EXPORT,
    CONF_EXPORT_PREFIX,
    CONF_INSTANCE_ID,
    DOMAIN,
    ISSUE_DEVICE_PREFIXES,
    ISSUE_DISCOVERY_DISABLED,
    ISSUE_KEPT_DUPLICATES,
    ISSUE_LOCAL_ACTION_FAILED_PREFIX,
    LOCAL_ACTIONS_STORE_KEY,
    STORE_KEY,
    STORE_PUBLISHED,
    STORE_VERSION,
)
from custom_components.mqtt_actions.local_actions_store import LocalActionsStoreError
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from tests.documents import document_payload, make_spec
from tests.fake_broker import FakeBroker, FakeGateway
from tests.helpers import open_hub_settings
from tests.log_helpers import own_warnings

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

BASE = "mqtt_actions"
ON_ACTIONS = [{"action": "test.on"}]
ORPHAN_ID = "5d9c1b0e-7c55-4c1e-8a11-0f7c3a9b2d44"


def _preload_store(hass_storage: dict[str, Any], key: str = STORE_KEY, *, published: list[str]) -> None:
    hass_storage[key] = {
        "version": STORE_VERSION,
        "minor_version": 1,
        "key": key,
        "data": {STORE_PUBLISHED: published},
    }


async def _setup(hass: HomeAssistant, entry: Any) -> Any:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


def _publishes(mqtt_mock: Any, topic: str) -> list[tuple]:
    """Return the (payload, qos, retain) tuples published on a topic, in order."""
    return [call.args[1:4] for call in mqtt_mock.async_publish.call_args_list if call.args[0] == topic]


def _empty_publishes(mqtt_mock: Any) -> list[str]:
    return [call.args[0] for call in mqtt_mock.async_publish.call_args_list if call.args[1] in {"", b""}]


def _own_issues(hass: HomeAssistant) -> list[str]:
    return sorted(issue_id for domain, issue_id in ir.async_get(hass).issues if domain == DOMAIN)


def _create_issues(hass: HomeAssistant, device_id: str) -> None:
    """Create one issue per per-device family plus the discovery-disabled issue."""
    for prefix in ISSUE_DEVICE_PREFIXES:
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{prefix}{device_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="action_failed",
            translation_placeholders={"trigger": "t", "device": "d", "time": "now", "error": "e"},
        )
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_DISCOVERY_DISABLED,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_DISCOVERY_DISABLED,
    )


# ----------------------------------------------------------------------------------------------- options flow


async def test_hub_has_options_flow_with_delete_choice(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    entry = await _setup(hass, make_hub_entry())

    result = await open_hub_settings(hass, entry)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    fields = {
        field["name"]: field
        for field in probatio.to_field_list(result["data_schema"], custom_serializer=cv.custom_serializer)
    }
    # The export switch and its prefix share the form since Phase 5 (D-03); the export has its own tests
    assert set(fields) == {CONF_DELETE_DEVICES_ON_REMOVE, CONF_DISCOVERY_EXPORT, CONF_EXPORT_PREFIX}
    assert fields[CONF_DELETE_DEVICES_ON_REMOVE]["selector"] == {"boolean": {}}
    suggested = {key.schema: key.description.get("suggested_value") for key in result["data_schema"].schema}
    assert suggested[CONF_DELETE_DEVICES_ON_REMOVE] is False

    result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_DELETE_DEVICES_ON_REMOVE: True})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_DELETE_DEVICES_ON_REMOVE: True}

    # The stored choice is what the form shows the next time
    again = await open_hub_settings(hass, entry)
    (key,) = (key for key in again["data_schema"].schema if key.schema == CONF_DELETE_DEVICES_ON_REMOVE)
    assert key.description["suggested_value"] is True
    # A hub still has no reconfigure step (D-01)
    assert not hasattr(MqttActionsConfigFlow, "async_step_reconfigure")


async def test_saving_the_option_publishes_nothing(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    devices_before = dict(entry.runtime_data.devices)
    mqtt_mock.async_publish.reset_mock()

    result = await open_hub_settings(hass, entry)
    await hass.config_entries.options.async_configure(result["flow_id"], {CONF_DELETE_DEVICES_ON_REMOVE: True})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert mqtt_mock.async_publish.call_args_list == []
    assert entry.runtime_data.devices == devices_before


# ---------------------------------------------------------------------------------------------------- removal


async def test_remove_with_default_keeps_everything_retained(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """T-03-11: without the option nothing on the broker is cleared; the local state and every issue go."""
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    _preload_store(hass_storage, published=[ORPHAN_ID])
    entry = await _setup(hass, make_hub_entry([sub]))
    _create_issues(hass, device_id)
    mqtt_mock.async_publish.reset_mock()

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _empty_publishes(mqtt_mock) == []
    assert STORE_KEY not in hass_storage
    assert _own_issues(hass) == []
    assert hass.config_entries.async_get_entry(entry.entry_id) is None


async def test_remove_with_delete_clears_everywhere(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    _preload_store(hass_storage, published=[ORPHAN_ID])
    entry = await _setup(hass, make_hub_entry([sub], options={CONF_DELETE_DEVICES_ON_REMOVE: True}))
    instance_id = entry.data[CONF_INSTANCE_ID]
    _create_issues(hass, device_id)

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    for owned_id in (device_id, ORPHAN_ID):
        assert _publishes(mqtt_mock, discovery_topic("homeassistant", owned_id))[-1] == ("", 1, True)
        assert _publishes(mqtt_mock, config_topic(BASE, owned_id))[-1] == ("", 1, True)
        assert _publishes(mqtt_mock, state_topic(BASE, owned_id))[-1] == ("", 1, True)
    assert _publishes(mqtt_mock, availability_topic(BASE, instance_id))[-1] == ("", 1, True)
    assert STORE_KEY not in hass_storage
    assert _own_issues(hass) == []


async def test_keep_leaves_the_offline_availability(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable, make_switch_subentry: Callable
) -> None:
    """D-11: orphans of a kept hub show unavailable, so the last availability publish is offline, not empty."""
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    instance_id = entry.data[CONF_INSTANCE_ID]

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _publishes(mqtt_mock, availability_topic(BASE, instance_id))[-1] == ("offline", 1, True)


@pytest.mark.parametrize("delete", [False, True], ids=["keep", "delete"])
async def test_both_modes_remove_store_and_every_issue_prefix(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    delete: bool,
) -> None:
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    options = {CONF_DELETE_DEVICES_ON_REMOVE: True} if delete else {}
    entry = await _setup(hass, make_hub_entry([sub], options=options))
    _create_issues(hass, device_id)
    assert len(_own_issues(hass)) == len(ISSUE_DEVICE_PREFIXES) + 1

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert STORE_KEY not in hass_storage
    assert _own_issues(hass) == []


@pytest.mark.parametrize("delete", [False, True], ids=["keep", "delete"])
async def test_hub_removal_deletes_the_kept_duplicates_warning(
    hass: HomeAssistant,
    mqtt_mock: Any,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    *,
    delete: bool,
) -> None:
    """The kept-duplicates warning is one issue per instance, so the removal deletes it by its id (FIX-08, D-02)."""
    options = {CONF_DELETE_DEVICES_ON_REMOVE: True} if delete else {}
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)], options=options))
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_KEPT_DUPLICATES,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_KEPT_DUPLICATES,
        translation_placeholders={"count": "1", "customized": "switch.lamp", "rejected": "—"},
    )
    assert _own_issues(hass) == [ISSUE_KEPT_DUPLICATES]

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _own_issues(hass) == []


async def test_delete_mode_survives_unavailable_mqtt(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    entry = await _setup(
        hass,
        make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)], options={CONF_DELETE_DEVICES_ON_REMOVE: True}),
    )
    assert await hass.config_entries.async_unload(entry.entry_id)

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ):
        assert await hass.config_entries.async_remove(entry.entry_id)

    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert STORE_KEY not in hass_storage
    assert [r for r in caplog.records if r.levelno == logging.WARNING and "MQTT" in r.getMessage()]


async def test_keep_mode_needs_no_mqtt(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)]))
    assert await hass.config_entries.async_unload(entry.entry_id)
    caplog.clear()

    with patch(
        "custom_components.mqtt_actions.mqtt_gateway.mqtt.async_publish", side_effect=HomeAssistantError("down")
    ) as publish:
        assert await hass.config_entries.async_remove(entry.entry_id)

    publish.assert_not_called()
    assert hass.config_entries.async_get_entry(entry.entry_id) is None
    assert STORE_KEY not in hass_storage
    assert [r for r in own_warnings(caplog, exact=True) if "MQTT" in r.getMessage()] == []


# ------------------------------------------------------------------------------------------ test seams


async def test_removal_functions_accept_gateway_and_store_key(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    sub = make_switch_subentry("Lamp", on=ON_ACTIONS)
    device_id = sub["data"][CONF_DEVICE_ID]
    entry = make_hub_entry([sub])
    entry.add_to_hass(hass)
    gateway = FakeGateway(FakeBroker(), hass)
    _preload_store(hass_storage, "x.state", published=[ORPHAN_ID])
    _preload_store(hass_storage, STORE_KEY, published=[])

    await manager_module.async_remove_all_devices(hass, entry, gateway=gateway, store_key="x.state")

    cleared = {topic for topic, payload, retain in gateway.published if payload == "" and retain}
    for owned_id in (device_id, ORPHAN_ID):
        assert {
            discovery_topic("homeassistant", owned_id),
            config_topic(BASE, owned_id),
            state_topic(BASE, owned_id),
        } <= cleared
    assert availability_topic(BASE, entry.data[CONF_INSTANCE_ID]) in cleared
    assert "x.state" not in hass_storage
    # The production key is untouched: the seam removes only what it was given
    assert STORE_KEY in hass_storage

    _preload_store(hass_storage, "x.state", published=[ORPHAN_ID])
    published_before = len(gateway.published)
    await manager_module.async_remove_local_state(hass, entry, store_key="x.state")
    assert "x.state" not in hass_storage
    assert len(gateway.published) == published_before
    assert STORE_KEY in hass_storage

    # Without the keywords the production defaults apply
    await manager_module.async_remove_local_state(hass, entry)
    assert STORE_KEY not in hass_storage


# ------------------------------------------------------------------------------- local actions (Plan 11-09, D-08)

TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / DOMAIN / "translations"
# Three distinct devices with saved local records, five records in total; none of them is mirrored, so all three are
# orphan-only. The count names devices, never triggers or action steps (D-08)
LOCAL_A = "0b6f3c1e-1d2a-4f5b-9c8d-7e6f5a4b3c21"
LOCAL_B = "1c7e4d2f-2e3b-4a6c-8d9e-8f7a6b5c4d32"
LOCAL_C = "2d8f5e3a-3f4c-4b7d-9e0f-9a8b7c6d5e43"
LOCAL_DEVICE_COUNT = 3


def _local_row(device_id: str, kind: str, state_value: str, mode: str = "additive") -> dict[str, Any]:
    return {
        "device_id": device_id,
        "kind": kind,
        "state_value": state_value,
        "label": state_value,
        "mode": mode,
        "actions": [{"action": "test.local"}, {"action": "test.local_two"}],
    }


LOCAL_ROWS = [
    _local_row(LOCAL_A, "switch", "ON"),
    _local_row(LOCAL_A, "switch", "OFF", "replacement"),
    _local_row(LOCAL_B, "switch", "ON"),
    _local_row(LOCAL_C, "select", "party"),
    _local_row(LOCAL_C, "select", "away", "replacement"),
]


def _seed_local_store(hass_storage: dict[str, Any], key: str = LOCAL_ACTIONS_STORE_KEY) -> None:
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": {"records": LOCAL_ROWS}}


def _create_local_issue(hass: HomeAssistant, device_id: str) -> str:
    issue_id = f"{ISSUE_LOCAL_ACTION_FAILED_PREFIX}{device_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="local_action_failed",
        translation_placeholders={"device": "d", "trigger": "t", "time": "now", "error": "e"},
    )
    return issue_id


@pytest.mark.parametrize("path", ["keep", "delete", "unloaded"])
async def test_every_removal_path_deletes_the_local_store_and_local_issues(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    path: str,
) -> None:
    """D-08: keep, delete and an unloaded hub all leave neither Store key nor any issue, local ones included."""
    _seed_local_store(hass_storage)
    options = {CONF_DELETE_DEVICES_ON_REMOVE: True} if path == "delete" else {}
    entry = await _setup(hass, make_hub_entry([make_switch_subentry("Lamp", on=ON_ACTIONS)], options=options))
    assert entry.runtime_data.local_action_counts().devices == LOCAL_DEVICE_COUNT
    local_issues = [_create_local_issue(hass, device_id) for device_id in (LOCAL_A, LOCAL_C)]
    assert set(local_issues) <= set(_own_issues(hass))
    if path == "unloaded":
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert LOCAL_ACTIONS_STORE_KEY in hass_storage, "an unload is not a removal and keeps the local actions"

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert LOCAL_ACTIONS_STORE_KEY not in hass_storage
    assert STORE_KEY not in hass_storage
    assert _own_issues(hass) == []


async def test_a_late_save_cannot_recreate_the_local_store(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
) -> None:
    """T-11-28: a save that arrives after the removal is refused, so the deleted local Store never comes back."""
    _seed_local_store(hass_storage)
    entry = await _setup(hass, make_hub_entry())
    manager = entry.runtime_data
    # The late callback writes through the stopped Manager's own Store object
    late_store = manager._local_store
    records = late_store.records
    assert len(records) == len(LOCAL_ROWS)

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert LOCAL_ACTIONS_STORE_KEY not in hass_storage

    with pytest.raises(LocalActionsStoreError):
        await late_store.async_save_records(records)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert LOCAL_ACTIONS_STORE_KEY not in hass_storage


async def _deliver_mirror(hass: HomeAssistant) -> str:
    """Deliver one foreign Switch document; the mirror has no local record and must not raise the count."""
    spec = make_spec(name="Mirrored without records", on=ON_ACTIONS)
    async_fire_mqtt_message(hass, config_topic(BASE, spec.device_id), document_payload(spec), retain=True)
    await hass.async_block_till_done(wait_background_tasks=True)
    return spec.device_id


@pytest.mark.parametrize("loaded", [True, False], ids=["loaded", "unloaded"])
async def test_removal_settings_name_the_distinct_device_count(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    *,
    loaded: bool,
) -> None:
    """D-08: the warning counts distinct devices with records, orphan-only ones included, not triggers or steps."""
    _seed_local_store(hass_storage)
    entry = await _setup(hass, make_hub_entry())
    mirror_id = await _deliver_mirror(hass)
    assert mirror_id in entry.runtime_data.mirrors
    if not loaded:
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)

    result = await open_hub_settings(hass, entry)

    assert result["step_id"] == "settings"
    assert result["description_placeholders"] == {"local_action_device_count": str(LOCAL_DEVICE_COUNT)}
    # Opening the settings never rewrites or removes the local Store
    assert hass_storage[LOCAL_ACTIONS_STORE_KEY]["data"]["records"] == LOCAL_ROWS


async def test_removal_settings_count_zero_without_local_records(
    hass: HomeAssistant, mqtt_mock: Any, make_hub_entry: Callable
) -> None:
    entry = await _setup(hass, make_hub_entry())
    await _deliver_mirror(hass)

    result = await open_hub_settings(hass, entry)

    assert result["description_placeholders"] == {"local_action_device_count": "0"}


@pytest.mark.parametrize(
    ("language", "rendered"),
    [
        ("en", "local actions of 3 devices on this instance"),
        ("de", "lokale Aktionen für 3 Geräte auf dieser Instanz gelöscht"),
    ],
)
def test_removal_settings_text_renders_the_device_count(language: str, rendered: str) -> None:
    """MIR-15: both languages name the count through the one placeholder the settings step supplies."""
    raw = json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
    description = raw["options"]["step"]["settings"]["description"]
    assert "{local_action_device_count}" in description
    assert rendered in description.format(local_action_device_count=LOCAL_DEVICE_COUNT)


async def test_local_removal_seam_removes_only_the_given_local_key(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
) -> None:
    entry = make_hub_entry()
    entry.add_to_hass(hass)
    gateway = FakeGateway(FakeBroker(), hass)
    _seed_local_store(hass_storage, "x.local")
    _seed_local_store(hass_storage)

    await manager_module.async_remove_local_state(hass, entry, store_key="x.state", local_store_key="x.local")
    assert "x.local" not in hass_storage
    assert LOCAL_ACTIONS_STORE_KEY in hass_storage

    _seed_local_store(hass_storage, "x.local")
    await manager_module.async_remove_all_devices(
        hass, entry, gateway=gateway, store_key="x.state", local_store_key="x.local"
    )
    assert "x.local" not in hass_storage
    assert LOCAL_ACTIONS_STORE_KEY in hass_storage

    # Without the keyword the production local key goes
    await manager_module.async_remove_local_state(hass, entry)
    assert LOCAL_ACTIONS_STORE_KEY not in hass_storage


# ---------------------------------------------------------------------- leftover local actions (Plan 11-16, G-03)


async def _submit_new_hub(hass: HomeAssistant) -> dict[str, Any]:
    """Run the hub user flow with the schema defaults and return the submit result."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    await hass.async_block_till_done(wait_background_tasks=True)
    return result


async def test_new_hub_never_loads_local_actions_left_by_an_earlier_hub(
    hass: HomeAssistant, mqtt_mock: Any, hass_storage: dict[str, Any]
) -> None:
    """G-03, D-08, D-02: a new hub removes a leftover local Store before its entry exists and starts without it."""
    _seed_local_store(hass_storage)
    assert hass.config_entries.async_entries(DOMAIN) == []

    result = await _submit_new_hub(hass)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.local_action_counts().devices == 0, (
        "a new hub must not load the local actions of an earlier, removed hub"
    )
    assert LOCAL_ACTIONS_STORE_KEY not in hass_storage
