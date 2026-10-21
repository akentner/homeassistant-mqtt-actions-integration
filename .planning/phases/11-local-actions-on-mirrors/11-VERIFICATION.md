---
phase: 11-local-actions-on-mirrors
verified: 2026-10-21T14:30:00Z
status: human_needed
score: 22/24 must-haves verified (1 deferred to Phase 12, 1 needs human)
covered_files:
  - .planning/phases/11-local-actions-on-mirrors/11-01-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-01-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-02-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-02-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-03-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-03-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-04-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-04-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-05-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-05-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-06-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-06-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-07-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-07-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-08-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-08-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-09-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-09-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-10-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-10-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-11-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-11-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-12-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-12-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-13-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-13-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-14-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-14-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-15-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-15-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-16-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-16-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-17-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-17-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-18-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-18-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-19-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-19-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-20-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-20-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-21-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-21-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-22-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-22-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-23-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-23-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-24-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-24-SUMMARY.md
  - .planning/phases/11-local-actions-on-mirrors/11-25-PLAN.md
  - .planning/phases/11-local-actions-on-mirrors/11-25-SUMMARY.md
  - README.md
  - custom_components/mqtt_actions/__init__.py
  - custom_components/mqtt_actions/config_flow.py
  - custom_components/mqtt_actions/const.py
  - custom_components/mqtt_actions/diagnostics.py
  - custom_components/mqtt_actions/local_actions.py
  - custom_components/mqtt_actions/local_actions_store.py
  - custom_components/mqtt_actions/manager.py
  - custom_components/mqtt_actions/repairs.py
  - custom_components/mqtt_actions/retrigger.py
  - custom_components/mqtt_actions/runner.py
  - custom_components/mqtt_actions/services.py
  - custom_components/mqtt_actions/sync.py
  - custom_components/mqtt_actions/translations/de.json
  - custom_components/mqtt_actions/translations/en.json
  - custom_components/mqtt_actions/trust.py
  - docs/diagnostics.md
  - docs/operations.md
  - docs/troubleshooting.md
  - tests/fake_broker.py
  - tests/helpers.py
  - tests/test_core_contracts.py
  - tests/test_diagnostics.py
  - tests/test_discovery_export.py
  - tests/test_docs.py
  - tests/test_hub_removal.py
  - tests/test_local_action_plans.py
  - tests/test_local_actions_flow.py
  - tests/test_local_actions_lifecycle.py
  - tests/test_local_actions_manager.py
  - tests/test_local_actions_store.py
  - tests/test_local_actions_store_instances.py
  - tests/test_local_invariants.py
  - tests/test_local_multi_instance.py
  - tests/test_local_parallel.py
  - tests/test_native_cleanup.py
  - tests/test_repairs_flow.py
  - tests/test_retrigger.py
  - tests/test_services.py
  - tests/test_sync_follower.py
  - tests/test_test_buttons.py
  - tests/test_translations.py
covered_digest: "v3:sha256:8fa3ffd8da21859647b8fb75146d197d15432f7b26a9f8fc7d71313783f15d70"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 18/22
  gaps_closed:
    - "G-1 / WR-05 (11-24): a newer-minor local Store is never written by a load, a start, a reload or the removal settings; a shape-invalid newer-minor Store stays byte-identical; unknown keys of a readable row survive every save"
    - "WR-06 (11-25): an in-flight failing local run can no longer re-create local_action_failed after a save without local actions"
  gaps_remaining: []
  regressions: []
gaps: []
deferred:
  - truth: "11-13: HACS validation passes on the Phase 11 build (with Ruff, format and hassfest)"
    addressed_in: "Phase 12"
    evidence: "Phase 12 success criterion 4: 'the release workflow, hassfest and HACS are green'. Ruff check and format --check are clean here (104 files). hacs.json, manifest.json and brand/ are unchanged."
behavior_unverified_items: []
coincidental_reliance_items: []
human_verification:
  - test: "Render the real hub options flow on the bench (Core 2026.9.4, frontend 20260826.7) in en and de: Settings > Integrations > MQTT Actions > Configure > menu 'init' > local actions > device picker (mirrors, orphan-only devices, tombstoned 'not mirrored' devices) > trigger picker (additive/replacement/muted/orphan/other kind) > editor (expanded section, mode select, ActionSelector) > save; mute and remove confirmations; the Settings step with the device count AND the settings_unreadable step (rename .storage/mqtt_actions.local_actions to a wrong shape, restart)"
    expected: "Every step renders translated titles, descriptions, menu options and selector labels (no raw keys) in both languages; save returns to the trigger picker and applies without restart; mute and remove confirmations are distinct; settings_unreadable shows no number and says the local actions cannot be read and are deleted on removal"
    why_human: "Only the disposable 11-02 smoke form was rendered in a browser; the production HubOptionsFlow and the settings_unreadable step have backend flow tests only (UAT test 1, still pending)"
  - test: "Decide the README sentence 'Starting this version or opening its settings never rewrites the file.' (README.md:371) against the label refresh at start (advisory review WR-01)"
    expected: "Either narrow the sentence (a load and opening the settings never write; only a local edit or the refresh of a changed friendly name does) or accept it as written. Verifier evidence: when the retained owner document arrives after a restart with a changed Select-option name, `_async_refresh_local_labels` (manager.py:1392) calls `async_save_records`, which re-stamps a newer-minor file as this release's minor version. Rows, unknown row keys and unknown top-level keys are all written back, so no data is lost. The plan itself lists the label refresh among the explicit saves (11-24 truth 4), so no must-have is falsified; the user-facing sentence overclaims"
    why_human: "Wording decision with a small contract effect. Judgment prohibition 11-24 #1 ('MUST NOT write, rewrite or re-stamp ... on a start') holds for every load path, and is breached only by this owner-document-driven save"
  - test: "Decide advisory review WR-02: a readable row with unknown keys (for example a newer 'enabled: false') is applied here without those keys and nothing says so"
    expected: "Owner decision of 2026-10-21 chose 'apply as today, keep the keys'; the README says it. Optional hardening: one warning log line per load counting records with non-empty `extra` (mirrors the 'Kept %d local action records ... not applied' line of local_actions_store.py:159)"
    why_human: "Design trade-off already decided by the owner; only the observability of the decision is open. No must-have requires it"
  - test: "Review judgment-tier prohibition 11-03: 'MUST NOT make local replacement or trusted-local execution confer approval on owner actions or make an unapproved mirror adoptable'"
    expected: "Holds. Non-authoritative verdict: approval_state() (manager.py) reads no local record; build_effective_trigger_plan gates owner on approval == APPROVED and not replaced; async_adopt_device refuses PENDING/BLOCKED; covering tests pass"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged; UAT test 2 pending)"
  - test: "Review judgment-tier prohibition 11-08: 'MUST NOT present empty replacement as deletion/owner-only behavior or imply that local replacement approves owner actions'"
    expected: "Holds. Non-authoritative verdict: local_actions_confirm_mute (en/de) says neither owner nor local actions run and muting neither approves nor rejects"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged; UAT test 3 pending)"
  - test: "Review judgment-tier prohibition 11-12: 'MUST NOT claim that the real v1.1 to v1.0.1 to v1.1 downgrade round trip or Phase 12 final-build verification has been performed'"
    expected: "Holds. Non-authoritative verdict: the README says the round trip has not been verified (MIR-F4); 11-release-notes.md is 'Unpublished draft'"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged; UAT test 4 pending)"
  - test: "Review judgment-tier prohibition 11-18: 'MUST NOT discard, rewrite or save local action records because of a broker message that carries no owner provenance, such as an empty retained config payload'"
    expected: "Holds for the named class. Non-authoritative verdict: sync._async_remove acts only on an existing mirror and async_remove_mirror never writes the local Store; test_tombstone_never_writes_the_local_store passes"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-19: 'MUST NOT clear the local failure issue of a trigger that still has local actions to run, except on a proven success of exactly that trigger or the removal of its customization'"
    expected: "Holds. Non-authoritative verdict: async_set_local_action clears only `if not record.actions` after the durable commit; async_report_local_outcome drops a FAILURE only when the record is missing or has no actions (11-25), so a trigger with actions keeps its issue (test_an_in_flight_failure_still_reports_while_its_trigger_has_local_actions passes)"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-21: 'MUST NOT erase, reorder ahead of parsed records, or execute stored local action rows that this release cannot parse'"
    expected: "Holds. Non-authoritative verdict: unparseable rows go to `preserved`, are written after the records and are never records. The earlier spirit caveat (rows that parse but carry unknown keys lose them on save) is closed by 11-24 (`LocalActionRecord.extra`)"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-22: 'MUST NOT state a number of devices in the removal warning when the saved local actions could not be read'"
    expected: "Holds. Non-authoritative verdict: None selects step settings_unreadable without placeholders; loaded hubs return None while _local_actions_readable is False; unloaded hubs return None on any read error, including a shape-invalid newer-minor Store (test_unloaded_hub_counts_unknown_for_every_unreadable_store_shape[shape_invalid_newer_minor]). Edge (IN-08): a readable file holding only unparseable rows without a string device_id shows '0 devices' although removal deletes them"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-23: 'MUST NOT change any requirement, success criterion or decision text other than MIR-08, Phase 11 success criterion 5, the D-05 pointer and the new Amendments block'"
    expected: "Holds. Non-authoritative verdict: commit 1e426b5 changes one line each in REQUIREMENTS.md and ROADMAP.md plus the release-notes Lifecycle bullet; commit b3ecda2 changes the D-05 pointer and adds the Amendments block. Note: 11-24 later extends the Amendments block (D-07 extended, D-19 amended) by owner decision of 2026-10-21"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-24 #2: 'MUST NOT drop any key of a stored local action row on a save, unless that row's customization is removed by the user or deleted by an adoption or a hub removal'"
    expected: "Holds. Non-authoritative verdict: parse_local_record keeps unknown keys in `extra`; local_record_data writes them back after the six known keys; async_set_local_action feeds existing.extra into make_local_record; with_label keeps extra; copy_local_records deep-copies it. Tests: test_unknown_keys_of_a_readable_row_survive_an_edit_and_a_label_refresh, test_failed_adoption_restores_unknown_row_keys, test_completed_adoption_keeps_unknown_keys_of_other_devices, test_unknown_row_keys_round_trip_as_copies. Edge (advisory IN-01): a later duplicate identity row that differs only in unknown keys is still dropped on the first save (D-10), with a warning log"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
  - test: "Review judgment-tier prohibition 11-25: 'MUST NOT clear or suppress local_action_failed for a trigger that still has local actions to run, except on a proven success of exactly that trigger or the removal of its customization'"
    expected: "Holds. Non-authoritative verdict: the guard `record is None or not record.actions` (manager.py async_report_local_outcome) drops only failures of triggers without local actions; the bound test keeps a failure whose trigger has actions"
    why_human: "unverified-prohibition - human review recommended (judgment tier, flagged)"
---

# Phase 11: Local Actions on Mirrors Verification Report

**Phase Goal:** On a follower, the user gives a mirrored device its own actions per trigger, in addition to or instead of the owner's actions. They run locally without approval under the device's mode and breaker, survive owner changes, and never leave the instance (MIR-01, backlog 999.1).
**Verified:** 2026-10-21T14:30:00Z
**Status:** human_needed
**Re-verification:** Ja, nach den Gap-Closure-Plänen 11-24 und 11-25. Der Vorbericht (`gaps_found`, 18/22) war durch die Änderungen an den abgedeckten Dateien veraltet.

## Zusammenfassung

Das Phasenziel ist erreicht. Die einzige offene Lücke des Vorberichts (G-1: Newer-Minor-Store wird beim Laden von Core neu geschrieben, plus WR-05 unbekannte Zeilenschlüssel) ist im Code geschlossen, nicht nur in den SUMMARY-Dateien. WR-06 (laufender Fehlerlauf öffnet das Issue nach einem Mute-Save wieder) ist ebenfalls behoben. Es bleiben keine `gaps`, keine Regressionen und keine Blocker.

Ich habe die Behauptungen selbst geprüft:
- `LocalActionsStore.async_load` liest über einen frischen `_LocalActionsReader` mit `read_only=True` (`local_actions_store.py:99-106`, Klasse ab `:42`). Core verwirft damit das Speichern nach dem Migrations-Hook. Der Writer-Store führt Cores Load nicht mehr aus.
- Meine beiden Sonden vom Vorbericht (Settings-Zähler eines entladenen Hubs mit `minor_version 2`; formungültiger `minor_version 2`-Store) sind jetzt grün: `after == before`, `bytes unchanged: True`, `LocalActionsStoreUnreadableError` weiterhin ausgelöst. Beim Vorbericht waren beide rot.
- Die WR-06-Sonde zeigt jetzt `issue after settle: False` (vorher `True`). Der Guard `record is None or not record.actions` steht in `async_report_local_outcome`.
- Unbekannte Schlüssel einer lesbaren Zeile liegen in `LocalActionRecord.extra` und werden von `local_record_data` hinter den sechs bekannten Schlüsseln zurückgeschrieben. Ein bekannter Schlüssel kann nie aus `extra` kommen.
- Vollständige Suite `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run python -m pytest -q -n 8`: 2115 passed, 2 xfailed. Das deckt sich mit dem Orchestrator-Stand.
- `ruff check` und `ruff format --check`: sauber (104 Dateien).

Zwei Warnungen aus dem Advisory-Review bestätigen sich, sie verletzen aber keine Must-have-Aussage (siehe Human Verification, Punkte 2 und 3):
- **README-Überanspruch:** "Starting this version or opening its settings never rewrites the file" stimmt für jeden Ladepfad, aber nicht für den Label-Refresh beim Start, wenn das Owner-Dokument einen geänderten Optionsnamen bringt. Die Daten bleiben vollständig; nur der Newer-Minor-Stempel wird auf Minor 1 gesetzt. Plan 11-24 zählt den Label-Refresh selbst zu den expliziten Saves.
- **Stille reduzierte Bedeutung:** Eine lesbare Zeile mit unbekannten Schlüsseln läuft ohne deren Semantik, ohne Log. Das ist die Owner-Entscheidung vom 2026-10-21 und im README dokumentiert.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1: options → mirror → trigger → "in addition to"/"instead of" → action editor; applies without restart; en+de texts (MIR-01, MIR-15) | ✓ VERIFIED (backend); rendering → human | `config_flow.py` HubOptionsFlow ruft `async_set_local_action`/`async_remove_local_action`; `test_local_actions_flow.py`, `test_translations.py` laufen grün |
| 2 | SC2: local runs without approval also when owner pending/blocked/empty; owner only on exact approved hash; empty "instead of" mutes; safe defaults while unapproved (MIR-02, MIR-05, MIR-11) | ✓ VERIFIED | `build_effective_trigger_plan` (`local_actions.py`), `effective_policy` → `LOCAL_SAFE_POLICY`; Gate-Matrix in `test_local_action_plans.py`, `test_local_invariants.py` |
| 3 | SC3: additive = one Script `parallel`, failure of one branch does not stop the other; mode and breaker gate local runs; edit releases breaker; test buttons/re-trigger run effective actions; own Repairs issue (MIR-03, MIR-09, MIR-10, MIR-13) | ✓ VERIFIED | `runner.py` einzelnes `parallel`; `test_local_parallel.py`, `test_test_buttons.py`, `test_retrigger.py` grün |
| 4 | SC4: nothing local leaves the instance; approvals valid; no new re-trigger words; count-only diagnostics; approval issue count while pending + adoption refused (MIR-04, MIR-10, MIR-12, MIR-14) | ✓ VERIFIED | `approval_state()` liest keinen lokalen Record; Byte-Identitäts-Tests in `test_local_invariants.py` grün; `extra` stammt nur aus der lokalen Store-Datei, nie vom Broker, und wird nie ausgeführt oder angezeigt |
| 5 | SC5 (amended): survive content change/rename/rev bump/restart/re-pin; orphan/removable/reattach; adoption discards with log + count; start-up, prunes and tombstones discard nothing; README documents all (MIR-06, MIR-07, MIR-08, MIR-15) | ✓ VERIFIED | `sync._async_remove` entfernt nur einen vorhandenen Mirror; `_async_discard_local_records` nur bei Adoption; Tombstone-Tests grün; README "Lifecycle" |
| 6 | 11-04: separate versioned Store; v1.0.1 main-Store save never touches it; newer major refused without overwrite; no startup GC | ✓ VERIFIED | `test_newer_major_version_refuses_and_keeps_the_stored_bytes` grün (Core wirft vor dem Migrations-Hook; Reader behält dieses Verhalten) |
| 7 | 11-10: two followers keep different overlays, shared bytes identical | ✓ VERIFIED | `test_local_multi_instance.py` grün |
| 8 | 11-14 (G-01): `local_action_failed` survives restart/prune/failed adoption; clears only on proven success, removal, completed adoption, hub removal (+ save-without-actions) | ✓ VERIFIED | Lifecycle-Tests grün |
| 9 | 11-15 (G-02): unreadable Store → one `local_actions_unreadable` issue (en/de); never overwritten; edits refused | ✓ VERIFIED (jetzt auch für newer minor) | `manager.py` `_async_load_local_actions`; der Newer-Minor-Fall liegt unter Truth 17 |
| 10 | 11-16 (G-03): a new hub removes a leftover local Store (incl. `.corrupt` copies) before entry creation; fails closed | ✓ VERIFIED | `test_hub_removal.py` grün |
| 11 | 11-17 (G-04): failed adoption keeps a tripped breaker paused | ✓ VERIFIED | `test_failed_adoption_keeps_a_tripped_breaker_paused` grün |
| 12 | 11-11/11-13: cross-file review ledger has no OPEN/ROUTED rows | ✓ VERIFIED | `11-REVIEW-DISPOSITION.md`: WR-01 bis WR-06 `fixed` |
| 13 | 11-13: Ruff, format, hassfest **and HACS** green | DEFERRED (HACS only) | Ruff und Format sauber; HACS läuft in Phase 12 |
| 14 | 11-13: manual frontend evidence is honestly PASS | ? UNCERTAIN → human | Das produktive HubOptionsFlow und `settings_unreadable` wurden nie im Browser gerendert (UAT Test 1 offen) |
| 15 | 11-18: empty retained config payload removes the mirror but never discards/rewrites/saves local records; device stays listed "not mirrored"; records reattach | ✓ VERIFIED | Siehe Truth 5 |
| 16 | 11-19: durable save of the named trigger without local actions deletes its `local_action_failed`; failed save, other trigger, save with actions, stop, owner results keep it | ✓ VERIFIED | `manager.py` löscht nach `_async_commit_local_records` nur bei `not record.actions`; Tests grün. Die frühere Coincidental-Reliance-Warnung (WR-06) ist durch Truth 24 behoben |
| 17 | 11-20: payload without a record list is unreadable; load raises, Store unloaded and refuses saves, issue raised, **stored bytes never change** | ✓ VERIFIED (jetzt auch für minor_version 2) | Sonde `test_probe_newer_minor_unreadable`: `LocalActionsStoreUnreadableError`, `bytes unchanged: True`. Regressionstests `test_shape_invalid_newer_minor_store_is_unreadable_and_never_written`, `..._for_every_unreadable_store_shape[shape_invalid_newer_minor]` grün |
| 18 | 11-20: corrupt copy beside a missing file is unreadable; null data / missing file load empty; `async_remove_records` deletes own copies; texts | ✓ VERIFIED | Store- und Manager-Tests grün |
| 19 | 11-21: unparseable rows and extra top-level keys kept verbatim after records on every save; never applied, counted or shown | ✓ VERIFIED | `parse_local_actions_payload`/`local_actions_payload`; Store `_preserved`/`_extra`; Tests grün |
| 20 | 11-22: unreadable Store (loaded or unloaded) never shows a count; `settings_unreadable` step (en/de) | ✓ VERIFIED | `config_flow.py`, `manager.py`; Tests grün |
| 21 | 11-22: a readable Store keeps the count for loaded and unloaded hubs; **opening the settings never writes the local Store** | ✓ VERIFIED (jetzt auch für minor_version 2) | Sonde `test_probe_newer_minor`: Count 1, `after == before` inklusive `minor_version: 2`. `test_unloaded_hub_settings_count_never_writes_a_newer_minor_local_store` grün. Docstring `manager.py:615` korrigiert ("The read goes through a read-only Store") |
| 22 | 11-23: amendments recorded in 11-CONTEXT.md; MIR-08, SC5 and release notes carry the amended tombstone rule | ✓ VERIFIED | Commits `1e426b5`, `b3ecda2`; ROADMAP SC5 und REQUIREMENTS MIR-08 tragen "(amended 2026-10-21 ...)" |
| 23 | 11-24: loading never writes the local Store (any version); newer minor keeps exact bytes through start, reload and removal settings of a loaded and an unloaded hub; shape-invalid newer minor stays unreadable and byte-identical; unknown row keys kept through every save; an explicit save keeps every key and stamps this minor; docstring contract for idempotent migrations; README "Newer versions"; CONTEXT amendments; WR-05 fixed | ✓ VERIFIED | `_LocalActionsReader` (`read_only=True`) und `LocalActionsStore.async_load` (`local_actions_store.py`); `LocalActionRecord.extra`, `make_local_record(extra=)`, `local_record_data`, `copy_local_records` (`local_actions.py`); `async_set_local_action` übergibt `existing.extra` (`manager.py`); Idempotenz-Vertrag im Docstring von `migrate_local_actions_payload`. Tests mit `minor_version 2`: `test_newer_minor_local_store_is_never_written_by_the_start_or_the_settings`, `test_newer_minor_version_load_never_writes_the_store`, `test_a_save_after_a_newer_minor_load_keeps_every_key_and_stamps_this_minor`, Core-Pin `test_a_read_only_store_returns_a_newer_minor_payload_without_writing`, `test_unknown_keys_of_a_readable_row_survive_an_edit_and_a_label_refresh` grün. Einschränkung: der Label-Refresh beim Start schreibt nach einem geänderten Owner-Dokument (siehe Human Verification, Punkt 2) |
| 24 | 11-25: a run in flight when the trigger is saved without local actions cannot re-create `local_action_failed`; a failure of a trigger that still has local actions is reported as before; a removed customization is still dropped; WR-06 fixed | ✓ VERIFIED | `async_report_local_outcome`: `record is None or not record.actions` → return. Sonde `test_probe_mute_race`: `issue right after mute save: False`, `issue after settle: False`. Tests `test_an_in_flight_failing_run_cannot_reopen_the_issue_after_a_mute_save`, `..._after_emptying_the_additive_actions`, `test_failure_outcome_of_a_customization_without_local_actions_raises_no_local_issue`, `test_an_in_flight_failure_still_reports_while_its_trigger_has_local_actions` grün |

**Score:** 22/24 truths verified. 1 deferred (HACS → Phase 12), 1 uncertain (Produktiv-UI-Rendering → human). 0 present but behavior-unverified.

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | HACS validation of the Phase 11 build | Phase 12 | SC4: "the release workflow, hassfest and HACS are green" |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `custom_components/mqtt_actions/local_actions_store.py` | Separater Store; `_LocalActionsReader`; `LocalActionsStoreUnreadableError`; Corrupt-Copy-Behandlung; `preserved_device_ids` | ✓ VERIFIED | Substantiell, in Manager, `__init__` und `config_flow` verdrahtet; Level 4: `_LocalActionsReader` wird von jedem `async_load_records` benutzt |
| `custom_components/mqtt_actions/local_actions.py` | Pure Modell, Pläne, Policy, `extra`, preserved/extra-Payload, Idempotenz-Vertrag | ✓ VERIFIED | `LocalActionRecord.extra`, `parse_local_record`, `local_record_data`, `copy_local_records` |
| `custom_components/mqtt_actions/manager.py` | Tombstone behält; Save ohne Actions löscht Issue; WR-06-Guard; `extra` im Save; korrigierte Docstrings | ✓ VERIFIED | Alle Symbole vorhanden und genutzt |
| `custom_components/mqtt_actions/sync.py`, `const.py`, `config_flow.py`, `translations/{en,de}.json` | Unverändert gegenüber Vorbericht | ✓ VERIFIED | Regressionstests grün |
| `README.md`, `docs/troubleshooting.md` | Tombstone, Save-ohne-Actions, Newer versions, cannot-be-read | ✓ VERIFIED (mit Wortlaut-Warnung) | `test_docs.py` grün; README:367-371 siehe Human Verification Punkt 2 |
| Tests (`test_hub_removal`, `test_local_actions_store`, `test_local_actions_lifecycle`, `test_local_actions_manager`, `test_core_contracts`, `test_docs`) | minor_version-2-Fixtures; In-Flight-Regression | ✓ VERIFIED | 12 `minor_version: 2`-Fixtures über 6 Dateien; vorher nur minor 1 |

### Key Link Verification

| From | To | Via | Status |
|------|----|-----|--------|
| `LocalActionsStore.async_load` | `_LocalActionsReader(...).async_load()` | frischer read-only Store pro Load | WIRED (`local_actions_store.py:99-106`) |
| `LocalActionsStore.async_load_records` | `async_load` | `stored = await self.async_load()` | WIRED |
| `async_local_action_device_count` (unloaded hub) | `LocalActionsStore.async_load_records` | read-only Reader | WIRED, durch Sonde bestätigt |
| `async_set_local_action` | `make_local_record(extra=existing.extra)` | Schlüssel der gespeicherten Zeile bleiben | WIRED |
| `local_record_data` | `record.extra` | hinter `RECORD_KEYS`, kein Überschreiben | WIRED |
| Runner `finally` → `on_local_outcome` | `async_report_local_outcome` | Guard `record is None or not record.actions` | WIRED |
| `sync._async_remove` / `_async_prune` | `manager.async_remove_mirror` | ohne Store-Write | WIRED (unverändert) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| Settings / `settings_unreadable` | `local_devices` | Manager-Records ∪ preserved ids, oder frischer Read; `None` bei unlesbar | Ja | ✓ FLOWING (schreibt nicht mehr) |
| Gespeicherte Zeile | `extra` | Parse der Store-Datei → Record → `local_record_data` | Ja | ✓ FLOWING |
| `local_action_failed` | Issue-Daten | `async_report_local_outcome` nach Guard | Ja | ✓ FLOWING |
| `adopt_device`-Antwort | `local_actions_discarded` | `_async_discard_local_records` | Ja | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Settings-Zähler eines entladenen Hubs lässt einen Newer-Minor-Store unberührt | Sonde `test_probe_newer_minor` (Scratchpad des Vorberichts) | Count 1; `after == before`, `minor_version: 2` bleibt | ✓ PASS (vorher FAIL) |
| Formungültiger Newer-Minor-Store bleibt byte-identisch und unlesbar | Sonde `test_probe_newer_minor_unreadable` | `LocalActionsStoreUnreadableError`; `bytes unchanged: True` | ✓ PASS (vorher FAIL) |
| Mute-Save während eines laufenden Fehlerlaufs lässt das Issue gelöscht | Sonde `test_probe_mute_race` | `issue right after mute save: False`, `issue after settle: False`, `record actions: [[]]` | ✓ PASS (vorher FAIL) |
| Volle Suite | `MQTT_ACTIONS_REQUIRE_BROKER=1 uv run python -m pytest -q -n 8` | 2115 passed, 2 xfailed in 43.7s (einmal ausgeführt) | ✓ PASS |
| Lint und Format | `uv run ruff check custom_components tests`; `ruff format --check` | All checks passed; 104 files already formatted | ✓ PASS |

Sonden liegen unter `/tmp/akentner/claude-1000/-home-akentner-Projects-homeassistant-mqtt-actions-integration/667d23fa-9fde-4c75-b77c-e0d2d74cb17b/scratchpad/verify/` (`test_probe_newer_minor.py`, `test_probe_mute_race.py`, `conftest.py`). Aufruf aus dem Repo-Root: `PYTHONPATH=. uv run python -m pytest --rootdir=<dir> -c pyproject.toml -s -p no:logging <file>`.

### Probe Execution

Es gibt kein `scripts/*/tests/probe-*.sh`, und kein Plan deklariert eines. Step 7c entfällt.

### Requirements Coverage

Alle 15 IDs (MIR-01 bis MIR-15) stehen in den `requirements:`-Feldern der PLAN-Dateien; `REQUIREMENTS.md` ordnet genau MIR-01 bis MIR-15 Phase 11 zu. Keine verwaisten Anforderungen.

| Requirement | Source Plan(s) | Status | Evidence |
|-------------|----------------|--------|----------|
| MIR-01 | 11-02, 11-08, 11-11, 11-13 | ✓ SATISFIED (Rendering: human) | Truth 1 |
| MIR-02 | 11-01, 11-03, 11-05, 11-10, 11-16 | ✓ SATISFIED | Truths 2, 10, 15 |
| MIR-03 | 11-01, 11-03, 11-07 | ✓ SATISFIED | Truth 3 |
| MIR-04 | 11-01, 11-04, 11-09, 11-10 | ✓ SATISFIED | Truth 4 |
| MIR-05 | 11-01, 11-03, 11-08, 11-15, 11-19, 11-20, 11-25 | ✓ SATISFIED | Truths 2, 16, 24 |
| MIR-06 | 11-04, 11-05, 11-06, 11-10, 11-15, 11-20, 11-21, 11-24 | ✓ SATISFIED | Truths 5, 6, 19, 23 |
| MIR-07 | 11-04, 11-06, 11-08, 11-18 | ✓ SATISFIED | Truths 5, 15 |
| MIR-08 (amended) | 11-06, 11-09, 11-12, 11-18, 11-22, 11-23, 11-24 | ✓ SATISFIED | Truths 5, 15, 22, 23 |
| MIR-09 | 11-05, 11-07, 11-10, 11-17 | ✓ SATISFIED | Truths 3, 11 |
| MIR-10 | 11-01, 11-07, 11-10 | ✓ SATISFIED | Truths 3, 4 |
| MIR-11 | 11-01, 11-03, 11-05, 11-10 | ✓ SATISFIED | Truth 2 |
| MIR-12 | 11-06, 11-07, 11-08 | ✓ SATISFIED | Truth 4 |
| MIR-13 | 11-01, 11-03, 11-07, 11-14, 11-19, 11-25 | ✓ SATISFIED | Truths 3, 8, 16, 24 |
| MIR-14 | 11-01, 11-09 | ✓ SATISFIED | Truth 4 |
| MIR-15 | 11-02, 11-08, 11-09, 11-12, 11-14..11-16, 11-18..11-22, 11-24 | ✓ SATISFIED (README-Wortlaut: Human Verification Punkt 2) | en/de-Parität und `test_docs.py` grün |

Hinweis für den Orchestrator: In `.planning/REQUIREMENTS.md` stehen MIR-01 bis MIR-04, MIR-07, MIR-09 bis MIR-12 und MIR-14 noch auf "Gaps Found" (Stand des Vorberichts, Commit `541cc7c`). Nach dieser Verifikation tragen alle 15 IDs Evidenz im Code; die Tabelle muss nach der Human-Freigabe aktualisiert werden. MIR-01 und MIR-15 hängen am UI-Rendering (Human Punkt 1).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| Phase-modified files | - | `TBD`/`FIXME`/`XXX` in `custom_components/` | none | `grep` findet keinen Treffer |
| `README.md` | 371 | "Starting this version ... never rewrites the file" überspannt den Label-Refresh beim Start | ⚠️ Warning | Dokumentationsgenauigkeit, kein Datenverlust (Human Punkt 2) |
| `local_actions_store.py` | 158-165 | Zeilen mit unbekannten Schlüsseln laufen still ohne deren Semantik | ⚠️ Warning (Owner-Entscheidung) | Beobachtbarkeit; kein Must-have verlangt ein Log (Human Punkt 3) |
| `local_actions.py` | 268-276 | IN-01: späteres Duplikat, das sich nur in unbekannten Schlüsseln unterscheidet, fällt beim ersten Save weg (D-10, mit Warn-Log) | ℹ️ Info | Altverhalten; neben dem README-Versprechen dokumentierbar |
| `local_actions_store.py` | 99-106 | IN-02: der Reader sieht nur geschriebene Daten, kein pending `_data` | ℹ️ Info | Praktisch unerreichbar, `async_save_records` wird vor jedem Load bis auf die Platte erwartet |
| diverse | - | IN-08 bis IN-10 und IN-03..IN-07 aus früheren Reviews | ℹ️ Info | Keine falsifiziert eine Truth |

### Human Verification Required

Siehe Frontmatter `human_verification` (14 Punkte). Zusammengefasst:

1. **Produktives HubOptionsFlow rendern (en/de)**, inklusive `settings_unreadable` und "not mirrored"-Geräte nach einem Tombstone. UAT Test 1, offen.
2. **README-Satz zum Neuschreiben** entscheiden: engen auf "ein Load und das Öffnen der Settings schreiben nie; nur eine lokale Änderung oder der Refresh eines geänderten Anzeigenamens schreibt" oder so belassen. Optional ein Test mit abweichendem Label in einer Minor-2-Datei.
3. **Stille reduzierte Bedeutung** entscheiden: optional eine Warn-Log-Zeile pro Load für Records mit nicht leerem `extra`.
4. **Judgment-Tier-Prohibitions** 11-03, 11-08, 11-12 (UAT 2-4, offen) sowie 11-18, 11-19, 11-21, 11-22, 11-23, 11-24 (zwei), 11-25: Für jede steht im Frontmatter ein nicht autoritatives Urteil ("hält"). Sie sind als `unverified-prohibition - human review recommended` markiert und werden nie stillschweigend als bestanden gezählt.

Ein neuer UAT-Lauf sollte die Punkte 2 bis 4 aufnehmen; UAT Test 5 (WR-01 bis WR-04) ist durch die Owner-Entscheidung vom 2026-10-21 erledigt.

### Gaps Summary

Keine Lücken. Die Phase kann nach der Human-Freigabe (vor allem Punkt 1, das Rendering auf dem Bench) abgeschlossen werden. Phase 12 erlaubt keine Produktänderungen; die Punkte 2 und 3 sind deshalb vor Phase 12 zu entscheiden, falls sie Code oder README ändern sollen.

---

_Verified: 2026-10-21T14:30:00Z_
_Verifier: Claude (gsd-verifier)_
