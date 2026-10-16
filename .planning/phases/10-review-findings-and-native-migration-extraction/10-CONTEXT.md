# Phase 10: Review Findings and Native Migration Extraction - Context

**Gathered:** 2026-10-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Close the info findings of both Phase 8 reviews (FIX-01 to FIX-08) and move the native-migration orchestration
(cutover, takeover pass, replay catch, duplicate guard, and the 09.2 shared-topic gate) out of `manager.py` into its own
module as a pure move, so that `manager.py` is smaller and quiet before MIR-01 (Phase 11) edits it. Also folded: the CI
push-trigger todo (unblocked since the v1.0.1 tag exists). No new user-facing capability except the FIX-08 Repairs
warning and the FIX-05 docs.

</domain>

<decisions>
## Implementation Decisions

### Carried forward (not re-asked)
- Roadmap plan order: FIX-01 loud registry-API test and FIX-03 shared test helpers first, then the start-up ordering spy
  test, then the pure move (FIX-02) as a plan of its own; FIX-04 to FIX-08 build on the moved module in separate plans.
  The move and a fix never share a plan.
- TDD: every fix starts with a failing test commit.
- 09.1 D-01 (CR-01 hard invariant, including core's clear-on-removal hook), D-03 (UNKNOWN keeps, count-only logs),
  D-04 (only `disabled_by: integration` rows are removal candidates); 09.2 D-01 to D-10 (peer heartbeat field for kept
  rows, owner-only topic empty, re-check before publish) stay in force unchanged. Nothing in this phase changes those
  rules.
- Pure-move discipline from research Pitfall 8: keep `@callback` methods synchronous, keep the start-up order, grep
  `patch(` targets after the move, run a mutation check per moved function.
- FIX-06 approach from research Pitfall 16: keep per-device isolation, accumulate the partial count before the
  exception, flush when `removed > 0` or an exception occurred; never catch inside `takeover.remove_replay_twins` and
  return 0.

### Repairs warning for kept duplicates (FIX-08)
- **D-01:** The warning lists the core MQTT entity ids of the enabled duplicates that are kept, each with a short reason
  (customized by the user, or the native twin was rejected, the WR-03 cases). The data is local registry data, never
  broker content.
- **D-02:** One non-fixable warning per instance (one issue id, e.g. `kept_duplicates`), not one per device. When the
  list changes, delete then create (research Pitfall 15: replacing keeps a dismissal). It goes away once no kept enabled
  duplicate remains. No fix flow, never a "delete" action, no registry row is ever removed. en and de translations. The
  hub-removal cleanup deletes it too.
- **D-03:** Only enabled kept duplicates. The disabled twins that the 09.1 D-03 / 09.2 D-03 fail-safe leaves behind
  (UNKNOWN content, unheard peer) are not part of this warning. They are harmless, resolve at a later start and are
  already documented in `docs/troubleshooting.md`.
- **D-04:** The warning is re-evaluated where duplicates are already evaluated: after the start-up takeover pass, after
  the duplicate guard runs for a create event, and at the end of the replay catch. No extra live listener on
  `entity_registry_updated`. A duplicate the user deletes clears the warning at the next of these runs.

### Private registry flush API (FIX-01)
- **D-05:** No product change. The runtime behavior stays as it is: `takeover.async_flush_registries` catches the
  failure, logs a warning, and HA's scheduled save follows.
- **D-06:** The loud test proves the immediate write: it calls `async_flush_registries` and, without advancing time,
  checks through `hass_storage` that the changed row is in `core.entity_registry` and `core.device_registry` and that the
  return value is `True`. A missing attribute fails hard. A structural check (attributes exist, are callable, need no
  args) may sit alongside it, as research Pitfall 9 suggests. Never skip, never xfail.

### Eager-task dependency (FIX-07)
- **D-07:** Pin it with a loud test, no product change. The test runs against real core behavior: an enabled, loaded
  core MQTT row is disabled and removed in the same synchronous step (`takeover.remove_replay_twins`), and the test
  asserts the observable outcome: no empty retained publish on the discovery topic, and the row is gone. It covers both
  call sites (start-up takeover path and replay catch). It asserts the outcome, not the mechanism. Its failure message
  names the core spot (`Entity._async_registry_updated`, eager task) and what to do next.
- **D-08:** All core-contract tests in this phase (FIX-01, FIX-04, FIX-07) follow one rule: never skip or xfail. A
  core or PHACC change that breaks them turns CI red, including Dependabot PRs. That is the wanted signal. No separate
  pytest marker.

### Module cut of the move (FIX-02)
- **D-09:** New module `custom_components/mqtt_actions/native_migration.py` with class `NativeMigration(manager)`, a
  collaborator with back-reference like `SyncManager`, `PresenceManager`, `RetriggerCoordinator`. It owns: the cutover
  timer and check plus its hint issue, the native takeover pass, the retry of unconfirmed clears, the replay catch timer
  and pass, the duplicate guard listener, the per-run sets, **and** the 09.2 gate logic used only by takeover and catch
  (`_shared_topic_verdict`, the peer-keep evaluation, `_rearm_or_log_replay_catch` and the like). The persisted
  `NativeState` stays in the Manager. `presence.py` keeps supplying only the heartbeat field. `takeover.py` stays
  registry primitives that never publish. The rule for the planner: whatever only the migration uses moves.
- **D-10:** In the move plan, tests stay unchanged: same test count, same assertions. The only allowed test edits are
  the `_cancel_replay_catch` access and `patch(` targets that must point at the new module. No test file is moved or
  renamed in this phase as part of the move.
- **D-11:** Shared test helpers live in `tests/helpers.py` (next to `documents.py`, `log_helpers.py`,
  `fake_broker.py`). Helpers lose their `_` prefix when they move, because they are public then. After FIX-03, no test
  module imports from another `test_*` module.

### Claude's Discretion
- Exact issue id and translation wording of the FIX-08 warning; reason labels; cap on the listed entity ids.
- Wording of the FIX-05 README and troubleshooting text (a duplicate the user re-enables is disabled again at the next
  start). Add a `tests/test_docs.py` claim if the existing doc tests cover similar statements.
- Public surface of `NativeMigration` (keep it small, e.g. one start-up entry point; the caller keeps holding the lock).
- Plan split within the fixed roadmap order, and where the folded CI todo goes (recommended: a small first plan).

### Folded Todos
- **Make ci.yml and validate.yml run on branch pushes again** (`.planning/todos/pending/2026-10-12-ci-push-trigger-branches.md`).
  Problem: `on.push` with only `tags-ignore` never runs for branch pushes (since 2f786d8). It was blocked until the
  v1.0.1 tag existed, which it does now. Fix: add `branches: ["**"]` next to `tags-ignore` in both workflows. It fits
  here because Phase 10 brings the first product commits after the tag, and they should get CI on push. A small,
  independent plan that runs first.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase scope and requirements
- `.planning/ROADMAP.md` § Phase 10: goal, success criteria, plan order, pure-move discipline
- `.planning/REQUIREMENTS.md`: FIX-01 to FIX-08

### Review findings being closed
- `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-REVIEW.md` § Info: second review IN-01 to IN-03
  (FIX-06, FIX-07, FIX-08); WR-02 and WR-03 define the kept cases
- First Phase 8 review: `git show d72c46b:.planning/phases/08-real-instance-verification/08-REVIEW.md`: IN-01 to IN-04
  (FIX-05, FIX-03, FIX-04, FIX-01 and FIX-02)

### Research (extraction and pitfalls)
- `.planning/research/ARCHITECTURE.md`: `NativeMigration` collaborator, seams, build order (line numbers predate
  09.1/09.2; re-map them against the current `manager.py`)
- `.planning/research/PITFALLS.md` § Pitfall 8 (refactor regressions, start-up order), § Pitfall 9 (core-internal pins),
  § Pitfall 15 (Repairs hint must never remove, delete-then-create), § Pitfall 16 (partial count)

### Prior decisions still in force
- `.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-CONTEXT.md`: D-01 to D-08
- `.planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-CONTEXT.md`: D-01 to D-12

### Docs touched
- `README.md`, `docs/troubleshooting.md` (§ "An enabled duplicate after the export prefix was set to the core prefix",
  around lines 102-141): FIX-05 text and the FIX-08 warning description

### CI
- `.planning/todos/pending/2026-10-12-ci-push-trigger-branches.md`, `.github/workflows/ci.yml`,
  `.github/workflows/validate.yml`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `takeover.py`: `remove_replay_twins` (304), `disable_duplicates` (385), `keeps_enabled_legacy_row` (288),
  `async_flush_registries` (443), `_is_customized` (463). FIX-08 can reuse the same keep predicates to build its list.
- `runner.py:246-279`: pattern for `ir.async_create_issue` / `async_delete_issue` with `is_fixable=False`.
- `const.py:264-307`: issue id constants, `ISSUE_DEVICE_PREFIXES` (per-device prefixes; the FIX-08 issue is per
  instance, so it needs its own constant and hub-removal cleanup).
- `tests/documents.py`, `tests/log_helpers.py`, `tests/fake_broker.py`: existing shared-helper modules, the model for
  `tests/helpers.py`.

### Established Patterns
- Collaborators with back-reference: `SyncManager` (`sync.py`), `PresenceManager` (`presence.py`),
  `RetriggerCoordinator` (`retrigger.py`).
- Start-up order in `Manager.async_start` (around `manager.py:778-826`): lock, store load, sync, presence, retrigger,
  `_async_native_takeover`, guard arming, publish owned, discovery check; after the lock: cutover, replay catch.
- Logs carry counts only, never broker content or registry content (T-04-14).

### Integration Points
- Migration code in `manager.py` today: state at 538-561, cutover at 822-839 and ~1298, takeover / verdict / twins /
  catch at ~850-1160, duplicate guard at 1230-1295. Re-map exact ranges at plan time.
- Cross-test imports to remove (FIX-03): `test_cutover`, `test_export_guard_receiver`, `test_docs`,
  `test_native_replay`, `test_native_cleanup`, `test_native_start`, `test_presence`, `test_discovery_content` import
  from `test_native_start`, `test_takeover`, `test_native_entities`, `test_discovery_export`, `test_native_replay`,
  `test_diagnostics`.

</code_context>

<specifics>
## Specific Ideas

- Core-contract test failure messages name the core spot and the documented fallback, so a red Dependabot PR explains
  itself.
- The move is proven by: the start-up ordering spy test (written before the move), the unchanged suite, and a mutation
  check per moved function.

</specifics>

<deferred>
## Deferred Ideas

- A Repairs notice for disabled twins left behind by the D-03 fail-safe (09.1 deferred to here): reviewed, not taken
  (D-03 above). Revisit only if users report confusion.
- Moving or renaming the orchestration tests to `tests/test_native_migration.py`: not in this phase (D-10). A later
  cleanup plan can do it if wanted.

</deferred>

---

*Phase: 10-review-findings-and-native-migration-extraction*
*Context gathered: 2026-10-16*
