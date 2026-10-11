---
phase: 08-real-instance-verification
fixed_at: 2026-10-11T16:30:00Z
review_path: .planning/phases/08-real-instance-verification/08-REVIEW.md
iteration: 1
supersedes: "first 08-REVIEW-FIX.md as of commit 4a894b2 (git show 4a894b2:.planning/phases/08-real-instance-verification/08-REVIEW-FIX.md)"
findings_in_scope: 5
fixed: 5
skipped: 0
skipped_parts: 3
deferred: 3
status: partial
---

# Phase 8: Code Review Fix Report (second review)

**Fixed at:** 2026-10-11T16:30:00Z
**Source review:** .planning/phases/08-real-instance-verification/08-REVIEW.md (second review, committed at `e256cba`)
**Iteration:** 1

This report replaces the first phase-08 fix report. That report is kept in git at commit `4a894b2`
(`git show 4a894b2:.planning/phases/08-real-instance-verification/08-REVIEW-FIX.md`).

**Summary:**
- Findings in scope: 5 (CR-01, WR-01, WR-02, WR-03, WR-04). The caller set the scope; IN-01 to IN-03 are deferred to v1.1.
- Fixed: 5. WR-04 was fixed by the tests written for the other four.
- Skipped parts: 3. In WR-02, entity-id rename detection and assistant-exposure detection were skipped. In WR-03, the
  Repairs issue was deferred. For the first two, core behaves differently from what the review assumed (see the core
  assumption check).
- Deferred: IN-01, IN-02, IN-03.
- TDD: for each finding there is a failing-test commit first, then one fix commit. Before each fix commit the failure
  was checked with `uv run pytest <test> -q`.
- Logic changes: CR-01, WR-02 and WR-03 change decision rules. Their status is **fixed: requires human
  verification**.

## Core assumption check

All checks were made against the installed Home Assistant 2026.9.4 at `.venv/lib/python3.14/site-packages/homeassistant/`.

### Confirmed

| # | Review claim | Evidence |
|---|--------------|----------|
| C1 | When core discovers an entity whose registry row is disabled, it aborts the add. | `helpers/entity_platform.py:1096-1103`: `if entity.registry_entry and entity.registry_entry.disabled:` leads to `entity.add_to_platform_abort()`. |
| C2 | The abort installs a registry hook that clears the discovery topic when the row is removed. | `components/mqtt/entity.py:1232-1252` (`add_to_platform_abort`): if `self.registry_entry is not None`, it registers `async_track_entity_registry_updated_event(..., async_clear_discovery_topic_if_entity_removed)`. `entity.py:770-777`: on `action == "remove"` the hook calls `async_remove_discovery_payload`. `entity.py:758-767` then publishes `None` with `retain=True` to `ATTR_DISCOVERY_TOPIC`. |
| C3 | This applies to device-based discovery topics. | `components/mqtt/discovery.py:414` takes the device branch (`component == CONF_DEVICE`) for every component of the device payload. `discovery.py:507-512` sets `ATTR_DISCOVERY_TOPIC: topic`, which is the received topic `homeassistant/device/<id>/config`. Removing one row therefore wipes the whole retained device payload, which for a mirror is the other instance's export. |
| C4 | The hook stays until the same hash is discovered again or MQTT unloads. | `entity.py:1016-1020`: a new `MqttDiscoveryUpdateMixin` with the same hash pops the hook. `components/mqtt/__init__.py:719-721`: unload pops all hooks. `_restart` in the tests only reloads this integration's entry, so the hook survives it, as it would in production between HA restarts. |
| C5 | Empirical check | The new manager-level test failed before the fix with `(None, 0, True)` published on `homeassistant/device/<id>/config` after `_restart` and `_quiet_period_passes`. The helper-level tests failed too: `remove_replay_twins` returned 3, and `async_take_over` published a `None` clear. |
| C6 | `device_class` on a registry row is a user override. | `helpers/entity_registry.py:1536`: a new row gets `device_class = None`. `:1506`: only a deleted record restores it. The integration's own class is `original_device_class`. |
| C7 | `hidden_by=INTEGRATION` marks a wrapped entity. | Switch-as-X and group helpers hide the entity they wrap. Note: core MQTT also sets it from a discovery payload with `visible_by_default: false` (`components/mqtt/entity.py:1674-1676`). The integration's own exports do not set that key. |

### Deviations (implemented differently or skipped)

| # | Review claim | What core does | Consequence |
|---|--------------|----------------|-------------|
| D1 | WR-02: `entry.aliases` truthy marks a customization. | `helpers/entity_registry.py:1532`: every new row gets `aliases = [COMPUTED_NAME]`, so the review's test would mark every row as customized. Migration 1.22 (`:942-949`) prepends `None` (COMPUTED_NAME) to existing rows. | Implemented with the correct rule: `list(entry.aliases) != [er.COMPUTED_NAME]`. |
| D2 | WR-02: entity-id rename detected with `not entry.entity_id.startswith(f"{entry.domain}.{entry.suggested_object_id or entry.object_id_base or ''}")`. | Core's generation rule is `_async_generate_entity_id` (`helpers/entity_registry.py:1339-1388`) together with `_async_get_full_entity_name` (`:493ff`). It slugifies (`:1319`), prefixes the device name (`name_by_user` first), plus the effective area and floor according to the `entity_id_parts` registry setting. It falls back to `<platform>_<unique_id>` and adds `_2`, `_3` on conflicts. The review's prefix test ignores all of this. Core's own "automatic entity id" is `async_regenerate_entity_id(entry)` (`:1390-1414`). HA uses it in `config/entity_registry/get_automatic_entity_ids` (`components/config/entity_registry.py:340-363`) to show which ids the user customized. But a restored row keeps the entity id of its deleted record when that id is free (`helpers/entity_registry.py:1518-1520`). Its automatic id also changes whenever the device name, the area or `entity_id_parts` changes. | **Skipped.** Probe: `_is_customized` was extended with `async_regenerate_entity_id(entry) != entry.entity_id` as an uncommitted scratch change, and the suite was run. Result: 8 failed, 1512 passed. All 8 failures are UAT-04 guard tests, for example `test_a_receiver_disables_the_duplicate_that_a_foreign_core_prefix_export_restores`. The rows restored from deleted records counted as "renamed", so the guard left them enabled. That would undo UAT-04. The gap is pinned as a strict `xfail` parameter `entity_id_rename` in both WR-02 parametrized tests. |
| D3 | WR-02: `options` (assistant exposure such as `conversation.should_expose`) is a user customization, filtered by "keys core sets by itself". | `components/homeassistant/exposed_entities.py:247-271`: core itself writes `{assistant: {"should_expose": <default>}}` the first time an assistant asks. `:67-69`: `DEFAULT_EXPOSED_ASSISTANT = {"conversation": True}`, and `switch` is in `DEFAULT_EXPOSED_DOMAINS` (`:32-44`). Without replaying core's preference logic, a stored `should_expose` cannot be told apart from the user's choice. | **Exposure skipped.** Other option keys are implemented (`_has_user_options` ignores only `should_expose`, which is `CORE_OPTION_KEYS`). The test `..._whose_only_option_is_the_exposure_core_stores_itself` pins that exposure alone does not protect a duplicate. |
| D4 | WR-01: "apply the same step before both removals in `async_take_over`" (legacy row and native twin). | The review's probe found only `mqtt` deleted records with `disabled_by=None`. The twin is a row of this integration's platform. Only the native platform creates that `(domain, mqtt_actions, unique_id)` again, and the entity it creates is meant to be enabled. | Applied to the legacy removal only. Disabling the twin before removal would make a later native entity come up disabled. The reason is written as a comment at `takeover.py` in `async_take_over`. |

## Fixed Issues

### CR-01: Removing an MQTT row that core discovered while disabled clears the retained topic

**Status:** fixed: requires human verification (decision rule change)
**Files modified:** `custom_components/mqtt_actions/takeover.py`, `custom_components/mqtt_actions/manager.py`, `tests/test_takeover.py`, `tests/test_export_guard_receiver.py`, `tests/test_native_replay.py`
**Commits:** test `612b0b7`, fix `ea258df`
**Applied fix:** This is the review's option 1: a disabled MQTT row is never removed.
- `remove_replay_twins` skips any legacy row with `disabled_by is not None`. An enabled row is still disabled and then
  removed in one synchronous step.
- `async_take_over` (the duplicate branch) leaves a disabled legacy row in place.
- These docstrings were rewritten: `remove_replay_twins` (was "nothing is published here" with a "may remove" claim),
  `disable_duplicates` (was "The replay catch may remove the disabled entry ..."),
  `Manager._arm_duplicate_guard` (`manager.py`, was the same claim), and the comment in `async_take_over`.

**Tests:**
- Manager level: `test_export_guard_receiver.py::test_a_row_a_foreign_export_created_disabled_survives_the_restart_and_its_export_is_never_cleared`.
  A native mirror receives a foreign core-prefix export, so the row is born disabled. Then `_restart` and
  `_quiet_period_passes` run. The test asserts no falsy publish on `homeassistant/device/<id>/config`, and that the
  row stays, disabled.
- Helper level: `test_takeover.py::test_remove_replay_twins_leaves_rows_core_discovered_while_they_were_disabled_so_nothing_is_cleared`
  and `test_take_over_leaves_a_disabled_legacy_duplicate_in_place_so_core_clears_nothing`.

**Behaviour change, deliberate (please review):** A disabled duplicate now stays in the registry. So does the MQTT
device it sits on, instead of being cleaned at the next start. Without broker knowledge the integration cannot tell
whether core holds an abort hook for the row. That is the review's option 2, and `takeover.py` deliberately has no
broker knowledge. Disabled rows that exports create (G5) already behave like this by design. Three existing tests
encoded the old cleanup, and their expectations were changed in the test commit:
- `test_export_guard_receiver.py`: G6 was renamed to
  `test_the_export_off_cycle_leaves_the_disabled_row_in_place_across_the_restart`. The row now stays disabled across
  the restart, and the returning export finds it disabled.
- `test_native_replay.py::test_a_replay_during_the_pass_leaves_no_duplicate[before_the_clear|after_the_clear]` and
  `test_a_replay_before_a_restart_of_a_finished_native_owner_is_cleaned_at_the_next_start`: these now use
  `_assert_no_working_duplicate`. The duplicate guard disables the replayed switch before the quiet period ends. That
  row stays disabled without a state, and every enabled replayed row is gone. D-05 ("no duplicate entity") still holds
  in the sense of no second working entity. It no longer holds in the sense of no registry row.

### WR-01: `async_take_over` removed enabled legacy rows without disabling them

**Status:** fixed
**Files modified:** `custom_components/mqtt_actions/takeover.py`, `tests/test_takeover.py`
**Commits:** test `2b50a1a`, fix `e37e7ba`
**Applied fix:** In the duplicate branch, an enabled legacy row is disabled (`INTEGRATION`) before
`async_remove`, so its deleted record restores as disabled. A disabled legacy row is not removed (CR-01). The twin's
removal is unchanged (D4).
**Test:** `test_take_over_disables_a_legacy_duplicate_before_it_removes_it_so_no_enabled_tombstone_stays`. It uses the
`test_a_customized_native_twin_is_kept_over_an_untouched_legacy_entry` setup. All three `mqtt` deleted records have
`disabled_by=INTEGRATION`, and there is no falsy publish on the topic. Before the fix all three records were `None`.

### WR-02: `_is_customized` missed common user customizations

**Status:** fixed: requires human verification (partial: entity-id rename and exposure skipped, see D2 and D3)
**Files modified:** `custom_components/mqtt_actions/takeover.py`, `tests/test_takeover.py`
**Commits:** test `4bc91d8`, fix `754999e`
**Applied fix:** `_is_customized` now also counts:
- aliases other than the default `[COMPUTED_NAME]` (D1);
- a `device_class` override;
- any option key other than core's own `should_expose` (`_has_user_options`, `CORE_OPTION_KEYS`);
- a hidden state.

The docstring explains why a renamed entity id is not detected.
**Tests:** Two parametrized tests, one per field (`aliases`, `device_class`, `options`, `hidden_by_integration`,
plus `entity_id_rename` as a strict xfail):
- `test_disable_duplicates_leaves_an_entry_enabled_that_holds_any_user_customization`. Before the fix:
  `assert 1 == 0`.
- `test_remove_replay_twins_leaves_a_newer_entry_that_holds_any_user_customization`. Before the fix:
  `assert 3 == 2`.

There is also the exposure pin `test_disable_duplicates_still_disables_an_entry_whose_only_option_is_the_exposure_core_stores_itself`.
It passes before and after, because it is a guard for D3.

### WR-03: Tie-breaks in `disable_duplicates` picked the wrong row

**Status:** fixed: requires human verification (partial: the Repairs issue is deferred)
**Files modified:** `custom_components/mqtt_actions/takeover.py`, `tests/test_takeover.py`
**Commits:** test `05b62df`, fix `31d6e5a`
**Applied fix:**
- New `_is_turned_off(entry)`: the row is disabled for any reason, or `hidden_by is USER`. `disable_duplicates` skips a
  legacy row whose twin is turned off, so it never disables the last enabled row.
- `disable_duplicates` skips a customized legacy row whatever the twin holds, which covers the both-customized case.
- `remove_replay_twins` skips a legacy row whenever `_is_customized(legacy)` is true, whatever its age.
- `_is_customized` no longer counts `disabled_by is USER` or `hidden_by is USER`. Those states mean the user rejected
  the row. Only `hidden_by is INTEGRATION`, the wrapper case, counts.

The `disable_duplicates` docstring was updated.
**Tests:**
- `test_disable_duplicates_keeps_the_legacy_entry_when_the_user_turned_the_native_twin_off`: 2x2 cases, twin
  `disabled_by=USER` or `hidden_by=USER`, legacy untouched or named "Kitchen".
- `test_disable_duplicates_disables_a_legacy_entry_the_user_hid`: the mirror case.
- `test_with_both_entries_customized_neither_the_guard_nor_the_catch_touches_the_legacy_entry`: the replayed row has
  `name` and `labels`, the moved twin has `name`. The catch returns 2 (buttons only) and the guard returns 0. Name,
  labels and the enabled state survive.

**Deferred part:** The review also suggested a Repairs issue that names both entity ids when both rows are
customized. It was not implemented: it is new user-facing UI with translations, and it is the same feature IN-03
asks for, which is deferred to v1.1. Both-customized rows are now left alone, with no hint to the user.

### WR-04: The tests covered only the narrowest sub-case

**Status:** fixed by the tests listed under CR-01 to WR-03. One of them goes through `Manager` (`_restart` +
`_quiet_period_passes`) and asserts no falsy-payload publish on the core-prefix topic.
**Commits:** `612b0b7`, `2b50a1a`, `4bc91d8`, `05b62df`
**Not added:** a dedicated test for the event-listener path (`manager.py`, `_on_duplicate_registry_updated`) with a
customized row. It runs the same `takeover.disable_duplicates` that the new helper tests cover.

## Skipped / Deferred Issues

### IN-01: A row that raises mid-loop keeps the emptied device and loses the partial count

**File:** `custom_components/mqtt_actions/takeover.py` (`remove_replay_twins`), `manager.py` (`_remove_replay_twins`)
**Reason:** deferred to v1.1 (user constraint)

### IN-02: The no-clear guarantee for loaded rows depends on an HA-internal eager task

**File:** `custom_components/mqtt_actions/takeover.py` (`remove_replay_twins`)
**Reason:** deferred to v1.1 (user constraint)

### IN-03: A customized legacy row kept enabled stays a permanent enabled duplicate without a hint

**File:** `custom_components/mqtt_actions/takeover.py` (`disable_duplicates`)
**Reason:** deferred to v1.1 (user constraint). WR-03 now also keeps both-customized rows enabled, so IN-03 covers
more cases. The Repairs hint from WR-03 belongs to the same v1.1 work.

## Verification

Everything ran in the **main checkout** (`workflow.use_worktrees: false`, no worktree was created). The numbers can be
reproduced from the tree at `31d6e5a`. `.planning/config.json` has unrelated local changes and was never staged.

- Baseline before any change: `uv run pytest tests -q`: `1516 passed in 115.06s`.
- After all fixes: `uv run pytest tests -q`: **`1535 passed, 2 xfailed in 120.14s`**. The 2 xfails are the strict
  `entity_id_rename` parameters (D2).
- `uv run ruff check`: **`All checks passed!`**
- `uv run ruff format --check` on the touched files (`takeover.py`, `manager.py`, `tests/test_takeover.py`,
  `tests/test_export_guard_receiver.py`, `tests/test_native_replay.py`): **`5 files already formatted`**
- Each test commit was run against the code before its fix and failed for the stated reason:
  - CR-01: 4 failed, including `(None, 0, True)` on the core-prefix topic.
  - WR-01: deleted records `None` where `INTEGRATION` was expected.
  - WR-02: 8 failed, plus 2 xfailed.
  - WR-03: 6 failed.

---

_Fixed: 2026-10-11T16:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
