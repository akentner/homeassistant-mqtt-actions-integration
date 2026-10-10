# Phase 8: Real-Instance Verification - Context

**Gathered:** 2026-10-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Manual verification, no code changes. Run the four Phase 5 UAT checks (UAT-01 to UAT-04) and the ten human-verification
items of Phases 1 to 3 (deferred from Phase 7, listed in `07-PROOF.md`, section "Open human-verification items") against
the current build on real HA instances, and record a pass or fail with evidence for each. A failure becomes a gap, not an
accepted skip.

</domain>

<decisions>
## Implementation Decisions

### Test environment
- **D-01:** All checks run in `~/ha-test`: `ha-a` ("Test HA One", 8123), `ha-b` ("Test HA Two", 8124), Mosquitto `mosq`,
  and the v0.1.0 component from `~/ha-test/v010` as the straggler for UAT-01. The live production broker and hosts are not touched.
- **D-02:** Exception: the two items that need a real host run there. Phase 1 #1 (HACS client install, add and remove only,
  no device created) runs on a production host; Phase 1 #6 (core version of hassio-n2plus) the owner reads in Settings > About.
- **D-03:** The build under test is the current HEAD of the phase branch, mounted live. The SHA is recorded in the evidence.
  A later code change makes affected checks stale and they are re-run.

### Execution
- **D-04:** Claude automates everything that does not need eyes or hands: broker publishes (`mosquitto_pub`/`mosquitto_sub`),
  container restarts, log and topic evaluation, and frontend steps via the browser MCP where it works. The owner performs only
  steps that need a human (real frontend rendering and DE/EN review, HACS client, anything the browser tooling cannot do).

### Evidence and results
- **D-05:** One `08-UAT.md` with one row per check (UAT-01 to UAT-04 plus the ten items): pass/fail, date, build SHA, evidence
  reference. Logs, topic dumps and screenshots go in `.planning/phases/08-real-instance-verification/08-evidence/`.
- **D-06:** After the run, `/gsd-verify-work` and the verifier refresh the Phase 1 to 3 reports (archived under
  `.planning/milestones/v1.0-phases/`) to `passed` where all their items passed.

### Scope
- **D-07:** All ten Phase 1 to 3 items are in scope (ROADMAP success criterion 6), grouped by setup so each instance state is
  built once. No item is waived by default; an owner override is only possible under the owner's own name.

### Failures
- **D-08:** A failed check is recorded as a gap and the remaining checks continue. Fixes go into a follow-up gap plan or phase,
  not into Phase 8 (consistent with "no code changes planned").
  - *Amendment 2026-10-08 (decision D08-WAIVER, relayed by the orchestrator from the owner's answer, confirmed directly by the owner in chat on 2026-10-11):* for the gap closure of
    UAT-04 clause 2 (plans 08-11 to 08-15) only, a product fix may land in Phase 8. The rest of D-08 stands, including the rule
    that a failed check is recorded as a gap and the remaining checks continue.

### Claude's Discretion
- Grouping and order of checks per instance setup, helper scripts for the automated steps, and the evidence file naming.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and requirements
- `.planning/ROADMAP.md` — Phase 8 goal and success criteria 1 to 6
- `.planning/REQUIREMENTS.md` — UAT-01 to UAT-04
- `.planning/phases/07-verification-stable-tests-and-pinned-ci/07-PROOF.md` — "Open human-verification items" (the ten items with cited automated coverage)
- `.planning/phases/07-verification-stable-tests-and-pinned-ci/07-CONTEXT.md` — Phase 7 decisions (verification mechanism, staleness)
- `.planning/phases/06-native-entity-residual-fixes/06-CONTEXT.md` — IN-02/IN-03 fixes the build includes (UAT-02 proves MIG-05)

### Prior UAT and design
- `.planning/milestones/v1.0-phases/05-native-entities-and-mqtt-discovery-export/05-UAT.md` (directory glob `05-*`) — the skipped Phase 5 checks
- `.planning/milestones/v1.0-phases/01-*/01-UAT.md`, `02-*/02-UAT.md`, `03-*/03-UAT.md`, `04-*/04-UAT.md` — earlier owner passes
- `.planning/milestones/v1.0-phases/0{1,2,3}-*/0{1,2,3}-VERIFICATION.md` — reports refreshed after this phase
- ADR 0001 (native entities, Discovery as optional export) — see `docs/` in the repo

### Test setup
- `~/ha-test/` — ha-a, ha-b, mosquitto (`acl`, `acl.bak-uat`), v010 component folder
- Memory: `phase-04-release-state` (ACL had to be extended with heartbeat, retrigger and acks topics) and `live-broker-no-auth-acl`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `~/ha-test` containers (`mosq`, `ha-a`, `ha-b` running) with the component mounted live from the repo.
- Phase 4 and 5 UAT procedures (`04-UAT.md`, `05-UAT.md`) as step templates.
- `ha-ws`, `ha` and `mosquitto_*` clients for automated steps; chrome-devtools MCP for frontend steps.

### Established Patterns
- UAT results are recorded per test in `*-UAT.md`; the verifier regenerates `*-VERIFICATION.md` with a digest.

### Integration Points
- No code integration. The v0.1.0 instance needs its own HA container or config pointing at `~/ha-test/v010`; confirm in planning how it is started next to ha-a/ha-b and that the Mosquitto ACL covers it.

</code_context>

<specifics>
## Specific Ideas

- Check the Mosquitto ACL before each group; earlier UATs failed silently on missing topics.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 8-Real-Instance Verification*
*Context gathered: 2026-10-04*
