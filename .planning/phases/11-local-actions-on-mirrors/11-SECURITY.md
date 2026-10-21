---
phase: "11"
slug: "local-actions-on-mirrors"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
threats_total: 47
asvs_level: 1
block_on: high
register_authored_at_plan_time: true
created: "2026-10-21"
---

# Phase 11 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register merged from the `<threat_model>` blocks of plans 11-01 to 11-17 and the `## Threat Flags` sections of their
> SUMMARYs (no plan reported a new flag). Verification depth: ASVS L1 (grep-level evidence plus the green test
> commands of `11-VALIDATION.md`). Paths are relative to the repo root; `C/` means `custom_components/mqtt_actions/`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Local Store to shared MQTT output | Trusted local action configuration must never serialize onto broker traffic | Local action records (private, instance-only) |
| Core Script/trace internals to integration | Phase behavior relies on pinned Core semantics | Run status, trace variables (ephemeral) |
| Bench UI to repository evidence | Visual evidence must match the recorded pinned versions | Screenshot, interaction table |
| Remote owner actions and local actions in one Script | Two trust levels share scheduler and variables, with different validation/guard rules | Owner (remote, untrusted until approved) and local (trusted) action lists |
| Core trace to Repairs state | Internal trace must reduce to bounded outcomes without content persistence | Bounded status and error text |
| HA Store JSON to local execution | Disk data is parsed before becoming runnable action input | `mqtt_actions` local Store payload |
| Main Store to local Store | Older code may rewrite only the main file and must not erase overlays | Two separate Store files |
| Unapproved owner document to local scheduler | Remote execution metadata cannot govern local work until exact approval | Owner mode/max_runs/breaker settings |
| Flow/service mutation to durable local Store | Stale or untrusted UI input crosses Manager validation and lock | Options-flow submissions |
| Remote lifecycle messages to local Store | Prune and tombstone have different authority to destroy local data | Retained prune/tombstone messages |
| Mirror to owned adoption | Two Store files plus ConfigSubentry creation without a DB transaction | Device spec, local records |
| Local BranchOutcome to Repairs registry | Runtime evidence controls issue creation and clearing | Bounded outcome per branch |
| Broker re-trigger to local runner | Remote request may invoke local actions only through the existing admin/rate/device gates | Re-trigger request |
| Options form to Manager; broker labels to Markdown | ActionSelector is presentation only; remote labels may contain markup | Form input, broker labels |
| Manager records to diagnostics | Private local action content must collapse to counts | Integer counts only |
| Removal lifecycle to HA Store callbacks | Late saves must not recreate deleted local state | Store keys, issues |
| Follower-local Stores on one broker | Local records must not cross instance boundaries | Per-instance Store keys |
| Phase 11 changes to native migration/shared topics | New lifecycle paths must not empty another instance's retained topic | Retained shared topics |
| Review ledger, gates and docs to Phase 12 / users | Unrouted findings, skipped tiers or overclaiming docs would create false assurance | Ledger rows, gate results, README/release notes |
| Issue registry across restart | HA persists only persistent issues with their data and placeholders | `.storage/repairs.issue_registry` |
| Leftover local Store to a new hub; hub flow to a live hub | Old trusted actions must not run on a new hub; cleanup must never touch a live hub | Local Store file |
| Admin adoption service to device runtime | A failed admin operation must leave the device exactly as it was, pause included | Breaker trip state |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation (evidence) | Status |
|-----------|----------|-----------|----------|-------------|-----------------------|--------|
| T-11-01 | Information disclosure | FakeGateway publication boundary | high | mitigate | Publication oracle for transient and retained publishes: `tests/test_local_invariants.py:442`, export bytes baseline `:370` (11-01-T1 green) | closed |
| T-11-02 | Elevation of privilege | Approval/customization gate | high | mitigate | 24-case authority oracle `tests/test_local_action_plans.py` (95 passed) | closed |
| T-11-03 | Repudiation | Native parallel outer result | high | mitigate | Masked/continued-error Core pins in `tests/test_local_parallel.py` (40 passed) | closed |
| T-11-04 | Repudiation | Frontend compatibility claim | medium | mitigate | `11-FRONTEND-SMOKE.md` `Verdict: PASS`, screenshot, human approval 2026-10-21 | closed |
| T-11-05 | Elevation of privilege | Trust-level mixing in one Script | high | mitigate | Separate branch validation; denylist + GuardedTemplate owner-only: `C/runner.py:182-183`; `tests/test_local_parallel.py -k "one_additive or owner_only_guard"` | closed |
| T-11-06 | Tampering | Immutable owner DeviceSpec | high | mitigate | Deep-copied record actions `C/local_actions.py:85`; byte-identical hash/adoption invariants in `tests/test_local_invariants.py` | closed |
| T-11-07 | Repudiation | Per-branch outcome reducer | high | mitigate | Conservative BranchOutcome reducer in `C/local_actions.py`; masked/cancelled/superseded cases in `tests/test_local_parallel.py` | closed |
| T-11-08 | Information disclosure | Core trace variables | medium | mitigate | Trace reduced to bounded status/error and collector discarded in `C/runner.py`; no trace in diagnostics (`tests/test_diagnostics.py` sentinels) | closed |
| T-11-09 | Tampering | LocalActionsStore payload | high | mitigate | Strict parser, newer-major refusal `C/local_actions_store.py:38,81`; `tests/test_local_actions_store.py -k "newer or malformed"` | closed |
| T-11-10 | Denial of service | Immediate local Store save | medium | mitigate | `LocalActionsStore.async_save_records` `C/local_actions_store.py:101` keeps prior snapshot on failure; `tests/test_local_actions_manager.py -k save_failure` | closed |
| T-11-11 | Information disclosure | Test Store key collision | medium | mitigate | Distinct keys via `tests/fake_broker.py` `instance_store_keys`; `tests/test_local_actions_store_instances.py` | closed |
| T-11-12 | Elevation of privilege | EffectivePolicy | high | mitigate | Fixed safe policy until exact approval `C/local_actions.py:390-400` (`effective_policy`); `test_pending_local_policy_is_false_serial_5_10_10_whatever_the_owner_says` | closed |
| T-11-13 | Tampering | Manager local mutation API | high | mitigate | Recheck under `self._lock` (11 lock sites in `C/manager.py`), validate, immediate save, swap; failed-save tests | closed |
| T-11-14 | Denial of service | Concurrent edit/approval/rebuild | medium | mitigate | Single Manager lock + immutable generation snapshot; `tests/test_local_actions_manager.py` (45 passed) | closed |
| T-11-15 | Repudiation | Breaker release on edit | medium | mitigate | Release only after durable target-device save; `-k breaker` tests; adoption release fixed by G-04 (T-11-46) | closed |
| T-11-16 | Tampering | Tombstone/prune distinction | high | mitigate | `MirrorRemovalCause` `C/const.py:268`; tombstone-after-prune tests in `tests/test_local_actions_lifecycle.py` | closed |
| T-11-17 | Denial of service | Cross-Store adoption failure | high | mitigate | Rollback restores mirror+records before any publish; injected-failure tests; residual trip/issue gaps fixed by G-01/G-04 | closed |
| T-11-18 | Elevation of privilege | Adoption with local replacement | high | mitigate | Approval gate stays owner-only; `test_every_trigger_replaced_keeps_pending_owner_hash_yaml_and_refused_adoption` | closed |
| T-11-19 | Information disclosure | Adoption response/log | medium | mitigate | Response carries count only: `C/services.py:318` `local_actions_discarded`; adoption byte oracle | closed |
| T-11-20 | Elevation of privilege | Re-trigger effective actions | high | mitigate | Existing receiver gates in `C/retrigger.py` unchanged; `tests/test_retrigger.py` + `-k retrigger` green | closed |
| T-11-21 | Repudiation | Local failure clear | high | mitigate | Clear only on same trigger + current Script/generation + proven success; issue/clear tests; F-01 fixed by 11-14 | closed |
| T-11-22 | Tampering | Approval view replacement count | medium | mitigate | Count-only `replaced_trigger_count` `C/trust.py:129`; owner hash/YAML assertions unchanged | closed |
| T-11-23 | Information disclosure | Repairs placeholders | medium | mitigate | Escaped/bounded label and error in `C/manager.py`; no actions or traces in placeholders | closed |
| T-11-24 | Tampering | HubOptionsFlow submit | high | mitigate | Stable identity, loaded-manager check, Manager recheck in `C/config_flow.py`; `tests/test_local_actions_flow.py` | closed |
| T-11-25 | Elevation of privilege | Replacement/mute UI | high | mitigate | Separate confirmations in `C/config_flow.py`; `test_empty_replacement_needs_the_mute_confirmation_before_any_save` | closed |
| T-11-26 | Information disclosure | Broker labels in flow | medium | mitigate | Markdown placeholders escaped in `C/config_flow.py`; diagnostics count-only | closed |
| T-11-27 | Information disclosure | Diagnostics | high | mitigate | Integer allow-list `C/diagnostics.py:9`; multi-sentinel test `tests/test_diagnostics.py` | closed |
| T-11-28 | Tampering | Hub removal | medium | mitigate | Common loaded/unloaded cleanup, both Store keys and issues asserted gone: `tests/test_hub_removal.py` (99 passed with translations) | closed |
| T-11-29 | Repudiation | Downgrade/release documentation | medium | mitigate | `tests/test_docs.py` deferred/MIR-F4 wording; release draft keeps round trip deferred | closed |
| T-11-30 | Information disclosure | Cross-instance overlay isolation | high | mitigate | Two-follower assertions `tests/test_local_multi_instance.py` (6 passed) | closed |
| T-11-31 | Elevation of privilege | Pending/empty owner across followers | high | mitigate | `test_followers_keep_exact_approvals_and_safe_policies_on_identical_shared_bytes` | closed |
| T-11-32 | Tampering | Shared-topic migration regressions | high | mitigate | Native/shared-topic suites run unchanged (11-10-T2: 280 passed) | closed |
| T-11-33 | Denial of service | Multi-instance loop/queue | medium | mitigate | Device-wide breaker/queue limits asserted per follower in `tests/test_local_multi_instance.py` | closed |
| T-11-34 | Tampering | Cross-file authority/lifecycle paths | high | mitigate | `11-CROSS-FILE-REVIEW.md` findings F-01 to F-20 with locations and regression tests | closed |
| T-11-35 | Repudiation | Final validation evidence | high | mitigate | 11-13 Final Gate records exact commands, `MQTT_ACTIONS_REQUIRE_BROKER=1`, no `--deselect`, separate frontend evidence | closed |
| T-11-36 | Elevation of privilege | Regression after review fix | high | mitigate | Precondition: all routed findings FIXED; four FIXED regression ids rerun plus full tiers (2072 passed) | closed |
| T-11-37 | Repudiation | Finding routing to Phase 11 fixes | high | mitigate | Ledger has 0 OPEN/ROUTED rows (4 FIXED, 16 NO-CHANGE); 11-13 precondition holds | closed |
| T-11-38 | Repudiation | Local failure issue lifecycle | medium | mitigate | Persistent issue `C/manager.py:1898` (`is_persistent=True`); `test_local_failure_issue_survives_restart_prune_and_failed_adoption_until_success_or_removal` | closed |
| T-11-39 | Information disclosure | Persistent issue data in `.storage/repairs.issue_registry` | low | accept | See Accepted Risks AR-02 | closed |
| T-11-40 | Denial of service | Start cleanup of stale local issues | medium | mitigate | Cleanup only after successful load; `test_refused_local_load_keeps_every_local_failure_issue` | closed |
| T-11-41 | Repudiation | Refused local load | medium | mitigate | Instance issue `local_actions_unreadable` `C/manager.py:198`, en/de translations | closed |
| T-11-42 | Tampering | Newer or damaged local Store file | high | mitigate | Saves refused after refused load; identical-bytes assertion in `test_unreadable_local_store_raises_an_instance_issue_and_applies_no_overlay` | closed |
| T-11-43 | Information disclosure | Issue text | low | accept | See Accepted Risks AR-03 | closed |
| T-11-44 | Elevation of privilege | Leftover local Store loaded by a new hub | medium | mitigate | Removal before entry creation, fail-closed `local_actions_not_removed` `C/config_flow.py:155`; `test_new_hub_never_loads_local_actions_left_by_an_earlier_hub` | closed |
| T-11-45 | Tampering | Hub flow removing a live hub's local Store | medium | mitigate | Abort `single_instance_allowed` `C/config_flow.py:149`; `test_new_hub_flow_never_removes_the_local_actions_of_an_existing_hub` | closed |
| T-11-46 | Elevation of privilege | Adoption rollback releasing a paused device | medium | mitigate | Tripped hash restored before mirror rebuild, `_restore_tripped` `C/manager.py:2851`; `test_failed_adoption_keeps_a_tripped_breaker_paused` | closed |
| T-11-SC | Tampering | npm/pip/cargo installs | low | accept | See Accepted Risks AR-01 | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-01 | T-11-SC | No package was installed or upgraded in Phase 11: `git diff 762a3db..HEAD -- pyproject.toml uv.lock custom_components/mqtt_actions/manifest.json` is empty; the locked environment is retained | Plan threat models 11-01 to 11-17 (accept disposition) | 2026-10-21 |
| AR-02 | T-11-39 | Persistent issue data holds only kind and StateValue; placeholders are cut and escaped (T-11-23); no action, trace or variable is stored; the file is local like every Repairs issue | Plan 11-14 threat model (accept disposition) | 2026-10-21 |
| AR-03 | T-11-43 | Fixed issue text without placeholders; no record, label, StateValue or error text reaches the issue | Plan 11-15 threat model (accept disposition) | 2026-10-21 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-21 | 47 | 47 | 0 | gsd-secure-phase (L1 short-circuit, orchestrator grep verification; auditor not spawned) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-21
