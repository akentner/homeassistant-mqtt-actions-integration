# Phase 11: Local Actions on Mirrors - Discussion Log

> **Audit trail only.** Not input to planning, research or execution.
> Decisions are captured in 11-CONTEXT.md.

**Date:** 2026-10-17
**Phase:** 11-local-actions-on-mirrors
**Areas discussed:** Storage and downgrade; trigger identity; editing flow; notices and error display.

The user selected all four areas. Interactive discussion used numbered text choices because the synchronous question tool is unavailable in Default mode. Each substantive answer selected option 1; each area-advance choice and the final context-writing choice also selected option 1.

## Storage and downgrade

### What happens to local actions during a temporary downgrade?

| Option | Selected |
|--------|----------|
| Keep via separate Store (recommended) | Yes |
| Accept loss via additive key in main Store |  |

**User’s choice:** Separate Store file. v1.0.1 ignores local actions; they are available after upgrading again.

### What happens to the local Store when the integration is removed?

| Option | Selected |
|--------|----------|
| Delete (recommended) | Yes |
| Keep for later setup |  |

**User’s choice:** Delete the local Store together with the integration.

### How should the removal warning describe local action loss?

| Option | Selected |
|--------|----------|
| Name device count (recommended) | Yes |
| Generic warning |  |

**User’s choice:** Include the number of affected devices.

### How prominently should downgrade execution behavior be documented?

| Option | Selected |
|--------|----------|
| Highlighted warning (recommended) | Yes |
| Normal downgrade paragraph |  |

**User’s choice:** Prominent warning in README and release notes: v1.0.1 ignores local replacement/mute settings and approved owner actions may run again.

## Trigger identity

### How are local actions bound to triggers?

| Option | Selected |
|--------|----------|
| Device ID + kind + StateValue (recommended) | Yes |
| Device ID + StateValue |  |

**User’s choice:** Device ID plus device kind plus StateValue; retain existing payload normalization.

### How are Select triggers displayed?

| Option | Selected |
|--------|----------|
| Friendly name + StateValue (recommended) | Yes |
| StateValue only |  |

**User’s choice:** Friendly name and StateValue, e.g. Gemütlich (cozy).

### How are removed Select options identified?

| Option | Selected |
|--------|----------|
| Last friendly name + StateValue (recommended) | Yes |
| StateValue only |  |

**User’s choice:** Keep the last known friendly name and StateValue and label as no longer present on the owner.

### What can users do with orphaned local actions?

| Option | Selected |
|--------|----------|
| View, edit, delete (recommended) | Yes |
| View or delete only |  |

**User’s choice:** View, edit or delete them while they stay inactive until the same option returns.

## Editing flow

### When do edits take effect?

| Option | Selected |
|--------|----------|
| Save per trigger (recommended) | Yes |
| Save all trigger drafts together |  |

**User’s choice:** Save per trigger and apply immediately, then return to trigger selection. Cancelling discards only the current edit.

### How does the user return to owner-only actions?

| Option | Selected |
|--------|----------|
| Dedicated removal entry (recommended) | Yes |
| Third mode Owner actions only |  |

**User’s choice:** Dedicated Remove local customization entry with confirmation; remove both local mode and actions. Keep distinct from empty replacement/mute.

### What mode is preselected for a new local customization?

| Option | Selected |
|--------|----------|
| In addition to (recommended) | Yes |
| No preselection |  |

**User’s choice:** In addition to.

### How is saving an empty replacement confirmed?

| Option | Selected |
|--------|----------|
| Additional confirmation (recommended) | Yes |
| Inline form explanation only |  |

**User’s choice:** Additional explicit confirmation that this trigger executes no actions on this instance.

## Notices and error display

### What does the trigger picker show?

| Option | Selected |
|--------|----------|
| Mode directly in picker (recommended) | Yes |
| Details only in edit form |  |

**User’s choice:** Show the local mode or local mute directly next to each trigger.

### What does the pending owner approval issue explain?

| Option | Selected |
|--------|----------|
| Explain independent local execution (recommended) | Yes |
| Only add replaced-trigger count |  |

**User’s choice:** Include replaced-trigger count and explicitly state that local actions may already run and approval concerns owner actions only.

### How are local failures grouped?

| Option | Selected |
|--------|----------|
| One issue per device (recommended) | Yes |
| One issue per trigger |  |

**User’s choice:** One independent local Repairs issue per device, showing the latest failed local trigger and its error.

### When does a local failure issue clear?

| Option | Selected |
|--------|----------|
| Affected trigger succeeds or customization removed (recommended) | Yes |
| Any local trigger of the device succeeds |  |

**User’s choice:** Only when the affected local trigger succeeds or its local customization is removed; another trigger or owner branch succeeding does not clear it.

## Implementation Discretion

No product decisions explicitly delegated. Schema/API details, exact wording and safe-default research remain implementation work within the locked requirements.

## Deferred Ideas

None introduced. Existing roadmap deferrals remain unchanged.
