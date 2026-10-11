# Architecture Research

**Domain:** HA custom integration `mqtt_actions`, milestone v1.1: per-instance local actions on mirrors (MIR-01), plus the manager extraction IN-04 that comes first
**Researched:** 2026-10-11
**Confidence:** HIGH for integration points, because every seam below was read in `custom_components/mqtt_actions/*.py` at HEAD `8157225` and the HA facts were checked against core 2026.9.4 in `.venv`. MEDIUM for the UI entry point and for the "owner settings when unapproved" rule. Both are design calls and need owner confirmation in requirements.

## Headline Decisions

1. **Storage: a new additive Store key `local_actions`, owned by the Manager.** It is keyed by mirror device id, then by **StateValue** (not by `trigger_key`), and holds `{mode, actions}` per trigger. Do not store it in config subentries. HA enforces subentry `unique_id` across **all** subentry types (`config_entries.py:2764-2772`). An overlay subentry keyed by the mirror id would therefore abort the adoption's `async_add_subentry` with `already_configured`.
2. **Composition: a pure function** `compose(spec, owner_enabled, overlay) -> tuple[TriggerPlan, ...]` in a new HA-free module `local_actions.py`. `owner_enabled` is exactly `approval_state(id) == APPROVED`. A `replace` overlay drops the owner part. An `add` overlay appends the local part after the owner part (if the owner part is enabled).
3. **Still one Script per mirror.** The runner gets a plan-based build. Each part of a trigger is validated on its own: the static denylist (`_refuse_denied`) applies to the **owner part only**, and `GuardedTemplate` (`guard_actions`) still wraps the **whole** tree. Local actions get deep validation, no static denylist and no approval, but they keep the execution-time guard on templated service names, because `state` in their templates is a broker-chosen StateValue.
4. **The mirror spec is never mutated.** Local actions never enter `DeviceSpec`, `MirrorInfo`, `actions_hash`, `build_content`, the approval view YAML, documents, exports, diagnostics content or retrigger payloads.
5. **UI: the hub options flow becomes a menu** (`settings` | `local_actions`). The local-actions branch picks a mirror, then a trigger, then a form with mode (`none` / `add` / `replace`) plus an `ActionSelector`. It writes through a new manager API, not through `entry.options`.
6. **IN-04 extracts all native-migration orchestration** (cutover, takeover pass, replay catch, duplicate guard; `manager.py:819-1153` plus `_async_retry_unconfirmed_clears` at `1304-1319`) into `native_migration.py` → `NativeMigration(manager)`. This follows the `SyncManager` / `PresenceManager` / `RetriggerCoordinator` pattern. None of these lines are MIR-01 seams. The extraction lands first only so that MIR-01 edits a manager about 330 lines smaller with less merge risk. It is a pure move.

## Standard Architecture

### System Overview (v1.1 target)

```
┌──────────────────────────────── UI layer ─────────────────────────────────────┐
│ HubOptionsFlow (menu)          ApprovalRepairFlow      Native entities         │
│  ├ settings (old form)          (owner part only)      (switch/select/test     │
│  └ local_actions ─┐                                     buttons, mode select)  │
└───────────────────┼───────────────────────────────────────────────────────────┘
                    │ async_set_local_actions(id, state_value, mode, actions)
┌───────────────────▼──────────── Manager (lock) ───────────────────────────────┐
│ devices{} (owned)   mirrors{} (Device w/o subentry)   _approvals{}   _local{} ◄─NEW
│        │                       │                          │             │      │
│        │       _async_refresh_mirror_script(device)  ◄────┴─────────────┘      │
│        │                 │  compose(spec, approved, overlay)  ◄── local_actions.py (NEW, pure)
│        ▼                 ▼                                                     │
│   ActionRunner.async_build_plans(id, name, run_mode, plans, restricted) ◄─MOD   │
│        one Script per device: choose on trigger_key → [owner seq][local seq]    │
│ Collaborators: SyncManager · PresenceManager · RetriggerCoordinator ·           │
│                NativeMigration (NEW, IN-04: cutover/takeover/replay/guard)      │
└─────────────────────────────────────────┬─────────────────────────────────────┘
                                          │
┌─────────────────────────────────────────▼──────── Persistence ────────────────┐
│ Store mqtt_actions.state: last_acted, mirrors, approvals, revs, tripped,       │
│ transfers, instance_mode, device_modes, native, previous_states, local_actions ◄─NEW (additive) │
│ Config entry: hub data/options, owned device subentries (unchanged)            │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities (new vs modified)

| Component | Status | Responsibility in v1.1 |
|-----------|--------|------------------------|
| `native_migration.py` → `NativeMigration` | **NEW (IN-04)** | Owns the cutover timer and check plus its hint issue, the native takeover pass (`take_over_one`, `finish`, `defer`), the retry of unconfirmed clears, the replay catch timer and pass, and the duplicate guard listener. It also owns the per-run sets `legacy_this_run` and `clear_unconfirmed`, and exposes `is_deferred(id)`, `clear_pending(id)` and `forget(id)`. The persisted `NativeState` stays in Manager. |
| `local_actions.py` | **NEW (MIR-01)** | Pure, no HA imports at runtime (like `model.py`). Holds `LOCAL_MODE_ADD` / `LOCAL_MODE_REPLACE`, the frozen dataclasses `LocalTrigger(mode, actions)` and `TriggerPlan(key, label, owner, local)`, `parse_local_actions(stored)` (untrusted Store input), `compose(...)`, `owner_shadowed(spec, overlay)` and `overlay_counts(...)` for diagnostics. |
| `manager.py` | **MODIFIED** | Adds `self._local: dict[str, dict[str, LocalTrigger]]`, its load and save, `async_set_local_actions`, `local_overlay(device_id)` and `local_targets()` (mirrors plus orphaned overlays, for the flow). `_async_refresh_mirror_script` is rewritten around `compose`. `_sync_approval_issues` suppresses the approval request when the owner part is fully shadowed. The overlay is dropped in `async_remove_mirror` and `_async_drop_mirror`, and is not GC'd at start. The orchestration moves to `NativeMigration`, with delegations left in `async_start`, `async_stop`, `_async_republish`, `on_roster_changed`, `is_native`, `heals_discovery`, `_forget_native` and `_follow_native_status`. |
| `runner.py` | **MODIFIED** | New `async_build_plans(...)`. `async_build_device(spec, restricted)` becomes a wrapper that builds owner-only plans, so owned devices and mirrors without an overlay behave and assemble exactly as today. Validation and `_refuse_denied` run per part, and a setup error names the part (`"<label> (local)"`). |
| `config_flow.py` | **MODIFIED** | `HubOptionsFlow.async_step_init` becomes a menu, and the old form moves to step `settings`. New steps: `local_actions` (mirror chooser), `local_trigger` (trigger chooser) and `local_trigger_edit` (mode plus ActionSelector, owner YAML shown read-only). `_async_check_actions` (invalid actions plus the device_id warning) is lifted out of `_DeviceSubentryFlow` into a shared helper. |
| `const.py` | **MODIFIED** | Adds `STORE_LOCAL_ACTIONS = "local_actions"`, `CONF_LOCAL_MODE`, the mode words and caps (reuse `MAX_OPTIONS`, `MAX_MIRRORS` and `MAX_DOCUMENT_BYTES` as sanity caps). It may add the new IN-03 issue prefix to `ISSUE_DEVICE_PREFIXES`. |
| `trust.py` | **MODIFIED (small, optional)** | The `ApprovalView` may gain one line saying which triggers are replaced locally. Hash binding is unchanged. |
| `retrigger.py` | **MODIFIED (small)** | `_run` answers a trigger that is locally replaced with nothing as `ACK_ERROR, REASON_NO_ACTIONS`. **No new wire words** (see Anti-Pattern 5). |
| `services.py` | **MODIFIED (small)** | The `adopt_device` response gains `local_actions_dropped: bool` (an additive response key). |
| `diagnostics.py` | **MODIFIED (small)** | Each mirror row gains `local_triggers` and `local_replaced` counts. Do not use the key `actions`: it is in `TO_REDACT`. |
| `translations/en.json`, `de.json` | **MODIFIED** | Options menu, three steps, mode words, abort reasons (`not_loaded`, `no_mirrors`, `changed`) and the saved message. |
| `takeover.py` | unchanged by MIR-01 | IN-04 adds only the loud test for `_store` and `_data_to_save`. Review-2 IN-01 changes the partial count in `remove_replay_twins` and in its caller, which by then lives in `NativeMigration`. |

## Recommended Project Structure (delta)

```
custom_components/mqtt_actions/
├── native_migration.py   # NEW (IN-04): cutover, takeover pass, replay catch, duplicate guard orchestration
├── takeover.py           # registry primitives (unchanged role)
├── local_actions.py      # NEW (MIR-01): pure overlay model, Store parsing, compose()
├── manager.py            # lifecycle, owned/mirror state, Store, gates; now ~2300 lines before MIR-01
├── runner.py             # plan-based Script build
└── config_flow.py        # hub options menu + local-actions steps
tests/
├── helpers.py            # NEW (review-1 IN-02): shared fixtures/helpers, also used by MIR-01 tests
├── test_native_migration.py   # moved/renamed orchestration tests (+ IN-01 partial count)
├── test_local_actions.py      # NEW: pure compose/parse tests (table-driven)
├── test_manager_local_actions.py  # NEW: lifecycle, gates, Store round trip
├── test_options_flow_local_actions.py  # NEW
└── test_multi_instance_local.py   # NEW: local actions never reach the broker
```

### Structure Rationale

- **`local_actions.py` pure:** compose is the security-relevant decision ("what runs on this instance"). Kept HA-free, it can be tested as a truth table: approved / pending / blocked / no_actions × none / add / replace × empty / non-empty local, plus the orphaned-StateValue case. `model.py` and `document.py` follow the same split.
- **`native_migration.py` next to `takeover.py`:** `takeover.py` stays "registry primitives, never publishes". `native_migration.py` is "orchestration with timers, lock and publish order". This is the split the IN-04 finding proposes.

## Architectural Patterns

### Pattern 1: Overlay outside the spec, composed at Script-build time

**What:** The mirror's `DeviceSpec` stays exactly what the owner published. The overlay lives in `Manager._local[device_id]` and is combined only inside `_async_refresh_mirror_script`, the existing single choke point for mirror Script builds. Its callers are `async_apply_mirror` (new or changed document), `async_approve`, `_async_restore_mirrors` and, new, `async_set_local_actions`.
**When to use:** always for MIR-01. Never put local data on `Device` either. A `Device` does not exist for an orphaned overlay (a cached mirror dropped at start), and the overlay must survive that.
**Trade-offs:** one extra dict lookup per build. The gain is that `actions_hash`, `build_content`, `approval_sections` and diagnostics stay untouched by construction.

**Example (`local_actions.py`):**
```python
def compose(spec: DeviceSpec, *, owner_enabled: bool, overlay: Mapping[str, LocalTrigger]) -> tuple[TriggerPlan, ...]:
    """overlay is keyed by trigger_key(StateValue); computed from the stored StateValues at load."""
    plans = []
    for trigger in spec.triggers.values():
        local = overlay.get(trigger.key)
        owner = trigger.actions if owner_enabled else []
        if local is not None and local.mode == LOCAL_MODE_REPLACE:
            owner = []  # replace ignores the owner part whatever its approval says
        local_actions = local.actions if local is not None else []
        if owner or local_actions:
            plans.append(TriggerPlan(trigger.key, trigger.label, owner, local_actions))
    return tuple(plans)
```
Notes:
- `owner_enabled = manager.approval_state(id) is ApprovalState.APPROVED`. This already folds in "not denied", "has actions" and "approved hash == actions_hash".
- `replace` with an empty list is a legal, useful state: it mutes this trigger on this instance. `add` with an empty list equals no overlay; the flow should store it as "none".
- An overlay entry whose StateValue no longer exists in the spec (the owner removed the option) does not match. It stays stored and inert, and the flow lists it under "options that no longer exist" with a remove action.

### Pattern 2: Part-wise validation and gating inside one Script

**What:** The runner keeps "one Script per device, `choose` on `trigger_key`" (D-10/D-11: serial ordering and restart cancellation across all triggers). Each trigger branch becomes `[{"sequence": owner}, {"sequence": local}]` when both parts exist. With only one part, it becomes that part's list directly, so the owner-only assembly is byte-identical to today.
**When to use:** for every mirror build, and for owned devices through the wrapper.
**Trade-offs:** an owner-part runtime failure, including a `DeniedServiceCallError` from the guard, aborts that run before the local part runs. That is normal HA sequence semantics. Document "owner first, then local". Alternatives with two Scripts per device break D-10/D-11 (Anti-Pattern 3).

**Example (`runner.py` sketch):**
```python
for plan in plans:
    owner = await self._valid_part(spec_ref, plan.label, plan.owner, deny=restricted)       # _refuse_denied only here
    local = await self._valid_part(spec_ref, f"{plan.label} (local)", plan.local, deny=False)
    branch = owner + local if not (owner and local) else [{"sequence": owner}, {"sequence": local}]
    if branch:
        runnable.append((plan.key, branch))
# assemble choose, validate once, then: validated = guard_actions(validated) if restricted
```
`sequence` is a core action (`cv.SCRIPT_ACTION_SEQUENCE`, `helpers/script.py:_async_step_sequence`, verified in 2026.9.4). The guard stays on the whole validated tree. It only wraps `Template` values under `action`/`service`/`service_template`, so static local service names, even denied domains like `shell_command.x`, run unrestricted, as they would on an owned device. A templated local name that resolves to a denied service is stopped. That protects against `action: "{{ state }}"`, where `state` is a StateValue chosen by the owner's document.

### Pattern 3: Collaborator with back-reference (for IN-04)

**What:** `NativeMigration(manager)` is constructed in `Manager.__init__` like `self.sync = SyncManager(self)`. It reads `manager.hass`, `entry`, `gateway`, `lock`, `running`, `devices`, `mirrors`, `_native` (via a small internal accessor) and `_store` save through a manager method `async_save_now()`.
**When to use:** IN-04 only. Do not split mirror trust or approvals out in this milestone. `_async_refresh_mirror_script` is already the one seam MIR-01 needs, and a second extraction would double the regression surface before the feature work.
**Trade-offs:** the back-reference keeps the coupling visible but does not remove it. That is acceptable and consistent with the existing three collaborators.

**Scope of the move (pure move, no behavior change):**

| Moves to `NativeMigration` | Stays in `Manager` (thin delegation) |
|---|---|
| `_arm_cutover`, `_on_cutover_due`, `_start_cutover_check`, `_async_cutover_check`, `_show_cutover_hint`, `_clear_cutover_hint`, `cutover_settle_seconds`, `_cancel_cutover`, `_cutover_ready`, `_cutover_hint` | `on_roster_changed()` → `self.migration.on_roster_changed()` (presence.py:403, 457 call it) |
| `_native_device_ids`, `_remove_replay_twins`, `_arm_replay_catch`, `_on_replay_catch_due`, `_async_replay_catch`, `_cancel_replay_catch` | `async_start` order: `migration.async_takeover()` → `migration.arm_duplicate_guard()` → publish → `migration.arm_cutover()` / `arm_replay_catch()` |
| `_duplicate_guard_ids`, `_arm/_disarm_duplicate_guard`, `_on_duplicate_registry_updated`, `_disable_duplicates`, `_cancel_duplicate_guard` | `async_stop` → `migration.async_stop()` (cancels all three timers or listeners) |
| `_async_native_takeover`, `_async_take_over_one`, `_async_finish_takeover`, `_async_defer_takeover`, `_async_retry_unconfirmed_clears` | `_async_republish` → `migration.async_retry_unconfirmed_clears()` |
| `_legacy_this_run`, `_clear_unconfirmed` (as `is_deferred(id)`, `clear_pending(id)`, `defer_for_run(id)`, `forget(id)`) | `is_native`, `heals_discovery`, `_forget_native`, `_follow_native_status` read and write through those methods. `NativeState` (persisted) and `_schedule_native_reload` stay. |

Test impact is small. Grep shows tests use the `takeover.*` functions directly. Only `tests/test_native_replay.py:209,217` reads `manager._cancel_replay_catch`, which becomes `manager.migration._cancel_replay_catch` or a public `replay_catch_armed` property.

## Data Flow

### Edit flow (new)

```
Options flow: menu → local_actions (choose mirror) → local_trigger (choose trigger) → local_trigger_edit
    │ submit: shared _async_check_actions (deep validate + device_id warning, warn-then-confirm)
    ▼
manager.async_set_local_actions(device_id, state_value, mode, actions)      [under manager lock]
    ├─ refuse: not running / unknown target / StateValue not shaped like one / structure invalid
    ├─ self._local[...] updated; mode "none" or (add, []) removes the trigger; an empty device dict is removed
    ├─ await self._store.async_save(self._data_to_save())     # immediate, user-authored content
    ├─ runner.clear_issue(device_id)                           # stale setup issue belongs to the old actions
    └─ await self._async_refresh_mirror_script(mirror)         # only if the mirror is present
```

### Execution flow (changed only inside the Script)

```
state topic → Manager._on_message → tracker.handle → _run_trigger(device, value)
   → runner.can_run(id, trigger_key)   # runnable = keys of non-empty plans (owner and/or local)
   → mode gate (observe/disabled) → breaker → runner.enqueue(..., {"device_id", "state"})
   → Script: choose trigger_key → [owner sequence (if approved & not replaced)] → [local sequence]
```
The mode gate, breaker, startup window, test buttons (`async_press_test`, `_on_test_message`) and retrigger receiver all run the composed set without code changes, because they all go through `can_run` and `enqueue`. This is intended: local actions obey the device and instance mode exactly like owner actions.

### Script rebuild triggers (all go through `_async_refresh_mirror_script`)

| Event | Path today | MIR-01 effect |
|---|---|---|
| New mirror / restart restore | `async_apply_mirror` → `_build_mirror`; `_async_restore_mirrors` | The overlay is already loaded from the Store, so the first build includes local parts. Load order `_async_load_store` → `_async_restore_mirrors` already holds. |
| Owner changes content | `async_apply_mirror` → `_update_mirror` → refresh | The approval usually breaks (new `actions_hash`). The owner part drops, local parts keep running. The overlay is re-matched by StateValue. |
| User approves | `async_approve` → refresh | The owner part is added. Nothing runs retroactively (unchanged). |
| Local edit | `async_set_local_actions` → refresh | **new** |
| Re-pin after adoption, same content | `async_apply_mirror` early branch, no rebuild | The overlay stays. Same device id, same spec. |

### Lifecycle of an overlay

| Event | Rule | Where |
|---|---|---|
| Tombstone (owner deleted) / prune with positive evidence | **Drop.** Device ids are uuid4 and never come back. This mirrors "an approval does not outlive its mirror" (A10). | `async_remove_mirror` (`manager.py:1865`): add `self._local.pop(device_id, None)` |
| Adoption of the mirror | **Drop**, and report it. An owned device has no overlay, and local actions must never be published, so they cannot be merged into the new subentry. The `adopt_device` response gets `local_actions_dropped: true`, plus an info log naming the device via `shown()`. The rollback path in `_async_adopt_locked` restores the overlay together with the approval. | `_async_drop_mirror` (`manager.py:1603`); rollback in `except` at `1582-1593` |
| Restart with the cached mirror dropped (invalid payload, MAX_MIRRORS) | **Keep, inert.** Unlike `_approvals`, do **not** filter `_local` to `self.mirrors` in `async_start` (`manager.py:788-790`). User-authored content must not vanish on a transient. The mirror usually returns via the retained replay. | `async_start` |
| Owner re-pin to an adopter with new content | Same as a content change: kept, re-matched. | `async_apply_mirror` |
| Release-locally / follow-adopter (owned → mirror) | Nothing to do: the owned device had no overlay. | — |
| Duplicate-instance-id fix | Mirrors are untouched, so the overlay stays. | — |
| Hub removal (either mode) | Gone with the Store (`async_remove_local_state`). | — |
| Downgrade to v1.0.x | v1.0.x ignores the key on load but rewrites the Store without it, so the overlay is **lost**. Document this in the release notes. | — |

### Store schema (additive, version stays 1)

```json
"local_actions": {
  "<mirror device uuid>": {
    "<StateValue as shown>": {"mode": "add" | "replace", "actions": [ ...raw ActionSelector output... ]}
  }
}
```
- Write the key only when it is non-empty, the same pattern as `native` and `previous_states`. An instance that never uses MIR-01 then keeps its exact key set, and existing `_data_to_save` tests stay green.
- `parse_local_actions` treats the Store as untrusted, like every other `_parse_*`. It keeps only valid device ids and StateValues that pass `invalid_name` (printable, at most 64 characters), `mode` in the two words, actions that pass `validate_actions_structure` and `actions_depth <= MAX_ACTION_DEPTH`, at most `MAX_MIRRORS` devices and `MAX_OPTIONS` triggers. Malformed items are dropped silently, with a debug log by capped id only.
- Store the StateValue, never `trigger_key`. `model.py:57` says the key "is never stored". Match via `trigger_key(state_value)` at load, which makes matching case-insensitive like `spec.accepted`.
- Persist the **raw** selector output, never the validated form (the `actions.py:25` rule).

## Gates: what applies to local actions

| Gate | Owner part | Local part | Rationale |
|---|---|---|---|
| Approval (hash binding) | yes | **no** | Owner decision. Local content is authored by the local admin. |
| Static denylist (`_refuse_denied`, `info.denied` → BLOCKED) | yes | **no** | Same trust as an owned device (owned builds are unrestricted). A BLOCKED mirror still runs its local parts. |
| Deep validation (`async_validate_actions`) | yes, at build | **yes**, in the flow and again at build | Catches broken service calls and device actions. An invalid local part is reported (`action_failed_<id>`, label `"<trigger> (local)"`) and skipped, and the owner part still runs. |
| `GuardedTemplate` on templated service names | yes | **yes (recommended)** | The run variables include `state`, a StateValue from the owner's document. Static local names are unaffected. Costs nothing for legitimate use. Flag it for owner confirmation. |
| Mode (observe/disabled), breaker, startup window | yes | yes | One device, one gate set. |
| device_id warning (warn-then-confirm) | at the owner's flow | yes, in the local flow | Here device ids are local and correct. The warning is still useful, but it is informational only. |

**Open design decision (needs owner input, recommendation given).** `run_on_startup`, `run_mode` and both breaker limits come from the owner document and are part of the approval hash. They are approved settings. For a mirror whose owner part is **not** approved but which has local parts, these unapproved owner settings would govern local execution. Two examples: a broker-chosen `run_on_startup: true` runs local actions at every start, and a loose breaker weakens loop protection. **Recommendation:** while `owner_enabled` is false, use the defaults (`run_on_startup=False`, `serial`, `DEFAULT_BREAKER_*`). Apply them in `_async_refresh_mirror_script` (tracker flag, `run_mode` passed to the build, breaker rebuilt on the approval transition). This adds about 20 lines, and the transition is already a rebuild point. The alternative, "owner settings always apply", is simpler but leaks broker control into unapproved execution.

**Approval issue when shadowed.** If every owner trigger with actions has a `replace` overlay, the approval request is noise. Suppress the `approval_<id>` issue (`_sync_approval_issues`, `manager.py:1829`). `approval_state` itself stays `PENDING`, so adoption still refuses: adopting would publish unreviewed owner actions as this instance's own. Keep the BLOCKED issue, because it is a security signal.

## UI Entry Point

**Recommended:** the hub options flow as a menu.

```
Configure (hub options) → menu
  ├─ settings        : existing form (delete-on-remove, export, prefix), unchanged logic, step renamed init→settings
  └─ local_actions   : only when the entry is LOADED; abort "no_mirrors" if no targets
        → choose mirror  (SelectSelector; value=uuid, label="<name> (<owner_name>)", orphaned overlays as "(not present)")
        → choose trigger (Switch: onChangeToOn/onChangeToOff; Select: "<friendly> (<StateValue>)"; orphaned StateValues listed)
        → edit: mode [none | add | replace] + ActionSelector; description shows approval state and the owner's
                actions as sanitized YAML (reuse trust._actions_yaml-style cleaning, capped) so "replace" is informed
        → back to trigger chooser ("done" ends with async_create_entry(data=dict(self.config_entry.options)))
```
- Finishing with unchanged options is a no-op update. `async_update_entry` returns without calling listeners, so no reconcile is triggered.
- Broker-sourced labels and description text go through `escape_markdown` and capping (the existing T-03-05 practice). `SelectSelector` labels are plain text but still capped.
- Test churn: three modules open the options flow and assert `step_id == "init"` as a form (`test_hub_removal.py:103-135`, `test_discovery_export.py:254-294`, `test_native_cleanup.py:232`). Add one `open_hub_settings()` helper to `tests/helpers.py` (review-1 IN-02 creates that file).

**Rejected alternatives:**

| Alternative | Why not |
|---|---|
| Config subentry type `local_actions` (native "Add" button and per-item reconfigure) | Subentry `unique_id` is unique across **all** types (`config_entries.py:2764-2772`, verified 2026.9.4). An overlay keyed by mirror id makes adoption's `async_add_subentry` raise `AbortFlow("already_configured")`, and the adoption rolls back. A prefixed unique id avoids that, but overlays would then show in the device list, every edit fires the owned-device reconcile, and removal on a tombstone has to remove a subentry from inside the manager lock. It also puts never-publish data in the same container that `_device_subentries` and portability read from, one refactor away from a leak. |
| A service `set_local_actions` only | No action editor. It could be added later for automation use; defer it. |
| Repairs flow / device page | Repairs is for problems. A device without a subentry has no "configure" entry point in HA. |

## Scaling Considerations

| Scale | Consideration |
|-------|---------------|
| Typical (2-5 instances, <20 mirrors) | No concern. One extra dict lookup per Script build. |
| Upper caps (100 mirrors × 50 options) | Store growth is bounded by caps. A local edit rebuilds one Script, never all of them. |
| Large overlay actions | Not bounded by `MAX_DOCUMENT_BYTES` (never published). Apply that cap per device anyway as a Store sanity limit. |

## Anti-Patterns

### Anti-Pattern 1: Merging local actions into `mirror.spec.triggers`
**What people do:** rebuild a `DeviceSpec` with combined actions and hand it to `async_build_device(restricted=True)`.
**Why it's wrong:** `_refuse_denied` would then judge local actions (wrong gate). Any later `analyze_spec`, `actions_hash`, `approval_sections` or `build_content` on that spec includes local content, which breaks approvals and risks leaking into the approval YAML, diagnostics hashes or an adoption subentry (`_async_adopt_locked` builds the subentry from `mirror.spec`).
**Do this instead:** pass `TriggerPlan`s with separate `owner` and `local` parts, and keep the spec as parsed.

### Anti-Pattern 2: Garbage-collecting overlays at start like approvals
**What people do:** copy the `self._approvals = {… if device_id in self.mirrors}` line for `_local`.
**Why it's wrong:** a cached mirror that fails re-parse at start, or briefly exceeds MAX_MIRRORS, would destroy user-authored actions. An approval is one click; an overlay can be a long action sequence.
**Do this instead:** drop overlays only on positive removal (`async_remove_mirror`) or adoption.

### Anti-Pattern 3: Two Scripts per mirror (owner Script + local Script)
**What people do:** keep the owner Script untouched and add a second local Script.
**Why it's wrong:** it breaks D-10/D-11 (serial queue and restart cancellation across a device's triggers), `script_count`, the generation-based issue clearing, and `async_stop_runs` on a breaker trip, which stops only one Script.
**Do this instead:** keep one Script with `sequence` sub-blocks per part.

### Anti-Pattern 4: Keying the Store by `trigger_key`
**Why it's wrong:** it contradicts the model rule, and the flow can no longer show an orphaned trigger by name.
**Do this instead:** key by StateValue and derive the key at load.

### Anti-Pattern 5: New retrigger ack words for "local only"
**Why it's wrong:** `parse_ack` rejects unknown `status` or `reason` words (`retrigger.py:158-167`), so a v1.0.x caller would turn the whole answer into `no_answer`. Mixed-version benches are the norm here.
**Do this instead:** reuse `executed` and `error/no_actions`, and document that `executed` may mean local-only.

### Anti-Pattern 6: Persisting validated actions or skipping the immediate save
**Why it's wrong:** validated trees hold `Template` objects and are not serializable. A delayed save (5 s) can lose an edit the user just confirmed.
**Do this instead:** save the raw selector output with `await self._store.async_save(...)`.

## Integration Points

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Options flow ↔ Manager | direct async call `async_set_local_actions`, under the manager lock | Same pattern as `ApprovalRepairFlow` → `async_approve`. The flow binds the target and re-checks it at submit (stale-flow guard: target gone → abort `changed`). |
| Manager ↔ `local_actions.compose` | pure function call | Inputs: spec, `approval_state == APPROVED`, overlay keyed by `trigger_key`. |
| Manager ↔ Runner | `async_build_plans(device_id, name, run_mode, plans, restricted=True)` | The owned path is unchanged via the wrapper. |
| Manager ↔ NativeMigration | back-reference collaborator | `presence.py` keeps calling `manager.on_roster_changed()`. |
| RetriggerCoordinator ↔ Manager | unchanged (`can_run`, `approval_state`) | Only the reason for a muted trigger changes. |
| Diagnostics ↔ Manager | `overlay_counts(device_id)` | Counts only, no action text. |

### External (broker / HA core)

| Interface | Change | Notes |
|---|---|---|
| Config documents, discovery, state, retrigger, heartbeat topics | **none** | Local actions are never published. Pin this with a multi-instance test that greps every publish of the fake broker for a marker string placed in local actions. |
| HA Script engine | uses the `sequence` action | Available long before the 2026.9 floor. |
| HA config entries | options flow menu | No new subentry type, and no subentry unique-id interaction. |

## Suggested Build Order

Dependencies first. Each step leaves the suite green.

1. **v1.0.1 release (no code).** Tag v1.0.1 from the current build **before** any IN-04 or MIR-01 commit lands on `main`, or from a release branch. Otherwise the bench re-run of UAT-02/UAT-04 is not testing the tagged code.
2. **IN-04a: loud test for the private registry API** (`registry._store`, `_data_to_save` exist and are callable). Tiny and independent.
3. **Review-1 IN-02: `tests/helpers.py`.** Moves the shared helpers now. Later steps (extraction, options-flow churn, MIR-01 tests) reuse them.
4. **IN-04b: extract `NativeMigration`.** Pure move, no behavior change. The only allowed test edit is the `_cancel_replay_catch` access. Gate: full three-tier suite green with zero assertion changes.
5. **Review-2 IN-01/IN-02/IN-03 and review-1 IN-01/IN-03** on top of the new module: partial count on a mid-loop exception, a HA-internals-independent no-clear test, a Repairs hint for customized duplicates (new prefix → `ISSUE_DEVICE_PREFIXES`), the docs sentence, the guard spy.
6. **MIR-01a: `local_actions.py`** (types, `parse_local_actions`, `compose`, `owner_shadowed`) with table-driven pure tests. No wiring.
7. **MIR-01b: runner plan-based build.** `async_build_device` becomes a wrapper. Regression gate: owned devices and overlay-free mirrors produce identical assembled sequences (snapshot or equality test) and all runner tests pass unchanged. New tests: per-part validation, `_refuse_denied` on the owner part only, guard covers the local part, `sequence` branch shape.
8. **MIR-01c: manager wiring.** Store key load and save, `async_set_local_actions`, refresh via `compose`, the lifecycle rules (remove, adopt incl. rollback, no start GC), approval-issue shadowing, the decision on owner settings while unapproved, diagnostics counts, the retrigger reason, and the adopt response field. Tests run against the fake broker, including "BLOCKED mirror still runs local", "pending + add runs local only", "approve adds owner part", "owner content change keeps local", "tombstone drops overlay", "adoption drops and reports".
9. **MIR-01d: options-flow UI.** Menu, three steps, shared `_async_check_actions` helper, en/de translations, the `test_translations` update, and the churn in the three existing options-flow tests via the helper.
10. **MIR-01e: docs and cross-instance proof.** README section ("owner first, then local", modes, mute via empty replace, adoption drops local actions, downgrade loses them). Add a multi-instance "never published" test and a real-Mosquitto tier test.
11. **Re-verification, UAT-02/UAT-04 on the final build, v1.1.0.**

Steps 6 and 7 can run in parallel. Step 8 needs both, step 9 needs step 8's API, and step 4 must land before step 8 because both edit `manager.py`.

## Sources

- Codebase at `8157225`: `manager.py` (seams at 469-557, 768-817, 819-1153, 1304-1319, 1365-1440, 1442-1485, 1487-1513, 1540-1626, 1757-1863, 1865-1898, 1962-2019, 2443-2472, 2573-2605), `runner.py` (48-135), `trust.py` (79-112), `document.py` (130-152, 460-575), `model.py` (53-60), `config_flow.py` (141-221), `sync.py` (444-499), `retrigger.py` (151-168, 434-452), `services.py` (299-313), `repairs.py`, `diagnostics.py`, `const.py`. Confidence HIGH.
- HA core 2026.9.4 in `.venv`: `config_entries.py:2764-2772` (subentry unique_id checked across all subentry types), `config_entries.py:3910+` (options flow finish → `async_update_entry`), `helpers/script.py:730` (`_async_step_sequence`), `helpers/config_validation.py:2060,2119` (`sequence` action schema). Confidence HIGH.
- `.planning/PROJECT.md` (MIR-01 owner semantics), first Phase 8 review `d72c46b:.planning/phases/08-real-instance-verification/08-REVIEW.md` (IN-01 to IN-04), second review `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-REVIEW.md` (IN-01 to IN-03).

---
*Architecture research for: MQTT Actions v1.1 (MIR-01 local actions on mirrors, IN-04 extraction)*
*Researched: 2026-10-11*
