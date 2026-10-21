# Phase 11: Local Actions on Mirrors - Context

**Gathered:** 2026-10-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement MIR-01 to MIR-15: followers configure local actions per trigger of mirrored Switch and Select devices, in addition to or instead of owner actions. Local actions require no remote approval, remain on the instance, and obey device mode and breaker gates. This phase includes UI, persistence, lifecycle, diagnostics, tests and documentation. Full final-build verification and v1.1.0 release remain Phase 12.

</domain>

<decisions>
## Implementation Decisions

### Carried forward from requirements and owner decisions of 2026-10-11
- **D-01:** One Script per device. In additive mode, owner and local actions run in parallel inside that Script; a runtime failure in either branch does not prevent the other. Run mode and breaker remain device-wide. No separate local Script and no step-level patches.
- **D-02:** Owner actions require approval of their exact actions hash. Local actions run independently of pending, blocked or empty owner actions, with owned-device trust: no GuardedTemplate or remote-action denylist on local actions. Apply static denial and runtime guards to the owner branch only, before assembly.
- **D-03:** While owner actions are unapproved, use safe defaults for local execution instead of owner-provided run_on_startup, run mode and breaker limits. Observe/disabled modes and breaker apply; a local edit releases a tripped breaker. Test buttons and re-trigger use effective actions, with no new broker status/reason words.
- **D-04:** Local actions never enter central config, actions hash, exports, diagnostics content or adoption payload. Existing approvals remain valid. Diagnostics expose counts only, including per-device and orphaned counts. Replacing triggers locally leaves approval pending and does not permit adoption of unapproved owner actions.
- **D-05:** Local actions survive owner content/name/revision changes, restarts and owner re-pins. Removed Select options remain inactive and automatically reattach when the same StateValue returns. Tombstones and adoption discard local actions with a log entry; adopt_device reports the discard. Startup and transient prune never discard them. (Tombstones amended 2026-10-21, see Amendments.)
- **D-06:** UI lives in a menu in the hub options flow, never a new config subentry type. All new UI texts exist in English and German. README covers add/replace, mute, parallel execution, lifecycle, downgrade and the {{ state }} template caveat.

### Storage, removal and downgrade
- **D-07:** Store local actions in a separate HA Store file. v1.0.1 ignores it and does not execute local actions; after upgrading again, saved local actions are available. Do not use an additive key in the existing main Store, which older versions drop on save.
- **D-08:** Removing the whole integration deletes its local Store, including when shared devices are retained. The removal warning includes the number of devices whose local actions will be deleted, e.g. 3 devices, rather than only a generic warning.
- **D-09:** README and release notes carry a prominent downgrade warning: v1.0.1 ignores local replacement and mute settings, so approved owner actions may run again. A downgrade round trip on the real bench remains deferred as MIR-F4; do not claim it has been verified.

### Trigger identity and orphaned options
- **D-10:** Stored identity is device ID plus device kind plus StateValue. Preserve existing state normalization; display-name edits retain identity. Matching StateValues across Switch and Select must not share local actions accidentally.
- **D-11:** Select trigger labels show friendly name and StateValue, e.g. Gemütlich (`cozy`). Retain the last known friendly name for orphaned options and label them as no longer present on the owner.
- **D-12:** Users can view, edit or delete orphaned local actions. Editing does not activate them; they stay inactive until their matching option returns. Keep kind-mismatched records inactive under the same identity rule, rather than applying them to another device kind.

### Editing flow
- **D-13:** Navigate hub options → mirrored device → trigger. Save mode and actions per trigger, apply immediately without restart, then return to trigger selection. Cancelling discards only the current unsaved edit, not already saved trigger changes.
- **D-14:** A dedicated Remove local customization entry removes the mode and local actions after confirmation. This restores owner-only behavior subject to approval. Keep removal distinct from an empty replacement, which mutes the trigger locally.
- **D-15:** New local customizations preselect In addition to. Saving Instead of with no local actions requires a separate confirmation stating that the trigger will execute no actions on this instance.

### Notices and local failures
- **D-16:** Trigger selection shows the mode directly: additional, instead of owner actions, or locally muted. Orphan labels retain the identifying name and StateValue.
- **D-17:** The owner approval issue includes the replaced-trigger count and explicitly explains that local actions may already run and that approval concerns owner actions only. Do not imply local replacements grant approval.
- **D-18:** Local action failures raise one Repairs issue per device, independent of owner failure issues. It names the latest failed local trigger and its error.
- **D-19:** Clear that local issue only when its affected local trigger successfully runs or its local customization is removed. A successful different trigger or owner branch does not clear it. Preserve existing protection against dropped, cancelled or superseded runs masquerading as success.

### Research and planning constraints carried forward
- **D-20:** Research must pin core 2026.9.4 parallel behavior, including stop, continue_on_error, response variables and exception propagation after both branches finish. If semantics conflict with D-01, return to the owner before any sequential fallback.
- **D-21:** Invariant tests first: hash equality, adoption payload bytes, approval-state × local-mode × owner-actions gate matrix (4×3×2), and every fake-broker publish checked for local-content leakage. Then HA-free overlay module and plan-based runner assembly; owned and overlay-free mirror sequences stay byte-identical to existing behavior. Next manager wiring, then thin options-flow client, translations, approval text and README.
- **D-22:** Load overlays before restoring mirrors; persist edits under the manager lock with an immediate save; no startup garbage collection. Research a separate Store skeleton with its own migration function and early bench rendering of section plus ActionSelector on the 2026.9 frontend.
- **D-23:** Add a security threat entry for trust-level mixing within one Script. End Phase 11 with milestone-wide cross-file review so product fixes land before Phase 12. Existing native migration and shared-topic invariants remain unchanged.

### Amendments (owner decision 2026-10-21, code review WR-01 to WR-04)
- **D-05 amended (WR-01):** A tombstone removes the mirror at once but keeps its local actions inactive, like after a prune. They are shown as not mirrored and stay until the user removes them or the device returns. Adoption still discards them with a log entry and the `adopt_device` count. Explicit removal and hub removal still delete them. The grace-timer alternative was rejected.
- **D-19 amended (WR-02):** Saving the customization of the named trigger without local actions (a mute or an empty additive list) also clears its local failure issue.
- **D-07 extended (WR-03):** A payload without a record list, or a missing file next to a Home Assistant `.corrupt` copy, counts as unreadable: issue raised, no overlay, saves refused. Stored rows this release cannot parse are kept unchanged on every save.
- **D-08 extended (WR-04):** When the saved local actions cannot be read, the removal settings show a dedicated warning, in English and German, that they cannot be read and will be deleted, instead of a device count.

### Implementation discretion
- Exact Store key/schema and migration mechanics, module/API names, plan splits, bounded diagnostics counts and translated wording are implementation details, subject to the decisions above.
- Research must select and justify safe local execution defaults under MIR-11. No numerical defaults were chosen in this discussion.
- The user selected concrete options throughout; no product decisions were explicitly delegated.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Scope and contracts
- `.planning/PROJECT.md` — core value, trust model, German UI/chat and English code conventions.
- `.planning/REQUIREMENTS.md` — MIR-01 to MIR-15 and deferred MIR-F1 to MIR-F4.
- `.planning/ROADMAP.md` — Phase 11 success criteria, research gates, test-first plan ordering and Phase 12 boundary.
- `docs/adr/0001-native-entities-instead-of-mqtt-discovery.md` — native entities and optional Discovery export.

### Existing safeguards and operational contracts
- `.planning/phases/10-review-findings-and-native-migration-extraction/10-CONTEXT.md` — extracted migration collaborator and loud core-contract tests.
- `.planning/phases/09.2-cr-01-cross-instance-gap-closure-no-catch-lets-core-clear-a/09.2-CONTEXT.md` — owner-only shared-topic clearing and cross-instance kept-row invariants.
- `.planning/phases/09.1-uat-02-gap-closure-remove-leftover-disabled-and-legacy-mqtt/09.1-CONTEXT.md` — fail-safe discovery handling and unchanged registry guarantees.
- `README.md` — existing action execution, approval, lifecycle and development documentation.
- `docs/diagnostics.md` — existing diagnostics privacy contract.

No separate phase SPEC.md or external specification was supplied for this discussion.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `custom_components/mqtt_actions/model.py`: DeviceSpec/TriggerSpec, device kind, StateValue-derived trigger keys and existing normalization.
- `custom_components/mqtt_actions/runner.py`: trigger validation, static refusal, guarded owner execution and the per-device Script choose dispatcher.
- `custom_components/mqtt_actions/config_flow.py`: HubOptionsFlow, action selectors and existing Select draft/menu patterns; retain per-trigger save semantics chosen here.
- `tests/conftest.py`, `tests/helpers.py`, `tests/fake_broker.py`: shared HA fixtures, helpers and multi-instance publish observation.

### Established Patterns
- Manager-owned HA Store and immediate async_save_now; locked mutation and reconciliation.
- Content hashes and per-instance approval keep broker-provided actions inert until approved; local overlays must not change those hashes.
- Repairs and diagnostics have bounded, content-conscious output; local actions must stay outside diagnostics content.
- Native migration orchestration is already extracted into NativeMigration; preserve its startup ordering and shared-topic safeguards.

### Integration Points
- `custom_components/mqtt_actions/manager.py`: load local Store before mirror restoration, mutation APIs, deletion/adoption, gating and runner rebuilds.
- `custom_components/mqtt_actions/runner.py`: assemble effective per-trigger action plans without guarding trusted local branches.
- `custom_components/mqtt_actions/config_flow.py`: options menu, mirror/trigger selectors, orphan editor and explicit confirmation steps.
- `custom_components/mqtt_actions/repairs.py`, `custom_components/mqtt_actions/diagnostics.py`, `custom_components/mqtt_actions/translations/en.json`, `custom_components/mqtt_actions/translations/de.json`: independent local errors, counts and bilingual descriptions.

</code_context>

<specifics>
## Specific Ideas

- Picker examples: Einschalten — zusätzlich; Ausschalten — lokal stummgeschaltet; Gemütlich (`cozy`) — statt Owner-Aktionen.
- Orphan example: Gemütlich (`cozy`) — beim Owner nicht mehr vorhanden.
- Mute confirmation: Dieser Auslöser führt auf dieser Instanz keine Aktionen mehr aus.
- Approval explanation: Lokale Aktionen können bereits laufen. Die Freigabe gilt ausschließlich für Owner-Aktionen.
- Hub removal warning example: Dabei werden auch lokale Aktionen für 3 Geräte auf dieser Instanz gelöscht.

</specifics>

<deferred>
## Deferred Ideas

None introduced in discussion. Existing roadmap deferrals remain: local actions on owned devices, local action export/import, richer re-trigger acknowledgements and the real-bench downgrade round trip. No pending todos matched this phase.

</deferred>

---

*Phase: 11-local-actions-on-mirrors*
*Context gathered: 2026-10-17*
