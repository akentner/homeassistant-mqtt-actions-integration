---
phase: 08-real-instance-verification
plan: 08
subsystem: verification-bench
tags: [uat, human-verify, p1-2, p3-1, hub-flow, translations, approval-request, repairs, hostile-names, evidence]
requires:
  - phase: 08-real-instance-verification
    provides: pinned bench, owner tokens, 08-UAT.md ledger and recorder gate, check-frontend.sh, UAT Marker fixture, all scripted checks recorded (plans 08-01 to 08-07)
provides:
  - P1-2 and P3-1 recorded as pass in 08-UAT.md (blocks 6 and 13) with the owner's statement verbatim, the build SHA and real screenshots
  - ha-b re-added as a native hub with a new instance id (b4cf285b-428f-426b-9500-8e269634356e) and a hostile instance name; its previous state backed up
  - check-p12.sh (outside the repo) with modes wait-b, remove-hub, after-add, approve-marker, import-hostile, delete-hostile
  - broker read-back that the hostile P3-1 device leaves no retained config topic after the integration's delete step
affects: [08-09, 08-10]
tech-stack:
  added: []
  patterns:
    - "destructive bench step last, after a full backup and only after every scripted check is recorded (D-03)"
    - "instance ids read from ~/ha-test/.instance-ids.env so the gates follow a re-added hub"
key-files:
  created:
    - .planning/phases/08-real-instance-verification/08-evidence/p1-2/ (01..08-*.png, screens.txt, hub-before.txt, new-instance-id.txt, acl-diff.txt, result.txt)
    - .planning/phases/08-real-instance-verification/08-evidence/p3-1/ (01..06-*.png, screens.txt, import-shape.txt, topics-after-delete.txt, result.txt)
    - .planning/phases/08-real-instance-verification/08-08-SUMMARY.md
  modified:
    - .planning/phases/08-real-instance-verification/08-UAT.md
decisions:
  - "ha-b is the owner of the hostile device and carries the hostile instance name; ha-a is the follower (roles reversed against the research table, planner decision kept)"
  - "The browser steps (hub flow, add-device dialog, approval dialog, profile language) were driven by the orchestrator through the chrome-devtools browser MCP; the executor ran the scripted steps in two worktree dispatches"
  - "REQUIREMENTS.md left unchanged: UAT-01..04 are shared by the whole phase and UAT-04 carries an open gap; the phase-end plan owns that file"
metrics:
  duration: 2026-10-06T19:51Z to 2026-10-07T21:25Z across three sessions; this continuation dispatch about 10 min
  completed: 2026-10-07
status: complete
commits: 1
plan_head_before: 51c0c591457dcb2f9a9fcd5b5826b75c5bf6c960
plan_head_after: 81bd0ab
actuals:
  tokens: 3900
  tasks: 3
  commits: 1
requirements-completed: [UAT-01, UAT-02, UAT-03, UAT-04]
coverage:
  - id: D1
    description: "P1-2: hub flow (English abort, German finish), Add switch device dialog (DE, EN) and the Repairs text (DE, EN) read correctly in the real frontend"
    requirement: UAT-01
    verification:
      - kind: manual_procedural
        ref: "08-evidence/p1-2/screens.txt (01..08-*.png) and 08-evidence/p3-1/screens.txt (01..06-*.png); owner statement \"approved P1-2 P3-1\""
        status: pass
      - kind: other
        ref: "~/ha-test/bin/check-recorded.sh P1-2"
        status: pass
    human_judgment: true
    rationale: "owner-judged rendering"
  - id: D2
    description: "P3-1: the approval request of a hostile-named mirrored device under a hostile owner name renders device name, owner name and action YAML as plain text in Settings > Repairs of the follower, in English and German"
    requirement: UAT-03
    verification:
      - kind: manual_procedural
        ref: "08-evidence/p3-1/screens.txt (01..06-*.png); owner statement \"approved P1-2 P3-1\""
        status: pass
      - kind: other
        ref: "~/ha-test/bin/check-recorded.sh P3-1"
        status: pass
    human_judgment: true
    rationale: "owner-judged rendering"
  - id: D3
    description: "ha-b re-added as a native hub with a new instance id and working broker access (availability online, heartbeat heard, no native_cutover_waiting); the hostile device deleted with its retained topic empty and the request gone from ha-a"
    verification:
      - kind: other
        ref: "~/ha-test/bin/check-p12.sh after-add (p1-2/new-instance-id.txt), check-p12.sh delete-hostile (p3-1/topics-after-delete.txt), check-frontend.sh cleanup, check-preflight.sh --quick"
        status: pass
    human_judgment: false
---

# Phase 8 Plan 08: P1-2 and P3-1 Summary

P1-2 (English and German strings of the hub flow, the add-device dialog and the Repairs text) and P3-1 (approval request with a hostile device name, a hostile owner name and hostile YAML) are recorded as `pass` on build b7f52b34 with the owner's verbatim statement "approved P1-2 P3-1" (2026-10-07) and, unlike plans 08-06 and 08-07, with real screenshots: the chrome-devtools browser MCP was available to the orchestrator in this run. ha-b was backed up, its hub removed and re-added in German under the hostile instance name `Haus \`x\` | _ab_ <b>fett</b>`, its broker access restored for the new instance id `b4cf285b-428f-426b-9500-8e269634356e`, and the hostile device was deleted again through the integration's own delete step with its retained topic read back empty. `commits:` is 1 measured from this worktree's ledger (`git rev-list --count 51c0c59..HEAD`); the plan's earlier commits sit on the phase branch below that base (see Task Commits).

## What was done

- **Task 1, steps 1-2 (543d14a executor, 1b57f36 merge, b3fd665 orchestrator):** the executor stopped ha-b, copied `~/ha-test/b` to `~/ha-test/_backup-pre-p12-b-20261006T195117Z` (`cp -a`, `diff -rq` identical), wrote the path to `~/ha-test/.current-backup-p12`, started ha-b, passed the precondition gates (UAT-01..04 and P1-5 recorded, `check-hac.sh stopped`, `check-preflight.sh --quick`) and removed the hub through `DELETE /api/config/config_entries/entry/{id}` with `delete_devices_on_remove` at its default (off), the call the frontend's Delete button makes (`hub-before.txt`). The orchestrator then drove the browser MCP on `localhost:8124`: hub form in English opened and aborted (`01`; config entries still held no `mqtt_actions` entry), profile language to German, hub form captured and finished with the hostile instance name typed as text (`02`-`05`), "Schalter-Gerät hinzufügen" captured and closed (`06`), language back to English, entry page and "Add switch device" captured and closed (`07`, `08`); `p1-2/screens.txt`.
- **Task 1, steps 3, 4, 6 (d046e93 executor, 197e6bd merge):** `check-p12.sh after-add` read the single field `instance_id` of ha-b's new entry with `jq`, wrote `p1-2/new-instance-id.txt` and `~/ha-test/.instance-ids.env` (`lib.sh` prefers that file), added `topic write mqtt_actions/v1/instances/b4cf285b-…/availability` to the `ha_two` ACL block (copy `acl.bak-phase8-08`, `p1-2/acl-diff.txt`), HUP'd `mosq`, reloaded the hub entry, and read back availability `1 online` and a heartbeat within 60 s with the probe; no `native_cutover_waiting` (ha-c stopped and offline). `approve-marker` re-approved the marker mirror on ha-b (approvals are removed with the hub). `import-hostile` imported `UAT P3-1 \`code\` | _u_ <b>bold</b>` (33 printable characters, actions `{{ 'system_log' }}.write` with the message `UAT P3-1 \`inert\` | _text_`, inert) on ha-b through the guard and waited for `approval_cac986bf-…` on ha-a, unapproved (`p3-1/import-shape.txt`). `check-frontend.sh prep p1-2 p3-1`, `check-preflight.sh --quick` and `check-evidence-clean.sh` printed PASS.
- **Task 1, step 5 (51c0c59 orchestrator):** the approval dialog on `localhost:8123` (Settings > Repairs) was opened, scrolled and closed in German (`01`-`03`), the language switched to English, the list and the dialog captured again (`04`-`06`), never submitted; `repairs/list_issues` on ha-a still listed the request with `ignored=false` afterwards. The a11y tree showed the names as StaticText with the backticks, underscores, pipe and literal `<b>`/`</b>` as characters, the YAML as one text block and the templated service name under the templated heading. Profile language verified `en` on ha-a and ha-b through the frontend (`hass.language`) at the end; `p3-1/screens.txt`.
- **Task 2:** blocking-human checkpoint. The owner answered the orchestrator directly in chat, verbatim: `approved P1-2 P3-1` (2026-10-07). No issue reported for either item.
- **Task 3 (81bd0ab executor, this dispatch):** wrote `p1-2/result.txt` and `p3-1/result.txt` (owner statement verbatim, date, build SHA, screenshot lists, who drove the browser), recorded blocks 6 and 13 (`result: pass`, `note: owner-signed 2026-10-07`, `sha:`, `date:`, `evidence:`), updated the table and the Summary counts (passed 11, issues 1, pending 2), and added the Observations and bench-state entries about ha-b's new hub. `check-p12.sh delete-hostile` deleted the hostile device on ha-b through the integration's reconfigure flow (menu step `delete_device` with the name placeholder `UAT P3-1 \\\`code\\\` \\| \\_u\\_ \\<b\\>bold\\</b\\>` markdown-escaped as plain text, count 1; `delete_confirmed` aborted with `device_deleted`); after 20 s `p3-1/topics-after-delete.txt` shows `retained topics: none (empty)`, `subentry on ha-b: gone`, `approval request on ha-a: gone`. Gates: `check-recorded.sh P1-2`, `check-recorded.sh P3-1`, `check-frontend.sh cleanup`, `check-preflight.sh --quick`, `check-evidence-clean.sh` all PASS; `git status --porcelain -- custom_components tests .github` empty.

## Task Commits

1. **Task 1 (steps 1-2):** `543d14a` (docs, executor worktree of 2026-10-06), `1b57f36` (merge of that worktree, recovered after the session crash), `b3fd665` (docs, orchestrator: P1-2 screenshots)
2. **Task 1 (steps 3, 4, 6):** `d046e93` (docs, executor worktree), `197e6bd` (merge)
3. **Task 1 (step 5):** `51c0c59` (docs, orchestrator: P3-1 screenshots)
4. **Task 2:** no commit (owner answer in chat)
5. **Task 3:** `81bd0ab` (docs: record P1-2 and P3-1)

**Plan metadata:** the commit of this SUMMARY (`docs(08-08): complete P1-2 and P3-1 plan summary`); STATE.md and ROADMAP.md are updated by the orchestrator after the worktree merge.

## Deviations from Plan

**1. [Plan adaptation] Browser steps by the orchestrator, not the executor.** The chrome-devtools browser MCP is not exposed to the subagent, but it WAS available to the orchestrator session this time (unlike 08-06/08-07). The orchestrator drove the hub flow, the add-device dialog, the profile-language switches and the approval dialog and took the screenshots (b3fd665, 51c0c59); the login was already present in the owner's browser, no credentials were read or typed, `/profile/security` was never opened. The owner judged the screenshots / the live view. `result.txt` and the ledger notes say who did what.

**2. [Rule 3 - Blocking] Session crash and worktree recovery.** The 2026-10-06 executor session crashed after the backup and hub removal (543d14a in a worktree). The orchestrator merged that worktree (1b57f36) and continued; the executor ran steps 3, 4 and 6 and Task 3 in two further worktree dispatches (d046e93 merged as 197e6bd; 81bd0ab in this one). The plan's "run in the main checkout" rule was therefore replaced by worktree dispatches with the bench scripts run from the worktree root (`evidence_root` follows the checkout; the object database is shared, so the pin check passes).

**3. [Plan adaptation] Bench script modes added.** `check-p12.sh` gained `import-hostile` (import on ha-b, wait for the unapproved request on ha-a, write `import-shape.txt`) and `delete-hostile` (integration delete step over the subentry flow REST endpoints, retained-topic read-back, request check on ha-a) beyond `wait-b`, `remove-hub`, `after-add`, `approve-marker`. `check-frontend.sh prep` knows `p1-2` and `p3-1`; `cleanup` checks the P3-1 mirror on both instances, ha-b's hub and `native_cutover_waiting`.

**4. [Plan adaptation] Approval of the marker mirror re-done.** Removing ha-b's hub also removed its approvals, so the UAT Marker mirror (plan 08-03) had to be approved again on ha-b (`approve-marker`), otherwise `check-marker.sh approved` and later gates would fail. Not foreseen in the plan text.

**5. [Observation] Orphan mirrors on ha-b.** After the re-add, the four devices formerly owned by the old id (Baz, dfgfdgd, dfsfasdf, Modus Schlaf) appear on ha-b as "mirror of Test HA Two" (retained orphans the new hub does not recognise as its own, `p1-2/04..07`). Recorded under Observations in `08-UAT.md`; the bench was not "fixed" and `check-frontend.sh cleanup` does not complain about them.

**6. [Observation] REQUIREMENTS.md not changed.** The plan carries UAT-01..04 only because the ten-item checks share the ledger; those requirements were proven by plans 08-02 to 08-05 and UAT-04 holds an open gap, so this plan leaves the checkboxes to the phase-end plan.

**7. Ledger.** The plan commit ledger is this worktree's base (51c0c59), so `commits:` counts only Task 3; the earlier six commits are listed above.

## Bench edits and state left behind (outside the repository)

- `~/ha-test/bin/check-p12.sh` (new), `~/ha-test/bin/lib.sh` (instance table prefers `~/ha-test/.instance-ids.env`), `~/ha-test/bin/check-frontend.sh` (p1-2, p3-1 in `prep` and `cleanup`).
- `~/ha-test/.instance-ids.env` (`INSTANCE_ID_B=b4cf285b-428f-426b-9500-8e269634356e`, not a secret); `~/ha-test/.fixtures-frontend.env` keeps `P31_ID` (device uuid) for the cleanup gate; `~/ha-test/.current-backup-p12` names the backup.
- `~/ha-test/_backup-pre-p12-b-20261006T195117Z/`: ha-b before the hub removal. Restore it with BOTH containers stopped if an earlier scripted check has to be re-run on the old state (D-03).
- `~/ha-test/mosquitto/acl`: availability line for the new id in the `ha_two` block next to the old one (copy before the edit `acl.bak-phase8-08`; `p1-2/acl-diff.txt`); `mosq` was HUP'd, not restarted.
- ha-b: new native hub, entry title `Haus \`x\` | _ab_ <b>fett</b>`, four orphan mirrors of the old owner id, marker mirror approved again; the old id's retained availability reads `offline`. ha-a: untouched except the request that came and went. Profile language English on both.
- The hostile P3-1 device is gone (retained topic empty, subentry gone, request gone from ha-a). Nothing was approved on ha-a. No token value was printed, no `.storage` file copied into the evidence, `ha-ws`/`ha` and the production hosts were not used.

## Self-Check: PASSED

Re-run at the end of Task 3 from the worktree root:

- Task 1 acceptance: `p1-2/new-instance-id.txt` holds the new id with `probe availability (retained flag, payload): 1 online` and `probe heartbeat within 60 s: heard`; `~/ha-test/.instance-ids.env` has the same id; `p1-2/acl-diff.txt` shows the new line in the `ha_two` block; the backup folder named in `~/ha-test/.current-backup-p12` exists; `p1-2/screens.txt` lists the hub form (EN abort, DE finish) and the add-device dialog (DE, EN); `p3-1/screens.txt` lists the approval dialog in EN and DE; `check-frontend.sh prep p1-2 p3-1` printed PASS before the checkpoint (d046e93).
- Task 3 acceptance: blocks 6 and 13 read `result: pass` with `sha:`, `date:`, `evidence:`; no `issue`, so no Gaps entry needed; `p3-1/topics-after-delete.txt` shows the retained config topic empty; `## Observations` records ha-b's new hub, its new instance id and the backup path.
- Plan verification: `check-recorded.sh P1-2` PASS, `check-recorded.sh P3-1` PASS, `check-frontend.sh cleanup` PASS, `check-preflight.sh --quick` PASS, `check-evidence-clean.sh .planning/phases/08-real-instance-verification/08-evidence` PASS, `git status --porcelain -- custom_components tests .github` empty.
- Files exist: `p1-2/result.txt`, `p3-1/result.txt`, `p3-1/topics-after-delete.txt`; commit `81bd0ab` is on this worktree branch (`git log --oneline -8`); no file deletions in that commit.
