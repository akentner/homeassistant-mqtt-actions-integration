"""
The Repairs warning for duplicates the guard keeps enabled (FIX-08, review 2 IN-03, D-01 to D-04).

The duplicate guard keeps a core MQTT row enabled next to its native twin when the user customized the row (WR-02) or
turned the twin off (WR-03). One non-fixable warning per instance lists those rows with their reason, follows the list
and goes away once none remains. It never removes, disables or enables a registry row.
"""

from typing import TYPE_CHECKING, Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.mqtt_actions.const import CONF_DEVICE_ID, DOMAIN
from custom_components.mqtt_actions.document import escape_markdown
from tests.helpers import create_mqtt_row, native_entity_id, restart_entry, seed_store, setup_entry

if TYPE_CHECKING:
    from collections.abc import Callable

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
