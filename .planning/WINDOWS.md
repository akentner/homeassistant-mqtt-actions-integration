---
schema_version: 1
open_count: 3
waived_count: 0
fixed_count: 1
total_count: 4
last_updated: 2026-10-21T05:14:08.429Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 10 | unmet-truth | custom_components/mqtt_actions/native_migration.py |  | defer_for_run mutant survives the suite (pre-existing at dbfbf81: _follow_native_status legacy add unpinned); pin in a later plan | open |  | 2026-10-16T13:35:57.906Z |  |
| 2 | 10 | unmet-truth | custom_components/mqtt_actions/native_migration.py |  | forget mutant survives the suite (pre-existing at dbfbf81: _forget_native per-run discards unpinned); pin in a later plan | open |  | 2026-10-16T13:35:58.035Z |  |
| 3 | 11 | stub | custom_components/mqtt_actions/translations/en.json |  | issues.local_action_failed title/description and the approval confirm {replaced} wording are not translated yet; Plan 11-08 Task 3 adds them (en/de) | fixed |  | 2026-10-21T02:01:56.737Z | 2026-10-21T02:25:38.899Z |
| 4 | 11 | unrun-verify | .github/workflows/validate.yml |  | HACS validation (hacs/action 22.5.0) not run on the Phase 11 build: branch not pushed; must pass on first push before Phase 12 release work | open |  | 2026-10-21T05:14:08.429Z |  |

````json
[
  {
    "id": 1,
    "kind": "unmet-truth",
    "phase": "10",
    "file": "custom_components/mqtt_actions/native_migration.py",
    "line": null,
    "description": "defer_for_run mutant survives the suite (pre-existing at dbfbf81: _follow_native_status legacy add unpinned); pin in a later plan",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-16T13:35:57.906Z",
    "resolved_at": null,
    "milestone": "v1.1"
  },
  {
    "id": 2,
    "kind": "unmet-truth",
    "phase": "10",
    "file": "custom_components/mqtt_actions/native_migration.py",
    "line": null,
    "description": "forget mutant survives the suite (pre-existing at dbfbf81: _forget_native per-run discards unpinned); pin in a later plan",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-16T13:35:58.035Z",
    "resolved_at": null,
    "milestone": "v1.1"
  },
  {
    "id": 3,
    "kind": "stub",
    "phase": "11",
    "file": "custom_components/mqtt_actions/translations/en.json",
    "line": null,
    "description": "issues.local_action_failed title/description and the approval confirm {replaced} wording are not translated yet; Plan 11-08 Task 3 adds them (en/de)",
    "status": "fixed",
    "reason": "",
    "recorded_at": "2026-10-21T02:01:56.737Z",
    "resolved_at": "2026-10-21T02:25:38.899Z",
    "milestone": "v1.1"
  },
  {
    "id": 4,
    "kind": "unrun-verify",
    "phase": "11",
    "file": ".github/workflows/validate.yml",
    "line": null,
    "description": "HACS validation (hacs/action 22.5.0) not run on the Phase 11 build: branch not pushed; must pass on first push before Phase 12 release work",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-10-21T05:14:08.429Z",
    "resolved_at": null,
    "milestone": "v1.1"
  }
]
````
