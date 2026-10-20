# Phase 11: Local Actions on Mirrors - Pattern Map

**Mapped:** 2026-10-17
**Files classified:** 35 candidate new/modified files, including documentation and planning artifacts
**Analogs found:** 32 / 35; five primary anchors, with supporting contract references

Names of new modules/tests below are proposed, not existing APIs. All existing repository analogs named below were checked against `git ls-files`; no installed package or runtime mirror is an editing target. D-01 through D-23 remain binding. This map adds no product decisions.

## File Classification

Paths in the first column are relative to `custom_components/mqtt_actions/` unless prefixed with `tests/`, `docs/`, `.planning/`, or `README`.

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `local_actions.py` (new) | model | transform | `custom_components/mqtt_actions/model.py` | role-match |
| `local_actions_store.py` (new) | service | file-I/O | No repository Store-subclass analog; manager supplies adapter seams | none |
| `runner.py` | service | event-driven | Same file, build/enqueue/run paths | exact |
| `manager.py` | service | event-driven, file-I/O | Same file, approval and local-state APIs | exact |
| `config_flow.py` | controller | request-response | Same file, HubOptionsFlow and Select editor | exact |
| `sync.py` | service | pub-sub | Same file, tombstone and prune paths | exact |
| `retrigger.py` | service | request-response, pub-sub | Same file, effective runnable gate | exact |
| `services.py` | controller | request-response | Same file, adoption handler | exact |
| `services.yaml` | config | request-response | Same file, adopt_device definition | exact |
| `repairs.py` | controller | request-response | Same file, exact-hash approval flow | exact |
| `diagnostics.py` | utility | transform | Same file, explicit output allow-list | exact |
| `trust.py` (if approval view gains count) | model | transform | Same file, ApprovalView builder | exact |
| `const.py` | config | transform | Same file, Store/default/issue families | exact |
| `__init__.py` (only if cleanup wiring needs it) | provider | event-driven | Same file, unloaded-entry removal | exact |
| `translations/en.json` | config | transform | Same file, options and issue keys | exact |
| `translations/de.json` | config | transform | Tracked English counterpart and existing German key tree | exact |
| `README.md` | config (documentation) | transform | Existing execution/approval/removal guidance | role-match |
| `docs/diagnostics.md` | config (documentation) | transform | Existing included/excluded field tables | exact |
| `docs/troubleshooting.md` | config (documentation) | transform | Existing Repairs troubleshooting sections | role-match |
| `tests/test_local_action_plans.py` (new) | test | transform | `tests/test_model.py`, pure model style | role-match |
| `tests/test_local_invariants.py` (new) | test | transform, pub-sub | `tests/test_diagnostics.py` sentinel assertions; fake gateway | role-match |
| `tests/test_local_parallel.py` (new) | test | event-driven | `tests/test_core_contracts.py`; held-service runner tests | role-match |
| `tests/test_local_actions_store.py` (new) | test | file-I/O | `tests/test_core_contracts.py` immediate persistence pins | role-match |
| `tests/test_local_actions_manager.py` (new) | test | event-driven | `tests/test_trust.py`, `tests/test_runner_modes.py` | role-match |
| `tests/test_local_actions_lifecycle.py` (new) | test | event-driven, file-I/O | `tests/test_hub_removal.py`, existing adoption paths | role-match |
| `tests/test_local_actions_flow.py` (new) | test | request-response | `tests/test_config_flow_select.py` selector/confirmation assertions | role-match |
| `tests/test_local_multi_instance.py` (new) | test | pub-sub | `tests/fake_broker.py` real-manager instances | role-match |
| `tests/fake_broker.py` | test | pub-sub | Same file, gateway history and injected Store key | exact |
| `tests/conftest.py` (only shared fixture additions) | test | event-driven | Same file, hub/device/instance factories | exact |
| `tests/test_core_contracts.py` (optional shared pins) | test | event-driven | Same file, installed-Core behavior with loud failure hints | exact |
| `tests/test_diagnostics.py` | test | transform | Same file, JSON sentinel and exact-key assertions | exact |
| `tests/test_translations.py` | test | transform | Same file, key/placeholder parity and issue text-source rules | exact |
| `tests/test_docs.py` | test | transform | Same file, documented keys/issues and links | exact |
| `.planning/phases/11-local-actions-on-mirrors/11-THREAT-MODEL.md` (proposed) | config | transform | Phase 11 RESEARCH security requirements; no source analog assigned | none |
| `.planning/phases/11-local-actions-on-mirrors/11-release-notes.md` (proposed draft) | config (documentation) | transform | No new release artifact path mandated; use D-09 wording | none |

Existing `model.py`, `state.py`, `actions.py`, `document.py`, `native_migration.py`, entity platforms and native-migration regressions are reference/guard surfaces, not automatic edit targets. A new trace-reducer module is unnecessary unless the planner explicitly splits it out of `runner.py`.

## Pattern Assignments

### Pure overlays: `local_actions.py`

**Primary analog:** `custom_components/mqtt_actions/model.py:3-6,37-40,53-90,136-153`. Copy the HA-free imports and typed frozen/slotted records, not `DeviceSpec` as the overlay container:

```python
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

@dataclass(frozen=True, slots=True)
class TriggerSpec:
    value: str
    key: str
    label: str
    friendly_name: str
    actions: list[dict[str, Any]]
```

**Identity:** `model.py:53-60` derives `hashlib.sha256(value.lower().encode()).hexdigest()[:12]`; `state.py:42-45` uses `accepted.get(payload.strip().lower())`. Preserve this normalization, never casefold. Store `(device_id, kind, canonical StateValue)`, original display value and last known friendly name. A hashed trigger key alone is insufficient across kinds. Owner identity, labels, revision and option position are not identity (D-05,D-10-D-12).

**Validation/error pattern:** `model.py:119-153` checks each row's shape and keeps valid options independently. Add a strict overlay parser and pure payload migration; retain valid unmatched records as inactive. Frozen records do not freeze nested action lists: deep-copy at input/output and assembly boundaries. Existing `_actions()` returns an alias and is not safe to copy for overlay ownership.

**Proposed responsibilities, not fixed signatures:** record parsing, active/orphan matching, effective policy, per-trigger owner/local plans and count summaries. Distinguish absent record, additive-empty and replacement-empty. Never mutate the original owner spec or its lists.

### Separate persistence: `local_actions_store.py`, `const.py`, test Store keys

**Closest supporting seams:** `manager.py:465-494` injects `store_key`; `manager.py:598-600` immediately saves; `manager.py:408-426` removes the Store and issues. No tracked integration module subclasses Store.

```python
# manager.py:491-494,598-600 — existing code, main Store only
self._approvals: dict[str, str] = {}
self._publisher: DiscoveryPublisher | None = None
self._store: Store[dict[str, Any]] = Store(hass, STORE_VERSION, store_key)

async def async_save_now(self) -> None:
    """Write the persisted state to the Store at once, without the delay of a scheduled save."""
    await self._store.async_save(self._data_to_save())
```

Use the research-backed **new** adapter contract, not an assumed constructor migration callback:

```python
from typing import Any
from homeassistant.helpers.storage import Store

class LocalActionsStore(Store[dict[str, Any]]):
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int,
        old_data: dict[str, Any],
    ) -> dict[str, Any]:
        return migrate_local_actions(old_major_version, old_minor_version, old_data)
```

`migrate_local_actions` is proposed and pure. Give this Store its own key, version and private atomic storage; retain raw serializable actions, reject unsupported newer versions without overwriting, test malformed rows independently. Do not add a local-actions key to the main serializer at `manager.py:1070-1118`. D-07 requires an independent file that v1.0.1 main-Store saves cannot erase.

`tests/fake_broker.py:266-279` injects `store_key = f"{STORE_KEY}.{name}"`; derive/inject equally isolated local keys for bare managers, real setup, restart and unloaded cleanup. Never let two test instances share the production local key.

### Assembly/outcomes: `runner.py`, `tests/test_local_parallel.py`

**Primary analog:** `runner.py:5-23,48-135,155-233,235-299`. Preserve one integration-owned Script per device, the choose dispatcher, per-trigger validation, queue/restart mapping and build-before-unload lifecycle:

```python
# runner.py:126-135
return Script(
    self._hass,
    validated,
    spec.name,
    DOMAIN,
    script_mode="queued" if spec.run_mode == RUN_MODE_SERIAL else "restart",
    max_runs=SERIAL_QUEUE_LIMIT,
    max_exceeded="WARNING",
    logger=LOGGER,
)
```

Keep the owned/overlay-free raw dispatcher byte-identical (`runner.py:105-118`). For customized mirrors, independently validate eligible owner and trusted local branches; apply static refusal to owner only. After any final HA validation, apply `guard_actions()` to the final owner subtree only. A second validation after wrapping must not erase GuardedTemplate identity. A failed branch setup must not suppress the other valid branch. Native parallel belongs inside this one Script; do not patch user steps or schedule another local Script (D-01,D-02,D-21).

**Shared validator:** `actions.py:21-31`:

```python
try:
    validated = cv.SCRIPT_SCHEMA(raw)
    return await script.async_validate_actions_config(hass, validated)
except (probatio.Invalid, HomeAssistantError) as err:
    raise ActionsInvalid(str(err)) from err
```

Persist raw input, never validated Templates. `trust.py:95-112` copies the guarded tree; `DeniedServiceCallError` deliberately derives from plain Exception (`trust.py:64-76`) so owner denial survives `continue_on_error`. Do not apply that restriction to local actions.

**Outcome protection to retain:** `runner.py:174-189` captures Script/generation and creates a config-entry background task; `runner.py:215-233` rejects obsolete Script identity and checks generation before clearing. Existing `result is not None` alone is insufficient for parallel branches. Add a fresh task-local trace per run, record branch paths in the execution plan, reduce after all branches settle, and discard trace content immediately. Research pins `trace_get(clear: bool = True)`; there is no tracked production reducer to copy.

Permanent loud target-Core tests must cover both failures, owner stop masking local error, error-stop, continued/nested errors, service/stop response variables and collisions, condition abort, cancellation, queued drops, rebuild and supersession. A local issue clears only on proven success of its affected local trigger with valid Script/generation, or removal of that customization. Owner success, other-trigger success, mute and orphan runs supply no local success (D-18-D-20). Continued-error classification remains an explicit research question, not an assumed success.

### Manager APIs/policy/lifecycle: `manager.py`, `sync.py`, `__init__.py`

**Primary analog:** `manager.py:1171-1197` rechecks target and hash under the manager lock:

```python
# manager.py:1179-1185 — excerpt of the approval precondition
async with self._lock:
    mirror = self.mirrors.get(device_id)
    info = None if mirror is None else mirror.mirror
    if (
        not self._running
        or mirror is None
        or info is None
```

New public list/read/save/remove/count APIs are implementation discretion. Recheck identity/current kind/allowed orphan target under the lock; validate raw actions in the manager; immediately save a copied candidate before replacing active state and rebuilding. On save failure retain the old customization. Apply saved changes without restart or retroactive execution. Local edit releases the device breaker (D-13,D-22).

Load local overlays before `_async_restore_mirrors()` (`manager.py:770-805,1645-1657`). Exclude overlays from startup intersections at `manager.py:784-796`. Preserve NativeMigration startup sequencing; it remains a collaborator initialized at `manager.py:518`.

`approval_state()` (`manager.py:1440-1457`) stays owner-only. `_async_refresh_mirror_script()` (`1530-1546`) currently unloads all execution for ineligible owners: replace this device-wide gate with effective-plan assembly while retaining owner eligibility. Research selects local startup **off**, **serial**, breaker **5/10 seconds**, queue **10**, from `const.py:39-48`; use one effective policy consistently in tracker, breaker, Script and displayed limits while owner hash is ineligible. Keep owner content immutable, including execution metadata. Audit breaker reporting at `manager.py:2174-2182,2210-2224`, which currently reads spec limits.

| Lifecycle seam | Existing source | Required adaptation |
|---|---|---|
| Owner update/re-pin | `manager.py:1704-1725` | Recompute matching/policy; retain records and unrelated local failure. Refresh last labels. |
| Transient prune | `sync.py:280-309` | Preserve overlays, even when mirror disappears. |
| Tombstone | `sync.py:487-499`; `manager.py:1548-1581` | Explicit deletion cause. Remove/log/durably save records even after earlier prune; address BOTH sync membership gate and manager early return. Owned ids remain protected. |
| Adoption | `manager.py:1211-1285` | Keep refusal gates; discard only on successful adoption, before owned execution/publish. Test both Stores and subentry rollback failures. |
| Hub removal, unloaded too | `__init__.py:82-94`; `manager.py:408-459` | Both modes delete local Store/issues. Prevent late callbacks recreating it; keep existing shared-topic ownership behavior. |

`_async_drop_mirror()` (`manager.py:1287-1310`) is also used for adoption; never attach unconditional overlay deletion to generic mirror unloading. Orphan-only devices must remain available for local edit/delete and counts. There is no startup garbage collection of overlays (D-05,D-08,D-12).

### Test/retrigger/adoption response: `retrigger.py`, `services.py`, `services.yaml`

`manager.py:2127-2155,2239-2288` passes canonical `state`, `device_id`, `trigger_key`, and `test`; keep that shared path. Native/legacy tests currently gate mode but do not check tripped breaker, whereas `retrigger.py:422-431` does. Pin the D-03/MIR-09 behavior before changing this seam. Effective runnability must work for pending/blocked/owner-empty mirrors with local actions, and replacement-empty must remain muted. Preserve acknowledgement status/reason vocabulary (`retrigger.py:434-452`).

`services.py:299-313` calls `manager.async_adopt()` and returns uuid/adopted/previous_owner. Add local discard reporting to the admin response; keep the original owner-only adoption payload:

```python
# manager.py:1233-1239
device_id = mirror.device_id
spec = mirror.spec
subentry = ConfigSubentry(
    data=MappingProxyType(subentry_payload(build_content(spec), device_id)),
    subentry_type=spec.kind,
    title=spec.name,
    unique_id=device_id,
```

The return type/response field name is discretionary. Never merge local actions into that payload or allow local replacement to satisfy approval.

### Hub UI: `config_flow.py`, `tests/test_local_actions_flow.py`

**Primary analog:** `config_flow.py:141-188` existing HubOptionsFlow; `392-672` Select menu/picker/edit/confirm. Imports use `probatio`, HA `selector`, `OptionsFlow` and relative integration imports (`3-23`). Retain settings in a submenu; use no new config-subentry type and store no overlay content in entry options.

```python
# config_flow.py:540-551 — chooser ingredients
probatio.Required(CONF_OPTION): selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=option[CONF_STATE_VALUE], label=option[CONF_FRIENDLY_NAME])
            for option in self._draft[CONF_OPTIONS]
        ],
        mode=selector.SelectSelectorMode.LIST,
    )
)
```

Use stable backend identities; show friendly name **and StateValue**, direct additional/replacement/muted marker, retained orphan label and kind mismatch as inactive. Copy ActionSelector and suggested-value handling (`config_flow.py:513-524,588-605`), plus `async_show_menu` confirmation (`616-641`). New records default additive. Empty replacement gets its own mute confirmation; Remove local customization gets a distinct confirmation and deletes the record. Save each trigger immediately through manager, then return to picker; cancel discards only the current unsaved draft. Do not copy Select's whole-device Save-the-device semantics.

Copy base-error handling (`config_flow.py:208-213`), since ActionSelector field errors may not render:

```python
try:
    await async_validate_actions(self.hass, raw_actions)
except ActionsInvalid as err:
    return {"base": "invalid_actions"}, {"field": label, "error": str(err)[:MAX_FLOW_ERROR_LENGTH]}
```

Manager validation remains authoritative. Check loaded state/runtime manager and stale target on submit. Escape broker labels using `escape_markdown` as existing flows do. Count distinct devices with saved overlays, including orphan-only devices, in the hub-removal settings notice; generic HA deletion has no custom confirmation hook. Early section + ActionSelector bench rendering remains an execution gate after invariant tests, with actual Core/frontend versions and screenshot; backend serialization tests cannot satisfy it (D-06,D-08,D-11-D-17,D-22).

### Repairs, approval count, diagnostics, bilingual documentation

**Local issue analog:** `runner.py:235-259` creates one issue per device using bounded error text, `IssueSeverity.ERROR`, translation key and device/trigger/time/error placeholders. Add an independent local issue prefix to `const.py` cleanup families and local reporting/recovery methods. Do not route local success through owner `clear_issue()` or owner refresh; preserve affected-trigger identity and dismissal behavior.

**Approval:** `manager.py:1479-1527` owns pending/blocked notices; `repairs.py:47-93` reads a consistent owner view and binds the exact displayed hash. Add replacement count and explicit owner-only approval explanation to the text/view as needed; the YAML view remains owner actions only. Replacing all triggers must retain pending approval and adoption refusal.

**Diagnostics:** `diagnostics.py:76-109` explicitly builds rows then calls `async_redact_data`. Add count-only manager summaries, including per-device, orphan and orphan-only device totals; never raw overlay records, labels, StateValues, Templates, errors or traces. Keep existing shared content hash field. Document added keys in `docs/diagnostics.md` and update exact-key tests.

**Translations:** English `options.step.init` (`translations/en.json:240-259`) and `issues.action_failed` (`294-298`) provide existing key layouts; mirror every new key/placeholder in German. A nonfixable local error uses issue title/description; fixable approval keeps its sole explanation in `fix_flow.step.confirm`, as enforced by `tests/test_translations.py`. Add local Repairs guidance to troubleshooting because `tests/test_docs.py:test_troubleshooting_covers_every_issue_key` checks all issue keys.

README/release draft must explain add/replace/mute, parallel failure/stop/shared response-variable behavior, orphan/edit/remove/reattach, kind identity, tombstone/adoption/removal, trusted local execution and canonical `{{ state }}` versus live entity lookup. Prominently warn: v1.0.1 ignores replacement/mute, so approved owner actions may run again; separate data can return on upgrade. Do not claim a real downgrade round trip; MIR-F4 remains deferred. Release publication/version bump and final-build re-verification stay Phase 12.

## Shared Patterns

### Immutable owner input and content-free transport

`document.py:100-152,171-190` is the invariant boundary. Hash input includes owner trigger actions and owner execution metadata, never overlays:

```python
# document.py:137-140
pairs = sorted(
    ([trigger.value.lower(), trigger.actions] for trigger in spec.triggers.values()),
    key=lambda pair: pair[0],
)
```

All exports/adoption/shared publications continue consuming original owner spec. Use deep copies for runtime plans. Do not add broker words or local-content acknowledgement fields. Existing HA/MQTT authentication remains unchanged; backend target checks and owner exact-hash guards remain necessary even with a thin UI.

### Meaningful test scaffolding and mandatory order

**Primary test anchor:** `tests/test_core_contracts.py:1-8,108-135` runs against actual installed Core, never skips/xfails coupled contracts and gives explicit failure hints. `tests/test_runner_modes.py:72-98` uses service callbacks and asyncio Events to prove ordering/cancellation. Copy that observable pattern; put any shared helpers in `tests/helpers.py` or a dedicated helper module, never import private helpers from another `test_*` module.

**Leak oracle:** `tests/fake_broker.py:100-102,141-145` records every publish:

```python
async def async_publish(self, topic: str, payload: str, *, retain: bool, qos: int = 1) -> None:
    """Record the publish and hand it to the broker."""
    self.published.append((topic, payload, retain))
    self.qos.append(qos)
    self.broker.publish(topic, payload, retain=retain)
```

Assert all integration-owned publishes, including transient ones, contain no local sentinels; retained-state inspection alone is insufficient. A trusted local action intentionally publishing its chosen data is not configuration serialization. `tests/test_diagnostics.py:151-169` supplies JSON sentinel testing; `tests/test_config_flow_select.py:169-183` proves serialized selectors; `tests/test_translations.py:342-351` proves en/de parity. Store tests assert `hass_storage` before advancing time and inject save failures.

Order required by D-21: (1) red hash equality, adoption-byte, 24-case `4 approval × 3 customization × 2 owner-trigger-presence` matrix and every-publish leakage tests, plus Core/guard/dispatcher pins; (2) pure model, Store parser and runner/trace assembly; (3) manager/storage/lifecycle; (4) thin UI, Repairs/diagnostics/text after early frontend smoke; (5) D-23 milestone-wide cross-file review and product fixes. Keep defensive impossible matrix combinations pure; do not fabricate inconsistent mirror documents in integration tests. Add mute/additive-empty, malformed/invalid branches, orphans, kind mismatch, restart/prune/adoption rollback and safe-policy cases separately.

Add the D-23 trust-level-mixing threat explicitly to the phase threat artifact. Preserve native migration/startup/shared-topic invariants and all current core-contract, kept-peer, export, registry and migration regressions. Run targeted nodes, then applicable unit/multi-instance/broker tiers and Ruff; final phase checks include hassfest/HACS. This documentation mapping does not claim tests or bench checks ran.

## No Analog Found

| File/behavior | Role | Data Flow | Reason / fallback |
|---|---|---|---|
| `local_actions_store.py` migration subclass | service | file-I/O | Existing manager instantiates plain Store only; use RESEARCH Store hook and pure upgrader. |
| New per-branch trace reducer inside `runner.py` | service | event-driven | Existing runner observes one outer result. Use research contract and permanent Core tests; no installed source path is a repository analog. |
| Proposed `11-THREAT-MODEL.md` | config | transform | Security mapping comes from D-23 and RESEARCH; no source-code pattern applies. |
| Proposed `11-release-notes.md` | config | transform | Draft artifact path is discretionary; required warning is D-09. No publication authorized by this phase map. |

The reducer gap is a behavior gap within an otherwise exactly matched existing file, so it adds no file to the 35-file count.

## Metadata

**Analog search scope:** tracked `custom_components/mqtt_actions/`, `tests/`, README/docs; phase context/research and canonical project/prior-phase decisions. No project `.codex/skills/` or `.agents/skills/` entries were present. Read repository AGENTS and Home Assistant integration knowledge skill, including Repairs/diagnostics guidance.

**Files scanned:** tracked inventory enumerated; 23 source/test files received content or signature inspection, with additional translation/docs inspection. Five primary anchors: model, runner, manager, config flow, Core-contract tests. Supporting references are focused seams, not competing analog searches.

**Pattern extraction date:** 2026-10-17. Line references describe the pre-execution checkout and should be resolved by symbol after edits. Actual frontend rendering, production trace-reducer completeness and cross-Store adoption failure ordering remain explicit implementation validation work.
