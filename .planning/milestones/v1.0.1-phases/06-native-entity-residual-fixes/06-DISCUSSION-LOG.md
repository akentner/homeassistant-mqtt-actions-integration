# Phase 6: Native Entity Residual Fixes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-04
**Phase:** 6-Native Entity Residual Fixes
**Areas discussed:** IN-02 flag location, IN-02 flag lifecycle, IN-03 replay strategy, test strategy

---

## IN-02: flag location

| Option | Description | Selected |
|--------|-------------|----------|
| Set in NativeState | New field in STORE_NATIVE next to pending/devices | ✓ |
| Field in mirror record | native bool stored beside the payload | |
| Headroom in size limit | Reserve marker space; conflicts with criterion 1 | |

**User's choice:** Set in NativeState
**Notes:** Legacy marker in stored payloads is still read, only the set is written; `with_native_marker` is removed.

## IN-02: flag lifecycle

| Option | Description | Selected |
|--------|-------------|----------|
| Only at mirror end | Delete, adoption, release remove the id; no marker never resets | ✓ |
| Also reset on owner change | Re-derive from the new owner's marker | |
| Derive on every save | Set = mirrors with native=True | |

**User's choice:** Only at mirror end

## IN-03: replay strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Catch duplicate after the move | Keep migrate, takeover, clear order; remove new mqtt-platform twin | ✓ |
| Wait for discovery queue | No public settle signal in core | |
| Combine both | Double complexity | |

**User's choice:** Catch duplicate after the move; run before the clear and again after it.

## Test strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Hook on the publisher clear | Replay played just before the clear, no production hook | ✓ |
| Fake-broker reconnect | Realistic, timing harder to pin | |
| Both | Fake broker as extra | |

**User's choice:** Hook on the publisher clear; failing-test commit first per fix.

## Claude's Discretion

Names and placement, quiet period length, optional multi-instance test, README and log wording.

## Deferred Ideas

None.
