"""
The Repairs warning for duplicates the guard keeps enabled (FIX-08, review 2 IN-03, D-01 to D-04).

The duplicate guard keeps a core MQTT row enabled next to its native twin when the user customized the row (WR-02) or
turned the twin off (WR-03). One non-fixable warning per instance lists those rows with their reason, follows the list
and goes away once none remains. It never removes, disables or enables a registry row.
"""

import dataclasses
import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.mqtt_actions import takeover
from custom_components.mqtt_actions.const import CONF_DEVICE_ID, DOMAIN
from custom_components.mqtt_actions.document import escape_markdown
from custom_components.mqtt_actions.native_migration import NativeMigration, kept_duplicates_placeholders
from custom_components.mqtt_actions.takeover import KeptReason
from tests.helpers import (
    create_mqtt_row,
    manager_of,
    native_entity_id,
    quiet_period_passes,
    restart_entry,
    seed_store,
    setup_entry,
)
from tests.log_helpers import OWN_LOGGER

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

# A literal on purpose: a RED run against code without the constant must fail on the missing issue, not on an import
ISSUE_ID = "kept_duplicates"
NONE_SHOWN = "—"


def _seed_native_instance(hass_storage: dict[str, Any]) -> None:
    seed_store(hass_storage, {"native": {"instance": True, "pending": [], "devices": []}})


async def _native_owner_with_a_guarded_row(
    hass: HomeAssistant, make_hub_entry: Callable, subentries: list[Any]
) -> tuple[MockConfigEntry, list[str]]:
    """Start a native instance with owned switch devices and let core create a duplicate the guard disables for each."""
    entry = await setup_entry(hass, make_hub_entry(subentries))
    rows = []
    for subentry in subentries:
        device_id = subentry["data"][CONF_DEVICE_ID]
        assert native_entity_id(hass, "switch", device_id) is not None
        row = create_mqtt_row(hass, "switch", device_id, device=True)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert er.async_get(hass).async_get(row).disabled_by is er.RegistryEntryDisabler.INTEGRATION
        rows.append(row)
    return entry, rows


def _kept_issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID)


async def test_a_customized_duplicate_kept_enabled_is_listed_in_one_warning(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-01, D-02: the row the user named and enabled again stays enabled, and one warning names it as customized."""
    _seed_native_instance(hass_storage)
    entry, (row,) = await _native_owner_with_a_guarded_row(hass, make_hub_entry, [make_switch_subentry("Lamp")])
    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(row, name="Kitchen lamp", disabled_by=None)

    await restart_entry(hass, entry)

    issue = _kept_issue(hass)
    assert issue is not None, "no kept_duplicates warning after the restart"
    assert issue.is_fixable is False
    assert issue.severity is ir.IssueSeverity.WARNING
    assert issue.translation_key == ISSUE_ID
    assert issue.translation_placeholders == {
        "count": "1",
        "customized": escape_markdown(row),
        "rejected": NONE_SHOWN,
    }
    kept = entity_registry.async_get(row)
    assert kept is not None
    assert (kept.name, kept.disabled_by) == ("Kitchen lamp", None)


async def _a_customized_duplicate_kept_enabled(
    hass: HomeAssistant, hass_storage: dict[str, Any], make_hub_entry: Callable, make_switch_subentry: Callable
) -> tuple[MockConfigEntry, str]:
    """The state of the first test after its restart: one customized duplicate kept enabled and listed."""
    _seed_native_instance(hass_storage)
    entry, (row,) = await _native_owner_with_a_guarded_row(hass, make_hub_entry, [make_switch_subentry("Lamp")])
    er.async_get(hass).async_update_entity(row, name="Kitchen lamp", disabled_by=None)
    await restart_entry(hass, entry)
    assert _kept_issue(hass) is not None
    return entry, row


async def test_a_duplicate_kept_because_the_native_twin_was_turned_off_is_listed_as_rejected(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-01, WR-03: an uncustomized duplicate next to a native switch the user disabled is listed as rejected."""
    _seed_native_instance(hass_storage)
    subentry = make_switch_subentry("Lamp")
    entry, (row,) = await _native_owner_with_a_guarded_row(hass, make_hub_entry, [subentry])
    entity_registry = er.async_get(hass)
    twin = native_entity_id(hass, "switch", subentry["data"][CONF_DEVICE_ID])
    entity_registry.async_update_entity(twin, disabled_by=er.RegistryEntryDisabler.USER)
    entity_registry.async_update_entity(row, disabled_by=None)

    await restart_entry(hass, entry)

    issue = _kept_issue(hass)
    assert issue is not None
    assert issue.translation_placeholders == {"count": "1", "customized": NONE_SHOWN, "rejected": escape_markdown(row)}
    assert entity_registry.async_get(row).disabled_by is None


async def test_the_warning_goes_away_once_no_kept_duplicate_remains_and_no_row_is_touched(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-02, CR-01: the refresh only reads the registry; once the user disabled the row the warning is gone."""
    entry, row = await _a_customized_duplicate_kept_enabled(hass, hass_storage, make_hub_entry, make_switch_subentry)
    entity_registry = er.async_get(hass)
    kept = entity_registry.async_get(row)

    await restart_entry(hass, entry)

    assert _kept_issue(hass) is not None
    assert entity_registry.async_get(row) == kept
    disabled = entity_registry.async_update_entity(row, disabled_by=er.RegistryEntryDisabler.USER)

    await restart_entry(hass, entry)

    assert _kept_issue(hass) is None
    assert entity_registry.async_get(row) == disabled


async def test_an_unchanged_list_keeps_a_dismissal_within_a_run(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-02, research Pitfall 15: a refresh with the same list leaves the issue, and with it the dismissal, alone."""
    entry, _row = await _a_customized_duplicate_kept_enabled(hass, hass_storage, make_hub_entry, make_switch_subentry)
    ir.async_ignore_issue(hass, DOMAIN, ISSUE_ID, True)
    assert _kept_issue(hass).dismissed_version is not None

    await restart_entry(hass, entry)

    issue = _kept_issue(hass)
    assert issue is not None
    assert issue.dismissed_version is not None, "a refresh with an unchanged list dropped the dismissal"


async def test_a_changed_list_shows_the_warning_again_after_a_dismissal(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-02, research Pitfall 15: a changed list deletes the dismissed issue and creates it again, active."""
    _seed_native_instance(hass_storage)
    entry, (first, second) = await _native_owner_with_a_guarded_row(
        hass, make_hub_entry, [make_switch_subentry("Lamp"), make_switch_subentry("Fan")]
    )
    entity_registry = er.async_get(hass)
    entity_registry.async_update_entity(first, name="Kitchen lamp", disabled_by=None)
    await restart_entry(hass, entry)
    assert _kept_issue(hass).translation_placeholders["count"] == "1"
    ir.async_ignore_issue(hass, DOMAIN, ISSUE_ID, True)
    entity_registry.async_update_entity(second, name="Ceiling fan", disabled_by=None)

    await restart_entry(hass, entry)

    issue = _kept_issue(hass)
    assert issue is not None
    assert issue.active is True
    assert issue.dismissed_version is None, "the changed list stayed hidden behind the earlier dismissal"
    assert issue.translation_placeholders["count"] == "2"


async def test_the_warning_is_refreshed_after_a_guard_pass_and_after_the_catch(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """D-04: the guard pass of a create event and the replay catch both re-evaluate the list, no listener of its own."""
    _seed_native_instance(hass_storage)
    subentry = make_switch_subentry("Lamp")
    original = NativeMigration._refresh_kept_duplicates
    with patch.object(NativeMigration, "_refresh_kept_duplicates", autospec=True, side_effect=original) as spy:
        entry = await setup_entry(hass, make_hub_entry([subentry]))
        after_setup = spy.call_count
        create_mqtt_row(hass, "switch", subentry["data"][CONF_DEVICE_ID], device=True)
        await hass.async_block_till_done(wait_background_tasks=True)

        assert spy.call_count == after_setup + 1, "the guard pass for the created row did not refresh the warning"

        await restart_entry(hass, entry)
        after_restart = spy.call_count
        await quiet_period_passes(hass)

        assert spy.call_count > after_restart, "the replay catch did not refresh the warning"


async def test_an_issue_restored_inactive_and_dismissed_is_created_again_active_and_undismissed(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
) -> None:
    """Research Pitfall 15: an issue HA restored inactive after its restart is rebuilt even with the same list."""
    entry, row = await _a_customized_duplicate_kept_enabled(hass, hass_storage, make_hub_entry, make_switch_subentry)
    placeholders = _kept_issue(hass).translation_placeholders
    ir.async_ignore_issue(hass, DOMAIN, ISSUE_ID, True)
    # What the issue registry restores from its Store after a restart of Home Assistant: inactive, dismissal kept
    registry = ir.async_get(hass)
    registry.issues[(DOMAIN, ISSUE_ID)] = dataclasses.replace(_kept_issue(hass), active=False)

    manager_of(entry).migration._refresh_kept_duplicates()

    issue = _kept_issue(hass)
    assert issue is not None
    assert issue.active is True
    assert issue.dismissed_version is None, "the restored dismissal hid the warning"
    assert issue.translation_placeholders == placeholders
    assert issue.is_persistent is False
    assert escape_markdown(row) == placeholders["customized"]


async def test_a_list_that_raises_leaves_the_warning_alone_and_logs_no_entity_id(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T-04-14: a raise while building the list keeps the issue as it is and logs a fixed warning and the type only."""
    entry, row = await _a_customized_duplicate_kept_enabled(hass, hass_storage, make_hub_entry, make_switch_subentry)
    before = _kept_issue(hass)
    caplog.clear()

    with (
        caplog.at_level(logging.DEBUG, logger=OWN_LOGGER),
        patch.object(takeover, "kept_duplicates", side_effect=RuntimeError(row)),
    ):
        manager_of(entry).migration._refresh_kept_duplicates()

    assert _kept_issue(hass) == before
    own = [record for record in caplog.records if record.name == OWN_LOGGER]
    assert [record.levelno for record in own] == [logging.WARNING, logging.DEBUG]
    assert "RuntimeError" in own[1].getMessage()
    for record in own:
        assert row not in record.getMessage()
        assert row not in str(record.args)


async def test_no_mqtt_entry_means_nothing_is_kept_and_the_warning_is_deleted(
    hass: HomeAssistant,
    mqtt_mock: Any,
    hass_storage: dict[str, Any],
    make_hub_entry: Callable,
    make_switch_subentry: Callable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-02: without an MQTT config entry the list is empty, so the refresh deletes the warning."""
    entry, _row = await _a_customized_duplicate_kept_enabled(hass, hass_storage, make_hub_entry, make_switch_subentry)
    manager = manager_of(entry)
    monkeypatch.setattr(manager.gateway, "mqtt_entry_id", lambda: None)

    manager.migration._refresh_kept_duplicates()

    assert _kept_issue(hass) is None


def test_the_placeholders_cap_and_escape_the_entity_ids() -> None:
    """D-01, T-10-13: sorted, escaped for Markdown, at most KEPT_DUPLICATES_MAX_SHOWN per reason, a dash for none."""
    customized = [f"switch.kitchen_lamp_{number:02d}" for number in range(12, 0, -1)]
    rows = [(entity_id, KeptReason.CUSTOMIZED) for entity_id in customized]
    rows.append(("select.hall_mode", KeptReason.TWIN_REJECTED))

    placeholders = kept_duplicates_placeholders(rows)

    shown = ", ".join(escape_markdown(entity_id) for entity_id in sorted(customized)[:10])
    assert placeholders == {
        "count": "13",
        "customized": f"{shown} …",
        "rejected": escape_markdown("select.hall_mode"),
    }
    assert placeholders["customized"].startswith("switch.kitchen\\_lamp\\_01, ")
    assert "switch.kitchen\\_lamp\\_11" not in placeholders["customized"]
    assert kept_duplicates_placeholders(rows[:2]) == {
        "count": "2",
        "customized": ", ".join(escape_markdown(entity_id) for entity_id in sorted(customized[:2])),
        "rejected": NONE_SHOWN,
    }
