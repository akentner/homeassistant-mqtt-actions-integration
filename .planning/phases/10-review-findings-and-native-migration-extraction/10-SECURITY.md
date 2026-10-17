---
phase: "10"
slug: "review-findings-and-native-migration-extraction"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (the blocking gate)
threats_open: 0
asvs_level: 1
created: "2026-10-17"
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Register taken from the `<threat_model>` blocks of 10-01 to 10-10 (authored at plan time); no SUMMARY carries a
> `## Threat Flags` entry. L1 verification by grep against code, tests and phase evidence; behavior backed by
> 10-VALIDATION.md (full suite 1773 passed, 2 xfailed on `7e7a5ca`) and 10-UAT.md (2/2 passed).

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| catch / takeover pass to the shared core-prefix topic | a removal that makes core publish its clear-on-remove empties a Discovery topic other instances use (CR-01 class) | retained discovery payloads (high impact) |
| installed HA core to private registry / MQTT internals | the integration relies on private core APIs (`_store`, `_data_to_save`, clear-on-remove path) that a core bump can change silently | registry state |
| local entity registry to the Repairs dialog and logs | entity ids of kept duplicates are shown in the issue text | entity ids (low, local only) |
| documentation to users | users act on the documented disable-vs-delete advice | docs |
| branch push to GitHub Actions | CI and Validate run on every branch push | repo contents, `contents: read` token |

---

## Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-10-01 | Elevation of privilege | CI and Validate on every branch push | low | mitigate | `permissions: {}` at workflow level in `.github/workflows/ci.yml:13`, `validate.yml:15`; pinned by `tests/test_repo_structure.py:351` `test_ci_has_one_job_per_tier` | closed |
| T-10-02 | Tampering | `takeover.async_flush_registries` after a core bump | medium | mitigate | Three never-skipped pins in `tests/test_core_contracts.py:108,123,138` (flush writes both registries, private API exists, refused write falls back) | closed |
| T-10-03 | Tampering | moved test helpers | medium | mitigate | `tests/test_repo_structure.py:525` `test_no_test_module_imports_from_another_test_module`; no `from tests.test_` import remains; suite green | closed |
| T-10-04 | Repudiation | start-up ordering test | low | mitigate | `tests/test_startup_order.py` (spies on non-moving seams, proven fail-first per 10-03-SUMMARY) | closed |
| T-10-05 | Tampering | moved catch, gate and takeover order | high | mitigate | `mutation/move-audit.txt` 28 PASS / 0 FAIL at `cbf5383`; `tests/test_startup_order.py` and 09.1/09.2 tests unchanged and green | closed |
| T-10-06 | Repudiation | tests that patch moved members | medium | mitigate | `mutation/post-move.tsv`; the two survivors (`defer_for_run`, `forget`) pinned in `7e7a5ca` (`tests/test_native_start.py`), both fail under their mutant (10-VALIDATION.md) | closed |
| T-10-07 | Denial of service | emptied core MQTT device after a partial failure | low | mitigate | `tests/test_native_replay.py:1421`, `tests/test_takeover.py:961` (emptied device removed before the raise) | closed |
| T-10-08 | Repudiation | failed row hidden by a catch returning 0 | medium | mitigate | `ReplayTwinsError` at `custom_components/mqtt_actions/takeover.py:140` carries the count; `tests/test_takeover.py:961` asserts raise and cause | closed |
| T-10-09 | Tampering | guard listener that silently stops running | low | mitigate | `tests/test_export_guard_receiver.py:419` (spy on second create event and restart sweep) plus `never_nest` test from `7e7a5ca` | closed |
| T-10-10 | Tampering | core change making takeover/catch publish clear-on-remove | high | mitigate | `tests/test_core_contracts.py:198,246` against installed core, never skipped (D-08, module docstring line 4) | closed |
| T-10-11 | Repudiation | docs omitting the re-disable at next start | low | mitigate | `tests/test_docs.py:450,462` | closed |
| T-10-12 | Tampering | warning path that removes or disables a row | high | mitigate | `_refresh_kept_duplicates` (`custom_components/mqtt_actions/native_migration.py:691-738`) only calls `ir.async_delete_issue` / `ir.async_create_issue` with `is_fixable=False`; `takeover.kept_duplicates` is read only; `tests/test_kept_duplicates.py:135` asserts no row is touched | closed |
| T-10-13 | Information disclosure | entity ids in Repairs text and logs | low | mitigate | `escape_markdown` and `KEPT_DUPLICATES_MAX_SHOWN` cap at `native_migration.py:80`; `7e7a5ca` test asserts no entity id in WARNING/DEBUG logs | closed |
| T-10-14 | Repudiation | dismissal hiding a changed list | medium | mitigate | Early return only when `current.active` and placeholders equal (`native_migration.py` refresh); `tests/test_kept_duplicates.py:159` and the restored-inactive test from `7e7a5ca` | closed |
| T-10-15 | Repudiation | warning outliving the hub | low | mitigate | `ISSUE_KEPT_DUPLICATES` deleted in `async_remove_local_state` (`custom_components/mqtt_actions/manager.py:420`); `tests/test_hub_removal.py:236` | closed |
| T-10-16 | Tampering | docs advising deletion of an MQTT duplicate | medium | mitigate | `README.md:110`, `docs/troubleshooting.md:89,118,217` advise disabling and explain why not to delete; pinned by `tests/test_docs.py` kept_duplicates tests | closed |
| T-10-SC | Tampering | npm/pip/cargo installs | low | accept | No package installed or upgraded in any plan of this phase | closed |

*Status: open · closed · open — below high threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above workflow.security_block_on count toward threats_open*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-01 | T-10-SC | No dependency is installed or upgraded in this phase; supply-chain surface unchanged | plan-time threat model (10-01 to 10-10) | 2026-10-17 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-10-17 | 17 | 17 | 0 | gsd-secure-phase (L1 grep, orchestrator) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-10-17
