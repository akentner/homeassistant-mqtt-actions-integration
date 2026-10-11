# Pitfalls Research

**Domain:** Adding per-instance local overrides (MIR-01) to a replicated, approval-gated HA custom integration, plus a manager refactor (IN-04), review follow-ups and two releases (v1.0.1, v1.1.0)
**Researched:** 2026-10-11
**Confidence:** HIGH overall. Most findings come from reading `custom_components/mqtt_actions/` at HEAD (`8157225`) and the installed core source (`homeassistant==2026.9.4` in `.venv`). The HACS release selection was read in `hacs/integration` main. GitHub release ordering is MEDIUM: it comes from the docs and was not cross-checked.

Phase names below are suggestions for the roadmapper:
- **P-REL1:** v1.0.1 bench re-run and release
- **P-INFO:** the Phase 8 info findings, including IN-04 (manager extraction), the internals-pinning tests and the Repairs hint
- **P-MIR-DATA:** MIR-01 data model, persistence and runtime
- **P-MIR-UI:** MIR-01 flow, Repairs, docs and diagnostics
- **P-VER:** full re-verification, UAT-02 and UAT-04 on the final build, then release v1.1.0

---

## Critical Pitfalls

### Pitfall 1: Local actions leak into the owner spec, so they reach the broker document, `actions_hash` or an adoption

**What goes wrong:**
For a mirror, `Device.spec` is the owner's `DeviceSpec`. Several code paths read it as "the owner's content":
- `document.actions_hash(spec)` and `build_content(spec)` (document.py:100-148)
- `approval_state` and `_async_refresh_mirror_script`, through `spec_has_actions(mirror.spec)` (manager.py:1770, 1860)
- the approval view, through `approval_sections(spec)` (trust.py)
- the adoption, through `subentry_payload(build_content(spec), device_id)` (manager.py:1551-1556), which becomes owned content and is published
- the export (portability `build_export`)
- diagnostics, through `content_hash(build_content(device.spec))` for owned devices

The tempting shortcut is to merge the local actions into `TriggerSpec.actions`, or to swap `Device.spec` for an "effective" spec, because the runner builds its Script from `spec.triggers`. Then:
- the approval hash changes locally, so the stored approval no longer matches and the mirror falls to `pending`. Worse, re-approving binds a hash that no other instance computes.
- an adoption publishes this follower's local actions as the new owner's content to every instance.
- `content_hash` in diagnostics drifts from the owner's.

**Why it happens:**
`DeviceSpec` is the single runtime model and the runner only understands `spec.triggers`. Merging is the smallest diff.

**How to avoid:**
- Keep `Device.spec` and `MirrorInfo` owner-only, byte-for-byte what `parse_document` produced.
- Hold local overrides in a separate structure, for example `LocalOverrides: dict[device_id, dict[state_value_lower, LocalTrigger(mode, actions)]]` owned by the manager or a new module.
- Combine the two only inside the runner's Script assembly, through a separate argument such as `async_build_device(spec, restricted=True, local=overrides)`.
- Never pass an effective spec to `actions_hash`, `build_content`, `build_document`, `approval_sections`, `build_export` or `subentry_payload`.

**Warning signs:**
- A test with local actions sees `approval_state` change, or `info.actions_hash` differ from `parsed.actions_hash`.
- Any call of `build_content` or `actions_hash` with an argument that is not `parsed.spec` or an owned subentry spec.
- The adoption test publishes a document whose triggers differ from the mirror's owner document.

**Prevention tests (pin them first, TDD):**
- With local actions set (additive and replace): `actions_hash(mirror.spec) == parsed.actions_hash` and `approval_state` is unchanged.
- The bytes published on adoption equal the owner content plus bookkeeping, with no local action in them.
- Export of a mirror is still refused (`export_not_owned`).

**Phase to address:** P-MIR-DATA (invariant and tests before the first runtime change).

---

### Pitfall 2: The trust gate is restructured wrongly. Either local actions never run on unapproved or blocked mirrors, or owner actions start running without approval

**What goes wrong:**
Today, `_async_refresh_mirror_script` (manager.py:1847-1863) unloads the whole Script of a mirror unless it is unblocked, has owner actions and is approved. The runner builds one restricted Script per device and skips triggers whose owner `actions` are empty (runner.py:59-61). MIR-01 requires local actions to run when the owner part is pending, blocked (`info.denied`) or empty. Two failure directions:

1. **Local actions silently never run.** This happens when:
   - the owner device has no actions at all (`spec_has_actions` is False, so the Script is unloaded). This is probably the main use case: an owner device with no actions, where every follower adds its own.
   - the mirror is `blocked`
   - the approval is pending
   - the owner trigger is empty, so `runner._runnable` lacks the key and `can_run` in `_run_trigger`, `_enqueue_test` and `RetriggerCoordinator._run` refuses it
2. **Owner actions run without approval.** This happens when the gate is relaxed to "build the Script when there is anything to run" and the owner branches are not filtered by `approved and mode != replace`. It also happens when a trigger is switched from replace to additive while the owner hash is unapproved.

**Why it happens:**
The invariant "no Script until the approved hash equals the actions hash" (TRU-01, T-03-33) is encoded at device level. MIR-01 makes it a per-source, per-trigger rule.

**How to avoid:**
- Restate TRU-01 per branch: *an owner branch of trigger T is in the Script only when `not info.denied`, `approvals[id] == info.actions_hash`, T has owner actions and the local mode of T is not `replace`. A local branch of T is in the Script whenever T has local actions.*
- Compute runnability from the union of both sources, not from `trigger.actions`.
- `approval_state()` keeps its exact current meaning, based on owner content only. Replace mode never records, implies or clears an approval.
- An approval issue may stay open for a fully replaced device. That is honest, because switching back to additive must not run unreviewed actions. If the owner decides to suppress the nag, do it in the issue text, never by changing `approval_state`.

**Warning signs:**
- A test matrix shows a missing cell. Cover owner part {none, pending, approved, blocked} x local {none, additive, replace} x trigger-has-owner-actions {yes, no}.
- `can_run` is still keyed on `trigger.actions`.
- `retrigger._run` returns `REASON_NO_ACTIONS` for a trigger that has local actions.

**Phase to address:** P-MIR-DATA. Write the 4x3x2 matrix as a parametrized test before implementation.

---

### Pitfall 3: Combining two action sources in one Script breaks isolation, the denylist guard or failure reporting

**What goes wrong:**
The runner wraps a mirror's whole validated tree with `guard_actions` (trust.py) and refuses statically denied triggers (`_refuse_denied`). Putting local actions into the same tree causes four problems:
- **Guard spill-over.** The local actions get the mirror denylist, for example a local `shell_command` is refused, although they are as trusted as owned actions. The opposite mistake is worse: building the combined Script unrestricted "because it has local parts" strips the guard from owner actions. That is a security regression.
- **A denied owner trigger drops the local branch too.** `_refuse_denied` raises for the whole trigger.
- **Failure coupling in additive mode.** If owner and local actions are concatenated into one sequence, a failing or denied owner step stops the local steps. That contradicts "local actions run even when owner actions are blocked". Core runs a `parallel` step with `asyncio.gather(..., return_exceptions=True)` and re-raises the first exception after all branches finish (verified in `helpers/script.py:711-727`, 2026.9.4). So `parallel` isolates exceptions, but behavior with `stop` or response variables inside a branch is not verified.
- **Shared Repairs and generation.** `report_failure` uses one issue `action_failed_<device_id>`. `_generation` decides who may clear it (A10). A successful local run clears an owner failure, and vice versa. `runner.clear_issue(device_id)` on every owner document change (manager.py:1473) also deletes a local failure.

**Why it happens:**
The runner was designed for exactly one trust level per device (`_restricted` is a device-level set).

**How to avoid (opinionated):**
- Keep one Script per device, so serial ordering, restart cancellation and `async_stop_runs` on a breaker trip stay single-point.
- Inside each `choose` branch, run the sources as `parallel: [owner_seq, local_seq]` in additive mode. Use `local_seq` only in replace mode, and `owner_seq` only without local actions.
- Validate the combined raw sequence once. Then apply `guard_actions` only to the owner subtrees (their paths are known from assembly). Never apply it to the local subtrees, or apply it to them deliberately as an owner decision, and document either choice.
- Apply `_refuse_denied` to the owner part only. The local part of the same trigger stays runnable.
- Give local failures their own issue id prefix (for example `local_action_failed_`). Add the prefix to `ISSUE_DEVICE_PREFIXES` so removal and hub removal clean it up, and give it its own generation counter.
- Before relying on it, verify `stop` and `continue_on_error` inside a `parallel` branch against the installed core. Pin it with a test, like `test_denied_call_aborts_the_run_even_with_continue_on_error` pins the guard.

**Warning signs:**
- A local action that calls a denied-domain service is refused (spill-over).
- An owner templated service that resolves to a denied service is NOT stopped once local actions exist (guard lost).
- A local success deletes an `action_failed_` issue that came from an owner run.

**Phase to address:** P-MIR-DATA (runner change), with a `/gsd-secure-phase` threat entry for "trust level mixing".

---

### Pitfall 4: Local actions are silently lost on owner change, rev bump, re-pin, start-up pruning or downgrade

**What goes wrong:** Mirror state is rebuilt in many places, and every rebuild is a chance to drop local data:
- `_update_mirror` and `_mirror_info` replace `MirrorInfo` on every changed document and on every same-content re-pin after adoption (manager.py:1458-1466, 2021-2042). Anything stored in `MirrorInfo`, or in the stored payload (`STORE_MIRRORS` keeps the raw received text), is gone at the next rev.
- **Start-up pruning.** `async_start` keeps approvals only for mirrors that were restored from cache (manager.py:788-790). It also drops cached mirrors that fail to parse, or that exceed `MAX_MIRRORS` (`_parse_mirrors`). If local overrides are pruned the same way, a cached payload that stops parsing after an upgrade (new validation rule) or a temporarily owned id deletes user-authored content before the broker replays the document. Approvals are cheap to redo; local action sequences are not.
- `async_remove_mirror` on a tombstone or prune (manager.py:1865-1898) forgets approvals, modes and history. If it also forgets local actions without a trace, an owner that deletes and re-creates a device, or a false-positive prune, destroys follower work.
- **Downgrade (verified).** HA `Store.async_load` with the same major version and a different minor version falls back to the raw data and re-saves it (`helpers/storage.py:431-460`). The old code's `_base_data_to_save` writes only the keys it knows, so a v1.1 to v1.0.x downgrade **drops any new key at the first save**, silently. A major version bump instead makes the old code raise `UnsupportedStorageVersionError` and fail setup. Neither is acceptable for user-authored content in the shared Store.

**Why it happens:**
The existing Store pattern is "additive key, no version bump, only written when non-empty" (manager.py:1390-1405). That is fine for derived or cheap state (`previous_states`, `native`). It is wrong for user-authored content.

**How to avoid:**
- Persist local overrides in a **separate Store file** (for example key `mqtt_actions.local_actions`, version 1, minor 1). Implement `_async_migrate_func` from day 1. Old code never opens that file, so a downgrade then upgrade keeps the overrides.
- Key the file by `device_id`. Never prune it at start based on which mirrors were restored. Prune only on an explicit user action or on a confirmed final removal.
- On `async_remove_mirror`, either keep the overrides as orphans for N days with a Repairs hint, or delete them only after a confirmable Repairs flow. Make it an owner decision and record it in a D-xx.
- Add the new file to `async_remove_local_state` (hub removal). Today it removes only `STORE_KEY` (manager.py:419-433).
- Load the overrides in `_async_load_store`, before `_async_restore_mirrors`. A restored mirror's first Script build must already include its local branches, so `run_on_startup` with a retained replay runs them. Today's comment at manager.py:1479 shows the Script must exist before the subscribe.

**Warning signs:**
- A test that changes the owner document (rev+1, changed actions, a re-pin with the same content under a new owner) does not assert that the local overrides survive.
- A restart test with a corrupted cached payload loses the overrides.
- `grep STORE_` shows the overrides inside `_base_data_to_save`.

**Phase to address:** P-MIR-DATA. The downgrade round trip (v1.1 Store, then v1.0.1 code, then v1.1 code) belongs in P-VER as a bench check.

---

### Pitfall 5: The trigger key drifts, so local actions orphan or resurrect when the owner changes options

**What goes wrong:**
`trigger_key(value)` is `sha256(value.lower())[:12]`. Its docstring says "The key is never stored", and the D-03 invariant locks the StateValue only within one owner edit. In practice:
- The owner removes a Select option. The follower's local actions for it are orphaned. If they stay keyed and invisible, they are dead data the user cannot see or delete.
- The owner removes an option and later adds one with the same StateValue in a different case (`On` and `on` share a key). The old local actions silently come back on a trigger the user may no longer expect.
- An adopter publishes changed content. The same thing happens, with no owner continuity.
- Storing the derived 12-hex key breaks the "never stored" contract. Any future change of `trigger_key` (casefold, a longer prefix) orphans every stored override.
- A changed `kind` for the same id (rare, but `parse_document` allows any valid document) would map Switch ON/OFF overrides onto Select options.

**How to avoid:**
- Store overrides keyed by the **lower-cased StateValue**, which is what `actions_hash` already uses. Store the display label and the device `kind` next to it. Derive `trigger_key` at runtime only.
- On every applied owner document, reconcile the overrides against `spec.accepted`:
  - matched overrides are active
  - unmatched ones become **inactive orphans**, never deleted silently. Show them in the flow and in one Repairs issue per device ("local actions for removed option X are inactive"), with a fix flow to delete them.
  - a `kind` mismatch makes all overrides of the device inactive.
- Decide explicitly, and record it, whether a re-added option re-activates its old override. The safe default is: yes, but with a log line and the Repairs hint cleared.

**Warning signs:** No test removes an option that has local actions. The runner never logs "inactive local actions". The Store contains 12-hex keys.

**Phase to address:** P-MIR-DATA (model and reconcile), P-MIR-UI (orphan display and Repairs).

---

### Pitfall 6: Adoption merges, keeps or drops local actions without a decision

**What goes wrong:**
`_async_adopt_locked` turns a mirror into an owned subentry from `mirror.spec` and drops the mirror (`_async_drop_mirror` removes its approval and Script). With MIR-01 there are three possible implicit outcomes, and all are bad:
- (a) Local actions are merged into the owned content and published. This leaks them to every instance and puts them in front of other followers' approval as if the original owner had written them.
- (b) Local actions are silently discarded. The device now runs owner actions here that were "replaced", so the behavior changes at the moment of adoption.
- (c) The override file still holds entries for an id that is now owned. Any code that applies overrides by id would run them on top of the owned device.

There is also a verified collision trap. If overrides are stored as a config subentry with `unique_id=device_id`, then `async_add_subentry` for the adoption raises `AbortFlow("already_configured")`. Subentry unique IDs are unique across all subentry types of an entry (`config_entries.py:2764-2772`). The adoption then takes its rollback path.

**How to avoid:**
- Overrides apply to mirrors only. Enforce it at the application point (`if device_id in self.devices: ignore`), not just in the flow.
- Treat adoption with local overrides as an explicit user choice in the adopt service or flow. For example, "discard local actions" versus "keep them inactive in case the device becomes a mirror again". Never offer an automatic merge into owned content. A user who wants them published can copy them in the owned device's reconfigure flow.
- Keep the adoption refusal rules unchanged: approval `pending` or `blocked` still refuses adoption, even when every trigger is replaced locally (T-04-50). Replace mode must not become a way around "unreviewed remote actions never become owned".
- Do not store overrides as subentries. If ever needed, give them a unique ID that is not the device_id.

**Phase to address:** P-MIR-DATA (rule and test), P-MIR-UI (adopt dialog text).

---

### Pitfall 7: Breaker and run mode drift. A local edit does not release the breaker, a persisted trip survives a fix, or two sources double-count

**What goes wrong:**
- The run mode (`queued` or `restart`) and the breaker limits come from the owner document. Local actions inherit them, and a follower cannot change them. In restart mode, every new edge cancels in-flight local actions too, which surprises users with long local sequences.
- A mirror's breaker fingerprint is `device.signature = canonical_json(parsed.content)` (manager.py:2014, 2034). It is persisted on a trip (2498) and compared at start (2514). Two consequences:
  - Editing local actions does not release a tripped breaker. An owned device's reconfigure does release it.
  - A trip caused by a local loop stays tripped across restarts after the user fixed it, until a reload.
- If two Scripts are introduced per device, a naive implementation counts each enqueue in the breaker (double counting). It may also stop only one Script on a trip (`async_stop_runs` stops one Script today). Then a loop in the other source keeps publishing.

**How to avoid:**
- Keep one breaker per device, counted per edge in `_run_trigger` (as today), and one Script per device (see Pitfall 3).
- Treat a local override edit like a reconfigure: rebuild the Script under the manager lock, use a fresh breaker, delete the breaker issue and pop `_tripped`.
- Include a digest of the active local overrides in the fingerprint used for `_tripped`, but not in anything published.
- State in the flow and the docs that run mode, breaker limits and `run_on_startup` are the owner's and apply to local actions.

**Warning signs:** No test trips the breaker through a local action and then edits the local actions.

**Phase to address:** P-MIR-DATA.

---

### Pitfall 8: Refactor regressions when IN-04 extracts takeover, replay and guard orchestration (the WR-01 class)

**What goes wrong:**
The fixed start-up order in `async_start` (manager.py:798-817) is load-bearing:
1. The lock is held.
2. `sync`, presence and retrigger start.
3. Orphan cleanup, then reconcile.
4. `_async_native_takeover`, whose own fixed order is: migrate payload, then takeover, then replay-twin removal, then registry flush, then retained clear.
5. `_arm_duplicate_guard`, then publish the owned devices, then `_check_discovery_enabled`.
6. After the lock: availability, heartbeat, cutover, replay catch.

There are also subtle sync/async contracts:
- `_on_duplicate_registry_updated` defers with `loop.call_soon` (it must not nest inside the registry event).
- `@callback` methods must stay synchronous.
- `_disable_duplicates` returns early when `_cancel_duplicate_guard is None`, so arming has to come first.

Typical extraction mistakes:
- Turning a `@callback` into a coroutine, which moves work by one loop iteration.
- Moving the guard arming after `_async_publish_owned`.
- Duplicating `_running` and lock checks inconsistently.
- Leaving tests that patch `custom_components.mqtt_actions.manager.takeover.<fn>` or `Manager._remove_replay_twins`. These still pass but no longer intercept the moved code, so they pass vacuously.
- Changing behavior "while at it" (for example the CR-01 "disable, never remove" rule), which mixes a refactor with a fix.

**Why it happens:**
A 2,613-line module with ordering encoded only in comments. Reviewers saw exactly this class as WR-01.

**How to avoid:**
- Do IN-04 as a **pure move**, behavior-neutral, in its own plan and commits, **before** MIR-01 touches the mirror paths.
- First add an ordering test that records the call sequence of the start-up steps through spies, so the order becomes executable.
- After the move, `grep -rn "patch(.*manager\." tests/` and update every target to the new module.
- For each moved function, break it once on purpose (mutation check) and confirm that at least one test fails.
- Keep the extracted unit's public surface small, for example `NativeMigration(manager).async_run_startup()`. Do not pass the lock around; the caller holds it, as documented today.
- No new features and no bug fixes in the same plan. Findings go to the review disposition.

**Warning signs:** The test count is unchanged but some tests no longer import the old path. A diff shows `async def` where `@callback def` was. Coverage of `takeover.py` drops.

**Phase to address:** P-INFO, before P-MIR-DATA. Run the deep cross-file review after P-MIR-DATA and **before** the P-VER bench re-run (a v1.0.1 lesson).

---

### Pitfall 9: Tests that "pin HA internals" are silent, too weak or flaky on the daily PHACC bump

**What goes wrong:**
- `takeover.async_flush_registries` calls `registry._store.async_save(registry._data_to_save())`, and `except Exception` turns any API change into a warning (takeover.py:308-325). A test that only checks "no exception" passes after a core rename, and the early write is lost silently. That is IN-04, part 1.
- The no-clear guarantee depends on core's eager task in `Entity._async_registry_updated` (`helpers/entity.py:1591-1592`, `eager_start=True`), which unsubscribes before the remove event (IN-02, review 2). If core drops `eager_start`, only a behavioral test catches it.
- A pin test that fails is easy to "fix" by marking it xfail, and the suite already carries 2 strict xfails. That turns the alarm off.

**How to avoid:**
- Pin each internal twice:
  - **structural:** `hasattr(registry, "_store")`, `callable(registry._data_to_save)`, and that the signature has no required args
  - **behavioral:** after `async_flush_registries`, the registry file content (or a spy on `Store._async_write_data`) shows the change before the scheduled delay
- For the eager task, assert the observable outcome: no falsy publish on the discovery topic after removing a loaded row. Do not assert the mechanism.
- Give each pin test a failure message that names the documented fallback (for example "core changed registry internals: switch to waiting for the scheduled save, see takeover.py docstring").
- Make the IN-02 review-2 fix independent of the internals where possible. For example, unsubscribe or disable explicitly before the remove, so the test pins a safety net and not the only guarantee.
- Never use `xfail` for internals pins; let them fail CI. Group PHACC bumps weekly (Dependabot) so a red build points to one core release.

**Phase to address:** P-INFO.

---

### Pitfall 10: The v1.0.1 release is tagged from the wrong commit, with the wrong manifest version, or bench evidence that does not cover the tagged bytes

**What goes wrong:**
- `manifest.json` on `main` still says `"version": "1.0.0"`. There are 183 commits after `v1.0.0`, 16 of them in `custom_components`. `release.yml` `check-version` rejects a `v1.0.1` tag until the manifest is bumped. That part is good. The trap is bumping after the bench run:
  - The manifest version flows into the Discovery export (`origin.sw_version`, discovery.py:134, 156) and the heartbeat.
  - UAT-04 checks the export shape, so the bench evidence would be for different bytes than the release.
- If v1.1 code lands on `main` before v1.0.1 is tagged, "tag main" ships half of MIR-01 as 1.0.1. "Tag an older commit" then needs the manifest bump on that lineage, which means a release branch, and the bench must run on that branch's SHA.
- The `[ci skip]` lesson from v1.0: a squash merge copies `[ci skip]` from PR commits into the head commit, and the tag-triggered workflow does not run.
- **HACS selection (verified in `hacs/integration` source):** HACS takes the first non-draft, non-prerelease entry of the GitHub releases list as `last_version`. GitHub's `created_at` for a release is the **date of the tagged commit**, not the publish date (GitHub REST docs; MEDIUM). Consequences:
  - Releasing v1.0.1 from an old-lineage commit *after* v1.1.0 cannot become "latest". That is harmless.
  - A v1.1.0 tagged on a commit older than the v1.0.1 release-branch commit would sort below v1.0.1, and HACS would keep offering 1.0.1. This can happen when the release branch has a later commit date than the v1.1.0 merge base.
- A `v1.1.0-rcN` with a hyphen becomes a prerelease (release.yml:62-65). HACS shows it only with "show beta". That is useful for bench installs but invisible to normal users.

**How to avoid (sequence):**
1. Freeze: no MIR-01 or IN-04 commit on `main` until v1.0.1 is tagged. Otherwise cut `release/1.0.1` from the v1.0.1 close commit.
2. Bump `manifest.json` to `1.0.1` and update the docs and changelog; commit without `[ci skip]` anywhere in the PR commits.
3. Deploy **that SHA** to ha-a, ha-b and ha-c. Run UAT-02 (replay with restarts) and UAT-04 (export shape). Record the SHA in the evidence.
4. Tag `v1.0.1` on exactly that SHA, and the user pushes it. Check that `check-version`, all three tiers, hassfest and HACS ran.
5. If a release branch was used, merge it back so `main`'s manifest is at least `1.0.1`. Then v1.1.0's commit is newer and sorts first.

Repeat the same steps for v1.1.0 in P-VER. Bump the manifest to `1.1.0` before the final bench run, not after it.

**Warning signs:**
- The bench evidence lacks a commit SHA.
- `jq .version manifest.json` does not match the tag about to be created.
- The release workflow is missing from the Actions tab after a tag push.

**Phase to address:** P-REL1 and P-VER.

---

## Moderate Pitfalls

### Pitfall 11: Re-trigger acknowledgements lie once local actions exist

`RetriggerCoordinator._run` answers `executed`, `not_approved` or `error/no_actions` from `can_run` and `approval_state`. With MIR-01, two answers become misleading:
- On a follower with replace mode, an owner's re-trigger runs local actions and answers `executed`. The requester believes its own actions ran.
- In additive mode with an unapproved owner part, only the local part runs, and the answer is still `executed`.

**Prevention:** Decide the semantics and record them in a D-xx. Recommended: the ack status stays as it is for wire compatibility (mixed fleets with v1.0.x read it), and a new optional field `local: true/"partial"` is added that older readers ignore. Follow the additive-marker pattern and keep the ACK wire format backward compatible. Test both modes. **Phase:** P-MIR-DATA.

### Pitfall 12: Local actions are edited through a path that reloads the entry or races the manager

- Storing overrides in `entry.options` fires the update listener and `async_reconcile` on every edit. The reconcile handles owned subentries only, so the overrides would not be applied, or a reload would be needed. A reload restarts all Scripts, cancels runs and re-runs the takeover and the replay catch.
- Editing without the manager lock races `async_apply_mirror`, which rebuilds the Script and unloads the old one after registering the new one. Two concurrent rebuilds can leave the stale Script in place.

**Prevention:**
- The flow calls a manager method, for example `async_set_local_actions(device_id, value, mode, actions)`. That method takes `self._lock`, validates, persists to its own Store, then calls `_async_refresh_mirror_script`. This is the pattern of `async_approve` (manager.py:1487-1513).
- Refuse the call when the entry is not loaded or the id is not a mirror.

**Phase:** P-MIR-DATA and P-MIR-UI.

### Pitfall 13: Local actions are validated like broker content, or not validated at all

- Running local actions through `parse_document`, the static denylist or the cross-instance `device_id` warning (`find_device_ids`, D-10) is wrong. Local actions run only here, so a `device_id` target is legitimate, and the warning misleads.
- Skipping validation is also wrong. Persist the RAW list (actions.py says so). Deep-validate it with `async_validate_actions` on save, because a local check is appropriate for local content. Re-validate at Script build: an invalid local trigger is reported and skipped, while the owner part keeps working.
- Cap the size and depth. Use `MAX_ACTION_DEPTH` and a per-device byte cap, so the Store (worst case `MAX_MIRRORS` times overrides), diagnostics and the flow stay bounded.

**Phase:** P-MIR-DATA.

### Pitfall 14: Diagnostics, logs or Repairs leak local action content

`diagnostics._device_row` is an allow-list with "no name and no action content". Adding the override dict to it, or logging `str(err)` from schema validation (actions.py warns that the error text may quote values), leaks entity IDs and payloads.

**Prevention:**
- Add counts only, for example `"local": {"active": n, "inactive": m, "replace": k}`.
- Log device and trigger labels only. The mirror device name comes from the broker, so a local failure issue on a mirror still needs `escape_markdown`, as `_restricted` does today.

**Phase:** P-MIR-UI.

### Pitfall 15: The Repairs hint for customized duplicates (IN-03 review 2, WR-03 cases) reintroduces removal or spams issues

- The fix flow must never remove registry rows. Removing a row core discovered while it was disabled makes core clear a foreign retained topic (CR-01).
- Offer guidance, or a "disable this one" action, never "delete".
- Create the hint from the guard pass, deduplicated per device. Do not create it from every registry event.
- Use delete-then-create when the content changes. Replacing an issue keeps its dismissal (Pitfall 8 of v1.0).
- Add the issue prefix to `ISSUE_DEVICE_PREFIXES` and to the hub-removal cleanup.
- Ship `en` and `de` translations and a `tests/test_docs.py` claim if the README mentions it.

**Phase:** P-INFO.

### Pitfall 16: Partial counts and mid-loop exceptions (IN-01 review 2) are fixed by widening the `except`

The loop in `_remove_replay_twins` must keep its per-device isolation. The fix is to accumulate the partial count before the exception and to flush whenever `removed > 0 or an exception occurred`. Do not catch inside `takeover.remove_replay_twins` and return 0, which would hide the emptied MQTT device. **Phase:** P-INFO, together with IN-04 (same code region; do the pure move first, the fix second).

---

## Minor Pitfalls

- **Re-approval UX after replace.** With every trigger replaced, the approval issue still asks for approval. Explain in the issue or flow text that approving is needed only if a trigger goes back to "in addition to". Do not auto-dismiss it. (P-MIR-UI)
- **Test-topic exposure.** A non-native mirror subscribes to the test topic (manager.py:2097-2100). Any broker client can then run *local* actions without approval, as it already can for owned devices. That matches the documented cooperative-broker decision. Mention it in the security accepted-risks log, not as a new todo (memory: no auth push). (P-MIR-UI docs)
- **Native test buttons.** Buttons exist per owner trigger. A local action on a trigger the owner later removed has no button. That is consistent with the orphan handling; document it. (P-MIR-UI)
- **Store key-set tests.** Several tests assert the exact Store key set. Following the "only write when non-empty" pattern in the main Store avoids churn, and a separate Store file sidesteps it entirely. (P-MIR-DATA)
- **`hacs.json` `homeassistant` floor.** Bump it from `2026.9.0` only when MIR-01 needs a newer core API. If a selector feature such as an ActionSelector option is used, check its minimum core version. (P-VER)
- **Stale verification again.** Any fix after the final verification makes reports stale (v1.0, v1.0.1 lesson). Plan the re-verification as the very last step, after the deep review. (P-VER)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Merge local actions into `TriggerSpec.actions` | Runner unchanged | Breaks approvals, adoption leaks, export leaks (Pitfall 1) | Never |
| New key in the main Store without a version bump | Matches the existing pattern | Downgrade drops user content silently (verified) | Only for derived or cheap state, never for local actions |
| Prune overrides at start like approvals | Symmetric code | User work lost on a parse failure or upgrade | Never |
| Store the derived `trigger_key` | Direct lookup | Orphans everything if the key function changes | Never; store the lower-cased StateValue |
| Guard the whole combined tree | One `guard_actions` call | Local actions get the mirror denylist | Acceptable only as an explicit, documented owner decision |
| Refactor and fix in one plan (IN-04 + IN-01) | Fewer plans | WR-01-class ordering bugs hidden in a move diff | Never |
| `xfail` an internals pin on a core bump | Green CI | The alarm is gone | Never |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| HA `Store` | Bump the major version without `_async_migrate_func` (raises `NotImplementedError`), or bump only the minor version and expect old code to keep keys | Separate file for local actions, a migrate func from the start, and a downgrade round trip on the bench |
| Config subentries | Store overrides as a subentry with `unique_id=device_id` | Unique IDs are entry-wide across types (verified), so adoption aborts with `already_configured`. Do not use subentries for overrides. |
| Config subentries | Attach mirror entities to an override subentry | `async_remove_subentry` clears entities and devices of that subentry (`config_entries.py:2709-2713`), so mirror entities would vanish |
| HA `Script` `parallel` | Assume `stop` and response variables behave as in a plain sequence | Exceptions are isolated (gather with `return_exceptions`); verify `stop` and `continue_on_error` in branches with a pin test |
| Entry update listener | Store overrides in `entry.options` | Every edit fires a reconcile or reload. Use a manager method under the lock with its own Store. |
| HACS / GitHub releases | Assume "latest" means latest published | HACS takes the first non-prerelease in the list, and `created_at` is the commit date. Tag releases on monotonically newer commits. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Rebuilding every mirror Script on any override save | UI lag; running sequences cancelled on unrelated mirrors | Rebuild only the edited device under the lock | With tens of mirrors (`MAX_MIRRORS=100`) |
| Unbounded local action size | Store writes of several MB, slow `async_delay_save`, large diagnostics | Per-device byte cap plus `MAX_ACTION_DEPTH` | A few large sequences times 100 mirrors |
| Deep validation of all overrides at start | Slow start-up, timeouts on small boards (hassio-n2plus) | Validate on save; at build, validate only the active triggers | Many mirrors on an ARM host |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Combined Script built unrestricted | Owner (broker) actions bypass the denylist guard | The guard applies to owner subtrees always; pin it with the existing denied-call test plus local actions |
| Replace mode treated as "approved" or "no actions" | Switching back to additive runs unreviewed remote actions | `approval_state` from owner content only; owner branch needs an exact hash match |
| Adoption merges local actions | Follower content published to every instance under a new owner | Overrides are never part of owned content; explicit user choice on adopt |
| Local actions loaded from the Store unchecked | A tampered Store injects actions | Parse defensively like the other `_parse_*` (types, caps); deep validation at build |
| Error text with action content in logs or Repairs | Leaks entity IDs and payloads | Log labels only; `escape_markdown` for broker-sourced names |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Orphaned overrides invisible | "My local actions stopped working" with no hint | Show inactive overrides in the flow plus a Repairs issue per device |
| No indication which source ran | Confusion about whether owner or local actions ran | Run-variable `source` in traces; log "local" in the run log line |
| Owner settings (run mode, breaker, startup) not explained | Local sequences cancelled in restart mode unexpectedly | Show the owner's settings read-only on the local-actions step |
| Approval nag for a fully replaced device | Users approve blindly to silence it | Issue text explains why approval still matters |

## "Looks Done But Isn't" Checklist

- [ ] **Local actions on a mirror whose owner has no actions at all.** Verify the Script is built and `can_run` is True for that trigger.
- [ ] **Local actions on a blocked mirror.** Verify they run, and the owner part does not.
- [ ] **Owner document change (rev+1) and same-content re-pin.** Verify the overrides are still active afterwards.
- [ ] **Restart with an unparseable cached payload.** Verify the overrides are still in the Store after the next save.
- [ ] **Downgrade round trip (v1.1, then v1.0.1, then v1.1).** Verify the overrides survive.
- [ ] **Adoption with overrides.** Verify the published document has no local action, and the user chose what happens to the overrides.
- [ ] **Re-trigger on a replace follower.** Verify the ack semantics match the D-xx.
- [ ] **Breaker trip caused by a local loop.** Verify that editing the local actions releases it.
- [ ] **Hub removal.** Verify the override Store file is removed too.
- [ ] **Diagnostics.** Verify no action content and only counts.
- [ ] **IN-04.** Verify every `patch(...)` target points at the new module and a mutation check fails at least one test per moved function.
- [ ] **v1.0.1 tag.** Verify the manifest says 1.0.1 *before* the bench run, the bench evidence names the SHA, and the release workflow ran.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Local actions published through adoption | HIGH | The new owner republishes content without them (rev+1); followers re-approve; the leaked actions stay in broker history |
| Overrides lost by downgrade or pruning | HIGH (user re-entry) | Restore `.storage/mqtt_actions.*` from an HA backup; prevention only |
| Owner actions ran unapproved | HIGH (trust breach) | Hotfix release; security advisory in README Limitations; audit with `/gsd-secure-phase` |
| Wrong commit tagged as v1.0.1 | MEDIUM | Delete the GitHub release and tag before HACS users update; re-tag the correct SHA; never re-use a tag that was already installed, use v1.0.2 instead |
| Refactor reordered start-up | MEDIUM | Revert the move commit (pure move, so it is atomic), re-apply with the ordering test first |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1 Leak into the owner spec, hash or adoption | P-MIR-DATA | Hash-equality and adoption-bytes tests |
| 2 Trust gate restructure | P-MIR-DATA | 4x3x2 parametrized matrix test |
| 3 Two sources in one Script | P-MIR-DATA | Guard test with local actions; per-source issue test; `parallel` pin test |
| 4 Silent loss (rev, start-up, removal, downgrade) | P-MIR-DATA, P-VER (bench downgrade) | Store survival tests; bench round trip |
| 5 Trigger-key drift and orphans | P-MIR-DATA, P-MIR-UI | Option removal and re-add tests; Repairs issue test |
| 6 Adoption semantics | P-MIR-DATA, P-MIR-UI | Adopt tests for both choices; refusal still holds |
| 7 Breaker and run mode | P-MIR-DATA | Local-loop trip, edit, release test |
| 8 IN-04 ordering regressions | P-INFO (before MIR) | Ordering spy test; mutation check; patch-target grep |
| 9 Internals pins | P-INFO | Structural plus behavioral pins with fallback messages |
| 10 Release mechanics | P-REL1, P-VER | SHA in evidence; `check-version` green; Actions run present |
| 11 Re-trigger ack | P-MIR-DATA | Ack tests for replace and partial |
| 12 Edit path and races | P-MIR-DATA, P-MIR-UI | Concurrent edit plus document apply test under the lock |
| 13 Validation of local content | P-MIR-DATA | `device_id` target allowed; caps enforced |
| 14 Diagnostics and log leak | P-MIR-UI | Diagnostics snapshot test |
| 15 Repairs hint for duplicates | P-INFO | No registry removal; dedup and dismissal tests; translations |
| 16 IN-01 partial count | P-INFO | Mid-loop exception test asserts count and flush |

## Sources

- Codebase at HEAD `8157225`, files under `custom_components/mqtt_actions/`:
  - `manager.py`: start-up order 768-817, takeover 1027-1098, Store 1365-1440, mirror apply, approve and adopt 1442-1601, approval and Script gate 1757-1863, removal 1865-1898, run path 2444-2605
  - `runner.py`, `trust.py`, `document.py`, `model.py`, `retrigger.py:404-455`, `diagnostics.py`, `portability.py`
  - `takeover.py:308-325`
  - `manifest.json`, `hacs.json`, `.github/workflows/release.yml` (HIGH)
- Installed core 2026.9.4 (HIGH):
  - `homeassistant/helpers/storage.py:426-460`: minor-version fallback and re-save, `UnsupportedStorageVersionError`
  - `homeassistant/config_entries.py:2700-2714`: subentry removal clears registry entries
  - `homeassistant/config_entries.py:2764-2772`: subentry unique ID is entry-wide
  - `homeassistant/helpers/script.py:711-727`: `parallel` uses gather with `return_exceptions`
  - `homeassistant/helpers/entity.py:1583-1593`: eager task
- Project history (HIGH): `.planning/RETROSPECTIVE.md` (lessons on `[ci skip]`, stale verification, review before the bench); `.planning/milestones/v1.0.1-phases/08-real-instance-verification/08-REVIEW.md` (CR-01, WR-01..04, IN-01..03); first Phase 8 review at commit `d72c46b` (IN-01..IN-04)
- HACS release selection: `hacs/integration` main, `custom_components/hacs/repositories/base.py` around lines 1100-1125, read via `gh api` (HIGH, primary source)
- GitHub REST docs, Releases: "The created_at attribute is the date of the commit used for the release" — https://docs.github.com/en/rest/releases/releases (MEDIUM; the ordering of the list endpoint is not documented explicitly)
- Background search on HACS version display: https://github.com/hacs/integration/releases, https://github.com/hacs/integration/issues/4782 (LOW, not used for claims)

---
*Pitfalls research for: per-instance local overrides on replicated, approval-gated HA integration (milestone v1.1)*
*Researched: 2026-10-11*
