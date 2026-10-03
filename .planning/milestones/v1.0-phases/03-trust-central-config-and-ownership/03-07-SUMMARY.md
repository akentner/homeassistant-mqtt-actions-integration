---
phase: 03-trust-central-config-and-ownership
plan: 07
subsystem: testing
tags: [mosquitto, acl, broker-tests, multi-instance, readme, trust-model, tdd]

requires:
  - phase: 03-trust-central-config-and-ownership
    provides: "Owner and follower sync, tombstones and prune, approval gate and denylist, delete and hub removal (plans 03-01 to 03-06); FakeBroker, FakeGateway and make_instance (plan 03-01)"
provides:
  - "docs/broker-acl.md: Mosquitto ACL example (one user per instance, an external publisher limited to the state topic), topic table, limits and transport guidance; the broker tests run exactly this block"
  - "tests/broker/conftest.py: start_acl_broker factory (password file and ACL file, anonymous access off, skips without mosquitto or mosquitto_passwd)"
  - "tests/broker/test_acl.py: seven ACL enforcement tests against a real Mosquitto 2.1.2 reading the acl block from the document"
  - "tests/test_multi_instance.py: twelve acceptance scenarios for the five phase success criteria on three instances sharing one fake broker"
  - "README: Multiple instances, Trust model and approval, Deleting devices and removing the integration; Security, Behavior and Limitations rewritten; no stale single-instance claims"
  - "tests/test_repo_structure.py: ACL document, README phase 3 and device_id-in-example checks"
affects: [04-operations, verification]

requirements-completed: [TRU-04, STA-03, SYN-04, SYN-05, SYN-06]

plan_head_before: ed5906335ebbe4277e23f3bb68c08b5ae4f6c4d6
plan_head_after: 86a6aebf0b799832768eb7b25e187b568f54ccf6

actuals:
  tokens: 13500
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "Documentation as tested artifact: the test extracts the first fenced acl block from the document, substitutes the instance id markers and runs a real broker with that text, so the example cannot drift"
    - "Denial assertions never rely on an error: a denied QoS 1 publish may be acknowledged, so tests assert on what a live reader receives and on a retained read-back by a later subscriber"
    - "Scenario helpers over three instances (_trio, _count_services, _ran, _approve, _publish_order) that count service calls per instance and classify publishes into config, discovery and availability"

key-files:
  created:
    - docs/broker-acl.md
    - tests/broker/test_acl.py
  modified:
    - tests/broker/conftest.py
    - tests/test_multi_instance.py
    - tests/test_repo_structure.py
    - README.md

key-decisions:
  - "The ACL example uses one MQTT user per instance with a marker for its instance id in the availability write rule; device topics cannot be bound to an owner because device ids are random, so the document states cooperative ownership and names approval as the real gate"
  - "The external publisher user gets readwrite on the state wildcard only: no read of config documents (they carry the actions) and no write of config, test, discovery or availability"
  - "The ownership conflict scenario captures the issue registry events of the follower instead of reading the registry at the end: the conflict issue is created and then deleted again as soon as the owner's healing republish is re-seen (see Issues Encountered)"
  - "No production file changed: every scenario passed against the code of plans 03-02 to 03-06, so there is no fix commit"

patterns-established:
  - "start_acl_broker(acl_text, users) fixture for broker-tier tests that need authentication"

coverage:
  - id: D1
    description: "The ACL example in docs/broker-acl.md is the text a real Mosquitto enforced: Home Assistant users write config, state, test, discovery and their own availability, the external publisher writes the state topic only and cannot read config, an instance cannot write another instance's availability, and a denied publish leaves no trace"
    requirement: TRU-04
    verification:
      - kind: integration
        ref: "tests/broker/test_acl.py#test_documented_acl_block_is_the_tested_acl"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_ha_users_can_write_config_state_test_and_discovery"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_external_publisher_can_only_write_state"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_instance_cannot_write_another_instances_availability"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_external_publisher_cannot_read_config"
        status: pass
      - kind: integration
        ref: "tests/broker/test_acl.py#test_denied_publish_leaves_no_trace"
        status: pass
    human_judgment: false
  - id: D2
    description: "The ACL document states the limits honestly (cooperative ownership, approval gate, test topic, discovery prefix, secrets in actions, TLS) and contains exactly one acl block"
    requirement: TRU-04
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_acl_document_states_the_limits"
        status: pass
    human_judgment: false
  - id: D3
    description: "A state change from a UI toggle on an approving instance or from an external client runs the actions once per real edge on every approving instance and never on one that did not approve, including its test button and run-on-startup flag"
    requirement: STA-03
    verification:
      - kind: integration
        ref: "tests/test_multi_instance.py#test_fanout_runs_on_every_approved_instance_and_only_there"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_owner_edit_requires_reapproval_on_followers"
        status: pass
    human_judgment: false
  - id: D4
    description: "Reconnect order (documents, discovery, availability), healing of a wiped broker without any follower removing or un-approving a mirror, and approved mirrors still running while the owner is offline"
    requirement: SYN-04
    verification:
      - kind: integration
        ref: "tests/test_multi_instance.py#test_first_start_publishes_documents_before_availability"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_reconnect_republishes_config_before_availability"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_reconnect_after_a_wiped_broker_heals_and_followers_keep_mirrors"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_owner_offline_follower_still_runs_actions"
        status: pass
    human_judgment: false
  - id: D5
    description: "Deleting a device removes it from every instance and leaves no retained config, discovery or state message; hub removal with delete clears everywhere and with keep leaves orphans that followers keep"
    requirement: SYN-06
    verification:
      - kind: integration
        ref: "tests/test_multi_instance.py#test_delete_removes_the_device_everywhere"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_hub_removal_delete_clears_everywhere_for_followers"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_hub_removal_keep_leaves_orphans_that_followers_keep"
        status: pass
    human_judgment: false
  - id: D6
    description: "Conflicting owners, forged tombstones and follower entity deletions end in the documented outcomes: pinning plus Repairs, owner healing with at most two republishes per window, mirror recreated unapproved, discovery restored with a trailing republish"
    requirement: SYN-05
    verification:
      - kind: integration
        ref: "tests/test_multi_instance.py#test_ownership_conflict_between_three_instances"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_forged_tombstone_followers_recover_unapproved"
        status: pass
      - kind: integration
        ref: "tests/test_multi_instance.py#test_follower_entity_deletion_heals_the_discovery"
        status: pass
    human_judgment: false
  - id: D7
    description: "The README describes multi-instance sync, the trust model and approval, the denylist and its residual risk, deleting devices and removing the hub including the generic Home Assistant delete dialog, and the limitations, without a device_id target in any example; wording that the generic dialog behaves as documented needs a real Home Assistant"
    requirement: TRU-04
    verification:
      - kind: unit
        ref: "tests/test_repo_structure.py#test_readme_documents_phase3_behavior"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_docs_examples_use_no_device_id_targets"
        status: pass
      - kind: unit
        ref: "tests/test_repo_structure.py#test_readme_no_longer_claims_single_instance_or_broker_never_supplies_actions"
        status: pass
    human_judgment: true
    rationale: "Whether the generic subentry delete dialog really deletes everywhere is a statement about Home Assistant's own UI that no test here can observe; the plan's manual UAT row covers it"

duration: 10min
completed: 2026-10-01
status: complete
---

# Phase 3 Plan 07: Broker ACL, Acceptance Scenarios and README Summary

**A Mosquitto ACL example that a real broker enforces in the test suite, twelve three-instance scenarios proving the five phase success criteria (no defect found), and a README that states the trust model and its limits.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-10-01T00:22:48Z
- **Completed:** 2026-10-01T00:33:05Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- `docs/broker-acl.md` holds one fenced `acl` block. `tests/broker/test_acl.py` reads that block, substitutes the two instance id markers and starts Mosquitto 2.1.2 with it (anonymous access off, password file, ACL file). The ACL tests ran and passed, none skipped (`-rs` shows no skip line). A mutation check (giving the bridge user config, discovery and availability access in the document) made three of the ACL tests fail, so the tests do detect a weakened ACL.
- The document says plainly what the ACL cannot do: ownership of a config topic is cooperative within the Home Assistant user group because device ids are random, approval is the real gate, instances need write access to the discovery prefix, the test topic is a second trigger source, a denied publish is not reported visibly, a discovery prefix change needs a reload, and actions are readable by every subscriber so they must not contain secrets.
- Twelve scenarios on three instances (owner, approving follower, unapproving follower) cover the five success criteria and the failure paths. All passed against the code of plans 03-02 to 03-06 at once, so no production file changed. Spot mutations (approval bypass in the Script gate, availability before documents on reconnect, prune without owner-online evidence) each made the intended scenarios fail.
- The README gained the sections Multiple instances, Trust model and approval and Deleting devices and removing the integration, lists the denylist and its residual risk, states that there is no hub-wide switch (reconciling the "local opt-in flag" wording of `.claude/CLAUDE.md`, which this plan does not edit), documents the generic delete dialog and both hub removal modes, and removes the single-instance, hub-removal and "never taken from a broker message" statements.

## Task Commits

1. **Task 1: Tracer, documented broker ACL enforced by a real Mosquitto** - `625bad2` (test, RED), `64d2d4d` (feat, GREEN)
2. **Task 2: Multi-instance acceptance scenarios** - `6f58bf9` (test; every scenario passed, no fix commit)
3. **Task 3: README for multi-instance sync, trust model, deletion and limitations** - `07487d1` (test, RED), `86a6aeb` (feat, GREEN)

**Plan metadata:** the docs commit that follows this summary.

Tracer gate (auto mode off, human_verify_mode end-of-phase, automated-only verify): the verify command was re-run end to end after the GREEN commit (27 ACL and repo-structure tests passed, full suite green, Ruff clean, no skips) before the expansion tasks began.

## Files Created/Modified

- `docs/broker-acl.md` - ACL example, topic table, limits, transport and secrets guidance
- `tests/broker/conftest.py` - `start_acl_broker` factory; the anonymous `mosquitto_port` fixture shares `_run_broker`
- `tests/broker/test_acl.py` - seven ACL tests, an authenticated paho client and the document reader
- `tests/test_multi_instance.py` - twelve phase acceptance scenarios and their helpers
- `tests/test_repo_structure.py` - ACL document limits, README phase 3 phrases and sections, no `device_id` in fenced examples, no stale claims
- `README.md` - the three new sections, topic contract, Behavior, Limitations and Security

## Decisions Made

See `key-decisions` in the frontmatter. The plan's assumptions were followed: no hub-level switch (Open Question 6), the generic delete dialog documented as unvetoable (Open Question 1), and `.claude/CLAUDE.md` left untouched.

## Deviations from Plan

None - plan executed exactly as written. Two small notes that are not deviations: a test helper import named `test_topic` was collected by pytest as a test, so it is imported as `press_topic`; and the instance id the ACL document tells operators to look up is read from the retained availability topic or the hub entry data (no UI shows it), which is stated in the document.

**Total deviations:** 0. **Impact on plan:** none.

## Defects Found by the Scenarios

None. No scenario failed, so `sync.py` and `manager.py` are unchanged and no `fix(03-07)` commit exists.

## Issues Encountered

- **Transient ownership conflict issue (observation for review, not a defect against the plan).** `owner_conflict_<id>` is created on the follower when another owner claims a mirrored device, and it is deleted again as soon as the follower re-sees the pinned owner's current document, which the owner's healing republish delivers immediately. With an online owner the issue therefore lives for a moment only (a probe confirmed it is gone after the heal). The scenario asserts the creation through the follower's issue registry events and the unchanged mirror. If the user expects the conflict to stay visible until dismissed, `_resolve` in `sync.py` (plan 03-04) should keep the conflict issue when it was caused by a foreign claim; that is a design decision for the user, not changed here.
- Mosquitto emits no visible error for a denied QoS 1 publish, as assumed in A12; the tests tolerate a missing acknowledgement and assert on received messages.
- The first `ruff format` run on the new test rewrote `except (RuntimeError, ValueError)` to the Python 3.14 form `except RuntimeError, ValueError:`; the repo's existing code uses that form already.

## Known Stubs

None.

## Threat Flags

None beyond the plan's threat model. T-03-34 (cooperative ownership) is accepted and stated in the ACL document and README; T-03-35 is mitigated by `test_documented_acl_block_is_the_tested_acl`; T-03-36 and T-03-37 are mitigated by the documents (no secrets in actions, test topic named as a trigger source and restricted to Home Assistant users). T-03-SC: no package was installed.

## User Setup Required

None. The ACL tests need the system `mosquitto` and `mosquitto_passwd` binaries (present here, Mosquitto 2.1.2) and skip without them; CI installs mosquitto already.

## Next Phase Readiness

- Phase 3 has all seven plans executed; phase verification can reconcile the shared requirement ids (SYN-03, SYN-04, SYN-05, SYN-06, STA-03).
- Manual UAT rows for the end of the phase (assumptions A3 and A4): on a real Home Assistant, delete a device through Home Assistant's own Delete dialog of the subentry and confirm that its entity disappears, that the broker holds no retained config, discovery or state message for it and that a second instance drops its mirror, then check that the README paragraph on the generic dialog matches; and check the approval YAML rendering in Repairs (plan 03-06 UAT row).
- Needs user confirmation at review: the wording of the README sections and the ACL document, that the denylist is listed in the README (so a change of `const.py` needs a README change), the transient conflict issue noted above, and the flag that `.claude/CLAUDE.md` still says "local opt-in flag" while the implementation uses per-device approval.

## Self-Check: PASSED

- Created files exist: `docs/broker-acl.md`, `tests/broker/test_acl.py` (FOUND)
- Commits exist: `625bad2`, `64d2d4d`, `6f58bf9`, `07487d1`, `86a6aeb` (FOUND); `test(03-07)` precedes `feat(03-07)` in both TDD tasks
- Acceptance: `grep -cP '^\x60{3}acl$' docs/broker-acl.md` prints 1; `grep -c "docs/broker-acl.md" README.md` prints 1; `uv run pytest tests/test_multi_instance.py -k "fanout or reconnect or prune" -q` ran 9 tests and passed; `test_delete_removes_the_device_everywhere` asserts the config, discovery and state topics are absent from the broker's retained set; `uv run pytest -q -rs` 780 passed with no skips; `uv run ruff check .` and `uv run ruff format --check .` clean
