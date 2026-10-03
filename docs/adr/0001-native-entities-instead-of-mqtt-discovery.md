# ADR 0001: Native switch and select entities instead of MQTT Discovery

Status: Accepted

Date: 2026-10-03

Accepted: 2026-10-03 (Go confirmed by the user at the blocking-human gate of plan 05-01)

## Context

Since v0.1.0 every device of this integration reaches Home Assistant as an MQTT Discovery device: the owner publishes a
retained device-based discovery payload, and core MQTT creates the switch or select and the test buttons. Three
findings led to this record:

- Backlog item 999.2 asked whether entities owned by the config entry could replace Discovery.
- The Phase 3 UAT showed that a user cannot find the devices of another instance on the integration page.
- The Phase 4 decision D-13 (revised) established the reason: a device belongs to exactly one config entry, so a
  Discovery device belongs to the core MQTT entry and can never appear on this integration's page. Phase 4 worked around
  it with a companion device per owned or mirrored device, which carries only the mode select.

The companion devices show the devices on the page, but the entities that matter (the switch or select and the test
buttons) stay on the core MQTT device, and a lot of code exists only to live with Discovery: healing after a remote
delete, ghost registry cleanup, the manual resync of discovery, the test topic and the companion and mirror device split.

Phase 5 decides, with evidence, whether native entities replace Discovery as the default (decision D-01).

## Decision drivers

Criterion (a): all devices and entities, mirrors included, on the integration page. Native entities carry the hub entry
id. Owned devices sit under their subentry, mirrored devices directly under the entry. Entities and devices of every
instance then appear where the user looks for them. Verdict: Go. The way the frontend counts devices and entities on the
integration page is an assumption (A1 of the research) that only the UAT can confirm.

Criterion (b): removal of Discovery complexity. Healing, ghost cleanup, the discovery-disabled and discovery-removed
issues, the test topic with its subscriptions and the companion split disappear for every device on the native path.
They do not disappear from the code in 0.2.x: decision D-10 keeps the legacy path alive while an online peer is not
native-capable, so these parts become conditional and are deleted only in a later release with a schema bump. A fresh
fleet and a fully upgraded fleet never run them. Verdict: Go, with the staged removal as an explicit price.

Criterion (c): non-HA consumers of the Discovery topics. Discovery stays as an optional export (D-04, D-11): off by
default, `enabled_by_default` false on every exported component so a Home Assistant instance listening to the same
prefix creates only a disabled duplicate, a configurable prefix, no test buttons and no healing. Verdict: Go, the cost is
low.

Criterion (d): migration cost and risk. The mechanics were executed against Home Assistant 2026.9.4 and are pinned as
regression tests (see Evidence). Three ordering rules keep user data safe: the migrate payload comes before the platform
move, entities move before their device, and the plain empty discovery payload comes last. Getting any of them wrong
destroys registry data silently, which is why each has a test and a negative control. The remaining cost is the
rewrite of the Discovery-centered tests (about 25 files mention Discovery, about 12 substantially) and of the
documentation that the documentation tests pin. Verdict: Go, gated by a UAT on two real instances.

## Options considered

1. Go with native entities as the default and Discovery as an optional export (recommended). Satisfies all four
   criteria; one-way for the registry ownership; the legacy path stays for the 0.2.x series.
2. No-Go, keep the companion devices. No migration risk and no change of the published v0.1.0 contract, but the
   entities of mirrored devices stay on the core MQTT device, the Discovery machinery stays, and the visible complaint of
   the Phase 3 UAT stays.
3. Go with a schema_version bump to 2 (the literal wording of D-06), so that v0.1.0 followers show the existing
   "update needed" Repairs hint. Not chosen: a bump makes a v0.1.0 follower keep its last mirror and apply no further
   document updates, which breaks the core value on that instance. It also contradicts D-09.

## Decision

Go, pending the human confirmation of the next gate. The decision consists of:

- D-03: native entities are the default; Discovery is an optional mode for external consumers with a documented warning
  about duplicate entities.
- D-05: existing installations migrate automatically and without a manual step; the registry ownership moves from core
  MQTT to this integration. This is one-way.
- D-09: D-06 is realized without a schema bump. `schema_version` stays 1; an additive marker in the document (never
  part of the content hash, parsed strictly, honored only from the pinned owner) and an additive heartbeat capability
  key signal native mode. This deviates from the literal D-06 wording: v0.1.0 instances get no Repairs hint.
- D-10: the owner switches to native mode only when every online peer is native-capable. An online legacy peer blocks
  the switch; offline peers do not.
- D-12: the takeover runs before the platform forward; a live cutover on a running follower reloads the config entry
  automatically.

## Cutover design

The owner performs the registry work in this order for each of its devices: it publishes the migrate payload on the
Discovery topic, waits until core MQTT has unloaded the entities, moves the entity registry entries to this
integration, moves the device, merges the companion into it, and only then publishes the retained clear. Followers do
the same registry steps for their mirrors without broadcasting anything. The marker is published only after the owner's
own takeover has finished, so a restarting follower can tell from the retained document that the device is native.

## Consequences

- A v0.1.0 instance that is online at the cutover blocks it. One that comes online later keeps running its actions
  (the document stays valid for it) but loses the UI entities of migrated devices and gets no hint; only the release
  notes and the README can tell it.
- Rollback to 0.1.0 is not supported. A downgrade makes core MQTT create new entries that cannot take the old entity
  ids, and the migrated entries become orphans (research pitfall 10).
- Recorder history survives, because it is keyed by entity id and the entity id does not change.
- Adoption between a new and an old instance (the discretion item of the context) is resolved as follows: a native
  mirror never reverts to legacy because a later document lacks the marker, an adopted native device stays native, and a
  concurrent adoption by an old and a new instance is a normal ownership conflict that the existing pin rule reports.
- The Discovery export is off by default, exports `enabled_by_default` false and uses a configurable prefix.
- The legacy path is conditional, not deleted, in 0.2.x. Deleting it needs a later release with a schema bump.
- A select no longer stays on a stale state after an option is renamed or removed: core reports an unknown option as
  no state. This replaces the Phase 2 decision and is a visible improvement.

## Evidence

The scenarios of the research spike, run against Home Assistant 2026.9.4 with real core MQTT discovery and kept as
regression tests in `tests/test_takeover.py`:

| Scenario | Test | Observed result |
|----------|------|-----------------|
| Full takeover in the fixed order | `test_full_takeover_sequence_keeps_identity` | Same entity id, registry id, device id, area and user name; the mode select keeps its entity id and registry id; one device with the new identifier; entities and device attached to the entry and its subentry; core published no empty Discovery payload |
| Plain empty payload on a loaded entity | `test_plain_clear_on_a_loaded_entity_deletes_the_registry_entry` | The switch and both buttons lose their registry entries and the key stays in `deleted_entities` |
| Migrate, then empty payload | `test_migrate_then_clear_keeps_the_registry_entry` | Every registry entry stays, unloaded, still platform `mqtt` |
| Platform move of a loaded entity | `test_loaded_entity_refuses_the_platform_move` | `ValueError` "Only entities that haven't been loaded can be migrated" |
| Device moved before its entities | `test_moving_the_device_first_removes_its_entities` | The switch and the buttons are removed, the mode select stays |
| Existing native entry with the same unique id | `test_core_does_not_guard_a_duplicate_unique_id` | Core raises nothing and leaves two entries with the same key, so the takeover module has to guard it |
| User-disabled entity | `test_user_disabled_entity_survives_the_migrate` | The entry survives migrate and migrate plus clear and stays disabled |

## Verified later

Three assumptions are settled only by the UAT of plan 05-09 on the real ha-one and ha-two setup with a Mosquitto
broker:

- A1: the integration page counts devices and entities by config entry and subentry, so native entities and mirror
  devices appear there.
- A4: a late replay of the retained Discovery on a real broker after the takeover is detected and cleaned up.
- A5: a takeover on a live running follower, followed by the scheduled reload, is clean.
