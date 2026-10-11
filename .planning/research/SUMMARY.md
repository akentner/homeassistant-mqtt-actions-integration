# Project Research Summary

**Project:** MQTT Actions Integration (`mqtt_actions`), milestone v1.1 "Local Actions on Mirrors"
**Domain:** Per-instance local overrides on a centrally owned, broker-synchronized, approval-gated HA custom integration; plus a manager refactor (IN-04), review follow-ups and two releases (v1.0.1, v1.1.0)
**Researched:** 2026-10-11
**Confidence:** HIGH for code seams and HA core APIs (read in source at `8157225` and in core 2026.9.4, diffed against 2026.10.1). MEDIUM for behavior and UX choices, which are design judgment. Five of those choices are contested between researchers, see "Conflicts / Owner Decisions Needed".

## Executive Summary

MIR-01 adds a second, locally authored action source to a device whose primary content comes from the broker and is protected by hash approval, a static denylist and a runtime `GuardedTemplate`. All four researchers agree on the shape of a safe solution: the owner's `DeviceSpec`, `MirrorInfo`, `actions_hash`, `build_content`, approval view, export, adoption payload and diagnostics content stay owner-only, byte for byte. The local overlay lives in a separate structure, keyed by mirror device uuid plus a trigger identity, and only meets the owner content inside the runner when the Script is built. Trust gates apply per part: approval and static denylist only to the owner part; mode (observe/disabled), breaker and startup window to both. Everything needed ships with HA 2026.9.x: no new dependencies, `hacs.json` floor stays `2026.9.0`.

The UI entry point is also settled by three of four researchers: turn the hub options flow into a menu (`settings` | `local_actions`) with mirror chooser, trigger chooser and an edit form (mode plus `ActionSelector`). Writes go through a manager method under the lock with an immediate `await Store.async_save`. FEATURES recommended a `local_actions` config subentry type. ARCHITECTURE and PITFALLS both verified that this breaks adoption: subentry `unique_id` is unique across all types (`config_entries.py:2764-2772`). Treat the options-flow menu as decided. Execution topology, lifecycle on removal and adoption, orphan handling, storage keying and the guard scope are still contested and need owner calls before planning. They are listed below with recommendations.

The biggest risks: (1) relaxing the trust gate so owner actions run without approval, or so local actions silently never run (most likely when the owner device has no actions at all, which is probably the main use case); (2) local content leaking into the hash, the document or an adoption; (3) silently losing user-authored local actions on start-up pruning, owner changes or a downgrade; (4) IN-04 start-up ordering regressions of the WR-01 class; (5) tagging v1.0.1 from the wrong SHA after v1.1 commits land on `main`. Mitigations: a parametrized 4x3x2 gate matrix test written before implementation, hash and adoption-bytes invariant tests, no start-up GC of overlays, IN-04 as a pure move with an ordering spy test, and a code freeze on `main` until v1.0.1 is tagged.

## Key Findings

### Recommended Stack

No new stack. Everything is HA core 2026.9.x, unchanged in 2026.10.1. Details: STACK.md.

**Core technologies:**
- `OptionsFlow` + `async_show_menu` + `data_entry_flow.section`: the local-actions editor. Finish with `async_create_entry(data=dict(self.config_entry.options))`. Unchanged options fire no update listener, so there is no reconcile.
- `ActionSelector` + existing `actions.async_validate_actions()`: authoring and deep validation at submit and again at build. Persist the raw selector output. Skip the `device_id` portability warning or make it informational (local content never leaves the instance).
- `helpers.script.Script`: execution. Topology is contested (Conflict 1).
- `helpers.storage.Store`: persistence. Main Store key versus separate file is contested (Conflict 4).
- `issue_registry.async_create_issue(is_fixable=False, is_persistent=False, severity=WARNING)`: the aggregated "customized duplicates" hint (review 2 IN-03), recomputed at start and after each guard pass.
- Registry flush: no public immediate-write API in 2026.9.4 or 2026.10.1. Keep `registry._store.async_save(registry._data_to_save())` and pin it with structural plus behavioral tests (`hass_storage` without advancing time). Never `xfail` those tests.

**Avoid:** `async_abort(translation_domain=...)` (2026.10 only), deprecated `DeviceEntry.config_entries`-family APIs, `async_delay_save` for user edits, `entry.options` as storage, PHACC bump mixed into feature commits.

### Expected Features

**Must have (v1.1.0):**
- T1/T2: per-trigger mode `none` / `add` ("in addition to") / `replace` ("instead of") with the action editor, reachable from the integration page
- T4: local parts run while the owner part is pending, blocked, or empty (owner rule 3)
- T5/T6: never published, never in any hash, never restricted by the static denylist
- T7-T10: device and instance mode gate local runs; breaker counts once per change and is released by a local edit (local digest in the trip fingerprint); test buttons and re-trigger run the effective actions, **with no new wire status words**
- T11: survives owner rename, rev bump, re-pin, owner flip
- T15-T17: diagnostics show counts only; `approval_state()` keeps its owner-only meaning, with local state reported as a separate dimension; overrides visible in the flow (and optionally as an entity attribute)
- Mute via empty `replace` (D1): ARCHITECTURE and FEATURES both endorse it. Confirm it in requirements.
- Orphan, tombstone and adoption behavior: needed, but the semantics are contested (Conflicts 2 and 3)

**Should have (v1.1.x):**
- D2/D3: approval request aware of local replacements (see open questions)
- D4/D5: optional ack field and run variable telling which part ran

**Defer (v1.2+):**
- D6 overlay export/import (HA backup covers it)
- D7 authoring local actions on owned devices
- D8/MAP-01 variable mapping

**Anti-features (all researchers):** auto-merging local actions into owned content on adoption, step-level patching of owner sequences, overloading `ApprovalState`, new re-trigger status words, auto-approving when all triggers are replaced, local override of run mode or breaker limits, catch-all local handlers.

### Architecture Approach

The pure overlay model sits outside the spec and is combined at a single point. A new HA-free module `local_actions.py` (types, `parse_local_actions` for untrusted Store input, `compose(spec, owner_enabled, overlay) -> TriggerPlan[]`, `owner_shadowed`, `overlay_counts`) holds the security-relevant "what runs here" decision and can be tested as a truth table. `Manager._async_refresh_mirror_script` stays the only choke point: called on apply, approve, restore and the new `async_set_local_actions`. The runner gets a plan-based build. `async_build_device` becomes a wrapper so that owned devices and overlay-free mirrors assemble byte-identically to today (regression gate). IN-04 moves cutover, takeover pass, replay catch, duplicate guard and the unconfirmed-clear retry (`manager.py:819-1153, 1304-1319`, about 330 lines) into `native_migration.py` → `NativeMigration(manager)`, the same back-reference pattern as `SyncManager`, `PresenceManager` and `RetriggerCoordinator`.

**Major components:**
1. `native_migration.py` (NEW, IN-04): start-up migration orchestration. Pure move with thin delegations left in Manager.
2. `local_actions.py` (NEW): overlay model, Store parsing, `compose`.
3. `manager.py` (MOD): `_local` overlay, `async_set_local_actions` under the lock, lifecycle hooks, approval-issue handling.
4. `runner.py` (MOD): plan-based build with per-part validation and `_refuse_denied` on the owner part only.
5. `config_flow.py` (MOD): options menu plus three local-action steps, with a shared `_async_check_actions` helper.
6. Small edits: `retrigger.py` (reason mapping, no new words), `diagnostics.py` (counts, avoid the redacted key `actions`), `services.py` (adopt response field, depending on Conflict 2), translations en/de.

### Critical Pitfalls

1. **Leak into owner spec, hash or adoption.** Never merge local actions into `TriggerSpec.actions` or pass an "effective spec" to `actions_hash`, `build_content`, `approval_sections`, `build_export` or `subentry_payload`. Pin it with hash-equality and adoption-bytes tests first.
2. **Trust gate restructured wrongly.** Restate TRU-01 per branch. An owner branch exists only if not denied, approved hash equals current hash, it has owner actions and is not replaced. A local branch exists whenever local actions exist. Runnability is the union. Write the 4 (none/pending/approved/blocked) x 3 (none/add/replace) x 2 (owner trigger has actions yes/no) matrix test before coding.
3. **Two sources in one runtime break isolation.** Watch for guard spill-over, losing the guard on owner subtrees, `_refuse_denied` dropping the local branch, and a shared `action_failed_<id>` issue cleared across sources (including `runner.clear_issue` on every owner document change). Local failures need their own issue prefix in `ISSUE_DEVICE_PREFIXES`, whatever topology wins.
4. **Silent loss of user content.** Do not GC overlays at start like approvals (`manager.py:788-790`). A v1.1 → v1.0.x downgrade drops an additive main-Store key on the first save (verified in `storage.py:431-460`). Load overlays before `_async_restore_mirrors`.
5. **IN-04 and release mechanics.** IN-04: pure move, ordering spy test first, keep `@callback` methods synchronous, grep `patch(` targets after the move, run a mutation check per moved function, and keep the IN-01 partial-count fix in a separate plan. Release: freeze `main` until v1.0.1 is tagged (or use `release/1.0.1`), bump the manifest **before** the bench run, record the SHA in the evidence, avoid `[ci skip]` in squashed commits, and tag v1.1.0 on a newer commit so HACS sorts it first.

## Conflicts / Owner Decisions Needed

Decide these in discuss-phase or requirements, before the MIR-01 data/runtime phase is planned. Each one changes data model or runner code.

### Conflict 1: Execution topology. One combined Script, or a separate local lane?

| Option | Advocates | Pros | Cons |
|---|---|---|---|
| **A. One Script per mirror, sequential** `[owner seq] → [local seq]` in a `sequence` block | FEATURES (T3), ARCHITECTURE (Pattern 2) | Serial queue and restart cancellation stay single-point (D-10/D-11); one `async_stop_runs` on a breaker trip; deterministic order "owner then local"; owner-only assembly stays byte-identical | An owner runtime failure or `DeniedServiceCallError` aborts the local part. That is in tension with the spirit of owner rule 3 ("local runs even when owner is blocked"): it holds for static blocking, not for runtime denial. Guarding only part of the tree needs careful assembly. |
| **B. One Script, `parallel: [owner, local]`** in `add` mode | PITFALLS (Pitfall 3) | Keeps single-Script run-mode semantics; exceptions are isolated (`gather(return_exceptions=True)`, verified `script.py:711-727`) | No ordering between owner and local; `stop`, response variables and `continue_on_error` inside branches are unverified (needs a pin test); the first exception is still re-raised after both branches finish, which affects failure reporting |
| **C. Separate unrestricted "local lane" Script per mirror** with its own issue prefix | STACK (decision 5) | Owner restricted build untouched; TRU-01 "no Script until approved" stays literally true; full failure isolation; no partial-tree guarding | Breaks D-10/D-11 across lanes (two runs of one change can interleave; `restart` does not cancel the other lane); breaker trip must stop two Scripts; `script_count` and generation logic double; "add" runs concurrently and unordered |

**Recommendation: B, with a fallback to A.** One Script keeps run-mode, breaker-stop and restart semantics consistent, and the architecture review rates C's D-10/D-11 break as an anti-pattern. `parallel` is the only single-Script option where owner rule 3 also holds for runtime owner failures. Before committing to it, write a pin test against core 2026.9.4 for `stop`, `continue_on_error` and the re-raise. If the test shows surprises, fall back to A and document "owner first, then local; an owner failure aborts the run". Regardless of topology: per-part validation, `_refuse_denied` on the owner part only, and a separate `local_action_failed_` issue prefix (STACK's argument holds even inside one Script: the issue is per source, not per Script). Owner question: is "local runs after owner" a user-facing promise (A), or is "local runs even if owner fails at runtime" the stronger promise (B/C)?

### Conflict 2: Lifecycle on tombstone/prune and on adoption

**Tombstone / confirmed prune:**
- Keep detached and dormant, with a Repairs issue to discard (FEATURES T13, PITFALLS Pitfall 4 leaning). Argument: tombstones can be forged by any broker writer; authored content is costlier than an approval.
- Drop, like approvals (ARCHITECTURE, STACK). Argument: device ids are uuid4 and never return, so a detached overlay can never re-attach in practice; symmetric with A10/T-04-26; less code.
- **Recommendation: drop on tombstone, but log it at info level and note it in the README next to the existing forged-tombstone limitation.** The re-attach benefit is close to zero with uuid4 ids. Broker forgery is an accepted risk (cooperative broker, EMQX later). HA backups restore `.storage`. **Never** drop on start-up or transient pruning (all agree).

**Adoption of a mirror with local actions:**
- Keep local and running on the now-owned device (FEATURES T14). Requires role-independent overlays and effectively pulls D7 (local actions on owned devices) into v1.1.
- Drop and report via `adopt_device` response `local_actions_dropped: true`, restored on rollback (ARCHITECTURE).
- Drop or fold, owner decides (STACK); explicit user choice at adopt time (PITFALLS).
- **Recommendation: drop and report, with an info log; the adopt service description warns beforehand.** Keeping them would need overlays on owned devices (D7, deferred), and a `replace` overlay on an owned device means "others run my published actions, I don't", which is confusing. Behavior change at adoption is acceptable because adoption is an explicit recovery action. Under all options: never merge into owned content, and adoption still requires an approved owner part even when every trigger is replaced (T-04-50).

### Conflict 3: Orphaned Select option (owner removes an option that has local actions)

- Keep inactive, list it in the flow, show a Repairs hint with discard, re-attach when the same StateValue returns (FEATURES T12, PITFALLS Pitfall 5, ARCHITECTURE Pattern 1 keeps it inert and lists it in the flow).
- Prune on mirror apply (STACK).
- **Recommendation: keep inactive, list it in the flow with a remove action, re-attach on re-add with an info log.** Three of four researchers agree, and an owner's temporary option edit should not destroy follower work. Whether there is also a Repairs issue per device is optional; listing in the flow plus diagnostics counts covers visibility, and a Repairs issue adds a new issue type to maintain. Suggest: flow listing in v1.1.0, Repairs hint only if users miss orphans.

### Conflict 4: Storage key and storage location

**Trigger identity in the Store:**
- StateValue (ARCHITECTURE: `model.py:57` says `trigger_key` "is never stored"; PITFALLS: lower-cased StateValue plus label and `kind`).
- `trigger_key` (FEATURES, STACK: StateValue immutable, so the key is stable).
- **Recommendation: store the StateValue (lower-cased for matching, the original kept for display), derive `trigger_key` at load.** It honors the existing model contract, survives any future change of the key function, and lets the flow name orphaned triggers. Also store the device `kind` so a kind change makes all overlays inactive (PITFALLS).

**Location:**
- Additive optional key `local_actions` in the main Store `mqtt_actions.state`, written only when non-empty, no version bump (STACK, ARCHITECTURE).
- Separate Store file `mqtt_actions.local_actions` with its own `_async_migrate_func` from day 1 (PITFALLS). Verified: v1.0.x drops unknown main-Store keys on its first save.
- **Recommendation: separate Store file.** It costs one extra `Store` object and one line in `async_remove_local_state`. In return, a downgrade/upgrade round trip keeps user-authored content, existing Store key-set tests stay untouched, and the lifecycle of approvals (cheap, prunable) and overlays (authored, not GC'd) is kept apart by construction. If the owner prefers the main Store, the downgrade loss must go into the v1.1.0 release notes.

### Conflict 5: `GuardedTemplate` on local actions

- Yes (ARCHITECTURE): run variables include `state`, a broker-chosen StateValue, so `action: "{{ state }}"` in a local template could be steered by the owner document. Static local service names are unaffected, so legitimate cost is near zero.
- No (STACK, PITFALLS default): local content has owned-device trust. Owned devices are not guarded either and also receive `state` from the broker.
- **Recommendation: no guard on local actions, consistent with owned devices, and document the `{{ state }}` templating caveat.** An owned device with `action: "{{ state }}"` has the identical exposure today, so guarding only local actions would be inconsistent. If the owner wants the guard, apply it to owned devices too as a separate decision. Either way, pin the choice with a test ("local templated denied service runs / is stopped").

### Smaller open questions

1. **Owner settings while the owner part is unapproved** (ARCHITECTURE). `run_on_startup`, `run_mode` and breaker limits come from the unapproved document but would govern local runs. Options: (a) owner settings always apply (FEATURES, PITFALLS: document it); (b) defaults (`run_on_startup=False`, serial, default breaker) until approved, about 20 lines. **Recommendation: (b).** Otherwise an unapproved broker document controls local execution, for example running local actions at every start.
2. **Approval issue when every owner trigger with actions is replaced.** ARCHITECTURE: suppress the issue, keep `PENDING`. FEATURES D2: suppress, defer to v1.1.x. PITFALLS: keep it, explain in the text. **Recommendation: keep the issue in v1.1.0, add "N of M triggers replaced locally" to its text (D3-style).** It is cheap and honest. Suppression can follow if users report noise. All agree: `approval_state` stays `PENDING` and adoption still refuses.
3. **Empty `replace` = mute.** ARCHITECTURE and FEATURES say yes. **Recommendation: yes.** It counts as "override active" for visibility, but not as a run for the breaker. `add` with empty actions is stored as "none".
4. **Re-trigger ack.** All agree: no new status or reason words (v1.0.x `parse_ack` rejects them). Open: an optional field (`parts`/`local`) now (PITFALLS) or in v1.1.x (FEATURES D4); local-replaced-with-empty answers `error/no_actions` (ARCHITECTURE). **Recommendation:** reuse `executed` / `not_approved` / `error/no_actions` in v1.1.0 and document that `executed` may mean local-only. Add the optional field only if cheap within the phase.
5. **Does a broker re-trigger run local actions at all?** STACK flags it as an owner decision. FEATURES and ARCHITECTURE assume yes (effective actions). **Recommendation: yes**, consistent with test buttons.
6. **Run-mode restart cancelling long local sequences.** Document it in the flow description: the owner's run mode governs local runs.

## Implications for Roadmap

The milestone order is fixed by PROJECT.md: release v1.0.1, then info findings, then MIR-01, then re-verification and v1.1.0. Research adds internal ordering. Continue phase numbering after Phase 8.

### Phase 9: v1.0.1 Release
**Rationale:** Must come before any IN-04 or MIR-01 commit on `main`, otherwise the tag ships half-built code or the bench evidence does not match the tagged bytes.
**Delivers:** manifest bumped to 1.0.1 **before** the bench run; UAT-02 and UAT-04 re-run on ha-a/b/c on that SHA (recorded in the evidence); tag `v1.0.1` pushed by the user; release workflow, all three tiers, hassfest and HACS confirmed. Closes ACCEPTED-GAP-V101 for that release.
**Avoids:** Pitfall 10 (wrong SHA, version after bench, `[ci skip]`, HACS sort order). If work must continue in parallel, use `release/1.0.1` and merge it back.

### Phase 10: Phase 8 Info Findings and IN-04 Extraction
**Rationale:** IN-04 shrinks `manager.py` by about 330 lines before MIR-01 edits it. The work touches the native-migration region, not the mirror seams, so it is safe to do first.
**Delivers, in plan order:**
1. Loud private-registry-API test (structural plus behavioral, fallback named in the failure message, no `xfail`)
2. Shared `tests/helpers.py` (review 1 IN-02), later reused by the options-flow churn and the MIR-01 tests
3. Start-up ordering spy test, then the `NativeMigration` pure move (only allowed test edit: the `_cancel_replay_catch` access)
4. On top of the move: review 2 IN-01 (partial count, no widened `except`), IN-02 (no-clear guarantee independent of the HA eager task), IN-03 (aggregated non-fixable Repairs hint for customized duplicates, never removes rows, new prefix in `ISSUE_DEVICE_PREFIXES`, en/de); review 1 IN-01 (docs sentence) and IN-03 (guard-test spy)

**Avoids:** Pitfalls 8, 9, 15, 16. Never mix the move and the fixes in one plan.

### Phase 11: MIR-01 Data Model, Runtime and Gates
**Rationale:** The storage and composition decisions drive everything else, and the runner change is the security centre. Needs Conflicts 1, 2, 4, 5 and open question 1 resolved first.
**Delivers:** invariant tests first (hash equality, adoption bytes, 4x3x2 gate matrix, "never published" marker grep across all fake-broker publishes); `local_actions.py` pure module with table-driven tests; plan-based runner build with a byte-identical regression gate for owned devices; manager wiring (Store load before restore, `async_set_local_actions` under the lock with immediate save, refresh via `compose`, lifecycle rules, no start-up GC, breaker release on local edit plus local digest in the trip fingerprint, separate local failure issue prefix); re-trigger and test-button semantics; diagnostics counts.
**Addresses:** T3-T11, T15, T16, D1.
**Avoids:** Pitfalls 1-7, 11-13. Add a `/gsd-secure-phase` threat entry for "trust-level mixing in one Script".
Plans for `local_actions.py` and the runner can run in parallel; the manager wiring needs both.

### Phase 12: MIR-01 UI, Visibility and Docs
**Rationale:** Needs the manager API from Phase 11.
**Delivers:** options flow `init` → menu (`settings` | `local_actions`), mirror chooser, trigger chooser (orphans listed), edit form (mode plus `ActionSelector`, owner state and sanitized owner YAML read-only, owner run settings shown); stale-flow guard (`changed` abort); en/de translations; churn in the three existing options-flow tests via helper; approval issue text "N of M replaced"; README section (modes, mute, order or parallel semantics, adoption and tombstone behavior, downgrade note, `{{ state }}` caveat, test-topic accepted risk); real-Mosquitto and multi-instance "never published" tests.
**Addresses:** T1, T2, T12, T17, D3.
**Avoids:** Pitfalls 12, 14; escape and cap broker-sourced labels.

### Phase 13: Full Re-verification and v1.1.0 Release
**Rationale:** Must be last. Any later fix makes reports stale (lesson from v1.0 and v1.0.1). Run the deep cross-file review **before** the bench.
**Delivers:** deep review → fixes → current verification reports for Phases 1-4, 7 and 9-12 (QLT-01) → manifest 1.1.0 → UAT-02, UAT-04 plus MIR-01 bench checks on that SHA (including the downgrade round trip v1.1 → v1.0.1 → v1.1 and "local actions on an owner device without actions") → tag v1.1.0 on a commit newer than v1.0.1.
**Avoids:** Pitfall 10 again; the stale-verification trap.

### Phase Ordering Rationale

- The release freeze (Phase 9) is a hard prerequisite for any code change on `main`.
- IN-04 before MIR-01: both edit `manager.py`; a pure move is only verifiable on a quiet file.
- Data/runtime before UI: the flow is a thin client of `async_set_local_actions`, and the gate matrix must be green before any user can author actions.
- Optional merge: Phases 11 and 12 could be one phase, but the security-relevant runner change deserves its own verification and secure-phase pass.

### Research Flags

Needs `/gsd-plan-phase --research-phase`:
- **Phase 11:** `parallel` semantics pin (`stop`, `continue_on_error`, re-raise) if Conflict 1 resolves to B; partial-tree `guard_actions` assembly on validated trees; separate-Store migrate skeleton.
- **Phase 12 (light):** `section` plus `ActionSelector` rendering in options flows on the 2026.9 frontend; options-menu test churn.

Standard patterns (skip research):
- **Phase 9:** release mechanics already documented (PITFALLS 10, RETROSPECTIVE).
- **Phase 10:** pure move along an existing collaborator pattern; seams mapped line by line in ARCHITECTURE.
- **Phase 13:** repeats the v1.0.1 verification process.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Every API checked in core 2026.9.4 and diffed against 2026.10.1. Frontend deep-link claims MEDIUM (main branch). |
| Features | MEDIUM | Code dependencies HIGH; behavior is design judgment backed by analogs (ESPHome, Syncthing, Kustomize: MEDIUM; Z2M: LOW). |
| Architecture | HIGH (seams) / MEDIUM (UI, owner-settings rule) | Subentry unique-id collision and `sequence` action verified in source. |
| Pitfalls | HIGH | Store downgrade behavior, `parallel` gather and subentry removal verified in source; HACS sort by commit date MEDIUM. |

**Overall confidence:** HIGH on what must not break, MEDIUM on the exact MIR-01 behavior until the five conflicts are resolved.

### Gaps to Address

- **Five conflicts and six open questions above:** resolve in discuss-phase for Phase 11 and record them as D-xx decisions.
- **`parallel` branch semantics:** unverified for `stop`, response variables and `continue_on_error`. A pin test is needed before choosing Option B.
- **Partial guarding:** applying `guard_actions` to owner subtrees only, after validating the combined tree, has not been prototyped. An alternative is validating and guarding the parts separately, then assembling.
- **HACS/GitHub release ordering by commit date:** MEDIUM. Avoid the question by tagging releases on monotonically newer commits.
- **Frontend rendering of `section` and the options menu on the 2026.9 frontend:** check on the bench early in Phase 12.

## Sources

### Primary (HIGH confidence)
- Codebase at `8157225`: `manager.py`, `runner.py`, `trust.py`, `document.py`, `model.py`, `retrigger.py`, `config_flow.py`, `takeover.py`, `diagnostics.py`, `portability.py`, `services.py`, `const.py`, `manifest.json`, `release.yml`
- HA core 2026.9.4 (`.venv`) and 2026.10.1 wheel: `config_entries.py` (2700-2714, 2764-2772, options finish), `helpers/storage.py` (426-460), `helpers/script.py` (323, 711-727, 730, 1505), `helpers/registry.py`, `helpers/issue_registry.py`, `helpers/selector.py`, `data_entry_flow.py` (878, 939), `helpers/entity.py` (1583-1593)
- `hacs/integration` main `repositories/base.py` (release selection); PHACC `plugins.py` (`hass_storage`)
- Project history: PROJECT.md, RETROSPECTIVE.md, Phase 8 reviews (`d72c46b` and `milestones/v1.0.1-phases/08-.../08-REVIEW.md`)

### Secondary (MEDIUM confidence)
- developers.home-assistant.io blog posts 2026-07-21, 2026-09-15, 2026-09-28; GitHub REST releases docs
- `home-assistant/frontend` main (deep links, device page, integration page hash)
- ESPHome packages, HA blueprint "take control", Syncthing receive-only, Kustomize patch failures

### Tertiary (LOW confidence)
- Zigbee2MQTT per-device option merge behavior; HACS version-display issue threads

---
*Research completed: 2026-10-11*
*Ready for roadmap: yes, after the owner resolves the listed conflicts (they can be resolved in discuss-phase for Phase 11 without blocking Phases 9-10)*
