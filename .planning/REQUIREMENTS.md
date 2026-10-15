# Requirements: MQTT Actions Integration

**Defined:** 2026-10-11
**Milestone:** v1.1 Local Actions on Mirrors
**Core Value:** A state change on one MQTT-backed device reliably triggers the configured actions on every connected HA instance, each executing them locally.

## v1.1 Requirements

Order is fixed by the owner: release v1.0.1 first, then the review findings, then MIR-01, then full re-verification and release v1.1.0.

### Release

- [x] **REL-01**: v1.0.1 is tagged on the commit whose manifest says 1.0.1, after UAT-02 and UAT-04 pass on the bench on exactly that SHA; release workflow, hassfest and HACS are green (closes ACCEPTED-GAP-V101 for that release)
- [ ] **REL-02**: v1.1.0 is tagged on a commit newer than v1.0.1 after all verification requirements pass; manifest says 1.1.0; release notes cover local actions and downgrade behavior

### Review Findings (Phase 8 info findings)

- [ ] **FIX-01**: A test fails loudly if the private registry API used for the immediate flush (`registry._store`, `registry._data_to_save`) disappears or stops writing (review 1 IN-04)
- [ ] **FIX-02**: The takeover, replay-catch and duplicate-guard orchestration lives in its own module outside `manager.py`, with unchanged behavior proven by the existing suite and a start-up ordering test (review 1 IN-04)
- [ ] **FIX-03**: Shared test helpers live in one module; no test module imports private helpers from another test module (review 1 IN-02)
- [ ] **FIX-04**: The guard test proves that the listener runs for a second create event and returns 0, not only that the registry restores the state (review 1 IN-03)
- [ ] **FIX-05**: README and troubleshooting say that a duplicate the user re-enables is disabled again at the next start (review 1 IN-01)
- [ ] **FIX-06**: A row that raises mid-loop in the replay catch leaves no emptied device behind and does not lose the partial count (review 2 IN-01)
- [ ] **FIX-07**: The no-clear guarantee for loaded rows no longer depends silently on the HA-internal eager task in `Entity._async_registry_updated` (made independent, or pinned by a test that fails loudly if core changes it) (review 2 IN-02)
- [ ] **FIX-08**: The user sees a non-fixable Repairs warning listing customized duplicates kept enabled (including the WR-03 cases); it disappears when none remain; no registry row is removed (review 2 IN-03)

### Local Actions on Mirrors (backlog 999.1)

- [ ] **MIR-01**: On a follower, the user sets local actions per trigger of a mirrored device (switch on/off, each Select option) with mode "in addition to" or "instead of" the owner's actions, from the integration's options
- [ ] **MIR-02**: Local actions run without approval, also while the owner's actions are pending, blocked or empty; the owner's actions still run only when their exact hash is approved
- [ ] **MIR-03**: In "in addition to" mode, owner and local parts run in parallel within the device's single Script; a runtime failure of one part does not stop the other; run mode and breaker stay device-wide
- [ ] **MIR-04**: Local actions never leave the instance: they are not in the central config, the actions hash, the export, diagnostics content or the adoption payload; existing approvals stay valid
- [ ] **MIR-05**: An empty "instead of" mutes the trigger on this instance
- [ ] **MIR-06**: Local actions survive owner content changes, renames, rev bumps, restarts and an owner re-pin
- [ ] **MIR-07**: Local actions of a Select option the owner removed are kept inactive, shown as orphaned in the flow, removable there, and re-attach when the same StateValue returns
- [ ] **MIR-08**: On a tombstone or an adoption, local actions are discarded and logged; `adopt_device` reports it in its response; nothing is discarded at start-up or on a transient prune
- [ ] **MIR-09**: Device mode (observe, disabled) and the circuit breaker apply to local actions; a local edit releases a tripped breaker
- [ ] **MIR-10**: Test buttons and the re-trigger service run the effective actions on this instance; no new status or reason words appear on the broker
- [ ] **MIR-11**: While the owner's actions are unapproved, `run_on_startup`, run mode and breaker limits from the owner's document do not govern local runs; safe defaults apply
- [ ] **MIR-12**: The approval issue shows how many triggers are replaced locally; the approval state stays pending and adoption stays refused
- [ ] **MIR-13**: Local action failures raise their own Repairs issue, independent of owner action failures
- [ ] **MIR-14**: Diagnostics show counts of local actions (per device, orphaned), never their content
- [ ] **MIR-15**: README documents modes, mute, parallel semantics, lifecycle (orphan, tombstone, adoption), downgrade behavior and the `{{ state }}` template caveat; UI texts exist in en and de

### Verification

- [ ] **QLT-01**: Every phase (1 to 12) has a current verification on the final build; `init.manager` reports none of Phases 9 to 12 as stale and `verification status` reads current for the archived Phases 1 to 8 (carried over from v1.0.1, extended to Phases 5, 6 and 8 on 2026-10-11)
- [ ] **QLT-04**: UAT-02 and UAT-04 pass on the bench on the final v1.1.0 build
- [ ] **QLT-05**: MIR-01 bench check on real instances: ha-b adds local actions to a device owned by ha-a ("in addition to", "instead of", owner device without actions), and nothing local appears on the broker

## Future Requirements

Deferred. Tracked but not in the current roadmap.

- **MAP-01**: Per-instance entity mapping for actions with instance-local entity IDs
- **AVL-01**: Heartbeat-based entity availability when the owner is offline
- **MIR-F1**: Local actions on owned devices
- **MIR-F2**: Export and import of local actions (HA backup covers them today)
- **MIR-F3**: Optional re-trigger ack field telling which parts ran (owner, local)
- **MIR-F4**: Downgrade round trip v1.1 → v1.0.1 → v1.1 checked on the bench

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automatic merge of local actions into owned content at adoption | Would publish one follower's local content to every instance |
| Step-level patches of the owner's action sequences | Fragile against owner edits; per-trigger add/replace covers the need |
| New re-trigger status or reason words on the wire | v1.0.x peers drop answers with unknown words |
| GuardedTemplate on local actions | Local actions have owned-device trust; owned devices are not guarded either (owner decision 2026-10-11) |
| Local override of run mode or breaker limits | Run mode and breaker stay device-wide so one Script keeps consistent semantics |
| Separate Script ("local lane") per mirror | Breaks device-wide serial/restart semantics; parallel branch in one Script chosen (owner decision 2026-10-11) |
| Authenticate or ACL-protect the cutover gate (WR-03) | Moves with the EMQX migration |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| REL-01 | Phase 9 | Complete |
| FIX-01 | Phase 10 | Pending |
| FIX-02 | Phase 10 | Pending |
| FIX-03 | Phase 10 | Pending |
| FIX-04 | Phase 10 | Pending |
| FIX-05 | Phase 10 | Pending |
| FIX-06 | Phase 10 | Pending |
| FIX-07 | Phase 10 | Pending |
| FIX-08 | Phase 10 | Pending |
| MIR-01 | Phase 11 | Pending |
| MIR-02 | Phase 11 | Pending |
| MIR-03 | Phase 11 | Pending |
| MIR-04 | Phase 11 | Pending |
| MIR-05 | Phase 11 | Pending |
| MIR-06 | Phase 11 | Pending |
| MIR-07 | Phase 11 | Pending |
| MIR-08 | Phase 11 | Pending |
| MIR-09 | Phase 11 | Pending |
| MIR-10 | Phase 11 | Pending |
| MIR-11 | Phase 11 | Pending |
| MIR-12 | Phase 11 | Pending |
| MIR-13 | Phase 11 | Pending |
| MIR-14 | Phase 11 | Pending |
| MIR-15 | Phase 11 | Pending |
| QLT-01 | Phase 12 | Pending |
| QLT-04 | Phase 12 | Pending |
| QLT-05 | Phase 12 | Pending |
| REL-02 | Phase 12 | Pending |

**Coverage:**
- v1.1 requirements: 28 total
- Mapped to phases: 28 (Phase 9: 1, Phase 10: 8, Phase 11: 15, Phase 12: 4)
- Unmapped: 0

---
*Requirements defined: 2026-10-11*
*Last updated: 2026-10-11 after roadmap creation (traceability filled)*
