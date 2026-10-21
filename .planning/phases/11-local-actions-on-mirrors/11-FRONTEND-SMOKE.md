# Phase 11 Frontend Smoke: Section + ActionSelector (D-06, D-22)

Captured: 2026-10-21T00:27Z (UTC) on the local bench, instance `ha-a` (Test HA One, http://localhost:8123).
Screenshot: `11-frontend-smoke.png`. It is a 2x2 composite of real browser captures: en edit, de edit, en reopen, de base alert.

Verdict: PASS

The verdict is the executor's record from the automated browser run.

Human approval (plan 11-02, Task 2, gate `blocking-human`): approved on 2026-10-21 by Alexander Kentner after reviewing `11-frontend-smoke.png` and this file (en/de, all 8 interactions PASS). Verbatim response: "approved — Beleg geprüft (Screenshot + 11-FRONTEND-SMOKE.md, en/de, alle 8 Interaktionen PASS)."

## Versions

| Item | Value | Source |
|------|-------|--------|
| Home Assistant Core | 2026.9.4 | `homeassistant.const.__version__` inside container `ha-a`; also `hass.config.version` read in the browser |
| Frontend package | home-assistant-frontend 20260826.7 | `pip show home-assistant-frontend` inside container `ha-a` (matches the Core manifest pin) |
| Container image | ghcr.io/home-assistant/home-assistant:2026.9 | `podman ps` |
| Browser | Playwright 1.64.0, Chrome Headless Shell 156.0.8078.4 (Linux x86_64) | `navigator.userAgent` |
| Viewport | 1280x1000, device scale 1 | Playwright context |
| Languages | `en` and `de` (bench user profile language; `hass.language` read in the browser) | per-run `hass.language` |

`ha-dev` was not used. It runs Core 2026.10.1 with frontend 20260930.3, so it is not the pinned version.

## Disposable form (bench only, removed)

- Throwaway custom integration `mqtt_actions_smoke`, written only to `~/ha-test/a/custom_components/` and not to the repository. One config entry, with an options flow step `init`.
- Its shape matches the planned per-trigger editor:
  - `section("local_actions", Schema({Required("mode", default="additive"): SelectSelector(options=["additive","replacement"], mode=LIST, translation_key="local_mode"), Optional("actions", default=[]): ActionSelector()}), {"collapsed": True})`
  - Suggested values come from the stored record through `add_suggested_values_to_schema`, nested into the section.
  - Validation: `cv.SCRIPT_SCHEMA` plus `script.async_validate_actions_config`. On failure the form returns `errors["base"] = "invalid_actions"`.
  - Labels come from `translations/en.json` and `translations/de.json` (`options.step.init.sections.local_actions.{name,description,data,data_description}`, `selector.local_mode.options`, `options.error.invalid_actions`).
- Each language run started from a freshly created entry, so the stored options were empty.
- Cleanup after capture:
  - Entry deleted.
  - Component directory removed.
  - `ha-a` restarted.
  - `mqtt_actions` is `loaded` again.
  - `mqtt_actions_smoke` occurs 0 times in `core.config_entries`, `core.device_registry` and `core.entity_registry`.
- The bench user's `language` profile was switched to `de` only for the German run. It was then restored to its original value, and a diff of the stored value was empty.
- No broker configuration, retained MQTT config or repository production file was touched.

## Interaction results

"Stored" means the entry options read back from `ha-a/.storage/core.config_entries` after the submit.

| # | Interaction | en | de | Observed |
|---|-------------|----|----|----------|
| 1 | Expand section | PASS | PASS | The section opens collapsed: header only, and the action editor is hidden. A click on the header expands it. It then shows the section description, the `Mode`/`Modus` label, both radio options and `Add action`/`Aktion hinzufügen`. |
| 2 | Add action | PASS | PASS | `Add action` opens the action picker dialog. Search `delay` (en) or `Verzögerung` (de) finds "Wait for time to pass (delay)" or "Eine Zeit warten (Verzögerung)". One action row is added with the duration editor. |
| 3 | Edit action and mode | PASS | PASS | Seconds set to 5, and the field shows `05`. The row title becomes "Delay for 5 seconds" or "Um 5 Sekunden verzögern". Radio set to `Instead of the owner actions`/`Statt der Besitzer-Aktionen`, and it is checked. |
| 4 | Save | PASS | PASS | The success step reads "Options successfully saved." or "Optionen wurden erfolgreich gespeichert.". Stored: `{"local_actions": {"mode": "replacement", "actions": [{"delay": {"hours": 0, "minutes": 0, "seconds": 5, "milliseconds": 0}}]}}`. |
| 5 | Reopen (suggested values) | PASS | PASS | A new dialog opens, and the section is expanded. The replacement radio is checked. There is 1 action row, collapsed, titled "Delay for 5 seconds" or "Um 5 Sekunden verzögern". |
| 6 | Clear actions | PASS | PASS | The row menu offers Delete (`Delete`/`Löschen`, among 12 items including `Edit in YAML`/`In YAML bearbeiten`). After deleting, the form has 0 rows. Submit stores `actions: []` and keeps `mode: replacement`. On reopen there are 0 rows. |
| 7 | Invalid action → base alert | PASS | PASS | A new delay row is switched to `Edit in YAML` and replaced with `action: not_a_service`. Submit renders a form-level `ha-alert`: "The local actions are invalid." or "Die lokalen Aktionen sind ungültig.". Stored options are unchanged (`actions: []`). |
| 8 | Invalid value kept | PASS | PASS | After the error, the form keeps the submitted value. Once the section is expanded again, the row with `not_a_service` is still present. |

Labels rendered from the custom translations:
- en:
  - Title: "Local actions for trigger (smoke)"
  - Section: "Local actions" / "Actions that run only on this instance."
  - Mode: "Mode"
  - Options: "Additional to the owner actions" / "Instead of the owner actions"
  - Actions label: "Actions"
- de:
  - Title: "Lokale Aktionen für Auslöser (Smoke)"
  - Section: "Lokale Aktionen" / "Aktionen, die nur auf dieser Instanz laufen."
  - Mode: "Modus"
  - Options: "Zusätzlich zu den Besitzer-Aktionen" / "Statt der Besitzer-Aktionen"
  - Actions label: "Aktionen"
  - Submit button: "OK"

## Findings for Plan 11-08 (observed rendering behavior)

1. **A collapsed section collapses again after a base error.** With `{"collapsed": True}`, the form re-renders after a refused submit. The alert is visible, but the section is folded, so the user must expand it again to fix the action. The submitted values are kept. Recommendation: use `{"collapsed": False}` for the per-trigger editor step. The trigger is already selected there, so the section is the whole form.
2. **The ActionSelector field shows no `data_description`.** The description of the `mode` field renders below the radio list. The description of the `actions` field did not appear anywhere in either language. Put guidance for the action list in the section `description` or the step description.
3. **The section `description` renders**, in both languages, directly under the section header.
4. **The ActionSelector returns frontend-shaped raw data.** For example, a delay is stored as an `{hours, minutes, seconds, milliseconds}` dict. Invalid YAML-authored content reaches the backend unchanged. Validation in the Manager remains mandatory, as the research expected.
5. **A base error is the right channel.** A form-level `ha-alert` rendered for `errors["base"]` in both languages, outside the section, so it stays visible even when the section is collapsed.

## Not covered

- The real `HubOptionsFlow` menu, the trigger picker and the replacement/mute confirmations are not built yet. They belong to plan 11-08. This smoke covers only the section + ActionSelector rendering.
- The checks ran in headless Chromium only. No other browser and no mobile viewport were tested.
