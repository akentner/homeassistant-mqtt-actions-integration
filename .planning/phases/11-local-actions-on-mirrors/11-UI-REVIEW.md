# Phase 11 — UI Review

**Audited:** 2026-10-21
**Baseline:** abstract 6-pillar standards (no UI-SPEC.md); scoped to what the integration controls (HA options flow, Repairs texts, en/de translations)
**Screenshots:** not captured by this audit (instructed: no dev server). Existing human-approved evidence used: `11-frontend-smoke.png` (2x2 composite, en/de, disposable smoke form, HA 2026.9.4 / frontend 20260826.7)
**Interaction captures:** off (workflow.ui_interaction_capture is false). Interaction findings below are code-derived or taken from 11-FRONTEND-SMOKE.md.

Important limit: the screenshot shows the 11-02 smoke form, not the shipped `HubOptionsFlow`. Menu, device picker, trigger picker, mute/remove confirmations and the real error texts are audited from code and translations only.

---

## Pillar Scores

| Pillar | Score | Key Finding |
|--------|-------|-------------|
| 1. Copywriting | 2/4 | Mode wording differs between editor, status label and confirm text; "{n} devices" without plural; very long descriptions |
| 2. Visuals | 3/4 | Good field order and expanded section; orphan-only devices labelled by raw device_id |
| 3. Color | 4/4 | Fully owned by HA frontend; no custom color; error uses stock ha-alert |
| 4. Typography | 4/4 | Fully owned by HA frontend; integration emits only plain text and safe markdown |
| 5. Spacing | 4/4 | Fully owned by HA frontend; one section, no custom layout |
| 6. Experience Design | 2/4 | No explicit exit/"done" from the trigger loop, no save confirmation, untested real flow rendering |

**Overall: 19/24** (pillars 3-5 are 4/4 by non-ownership, not by merit; the integration-controlled pillars average 2.3)

---

## Top 3 Priority Fixes

1. **WARNING — Inconsistent mode wording (en)** — users see three names for one concept: editor option "In addition to the owner actions" (`translations/en.json` selector.local_mode.options.additive), trigger status "additional to the owner actions" (selector.local_trigger_status.options.additive), and confirm texts that quote "Instead of the owner actions" without quotes so it reads as running prose (options.step.local_actions_confirm_mute / _confirm_remove description). Fix: use exactly "In addition to the owner actions" in the status label and wrap option names in quotes or bold in both confirm texts (de already uses „…“).
2. **WARNING — Trigger loop has no exit and no save feedback** — after save/remove/mute, `_async_save_local` and `async_step_local_actions_remove_confirmed` (`config_flow.py` ~line 438, ~470) return to the trigger picker form; the only way out is the dialog X, and nothing confirms the save other than the changed label. Users can't tell whether X discards saved work (it doesn't, per D-13). Fix: append a sentence to `local_actions_device.description` ("Saved changes are already active. Close this dialog when you are done.") or make the picker a menu with a "Done" option that ends with `async_create_entry(data=self.config_entry.options)`.
3. **WARNING — Settings description pluralization and zero case** — `options.step.settings.description` always says "…deletes the local actions of {local_action_device_count} devices…", producing "1 devices" and "0 devices" (de: "für 1 Geräte"). Fix: pass a pre-formatted phrase as the placeholder (empty when 0, singular/plural handled in code), or rephrase to "Number of devices with local actions that are deleted: {count}".

---

## Detailed Findings

### Pillar 1: Copywriting (2/4)
- WARNING: mode name drift (see fix 1). Also the smoke form used "Additional to…"; the shipped editor uses "In addition to…", so the approved screenshot does not show the shipped string.
- WARNING: plural "{n} devices"/"{n} Geräte" in settings description (fix 3).
- WARNING: text density. `local_actions_edit.sections.local_actions.description` packs four ideas (full access, parallel, replacement, orphan inactivity) in one paragraph, and the step description repeats "combine with the owner actions". The approval fix_flow text is a ~12-paragraph wall. Split the section description into short sentences per mode; move the orphan sentence to the trigger menu description where it applies.
- WARNING: en "with its full access" (section description) is ambiguous; prefer "with full access to this instance".
- Minor: de uses "Besitzerin" (feminine, agreeing with "Instanz") throughout, while the approved smoke and common HA usage say "Besitzer". Consistent internally, but reads unusual; decide deliberately.
- Minor: `error.invalid_local_actions` appends raw validator text `{error}` (capped) in English even in de.
- Good: errors say what happened and that nothing was saved (`not_loaded`, `stale_target`, `save_failed`); D-17 approval paragraph explicitly says replacements never approve; mute vs remove distinction is clearly explained in both confirm steps; abort `no_local_devices` is a proper empty state.

### Pillar 2: Visuals (3/4)
- Good: editor section is forced expanded (`config_flow.py:506`, `{"collapsed": False}`), directly addressing smoke finding 1; mode precedes actions; mode `data_description` renders under the radios (screenshot).
- WARNING: devices known only from saved records are labelled `"<device_id> · inactive, not mirrored…"` (`_device_label`, `config_flow.py:541-545`) — a hex id with no friendly name, unlike D-11's "retain last known friendly name" for triggers. Store and show the last known device name.
- Minor: device picker shows no hint which devices already have customizations (no count marker), so finding existing customizations requires opening every device.
- Minor: the ActionSelector field description does not render (smoke finding 2); code correctly puts guidance in the section description, but that makes the section header text long (see Pillar 1).

### Pillar 3: Color (4/4)
- No CSS/colors controlled by the integration. Error state uses stock `ha-alert` (red, screenshot bottom-right). Nothing to flag; score reflects non-ownership.

### Pillar 4: Typography (4/4)
- Owned by HA frontend. Placeholders are passed through `escape_markdown` (`config_flow.py` trigger picker), so user-supplied names cannot inject bold/headers. Bold is used sparingly only in the approval text.

### Pillar 5: Spacing (4/4)
- Owned by HA frontend. Single section, stock LIST selectors; no layout overrides possible or used.

### Pillar 6: Experience Design (2/4)
- Good: confirmations for both destructive/ambiguous actions (mute D-15, remove D-14) via menus with explicit "back" and "discard" choices; draft preserved when going back to the editor; refused save re-renders editor with base error and submitted values; stale target detection; empty state abort; separate Repairs issue for local failures and for unreadable store.
- WARNING: no terminal step — trigger picker loops indefinitely, no Done, no success message (fix 2).
- WARNING: a trigger without customization jumps straight into the editor (`config_flow.py:326-327`), while a customized one goes to a menu. Inconsistent navigation; the editor itself has no in-form "back" (only X, which closes the whole options flow, not just the edit).
- WARNING: rendered evidence covers only the disposable smoke form. Real menus, LIST pickers with long status suffixes, `{error}` placeholder alert, and mobile viewport were never rendered. Recommend a Phase 12 bench capture of the real flow in en/de.
- Minor: remove errors are shown on the trigger picker (not the remove menu), so context of what failed is weaker.

---

## Files Audited
- custom_components/mqtt_actions/config_flow.py (HubOptionsFlow, lines 210-520)
- custom_components/mqtt_actions/translations/en.json
- custom_components/mqtt_actions/translations/de.json
- .planning/phases/11-local-actions-on-mirrors/11-FRONTEND-SMOKE.md
- .planning/phases/11-local-actions-on-mirrors/11-frontend-smoke.png
- .planning/phases/11-local-actions-on-mirrors/11-CONTEXT.md
