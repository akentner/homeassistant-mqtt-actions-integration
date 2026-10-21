Status: Unpublished draft (version, tag and publication belong to Phase 12)

# MQTT Actions: local actions on mirrored devices (draft)

This draft collects the user-facing release notes for the local actions of Phase 11. Phase 12 sets the version, bumps
`manifest.json`, runs the final bench checks on the release SHA, and publishes the notes with the tag. Nothing here has
been released, tagged or published.

## Downgrade warning

> [!WARNING]
> Version 1.0.1 ignores local actions, including the modes **Instead of the owner actions** and **Locally muted**.
> After a downgrade to v1.0.1 an instance runs no local actions, and approved owner actions may run again on triggers
> that were replaced or muted locally. The local actions are kept in a separate storage file that v1.0.1 does not
> read or change, so by design they are available again after an upgrade back. The downgrade round trip on a real
> bench is deferred as MIR-F4 and has not been run.

## New: local actions on mirrored devices

- A follower can give each trigger of a mirrored Switch or Select local actions in the hub options: **Configure**, then
  **Local actions of mirrored devices**, the device and the trigger.
- Modes: **In addition to the owner actions** (both run in parallel in the single Script of the device), **Instead of
  the owner actions**, and a locally muted trigger (instead of the owner actions, without local actions, after a separate
  confirmation). **Remove local customization** brings back the owner actions.
- Lifecycle: local actions survive owner edits, renames, new revisions, restarts and a new pinned owner. Local actions
  of a removed Select option stay inactive and reattach when the same state value returns. A start, a prune or a
  tombstone discards nothing: the local actions of a deleted device stay inactive until you remove them, and apply
  again if the device returns. An adoption discards them and logs the count. Removing the integration deletes them,
  and the removal settings name how many devices are affected.
- Repairs: local failures raise their own issue `local_action_failed`, independent of `action_failed`. An error that a
  local step handles with `continue_on_error` still raises it. A later successful run of the same trigger, saving that
  trigger without local actions (locally muted, or additive with an empty list), or removing its customization clears
  it.
- Templates: `{{ state }}` is the canonical state value of the trigger that runs. A live entity lookup can show a newer
  value or, for a Select, the friendly name.

## Trust boundary

- Local actions need no approval and run with the full access of the instance, like the actions of owned devices. The
  denylist for actions of other instances does not apply to them.
- The approval concerns only the owner actions. A local customization never approves them, and adoption stays refused
  while they are pending. The approval request shows how many triggers are replaced locally.
- While the owner actions are not approved, the device runs with safe defaults: run on startup off, `serial`, and a
  circuit breaker of 5 runs in 10 seconds. Observe, disabled and the circuit breaker apply to local actions. A local
  edit releases a tripped breaker.
- Local actions never leave the instance. They are not in the config document, the actions hash, the export or the
  adoption payload, so existing approvals stay valid. Test buttons and the re-trigger run the effective actions. The
  re-trigger has no new status or reason words.

## Diagnostics

Diagnostics show counts only: `local_actions.devices`, `triggers`, `orphaned_triggers` and `orphan_only_devices`, and
per device `local_action_triggers` and `local_action_orphans`. They never contain the local actions, their labels,
state values, templates, errors or traces.

## Service response

`mqtt_actions.adopt_device` now returns `local_actions_discarded`, next to `uuid`, `adopted` and `previous_owner`. It is
the count of triggers whose local actions on this instance were discarded by the adoption.

## Left to Phase 12

- Version number, `manifest.json` bump, tag and GitHub release.
- Final-build verification and the bench check of local actions on real instances (QLT-05).
- The downgrade round trip v1.1 to v1.0.1 to v1.1 stays deferred (MIR-F4) and is not part of this release's evidence.
