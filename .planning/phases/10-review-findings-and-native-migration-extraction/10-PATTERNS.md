# Phase 10: Review Findings and Native Migration Extraction - Pattern Map

**Mapped:** 2026-10-16
**Files analyzed:** 14
**Analogs found:** 14 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `.github/workflows/ci.yml`, `validate.yml` | config | CI trigger | `.github/workflows/release.yml:4-6` (`push.tags`) | exact |
| `custom_components/mqtt_actions/native_migration.py` (new, FIX-02) | service (collaborator) | event-driven (timers, registry listener) | `presence.py` `PresenceManager` (319-337) | exact |
| `custom_components/mqtt_actions/manager.py` (FIX-02 move source, FIX-06, FIX-08 call sites) | service | event-driven | itself | n/a |
| `custom_components/mqtt_actions/takeover.py` (FIX-08 keep predicates, read-only reuse) | utility | registry CRUD | itself (`_is_customized` 463, `keeps_enabled_legacy_row` 288) | n/a |
| `custom_components/mqtt_actions/const.py` (new `ISSUE_KEPT_DUPLICATES`) | config | n/a | `ISSUE_DUPLICATE_INSTANCE_ID` (const.py ~290) | exact |
| `translations/en.json`, `de.json` (new issue) | config | n/a | `issues.native_cutover_waiting` (en.json:303-306) | exact |
| `tests/helpers.py` (new, FIX-03) | test utility | n/a | `tests/log_helpers.py`, `tests/documents.py` | exact |
| `tests/test_native_start.py`, `test_cutover.py`, `test_export_guard_receiver.py`, `test_docs.py`, `test_native_replay.py`, `test_native_cleanup.py`, `test_presence.py`, `test_discovery_content.py` (import edits) | test | n/a | — | n/a |
| `tests/test_takeover.py` (FIX-01, FIX-07 loud tests; helper source) | test | registry I/O | itself (`test_plain_clear_on_a_loaded_entity_deletes_the_registry_entry` 276) | exact |
| start-up ordering spy test (new, in `tests/test_native_start.py` or `test_manager.py`) | test | n/a | `tests/test_native_start.py` (uses `patch`, `AsyncMock`, `DEFAULT`) | role-match |
| FIX-04 guard test (in `tests/test_export_guard_receiver.py`) | test | event-driven | same file | exact |
| FIX-06 test (in `tests/test_native_replay.py`) | test | event-driven | same file (`_cancel_replay_catch` at 251/259) | exact |
| FIX-08 tests (new or in `test_native_replay.py` / `test_hub_removal.py`) | test | n/a | `tests/test_hub_removal.py`, `tests/test_cutover.py` (cutover hint issue) | role-match |
| `README.md`, `docs/troubleshooting.md`, `tests/test_docs.py` (FIX-05) | docs + test | n/a | `tests/test_docs.py:47` `test_readme_states_what_the_approval_hash_binds` | exact |

## Pattern Assignments

### `.github/workflows/ci.yml` / `validate.yml` (folded todo)
Current (ci.yml:4-7, validate.yml:4-7):
```yaml
  push:
    # A version tag runs these checks once, through release.yml
    tags-ignore:
      - "v*.*.*"
```
Add `branches: ["**"]` beside `tags-ignore` in both files. Nothing else.

### `native_migration.py` (new collaborator)
**Analog:** `presence.py` header and constructor.

Imports (presence.py:19-58): `from __future__ import annotations`, HA `callback`, `async_call_later`, `ir`, `er`; `from .const import (...)`; `from . import takeover`; manager only under `TYPE_CHECKING`:
```python
if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from homeassistant.core import CALLBACK_TYPE
    from .manager import Manager
```
Constructor (presence.py:319-337):
```python
class PresenceManager:
    """Publishes the heartbeat of this instance and keeps the roster of the others."""

    def __init__(self, manager: Manager) -> None:
        self._manager = manager
        ...
```
Wiring in Manager (manager.py:523-525):
```python
        self.sync = SyncManager(self)
        self.presence = PresenceManager(self)
        self.retrigger = RetriggerCoordinator(self)
```
-> add `self.migration = NativeMigration(self)` after these (it reads `manager.presence`, `manager.gateway`, `manager._native`).

**State that moves** (manager.py:541-561): `_legacy_this_run`?, `_clear_unconfirmed`, `cutover_settle_seconds`, `_cancel_cutover`, `_cancel_replay_catch`, `_replay_catch_retries`, `_replay_catch_armed`, `_cancel_duplicate_guard`, `_cutover_ready`, `_cutover_hint`, `_reload_scheduled`. `self._native = NativeState()` (line 535) STAYS in Manager (D-09). Planner must check each attribute with `grep -n "self\.<attr>" manager.py` — any use outside migration code means it stays or gets a property.

**Methods that move** (current lines, re-check at plan time):
- cutover: `_arm_cutover` 828, `_on_cutover_due` 835, `_start_cutover_check` 1303, `_show_cutover_hint` 1331, `_clear_cutover_hint` 1355, `on_roster_changed` 1297 (presence calls it — keep a Manager delegator or repoint presence)
- takeover/gate: `_topic_verdict` 880, `_ids_that_may_empty_the_topic` 898, `_remove_replay_twins` 914, `_async_native_takeover` ~1360+
- replay catch: `_arm_replay_catch` 950, `on_discovery_emptied` 963 (external caller, keep delegator), `_on_replay_catch_due` 991, `_rearm_or_log_replay_catch` 1121, `_may_clear` 1201
- guard: `_duplicate_guard_ids` 1218, `_disarm_duplicate_guard` 1223, `_arm_duplicate_guard` 1230, `_on_duplicate_registry_updated` 1253, `_disable_duplicates` 1278
- stays in Manager (shared with presence/heartbeat): `kept_legacy_ids` 845, `_native_device_ids` 841 (verify callers).

**Start-up order to preserve** (manager.py `async_start`, inside lock then after):
```python
            await self._async_reconcile_locked(startup=True)
            await self._async_native_takeover()
            self._arm_duplicate_guard()
            await self._async_publish_owned()
            self._check_discovery_enabled()
        await self._async_publish_availability(AvailabilityState.ONLINE)
        await self.presence.async_publish_heartbeat()
        self._arm_cutover()
        self._arm_replay_catch()
```
Replace with `await self.migration.async_takeover()`, `self.migration.arm_guard()`, ... `self.migration.arm_timers()` in the same slots. All `@callback` methods stay sync (Pitfall 8).

**Test-access edit allowed by D-10:** `tests/test_native_replay.py:251,259` read `_manager(legacy.entry)._cancel_replay_catch` -> `.migration._cancel_replay_catch`. No `patch("custom_components.mqtt_actions.manager...")` string targets exist today (grep showed none), so only `patch.object` targets on the manager need checking: `grep -n "patch.object" tests/*.py`.

### `manager.py` FIX-06 (in moved replay-catch loop)
Per-device isolation pattern to follow (manager.py:1278-1294, `_disable_duplicates`):
```python
        disabled = 0
        for device_id in device_ids:
            try:
                disabled += takeover.disable_duplicates(...)
            except Exception as err:  # noqa: BLE001
                LOGGER.warning("The check for an enabled duplicate of a device raised an unexpected error")
                LOGGER.debug("The check for an enabled duplicate failed with %s", type(err).__name__)
        if disabled:
            LOGGER.info("Disabled %d duplicate entities ...", disabled)
```
Apply to the catch loop around `_remove_replay_twins` (914) / `_on_replay_catch_due` (991): keep the partial count, set an `errored` flag, flush registries (`takeover.async_flush_registries`) when `removed > 0 or errored`. Never catch inside `takeover.remove_replay_twins` (takeover.py:304).

### FIX-08 Repairs warning
**Issue create/delete analog:** `_show_cutover_hint` (manager.py:1331-1358) — already delete-then-create and cached to avoid rebuilds:
```python
        if blocking == self._cutover_hint:
            return
        self._cutover_hint = blocking
        shown = ", ".join(escape_markdown(name) for name in blocking[:CUTOVER_HINT_MAX_NAMES])
        instances = f"{shown} …" if len(blocking) > CUTOVER_HINT_MAX_NAMES else shown
        ir.async_delete_issue(self._hass, DOMAIN, ISSUE_NATIVE_CUTOVER_WAITING)
        ir.async_create_issue(
            self._hass, DOMAIN, ISSUE_NATIVE_CUTOVER_WAITING,
            is_fixable=False, severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_NATIVE_CUTOVER_WAITING,
            translation_placeholders={"instances": instances},
        )
```
Copy for `_show_kept_duplicates(rows: tuple[str, ...])` / `_clear_kept_duplicates()`; cap constant like `CUTOVER_HINT_MAX_NAMES`. Lives in `native_migration.py`. Call at end of takeover pass, at end of `_disable_duplicates`, at end of replay catch (D-04).
**List source:** reuse `takeover._is_customized` (takeover.py:463) and the WR-03 rejected-twin predicate in `takeover.py` (around `keeps_enabled_legacy_row` 288); add a small public read-only function in takeover.py returning `(entity_id, reason)` for enabled kept core rows — never publishes, never removes.
**Constant:** const.py next to `ISSUE_DUPLICATE_INSTANCE_ID` (one per instance, NOT in `ISSUE_DEVICE_PREFIXES`):
```python
ISSUE_KEPT_DUPLICATES: Final = "kept_duplicates"
```
**Hub-removal cleanup:** manager.py:429-434 — add to the set:
```python
            or issue_id in {ISSUE_DISCOVERY_DISABLED, ISSUE_DUPLICATE_INSTANCE_ID, ISSUE_NATIVE_CUTOVER_WAITING}
```
**Translations:** add `issues.kept_duplicates` in en.json and de.json next to `native_cutover_waiting` (en.json:303); `tests/test_translations.py` checks key parity.

### `tests/helpers.py` (new, FIX-03)
**Analog:** `tests/log_helpers.py` (whole file, 26 lines): module docstring, `from __future__ import annotations`, typing imports under `TYPE_CHECKING`, public functions with docstrings.
Helpers to move from `tests/test_takeover.py` (drop `_` prefix): `setup_legacy_device` 67, `_published_payload` 96, `_mqtt_entry_id` 103, `customize_mqtt_device` 107, `legacy_entity_ids` 117, `_deliver` 127, `_subentry` 133, `_mqtt_device` 137, `_move_entities` 143, `_discovery_clears` 155, `_falsy_publishes` 160, `_forward_native_switch` 177, `_run_takeover` 193, plus `LegacyDevice`. Also helpers imported from `test_native_start`, `test_native_entities`, `test_discovery_export`, `test_native_replay`, `test_diagnostics` (find with `grep -n "^from tests.test_" tests/*.py`). Example consumer today (test_native_start.py:36-37):
```python
from tests.documents import FOREIGN_OWNER, document_payload, make_spec
from tests.test_takeover import (
```
Target: `from tests.helpers import (...)`. Exit check: `grep -n "from tests.test_" tests/` is empty.

### FIX-01 / FIX-07 loud core-contract tests (`tests/test_takeover.py`)
Target under test: `takeover.async_flush_registries` (takeover.py:443-460):
```python
    for registry in (er.async_get(hass), dr.async_get(hass)):
        try:
            await registry._store.async_save(registry._data_to_save())  # noqa: SLF001
        except Exception:  # noqa: BLE001
            LOGGER.warning(...)
            flushed = False
    return flushed
```
FIX-01: change a row, call it, assert return `True` and `hass_storage["core.entity_registry"]` / `["core.device_registry"]` contain the change without `async_fire_time_changed`. Plus structural check `callable(registry._data_to_save)`. Since the function catches, an `AttributeError` yields `False` -> assert on `True` makes it loud.
FIX-07: analog `test_plain_clear_on_a_loaded_entity_deletes_the_registry_entry` (test_takeover.py:276) and `_discovery_clears` / `_falsy_publishes` helpers (155/160) for "no empty retained publish" assertion. Failure message names `Entity._async_registry_updated` eager task. Never skip/xfail (D-08).

### FIX-05 docs test
**Analog:** `tests/test_docs.py:47` `test_readme_states_what_the_approval_hash_binds` — reads README text and asserts a claim sentence. Add one for "re-enabled duplicate is disabled again at the next start" in README and `docs/troubleshooting.md` (§ around lines 102-141).

## Shared Patterns

### Logging (T-04-14)
Counts only, never broker or registry content; detail at DEBUG with `type(err).__name__` (manager.py:1288-1294). Applies to native_migration.py, FIX-06, FIX-08.

### Repairs issues
`ir.async_create_issue(..., is_fixable=False, severity=..., translation_key=...)` + `ir.async_delete_issue` (runner.py:246-279, manager.py:1343-1358). Broker-sourced text via `escape_markdown`; FIX-08 data is local registry data but cap the list.

### Collaborator back-reference
`Class(manager)` storing `self._manager`, manager imported only under `TYPE_CHECKING` (presence.py:52-58, 322-324).

## No Analog Found
None. The start-up ordering spy test has no direct precedent; build it with `patch.object(..., side_effect=...)` recording call order, using `unittest.mock` imports as in test_native_start.py:6.

## Metadata
**Search scope:** `custom_components/mqtt_actions/`, `tests/`, `.github/workflows/`
**Files scanned:** ~20
**Note:** manager.py line numbers are as of commit 6263692; re-map at plan time.
