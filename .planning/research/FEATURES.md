# Feature Research: MIR-01 Local Actions on Mirrors (milestone v1.1)

**Domain:** Per-instance local overrides on a centrally owned, broker-synchronized HA device (HA custom integration `mqtt_actions`)
**Researched:** 2026-10-11
**Confidence:** HIGH for the dependencies on existing code (read from the source at `main`). MEDIUM for the recommended behavior, which is design judgment checked against analogous systems. LOW to MEDIUM for the analog facts themselves (web sources only).

Scope: only what MIR-01 adds. The owner fixed four rules, and this document treats them as constraints, not options:

1. Per trigger, a follower chooses **additional** ("in addition to") or **replace** ("instead of") the owner's actions.
2. Local actions need **no approval**.
3. Local actions **run even when the owner's actions are unapproved or blocked**.
4. Local actions are **never published** to the broker.

## Facts From the Codebase That Shape the Features

These facts drive most of the behavior decisions below.

| Fact | Where | Consequence for MIR-01 |
|------|-------|------------------------|
| A trigger's identity is `trigger_key(StateValue)`, a sha256 prefix of the lower-cased StateValue. The StateValue cannot be changed after the option exists. | `model.py` `trigger_key`, README "Select devices" | Key local actions by `(device uuid, trigger key)`. They survive friendly-name renames for free. If an option is removed and later re-added with the same StateValue, it gets the same key again. |
| Each device has exactly **one** `Script`. It is a `choose` that dispatches on the run variable `trigger_key`, so serial queuing and restart cancellation hold across all triggers (D-10, D-11). | `runner.py` `async_build_device`, `_async_build_script` | Local actions must go into the **same** Script as the owner's actions. A second Script per device would break serial ordering and restart cancellation. |
| A mirror's Script is built only when the stored approval equals the actions hash. `can_run()` false means "nothing runs" everywhere (state change, test button, re-trigger). | `manager.py` `_async_refresh_mirror_script`, `_run_trigger`, `_enqueue_test`; `retrigger.py` `_run` | The gate changes from "approved" to "approved owner part, or any local part". Every caller of `can_run` / `script_for` needs a review, not just `_run_trigger`. |
| A restricted build guards **the whole validated tree** (`guard_actions(validated)`) and refuses triggers with denied services. | `runner.py` lines with `guard_actions`, `_refuse_denied` | The owner part must be validated and guarded **separately** from the local part. Local actions are local content and must not be restricted, just as owned devices are not. |
| `ApprovalState` is a public word set (`owned`, `approved`, `pending`, `blocked`, `no_actions`, `unknown`) used by diagnostics, adoption and re-trigger. | `trust.py`, `diagnostics.py`, `retrigger.py` | Do not overload it. Report local actions as a separate dimension. |
| `parse_ack` reads named keys with `data.get` and ignores unknown keys. `status` must be one of a fixed word set. | `retrigger.py` `parse_ack` | A new optional ack field is backward compatible. A new status word is **not**: an older caller drops the ack and shows `no_answer`. |
| Mirrors have **no config subentry** and no edit dialog. They are devices directly under the hub entry. Adoption turns a mirror into a subentry. Release-locally turns a subentry into a mirror. | `manager.py` `_async_adopt_locked`, `async_release_locally`, README "Multiple instances" | MIR-01 needs a new authoring entry point. Data keyed by device uuid stays valid across both role flips. |
| Approval, mode, companion device and previous-state history "do not outlive the mirror" (A10, T-04-26). Tombstones can be forged by anyone with write access to the config topic. | `manager.py` `async_remove_mirror`, README Limitations | A forged tombstone would destroy **user-authored** local actions if they followed the same rule. An approval costs one click to redo; local actions are authored content. |
| The breaker counts only runs that would run actions, and stays tripped until a config change or reload. The trip is persisted via a fingerprint of the device signature. | `manager.py` `_run_trigger`, `_trip`, `_restore_tripped` | Local runs must count. Editing the local actions must count as a "change" that releases the breaker, otherwise a follower cannot fix its own loop except by a reload. |
| Export covers owned devices only. Import always assigns **new** uuids. | `portability.py` docstring | Local actions bound to mirror uuids cannot ride on the existing export format. |
| Diagnostics are allow-list only and never contain action content. | `diagnostics.py` | Local actions need allow-listed **structure** fields only (counts and modes, never actions). |

## Feature Landscape

### Table Stakes (Users Expect These)

Without these the feature feels broken or unsafe. Complexity is relative to this codebase.

| # | Feature | Why Expected | Complexity | Notes / Dependencies on Existing |
|---|---------|--------------|------------|----------------------------------|
| T1 | **Per-trigger local actions with mode `off` / `additional` / `replace`**, edited with the native action selector | This is the core of MIR-01. Users know the action editor from automations. | MEDIUM | Reuses `ActionSelector` and `async_validate_actions`. The action is stored per `(device uuid, trigger key)`. `off` (no entry) is the default, and the mode cannot be set without actions. Leaving the actions empty in `replace` mode is a valid way to mute a trigger locally (see D1). |
| T2 | **Authoring UI reachable from the integration page for every mirror** | Today a mirror is read-only and has no dialog. Without a UI there is no feature. | MEDIUM-HIGH | Recommended: a new subentry type `local_actions`, one per mirror (`unique_id` = device uuid). It gets an "Add local actions" button, reconfigure and delete for free, and the integration page lists which mirrors have local actions. **Never** attach the mirror's device to this subentry: HA removes the devices of a deleted subentry, so deleting local actions would delete the mirror's entities (see the pitfall). Alternative: a step in the hub options flow, which lists overlays less clearly. Needs a phase-level spike on subentry UI and device linkage. |
| T3 | **One Script per device, local actions composed into it** | Run mode (`serial` / `restart`) must mean the same thing whether a run executes owner actions, local actions or both. | MEDIUM | `runner.py`: the branch for a trigger becomes `replace` → local sequence only; `additional` → owner sequence (guarded, only if approved and not blocked) **then** local sequence. Validate and guard the owner part on its own, leave the local part unrestricted, then compose. This changes `_async_build_script`, which today validates and guards the combined tree. |
| T4 | **Local actions run when the owner part is pending or blocked** | Owner rule 3 | MEDIUM | `_async_refresh_mirror_script` must build a Script whenever any trigger has a runnable part. `_runnable` must hold triggers whose effective actions are non-empty. Static block (`info.denied`) or a pending approval removes only the owner part. |
| T5 | **Local actions are never published** | Owner rule 4, privacy, portability | LOW | Stored only locally: config entry subentry data or the Store, both covered by HA backups. They are never in the config document, the content hash, the actions hash, the Discovery export, the re-trigger request or diagnostics content. Add a test that serializes every outbound payload and asserts no local content. |
| T6 | **Local actions do not touch the approval hash and are not restricted by the denylist** | They are locally authored, like owned devices, which "are not restricted at all" (README). | LOW | `actions_hash` and approval stay as they are. Deep validation of local actions on save and on each build reuses the existing trigger-setup issue. Watch that `guard_actions` / `_refuse_denied` are never applied to the local part. |
| T7 | **Mode select (run / observe / disabled) gates local actions too** | The mode is "this instance runs nothing / only logs". A local exception would surprise users. | LOW | `effective_mode` already sits before `can_run` in every path. In observe mode, the log line should say whether owner actions, local actions or both would have run. |
| T8 | **Circuit breaker counts every run that executes anything, owner or local, once per change** | Loop protection is per device. Local actions are the most likely loop source, because they target local entities, including the mirror's own entity. | LOW-MEDIUM | `_run_trigger` already counts after `can_run`. A local-only run must count, and a trigger with no effective actions must not. A trip stops the whole Script, local part included. **Editing the local actions releases the breaker** on this instance. Include the local actions hash in the persisted trip fingerprint so that a restart with unchanged local actions stays tripped. |
| T9 | **Test buttons run the trigger's effective actions on this instance** | A test means "what would run here". With `replace` active on an unapproved mirror, that is the local actions. | LOW | `_enqueue_test` and `async_press_test` follow `can_run`. Optional: pass the run variable `local: true/false` per part so templates can tell. |
| T10 | **Re-trigger runs the effective actions on each receiving instance** | The README defines re-trigger as "runs the actions of one device again". For a follower with local actions, those are the effective actions. | LOW-MEDIUM | `retrigger.py` `_run`: answer `executed` when anything ran. Answer `not_approved` only when nothing is runnable **and** the owner part is pending or blocked. **Do not add a status word.** Old callers would drop the ack. An optional extra field is safe (see D4). |
| T11 | **Owner changes are absorbed without losing local actions**: rename, changes to the owner's actions, run mode or limits, owner flip by adoption elsewhere, ownership conflict | Overrides keyed by a stable id must survive the upstream changing around them, as ESPHome `!extend` on component ids and Z2M per-device entries by IEEE address do. | LOW | Keying by device uuid and trigger key gives this for free. A new owner with the same content only moves bookkeeping (`async_apply_mirror`, D-09), and the local actions stay attached. A changed owner actions hash makes the approval lapse. The `additional` triggers keep running their local part, and `replace` triggers are unaffected. |
| T12 | **Orphaned local actions are kept, shown and removable** when the owner removes a Select option | Silent deletion destroys user work on an owner's mistake. Silently keeping them is invisible, like a Z2M per-device key that does not match and fails silently. | MEDIUM | The orphan is kept dormant (it never runs, because there is no trigger) and is listed as "orphaned" in the local actions dialog. It is counted in diagnostics, and a Repairs hint offers "discard". If the owner re-adds the same StateValue, the key matches again and the local actions re-attach. Log that at info level. |
| T13 | **Tombstone or prune does not destroy local actions immediately** | Tombstones can be forged (README Limitations). Local actions are authored content, unlike an approval, which costs one click. | MEDIUM | On mirror removal, keep the local actions **detached** (dormant, bounded in number) and raise a Repairs issue: "local actions of removed device X were kept, discard?". If the same uuid returns, they re-attach. Deliberate difference from A10 / T-04-26. Document it next to "an approval does not outlive its mirror". |
| T14 | **Adoption keeps this instance's behavior unchanged** | Adoption is recovery: "the owner is gone, keep things working". Publishing local content or dropping it silently both change behavior somewhere. | MEDIUM | Recommended: the shared content stays exactly as approved, as today, so other followers keep running without re-approval. The local actions stay **local**, attached to the now-owned device, and keep running. The owned device's dialog shows them, with "remove" and an explicit "copy into shared actions". Copying is a normal edit that publishes and changes the hash, so followers must approve again. This requires overlays to be **role-independent** in storage and runtime (keyed by uuid, not by "is mirror"). Release-locally (owned → mirror) then also keeps them. The adoption precondition (owner part approved, T-04-50) stays unchanged. Local actions do not make an unapproved mirror adoptable. |
| T15 | **Diagnostics show structure of local actions, never content** | `docs/diagnostics.md` promises structure for every device. A bug report must show "this follower replaces 2 triggers locally". | LOW | Add `local_actions: {"additional": n, "replace": m, "orphaned": k}` per device row, plus a hub-level count of detached overlays. No trigger labels, because state values are on `TO_REDACT`. Extend the redaction test. |
| T16 | **Approval state stays truthful and separate** | `ApprovalState` feeds adoption, re-trigger and diagnostics. Overloading it, for example "approved" because everything is replaced, would break those gates. | LOW | Keep `approval_state()` about the owner part only. Add a separate accessor, e.g. `local_state(device_id)`, that returns `none`, `additional`, `replace`, `mixed` or `replace_all`. Diagnostics and UI show both. |
| T17 | **Visibility of which triggers are overridden** | Users must see that this instance does not do what the owner configured. This is the Syncthing receive-only lesson: local changes are always listed ("Locally Changed Items") and revertible. | LOW-MEDIUM | Minimum: the subentry list (T2) plus, in the dialog, per trigger the mode and owner state ("owner: approved / pending / blocked / no actions"). Plus one entity attribute on the mirror's Switch or Select, e.g. `local_actions: {"on": "replace"}`, keyed by StateValue. It names no action content and supports dashboards. A "revert all local actions" step = delete the subentry. |

### Differentiators (Competitive Advantage)

These are valuable but not required to ship MIR-01. They align with the core value of "each instance executes locally".

| # | Feature | Value Proposition | Complexity | Notes |
|---|---------|-------------------|------------|-------|
| D1 | **"Mute locally"**: `replace` with an empty action list | Lets a follower opt one trigger out (for example "do not run the owner's 'off' here") without approving or disabling the whole device. | LOW, if allowed by T1 | Decide explicitly. It is cheap and useful, but an empty `replace` must still count as "override active" for visibility (T17). It must not count as a run for the breaker (nothing runs). |
| D2 | **Suppress the approval Repairs request when every trigger with owner actions is replaced locally** | Approving content that can never run here is noise. | LOW-MEDIUM | The state stays `pending` (T16), so adoption still needs a real approval. Re-raise the request as soon as one replacement is removed. The alternative is a cheaper text change: add "N of M triggers are replaced locally" to the request. |
| D3 | **Approval dialog shows which triggers are replaced locally** | Helps decide what to approve. A replaced trigger's owner YAML is irrelevant here. | LOW | `ApprovalView` gets one extra bullet list. It is local data, so no escaping risk. |
| D4 | **Re-trigger ack carries the composition** (`"parts": "owner" / "local" / "both"`) as an optional field | The caller sees that an instance ran its own variant, so "executed" is not misread as "ran the owner's actions". | LOW | Backward compatible: `parse_ack` ignores unknown keys. It reveals to the broker that an instance has local overrides (structure, not content). Mention that in `docs/broker-acl.md`. |
| D5 | **Run variable `part` / `local`** inside local actions, next to the existing `device_id`, `state`, `trigger_key`, `test` | Lets one local sequence branch on test versus real, or know it runs replaced. | LOW | `runner.enqueue` already merges run variables. |
| D6 | **Export and import of local actions** keyed by mirror uuid (`mqtt_actions.export_local_actions` / `import_local_actions`, separate format) | Move overlays to a rebuilt instance on the same broker without a full HA backup. | MEDIUM | Separate format and service. Never mix it into `mqtt_actions_export` v1, whose import assigns new uuids, so the binding would be meaningless. Import must refuse uuids that are not a current mirror or owned device, or store them as detached (T13). HA backup already covers disaster recovery, so defer this. |
| D7 | **Local actions on owned devices** (authoring, not only the carry-over of T14) | An owner instance can run something only for itself (a local notify) without publishing it. | LOW once overlays are role-independent (T14) | Opening authoring for owned devices is a UX decision. `replace` on an owned device means "others run my published actions, I don't", which is confusing but legitimate. Defer unless T14 already exposes the UI. |
| D8 | **MAP-01-style variable mapping** (owner actions reference `{{ local.lamp }}`, each instance maps it) | Solves "different entity ids per instance" without duplicating the whole sequence. | HIGH | It is a different feature: it changes the meaning of approved content and the hash story. MIR-01's overlay is the simple first step. Keep MAP-01 for later. |

### Anti-Features (Commonly Requested, Often Problematic)

| Anti-Feature | Why Requested | Why Problematic | Alternative |
|--------------|---------------|-----------------|-------------|
| **Automatically merge local actions into the owned actions on adoption** | "Take control" in HA blueprints bakes the effective config into a standalone automation. It looks natural. | It publishes instance-local content (local entity ids, possibly secrets) to every client of the config topic. It changes the actions hash, so every other follower stops running until it approves again. That turns a recovery action into an outage. It also contradicts owner rule 4. | T14: keep them local and attached, and offer an explicit "copy into shared actions" edit. |
| **Partial patching of owner actions** (edit or remove one step of the owner's sequence, like ESPHome `!extend` / `!remove` or a Kustomize patch) | It is finer-grained than "replace all". | Owner steps have no stable ids. Any owner edit misaligns the patch, which is the Kustomize "failed to find unique target for patch" class of failure. It also blurs what was approved: a patched owner sequence is neither the approved content nor local content. | Whole-sequence `replace` per trigger. A follower who wants most of the owner's steps copies them into the local actions. |
| **Overloading `ApprovalState`** (for example reporting `approved` or a new word `local` when replace is active) | One status field is simpler to show. | Adoption, re-trigger and diagnostics rely on the word meaning "the owner content may run here". A new word breaks strict parsers of older peers in acks. | T16: a separate `local_state` dimension. |
| **New re-trigger status word** (`executed_local`) | It would be more precise. | `parse_ack` on v1.0.x callers rejects unknown status words, so the instance shows as `no_answer`. | `executed` plus the optional `parts` field (D4). |
| **Auto-approve the owner's actions when all triggers are replaced** | It removes the pending noise. | An approval is the explicit opt-in for remote content. It would silently make unreviewed content adoptable and runnable the moment a replacement is removed. | D2: suppress the request, keep the state `pending`. |
| **Local override of run mode, run-on-startup or breaker limits** | "My local actions need `restart`." | The device would have two run modes for one Script, or a split Script (see T3). It adds UI and a second fingerprint for little gain. The owner settings are validated ranges either way. | The document's settings apply to the whole device on this instance. Document that these owner-controlled settings also govern local runs, even while the owner part is unapproved. Revisit only if users ask. |
| **Separate Script for local actions** (owner Script plus local Script per device) | Simpler failure isolation, and the existing restricted build stays untouched. | It breaks serial queuing and restart cancellation across owner and local runs (D-10, D-11). Two runs of one change could interleave, and a restart would not cancel the other half. | One composed Script (T3). |
| **Sharing local overlays between followers** (a "follower group" that publishes overlays) | "Three followers need the same variant." | That is multi-writer editing, which PROJECT.md excludes, and it would need its own trust and approval path. | Make one follower the owner of a second device, or wait for MAP-01. |
| **Deleting local actions on tombstone, like approvals** | It looks consistent with A10 and T-04-26. | A forged tombstone (README Limitations) would destroy authored content. | T13: detach, keep dormant, ask in Repairs. |
| **Running local actions on payloads that match no trigger** ("catch-all local handler") | Some users want to react to every payload. | The accepted values come from the owner's document, and unknown payloads are logged and ignored (T-02-08). A catch-all widens the state-topic trust boundary. | A normal HA automation on the mirror's entity. |

## Expected Behavior Matrix (Edge Cases)

The recommendation is listed per scenario. "Effective actions" of a trigger on this instance means: `replace` → local only; `additional` → owner part (if approved and not blocked) then local; `off` → owner part (if approved and not blocked).

| Scenario | Expected behavior | Confidence |
|----------|-------------------|------------|
| Owner renames a Select option (friendly name) | Local actions stay, because the key comes from the StateValue. The UI label updates. | HIGH (code) |
| Owner removes a Select option | The local actions become orphaned: dormant, listed, counted in diagnostics, with a Repairs hint and "discard" (T12). The `select` entity already shows `unknown` for removed values. | MEDIUM |
| Owner re-adds an option with the same StateValue | The same key re-attaches the orphaned local actions, logged at info level. The user discarded them via Repairs if unwanted. | MEDIUM |
| Owner changes the owner actions (approval lapses) | The owner part stops (no Script part). `additional` triggers keep running the local part, and `replace` triggers are unaffected. The approval request appears as today (or D2/D3). | HIGH (owner rule) |
| Owner actions are statically blocked (denylist) | Same as pending: the owner part is absent and local actions run. The blocked issue stays. | HIGH (owner rule) |
| Owner part fails at run time (exception, or a templated service resolves to a denied one) in `additional` mode | Recommended: the run aborts, local part included, consistent with HA sequence semantics. The failure or denied-call issue is raised. The alternative (local first, or isolating the parts) is an owner decision, see Gaps. | MEDIUM |
| Owner tombstones or the mirror is pruned | The mirror goes as today. Local actions are **detached**, kept dormant, with a Repairs question to discard them. If the same uuid returns, they re-attach (T13). | MEDIUM |
| Mirror flips owner (adopted by a third instance, same content) | Only bookkeeping moves, and the local actions stay attached (T11). | HIGH (code) |
| Ownership conflict (two claims) | No change: the pin decides which document is mirrored, and the local actions apply to it. | HIGH (code) |
| This instance adopts a mirror that has local actions | The shared content is unchanged, and the local actions stay local and keep running on the now-owned device. "Copy into shared actions" is an explicit edit (T14). Adoption still requires an approved owner part. | MEDIUM (owner decision recommended) |
| This instance releases an owned device locally and becomes a follower | The local actions keyed by uuid stay and apply to the new mirror. | MEDIUM |
| Re-trigger received | Runs the effective actions. The status is `executed` if anything ran, and `not_approved` only if nothing is runnable and the owner part is pending or blocked (T10). | MEDIUM-HIGH |
| Test button pressed | Runs the effective actions locally and never changes the state (T9). On the legacy path, a remote test-topic press also runs the effective actions on this instance. | MEDIUM |
| Mode observe / disabled | Nothing runs, local included. Observe logs which parts would have run (T7). | HIGH |
| Breaker | One count per change that runs anything. A trip stops owner and local parts. Editing the local actions releases the trip on this instance (T8). | MEDIUM-HIGH |
| Run mode | The owner's mode applies to the composed Script. Within one run, the owner part runs first, then the local part (`additional`). `restart` cancels both (T3). | MEDIUM-HIGH |
| Run on startup | The owner's flag applies to the whole device, including local-only triggers (document it). | MEDIUM |
| Export / import | Not in `export_devices` (owned only, new uuids). HA backup covers local actions. A separate overlay export is D6, deferred. | HIGH (code) |
| Diagnostics | Counts per device and the number of detached overlays. No content (T15). | HIGH |
| Duplicate instance id (cloned backup) | The clone carries the same local actions, which is correct per instance. No special handling. | MEDIUM |
| A local action changes the mirror's own state (select_option on the mirror) | It publishes to the shared state topic, so **every** instance reacts, the owner included. Local actions are invisible to others, but their side effects are global. The per-instance breaker catches loops. Document this prominently. | HIGH (code) |

## Feature Dependencies

```
[T2 Authoring UI (subentry type local_actions)]
    └──requires──> [Overlay storage keyed by (device uuid, trigger key), role-independent]
                       └──requires──> [trigger_key / StateValue immutability]   (exists, model.py)

[T3 Composed Script] ──requires──> [split validate+guard of owner part vs local part in runner.py]
[T4 Local runs while pending/blocked] ──requires──> [T3] + [new runnable gate in _async_refresh_mirror_script]
[T7 modes], [T8 breaker], [T9 tests], [T10 retrigger] ──require──> [T4 new can_run semantics]
[T8 breaker release on local edit] ──requires──> [local actions hash in trip fingerprint]

[T12 orphans] ──requires──> [overlay storage independent of current triggers]
[T13 detached on tombstone] ──requires──> [overlay storage independent of mirror lifetime]
[T14 adoption carry-over] ──requires──> [role-independent overlays] ──enhances──> [D7 local actions on owned devices]

[T15 diagnostics], [T16 local_state], [T17 visibility] ──require──> [overlay storage] (read-only consumers)
[D2 suppress approval request] ──requires──> [T16]
[D4 ack parts field] ──requires──> [T10]

[Anti: auto-merge on adoption] ──conflicts──> [owner rule 4 "never published"]
[Anti: separate local Script] ──conflicts──> [D-10/D-11 run-mode semantics]
```

### Dependency Notes

- **Storage first:** every behavior row depends on one decision: overlays keyed by `(device uuid, trigger key)`, independent of whether the device is currently a mirror, owned or gone. Settle this, and its home (subentry data or Store), before the runner work.
- **The runner change is the risk centre:** `runner.py` today validates and guards the combined tree. Splitting the parts touches the trust gate (T-03-33, D-03, D-05). It needs tests proving that the owner part is still guarded and denied-refused, and that the local part never is.
- **`can_run` callers:** `_run_trigger`, `_enqueue_test`, `_on_test_message`, `retrigger._run`, and the `not_approved` decision. One semantic change, five call sites, each with existing tests to extend.
- **The Phase 8 IN-04 extraction** (takeover, replay and guard orchestration out of `manager.py`) is in the same milestone and touches `manager.py`. Do it **before** MIR-01, otherwise both phases fight over the same 2,600-line file.

## MVP Definition

### Launch With (v1.1.0)

- [ ] T1, T2: per-trigger `additional` / `replace` with the action selector, UI on the integration page
- [ ] T3, T4: one composed Script per device. Local runs while the owner part is pending or blocked.
- [ ] T5, T6: never published, no approval, not restricted
- [ ] T7, T8, T9, T10: mode, breaker (including release on local edit), test buttons, re-trigger with existing status words
- [ ] T11, T12, T13: survives owner changes. Orphans and detached overlays are kept, shown and discardable.
- [ ] T14: adoption and release keep local actions local and running
- [ ] T15, T16, T17: diagnostics counts, separate local state, visible overrides (dialog, subentry list, entity attribute)
- [ ] D1: empty `replace` = mute (decide yes or no; nearly free)

### Add After Validation (v1.1.x)

- [ ] D2 or D3: approval request aware of local replacements, once users report the noise
- [ ] D4, D5: ack `parts` field and run variable, once someone debugs a confusing `executed`

### Future Consideration (v1.2+)

- [ ] D6: overlay export and import. HA backup covers it until then.
- [ ] D7: authoring local actions on owned devices
- [ ] D8 / MAP-01: per-instance variable mapping

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| T1-T4 core overlay plus composed Script | HIGH | MEDIUM-HIGH | P1 |
| T5, T6 never published, unrestricted | HIGH (safety) | LOW | P1 |
| T7-T10 consistent gates (mode, breaker, test, re-trigger) | HIGH | LOW-MEDIUM | P1 |
| T11-T13 survive owner changes, orphans, detach | HIGH | MEDIUM | P1 |
| T14 adoption carry-over | MEDIUM | MEDIUM | P1 (rare path, but data loss otherwise) |
| T15-T17 diagnostics, state, visibility | MEDIUM-HIGH | LOW-MEDIUM | P1 |
| D1 mute locally | MEDIUM | LOW | P1/P2 |
| D2/D3 approval UX | MEDIUM | LOW | P2 |
| D4/D5 ack field, run variable | LOW-MEDIUM | LOW | P2 |
| D6 overlay export | LOW | MEDIUM | P3 |
| D7 owned-device authoring | LOW-MEDIUM | LOW (after T14) | P3 |
| D8 MAP-01 mapping | HIGH (long term) | HIGH | P3 |

## Analog Analysis

| Concern | ESPHome packages | HA blueprints | Zigbee2MQTT | Syncthing receive-only | Kustomize overlays | Our Approach |
|---------|------------------|---------------|-------------|------------------------|--------------------|--------------|
| Override key | Component `id` (`!extend id`, `!remove id`) | Blueprint inputs. "Take control" converts to standalone. | IEEE address under `devices` | File path | Resource kind and name | `(device uuid, trigger key)`. The key comes from the immutable StateValue. |
| Granularity | Merge by key, lists by id, scalars replaced | Inputs only, or everything after taking control | Per option | Per file | Strategic or JSON patch | Whole action sequence per trigger, `additional` or `replace`. No step patching. |
| Upstream removes the target | Build error (unknown id) | n/a | Wrong key fails **silently** | n/a | Build error "failed to find unique target" | Keep dormant, show, Repairs "discard" (neither silent nor fatal) |
| Visibility of local divergence | Only in the YAML | The automation shows its blueprint origin | None | "Locally Changed Items" list, red **Revert** button | Visible in overlay files | Subentry list, per-trigger mode in the dialog, entity attribute, diagnostics counts, delete = revert |
| Local changes propagate? | No | No | No | Never ("receive only") | No | Never (owner rule 4) |
| Convert to owned | n/a | "Take control" bakes inputs in, one-way, no more upstream updates | n/a | n/a | n/a | Adoption keeps shared content unchanged and local stays local. Merge only by explicit edit. |

Takeaways: (1) every mature system keys overrides by a stable id, and so do we. (2) Silent orphans (Z2M) are the worst outcome, and fatal errors (ESPHome, Kustomize) do not fit a runtime system, so keep orphans visible. (3) Syncthing shows that local divergence must be permanently visible and revertible in one step. (4) The blueprint "take control" path bakes the effective config in, which is right for a single instance and wrong for a broadcast document.

## Gaps / Open Questions for the Owner (resolve in discuss-phase)

1. **Runtime failure of the owner part in `additional` mode:** should the local part still run? Recommended: no (HA sequence semantics, one Script). The alternative is "local first" or isolating the parts with `continue_on_error`, which does not catch `DeniedServiceCallError` by design.
2. **Order in `additional`:** owner then local (recommended) or a per-trigger choice "before / after".
3. **Detached overlays on tombstone (T13):** keep until discarded (recommended), keep with a TTL, or delete like approvals.
4. **Adoption (T14):** keep local and running (recommended), or ask at adoption time (`adopt_device` field `local_actions: keep|discard`).
5. **UI home (T2):** subentry type `local_actions` (recommended, needs a spike on subentry/device linkage and the "Add" button label) or a hub options-flow step.
6. **D1 mute:** allow an empty `replace`?
7. **Storage home:** subentry data (backed up, visible, triggers the update listener and reconcile) or the Store (already holds approvals and modes). Check that a `local_actions` subentry type cannot be mistaken for a device subentry by `_device_subentries` and the reconcile.

## Sources

- Codebase at `main` (8157225): `custom_components/mqtt_actions/{model,runner,trust,manager,retrigger,breaker,modes,diagnostics,portability,config_flow}.py`; README.md; `.planning/PROJECT.md`; ROADMAP backlog 999.1. HIGH.
- ESPHome packages, merge rules and `!extend` / `!remove`: https://esphome.io/components/packages/ (official, merge rules); https://tecnoyfoto.com/en/esphome-substitutions-packages-guide (third-party, `!extend` / `!remove` syntax). MEDIUM.
- HA blueprints "take control": https://www.home-assistant.io/integrations/blueprint ; https://community.home-assistant.io/t/taking-control-variables/753819 . MEDIUM.
- Syncthing receive-only folders, "Locally Changed Items" and "Revert Local Changes": https://docs.syncthing.net/users/foldertypes.html ; https://forum.syncthing.net/t/what-is-local-additions-and-revert-local-changes-mean/15367 . MEDIUM.
- Zigbee2MQTT per-device options: https://zigbee2mqtt.io/guide/configuration/devices-groups.html ; https://privatehomelab.com/zigbee2mqtt-mqtt-topics-attribute-output-explained/ . LOW (merge rule not confirmed in the official docs).
- Kustomize orphan patch failure: https://discuss.kubernetes.io/t/kustomize-failed-to-find-unique-target-for-patch/10582 ; https://github.com/argoproj/argo-rollouts/discussions/890 . MEDIUM.

---
*Feature research for: MIR-01 per-instance local actions on mirrored devices*
*Researched: 2026-10-11*
