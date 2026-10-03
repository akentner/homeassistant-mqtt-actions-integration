# Phase 3: Trust, Central Config and Ownership - Context

**Gathered:** 2026-10-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Devices created on one instance are published as one retained, versioned config document per device. Other instances on the same broker mirror them read-only. A mirror's actions run only after the user approves them on that instance (Repairs, bound to the action hash). Only the owner edits or deletes a device; followers pin the owner. Deleting a device needs an explicit confirmation and removes it everywhere. Re-trigger service, roster, resync, import/export, ownership transfer/adopt and diagnostics belong to Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Trust gate and approval (TRU-01..04)
- **D-01:** There is no hub-wide trust policy. Remote actions are denied until the user approves a device on that instance. No `ask`/`auto` modes in v1 (keeps "auto-accepting remote config" out of scope).
- **D-02:** The approval is a Repairs flow showing device name, owner name and the full action sequence as YAML. The approval is bound to the canonical action hash. If the owner changes the actions, the old approval lapses, the mirror's actions pause and a new Repairs issue shows the new sequence. Owned devices never need approval.
- **D-03:** The service denylist is a fixed constant in `const.py` and applies only to actions received from the broker (mirrors). Owned actions stay unrestricted. The user cannot change the list.
- **D-04:** The denylist check walks the action tree recursively (choose, repeat, sequence, parallel, if, ...). Templated service names are allowed but flagged in the approval view.
- **D-05:** Because templates stay allowed, the denylist is also enforced at execution time on the resolved service name of mirror scripts. A hit aborts the run and is surfaced (log + Repairs). If the researcher finds no feasible hook, fallback: reject templated service names in mirrors.
- **D-06:** Every document from the broker is schema-validated (`cv.SCRIPT_SCHEMA` / `async_validate_actions_config`) before it is stored or offered for approval; invalid documents are dropped and logged.
- **D-07:** Docs (TRU-04) include a broker ACL example binding each instance to its own topics.

### Mirror storage and removal (SYN-02, SYN-05)
- **D-08:** Mirrors live in the HA `Store` (cached config, approval state, `last_acted`), not as subentries. Subentries stay exclusively owned devices. Mirrors are surfaced through their entities and Repairs, not an editable UI.
- **D-09:** A live tombstone (empty retained config payload) removes the mirror at once, including leftover entity/device registry entries.
- **D-10:** Deletions missed while offline are detected by a grace window after subscribe: a mirror whose config was not seen again within the window is removed, but only if its owner was seen online (owner availability topic). Owner offline or unknown: the mirror stays. A missing message alone never deletes a mirror.
- **D-11:** Removing the hub lets the user choose: keep devices (they become orphaned, config/discovery/state stay retained) or delete all owned devices everywhere. Local mirrors and Store are always removed. Replaces D-15 of Phase 1. Without an explicit choice the default is keep. — **Reversibility:** costly — changes what persists on the broker after uninstall.

### Central config document (SYN-01, SYN-04)
- **D-12:** One retained (QoS 1) document per device at `<base>/v1/devices/<device_id>/config`, written only by the owner. It carries `schema_version`, `device_id`, `owner` (instance ID), `owner_name`, `rev`, canonical content hash, name, kind, options/actions as raw ActionSelector output. — **Reversibility:** one-way — the document layout and topic become the cross-instance wire contract.
- **D-13:** Shared by the document: name, kind, options (StateValue, friendly name, actions), `run_mode`, `run_on_startup`, breaker limits. Local per instance: breaker tripped state, `last_acted`, approval. A device behaves the same everywhere.
- **D-14:** A follower rejects a document with a higher `schema_version` than it knows: nothing is applied, the existing mirror stays at its last known state, a Repairs issue asks to update the integration. Older versions are read through migration.
- **D-15:** Followers apply only a higher `rev` or a different hash; an identical hash is a no-op. The owner republishes all owned documents on every MQTT reconnect. If a retained document for an owned device differs from local truth (foreign write, wiped broker), the owner republishes and raises a Repairs issue when content differed.

### Ownership, delete and discovery healing (SYN-03, SYN-06, DSC-03)
- **D-16:** Delete confirmation is a step in the subentry flow stating that the device is removed on all connected instances, listing the instances that mirror it as far as known. Order as in D-16 of Phase 1: discovery first, unsubscribe, then config tombstone and state topic. No typed-name confirmation.
- **D-17:** Owner conflicts: first owner wins. A follower pins the owner on first sight and ignores documents from other owners for that `device_id`, with a Repairs issue naming both claims. An owner that sees its own `device_id` claimed by another republishes and raises Repairs. No takeover in v1.
- **D-18:** If a follower deletes the mirrored entity (core MQTT clears the retained discovery topic), the owner watches its discovery topics and republishes, throttled per device (start value one republish per 60 s). Repeated removals raise a Repairs hint.
- **D-19:** Discovery keeps the owner's availability topic. Owner offline means mirror entities are `unavailable`; followers still run actions for external state changes. No change to the Phase 1 discovery contract.

### Claude's Discretion
- Exact grace window length, throttle value, canonical-JSON/hash algorithm, Store layout and key names, step ids and Repairs wording, translation keys, YAML rendering in the approval view.
- How the delete step learns which instances mirror a device in Phase 3 (best effort from instance availability topics seen; a full roster is Phase 4).
- How the hub-removal choice (D-11) is offered, since HA has no hook in entry removal (likely a reconfigure/options step before removal).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/PROJECT.md` - core value, security constraint, key decisions
- `.planning/REQUIREMENTS.md` - SYN-01..06, TRU-01..04, STA-03, DSC-03
- `.planning/ROADMAP.md` - Phase 3 goal and success criteria
- `.planning/phases/01-walking-skeleton-installable-switch/01-CONTEXT.md` - topics, payloads, baseline, D-15/D-16 hub and delete behavior
- `.planning/phases/02-select-devices-and-reliable-execution/02-CONTEXT.md` - Select wire mapping, run mode, breaker, trigger keys

### Research
- `.planning/research/ARCHITECTURE.md` - config topic, SyncManager, owner pinning, trust gate, tombstone problem (grace window vs manifest)
- `.planning/research/PITFALLS.md` - retained-message semantics, echo and ping-pong risks
- `.planning/research/SUMMARY.md` - roadmap-level conclusions
- `.planning/research/STACK.md` - MQTT API shapes, `Script`, `Store`, validation

### Project instructions
- `.claude/CLAUDE.md` - stack rules and "Do not use" list (no execution of received actions without opt-in and validation; no `device_id` targets in defaults)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `custom_components/mqtt_actions/topics.py`: topic builders; add the config topic and owner availability parsing.
- `custom_components/mqtt_actions/model.py` (`DeviceSpec`, `TriggerSpec`, `trigger_key`): build specs from a config document as well as from subentry data.
- `custom_components/mqtt_actions/manager.py`: device lifecycle, baseline and store handling; hosts the new sync manager or delegates to it.
- `custom_components/mqtt_actions/runner.py` (`ActionRunner`): one Script per device; needs a guard for mirror scripts (D-05) and a pause on missing approval.
- `custom_components/mqtt_actions/discovery.py` (`DiscoveryPublisher`): owner-only publishing, now also watched for removal (D-18).
- `custom_components/mqtt_actions/mqtt_gateway.py`: the only MQTT seam; basis for the in-memory fake broker.
- `custom_components/mqtt_actions/config_flow.py`: device_id warning and action validation; delete step goes here.

### Established Patterns
- Subentry per owned device, UUID `device_id` as `unique_id` and topic segment; state topic equals command topic.
- One Repairs issue per device and kind; en/de translations with a parity test.
- TDD is on: tests come with each task; multi-instance scenarios via a fake broker tier.

### Integration Points
- Hub unload/remove path (D-11) and delete path (D-16).
- `async_get_supported_subentry_types`: unchanged; mirrors are not subentries.
- Repairs platform (new `repairs.py`) for approval and conflict issues.

</code_context>

<specifics>
## Specific Ideas

The user chose the recommended option in every area except two: the hub-removal behavior (D-11) is an explicit user choice in a dialog, and templated service names are allowed with a warning (D-04) and backed by an execution-time denylist (D-05).

</specifics>

<deferred>
## Deferred Ideas

- Hub-wide `ask`/`auto` trust policy.
- User-extendable denylist.
- Diff view between old and new actions on re-approval.
- Owner manifest topic for deterministic pruning (revisit if grace-window pruning proves fragile).
- Typed-name delete confirmation.
- Ownership transfer and adopting orphans (Phase 4, SYN-07).
- Full instance roster (Phase 4, OPS-03).

</deferred>

---

*Phase: 3-Trust, Central Config and Ownership*
*Context gathered: 2026-10-01*
