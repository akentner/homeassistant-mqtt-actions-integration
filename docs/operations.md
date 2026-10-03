# Operating MQTT Actions

This page describes what the operations tools of MQTT Actions do, who may use them, what they return and where their
limits are. It is written from the code: every service, field, topic, status word and number below is checked against
the integration by the test suite, so a page that drifts from the code fails the build.

Related pages: the [README](../README.md) is the entry point, [docs/broker-acl.md](broker-acl.md) has the broker
access rules that the topics below need, [docs/diagnostics.md](diagnostics.md) describes the diagnostics file and
[docs/troubleshooting.md](troubleshooting.md) explains every Repairs issue and the common operating problems.

Security limits first, because they apply to everything here:

- **Acknowledgements are advisory.** Any Home Assistant user of the broker group can write the acknowledgement topic of
  any requester and so can forge an answer. An answer only tells the caller who claims to have acted. It never causes
  an action to run, and `executed` means that the actions were started, not that they finished or succeeded.
- **Ownership is cooperative.** The broker cannot bind a device to its owner, so any instance of the group can write any
  config topic. The per-instance approval stays the real control.
- **Adoption and import put content under the administrator's responsibility.** Both create devices that this instance
  owns and that therefore run without an approval here. Read what you adopt or import (see the sections below).

## Services

All services are registered once when the integration loads, so they exist as long as Home Assistant runs. Every
service is **admin only**: only an administrator may call it, because each one republishes, exports or changes what
runs. Every service **may return a response** (`return_response` in a script, or **Developer tools > Actions**). With
no loaded MQTT Actions entry a call fails with a translated error.

| Service | Fields | Returns |
|---------|--------|---------|
| `resync` | none | `resynced: true` |
| `export_devices` | `device_id` (optional, several allowed), `file_name` (optional) | `export` (the export document) and `file` (the relative path, or none) |
| `import_devices` | `data` or `file_name`, exactly one of them | `imported`: one entry per created device with `index`, `uuid` and `name` |
| `retrigger` | `device_id` (required), `state` (optional) | `request_id`, `uuid`, `state` and `instances`, one entry per instance |
| `adopt_device` | `device_id` (required), `force` (optional, default false) | `uuid`, `adopted` and `previous_owner` |

The field `device_id` of a service is the **Home Assistant registry id of the device of MQTT Actions** (since 0.2 the
same device that carries the entities; a device on the legacy path uses its companion device, see
[Modes and devices](#modes-and-devices)); the device selector of the action editor produces it. The responses name a
device by its `uuid`, the random id that the device has on the broker. Only the device of a device of this integration
is accepted: the hub device and devices of other integrations are refused.

The value of `device_id` is the Home Assistant registry id of the device on this instance, so it differs between
instances and must not be used in shared actions. It is only a field of a service call that you start on this instance:

```yaml
action: mqtt_actions.retrigger
data:
  device_id: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
  state: "ON"
```

Inside the actions of a device that other instances mirror, use entity, area or label targets instead.

## Re-trigger and acknowledgements

`retrigger` runs the actions of one device again, on every instance that approved the device, this one included, and
returns who executed them. It is meant for the moment when something went wrong: a lamp was switched by hand, an
instance was down, and the actions should run once more without changing the state.

- **One device per call.** There is no call for all devices and no instance filter.
- **The trigger** is the state this instance acted on last, which for a Select is the current option, or the `state`
  you name. A named state is matched like a state message (trimmed, capitalization ignored) and must belong to the
  device; a Select needs the value of one of its options. A device that this instance has not acted on yet needs the
  `state` in the call.
- **What it never does:** it does not change the entity state, the baseline, the state topic, the revision or the
  circuit breaker count. It runs the actions exactly like a test button press.
- **What it respects:** the gates of each receiving instance. A mirror that is not approved there runs nothing, a
  device in observe or disabled mode runs nothing, a device that the circuit breaker paused runs nothing, and a device
  without runnable actions runs nothing. The request carries a state of the device, never actions.
- **What it returns:** one entry per instance with `instance_id`, `instance_name`, `status` and, for some statuses, a
  `reason`. The caller waits for the instances that the roster shows as online and leaves as soon as all of them
  answered, or after `RETRIGGER_ACK_WINDOW_SECONDS` at the latest.

```yaml
request_id: 0f6c1d3e-8a52-4d0b-9a3e-5b7c2e1f4a90
uuid: 5d1c9a52-3b7e-4c6f-8f10-2a9e7d4b6c31
state: "ON"
instances:
  - instance_id: 7e4b2c91-0a3d-4f58-b6e2-91c4d8a0f357
    instance_name: Living room
    status: executed
  - instance_id: c2f8a6d4-5b19-47e3-8d70-3e6a1b9c4f52
    instance_name: Cellar
    status: no_answer
    reason: offline
```

The statuses of an acknowledgement:

| Status | Meaning |
|--------|---------|
| `executed` | The actions of the trigger were started on that instance. They may still be running or fail later |
| `not_approved` | The device is a mirror there that is not approved yet, or it is blocked by the service denylist |
| `paused` | The circuit breaker of the device is tripped there |
| `observing` | The device or the instance is in observe mode there; the run was only logged |
| `disabled` | The device or the instance is in disabled mode there |
| `error` | The instance could not run it, with a `reason` |
| `no_answer` | Produced by the caller only, never sent on the wire: an instance that should have answered did not within the window, or the roster shows it as offline (`reason` is `offline`) |

The reasons that accompany a status are `unknown_device` (the instance does not know the device), `bad_state` (the
state does not belong to the device there), `no_actions` (the trigger has no actions), `not_runnable` (the actions
cannot run there) and `offline`. A call is **refused before anything is sent**, as a translated error, when the device
is unknown, when the `state` does not belong to the device, when there is nothing to run again because this instance
has not acted on the device yet, or when the same device was re-triggered less than `RETRIGGER_DEVICE_INTERVAL_SECONDS`
ago.

The limits, fixed in the code and not configurable, are in the table [Limits](#limits). A receiver drops a request that
is retained, too large, malformed, older than `RETRIGGER_MAX_AGE_SECONDS` (or that far in the future, which is also the
clock skew tolerance between instances), repeated, or the second one for a device inside the interval. Requests travel
at QoS 1, so a request can arrive twice; the remembered request ids make the second one run nothing.

The topics and fields (not retained, no JSON examples here because the payloads are plain data). The path segment
`v1` is the protocol version of every topic of the integration; a change of it would be a breaking change of the protocol:

| Topic | Written by | Fields |
|-------|------------|--------|
| `<base topic>/v1/devices/<device uuid>/retrigger` | the calling instance | `request_id` (a uuid), `requester` (the instance id of the caller), `state` (the exact state value to run), `sent_at` (the wall clock time of the caller in seconds) |
| `<base topic>/v1/instances/<requester id>/acks` | every answering instance | `request_id`, `device_id` (here the device uuid), `instance_id`, `instance_name`, `status`, `reason` (only with some statuses) |

In an acknowledgement `device_id` is the uuid of the device on the broker, not a registry id. Who may write and read the
topics is in [docs/broker-acl.md](broker-acl.md).

## Roster and heartbeat

Every instance publishes a **heartbeat** on `<base topic>/v1/instances/<instance id>/heartbeat` every
`HEARTBEAT_INTERVAL_SECONDS` and once at the end of every start and republish. It is not retained and is sent at QoS 0.
A peer counts as **offline** once no heartbeat arrived for `HEARTBEAT_OFFLINE_SECONDS`, or as soon as its retained
availability says `offline`, which a clean shutdown sets at once.

| Field | Meaning |
|-------|---------|
| `instance_id` | The instance id, equal to the segment of the topic |
| `name` | The instance name |
| `version` | The integration version |
| `devices` | The number of devices the instance owns |
| `session` | A random id of the current run, new at every start |

The heartbeat makes a crash visible. A crashed instance cannot set its availability to offline, and Home Assistant owns
the MQTT connection, so there is no Last Will; the retained availability can stay `online` for good. After the timeout
the roster turns the instance offline anyway. The heartbeat does not change the availability of the mirrored
entities, which still follows the retained availability.

The **roster** is the diagnostic sensor **Instances online** of the hub device. Its state is the number of instances
that are online, this one included. Its attribute `instances` lists this instance first and then every known peer,
online or not, with `name`, `id`, `version`, `last_seen` and `online`. The attribute is not written to the recorder.
Only instances that sent a heartbeat are listed, so an instance on an older version of the integration does not appear.

The `session` lets an instance tell its own restart from a clone: see [Duplicate instance id](#duplicate-instance-id).

## Resync

Resync publishes everything this instance owns again: the config documents, then the discovery (for a device on the
legacy path, and the export of a native device while the export is on), then the retained `online` availability, then
one heartbeat. This is the order of a start, so a follower never mistakes a document that is
about to arrive for a deleted one. It heals a broker that lost its retained messages and, for a device on the legacy path, restores entities that were
removed. The entities of a native device belong to the integration and need no restore. It **never deletes**
anything.

Use the **Resync** button of the hub device (a configuration entity) or the service `resync`. A second resync inside
`RESYNC_MIN_INTERVAL_SECONDS` is refused with an error, so a held button or a looping automation cannot queue
republishes. It republishes what this instance owns. The documents of the mirrors of other instances come from their
owners; their Resync button republishes those.

## Modes and devices

Every device, owned or mirrored, and the instance as a whole has a **mode**. The mode is local to the instance: it is
never part of a config document, never part of a hash and never shared, and it survives a restart.

| Mode | What happens |
|------|--------------|
| `run` | Normal operation |
| `observe` | The state and the baseline are tracked, but no action runs; each suppressed run is logged |
| `disabled` | The state topic is ignored completely: no entity state, no baseline, no run |

The effective mode of a device is the most restrictive of the instance mode and the device mode: disabled beats observe
beats run. The test topic and the re-trigger obey it as well (a re-trigger of a device in observe mode answers
`observing`). Leaving `disabled` takes the retained state at that moment as the new baseline, so a stale retained value
never runs. The run mode of a device (serial or restart) is a different setting and untouched.

The mode is chosen with a select entity: **Instance mode** on the hub device and **Mode** on the device of each
device. Since 0.2 the companion concept has ended for native devices: the device of MQTT Actions carries the Switch or
Select, the test buttons and the **Mode** select together, under its subentry for an owned device and directly under
the config entry for a mirror (a device without an edit dialog, marked with its owner). The integration page shows the
hub device with the roster, the resync button and the instance mode, and one device for each device, with all of its
entities. The `device_id` field of the services is the registry id of this device.

A device that is still on the legacy path (see [Upgrade notes](#upgrade-notes)) keeps a **companion device**: the
entities of the device itself sit on a device of the core MQTT integration with the same name, and the companion
device carries only the **Mode** select. When the device switches to the native path, both devices become
one and the entities keep their ids. A device is renamed and removed together with the device it belongs to.

## Adoption

Adoption takes over a device whose owner is gone, so that its entities keep working and can be edited again. It is the
only exception to the rule that the first owner of a device keeps it. It is not a hand-off: a device cannot be taken
from an owner that is online, except by force.

Call `adopt_device` with the `device_id` of the mirror on this instance. The preconditions are checked in this order,
before anything changes:

1. The device is a mirror here, else the call fails with the error that there is nothing to adopt.
2. The actions of the mirror are **approved on this instance**, or it has no actions. A mirror that is not approved, or
   that the service denylist blocks, is refused, also with `force`. Unreviewed remote actions never become owned ones.
3. The owner is offline: it announced `offline`, or its last heartbeat is older than `HEARTBEAT_OFFLINE_SECONDS`, or
   nothing is known about it after this instance listened for that long. An owner that is shown as online without
   a heartbeat, for example one on an older version, is not treated as offline. Otherwise the call fails and names
   `force: true`.

`force` overrides only the third check. Use it only when you know the other instance is gone, because two owners of one
device overwrite each other's document.

```yaml
action: mqtt_actions.adopt_device
data:
  device_id: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
  force: false
```

The device id above differs between instances and must not be used in shared actions; it only names the device for this
call.

What adoption does: this instance becomes the owner under the **same uuid**, so the entities, the state topic, the last
known state and the mode stay. It publishes a new config document with itself as the owner and with the **transfer
marker** `transferred_from`, which lists the ids of the previous owners, newest last, at most
`MAX_TRANSFER_HISTORY` entries. The first revision is the old one plus one. The mirror and its approval are dropped here
and the device is added as an owned device, which does not need an approval. Nothing is removed from the broker.

The marker is additive: it is an optional key of the document, there is no schema change, and a document without it
means the device was never adopted. Followers honor it only when their pinned owner is offline according to their
roster; for any other claim the rule of the first owner stays, with the usual owner conflict issue. An instance on an
older version of the integration ignores the marker, keeps following the old owner and raises that conflict, so update
it.

**The old owner may come back.** When it starts, it can publish its document before it has heard the adopter's retained
one. An old owner that sees a valid document of another instance with a marker that names itself stops publishing that
device, raises the Repairs issue **A device you own was adopted by another instance** and stays quiet about it. The
issue has a fix that lets it follow the adopter: it forgets the device locally, changes nothing on the broker and then
shows the device as a mirror of the adopter, which needs an approval there. Know the limits:

- Until the fix is confirmed, the old owner still owns the device locally and runs its own actions for it.
- The recognition is held in memory only. After a restart of the old owner, it can briefly overwrite the adopter's
  document again before it hears the adopter's retained document, and the issue returns. The Resync button of the
  adopter restores the discovery when the adopter's availability topic was replaced meanwhile.
- A device that was adopted away is only forgotten locally when you delete it on the old owner; nothing of the adopter
  is cleared. A hub removal with the option to delete all devices, on a former owner after a restart, could still clear
  the topics of such a device, because the recognition does not survive the restart.
- The baseline of a device that was released is not kept across a restart of the instance.
- A follower whose roster still shows the old owner as online when the adopter's document arrives raises an owner
  conflict and moves its pin with the next document of the adopter. Resync on the adopter closes that gap.

## Duplicate instance id

Two instances share an instance id when a backup was restored on a second machine or a virtual machine was cloned.
Both then write the same availability and heartbeat topics and the same documents.

Detection uses the `session` of the heartbeat: an instance that hears a heartbeat with its own `instance_id` but another
`session` records it. After `DUPLICATE_ID_CONFIRMATIONS` such heartbeats inside `HEARTBEAT_OFFLINE_SECONDS` the
Repairs issue **Another instance uses the same instance ID** appears on both instances; it disappears when none was
heard for that long. Nothing happens automatically.

The fix flow of the issue gives this instance a new random instance id after one confirmation:

- It forgets its own devices **locally**. It never publishes a tombstone, never clears a discovery, a config document or
  a state topic and never changes the availability of the old id: the original keeps its devices, its topics and its
  ownership.
- It then reloads with the new id and shows the same devices as read-only mirrors of the original, which need an approval
  on this instance.
- Devices that this instance should own independently have to be created again, or imported from an export of the
  original.
- **The new instance id is not in a per-instance ACL.** Add it to the broker ACL, or this instance can only read; see
  [docs/broker-acl.md](broker-acl.md).

Confirm the fix only on the instance that is the copy, the restored backup or the clone. The other one keeps its id.

## Export and import

`export_devices` returns the devices this instance owns as a JSON document, and with `file_name` it also writes the
document to a file. Without `device_id` it exports all of them; a selection must be owned devices (a mirror is refused).
The document has the keys `format` (always `mqtt_actions_export`), `export_version` (currently `1`) and `devices`, a list
with the shared content of each device: name, kind, options, actions, run mode, startup flag and breaker limits. It
holds **no device ids, owner, revision or hash**, so an import never collides with an existing device.

The file is written only to the private directory `mqtt_actions` below the Home Assistant configuration directory, never
to `www`, which Home Assistant serves without authentication. The directory is private to the Home Assistant user and
so is the file. The name is a bare name: letters, digits, dot, dash and underscore only, starting with a letter or digit
and ending in `.json`, at most 64 characters before the extension. A link, a path or any other name is refused.

`import_devices` creates one new owned device per item of an export. Give the export as `data` (for example the
response of the export) or the name of a file in the private directory, but not both and not neither. Every item gets a
**new uuid**, this instance as the owner and revision 1. After the import, the instance publishes each device, and every
connected instance receives it as a mirror that needs an approval there.

```yaml
action: mqtt_actions.import_devices
data:
  file_name: backup.json
```

Every item is checked as strictly as a document received from the broker, then against the action schema and the
fixed denylist of services, before the first device is created:

- **All or nothing.** When one item is refused, no device is created. The error names the position of the item (the
  number in the export, a dash for the export as a whole) and a reason: `bad_format` (not an export of this
  integration), `too_new` (an export of a newer version), `too_many`, `too_large`, `not_json`, `invalid_device`,
  `invalid_actions` and `denied_service`. A file that cannot be named or read has a message of its own. The error never
  repeats content of the import. Creating the devices after the check is not transactional: a failure halfway, which
  is rare, would leave the devices created so far.
- **Denied services.** An item whose actions call a service of the denylist (see the
  [README](../README.md#trust-model-and-approval)) is refused. A legitimate device that really has to call such a
  service must be created in the UI of the owner.
- **Deep validation** is the check of the UI flows. It does not check that a service exists: an unknown service name is
  accepted, and a device action that does not resolve on this instance is refused.
- **Responsibility.** The denylist is best effort and the imported devices are owned, so they run here without an
  approval. An administrator who imports a file they did not read takes the content on their own responsibility, as
  with any action written by hand. Read an export before importing it, and do not put secrets into actions: an export is
  a plain text file.

## Limits

Fixed in the code, not configurable. The page and the test suite use the constant names of `const.py`.

| Constant | Value | Where it applies |
|----------|-------|------------------|
| `HEARTBEAT_INTERVAL_SECONDS` | 30 seconds | The time between two heartbeats of an instance |
| `HEARTBEAT_OFFLINE_SECONDS` | 90 seconds | An instance without a heartbeat for this long is offline |
| `DUPLICATE_ID_CONFIRMATIONS` | 2 heartbeats | Heartbeats of another session under the own id that confirm a duplicate |
| `RETRIGGER_ACK_WINDOW_SECONDS` | 5 seconds | The longest the caller waits for acknowledgements |
| `RETRIGGER_DEVICE_INTERVAL_SECONDS` | 5 seconds | One accepted re-trigger per device in this time, on the caller and on a receiver |
| `RETRIGGER_SEEN_LIMIT` | 128 request ids | The request ids a receiver remembers to drop repeats |
| `RETRIGGER_MAX_AGE_SECONDS` | 60 seconds | A request older than this, or sent this far ahead, is dropped |
| `RESYNC_MIN_INTERVAL_SECONDS` | 5 seconds | The shortest time between two accepted resyncs |
| `MAX_IMPORT_DEVICES` | 100 devices | The most devices in one import |
| `MAX_IMPORT_BYTES` | 4 MiB | The largest import, as data or as file |
| `MAX_TRANSFER_HISTORY` | 8 entries | The previous owners the transfer marker lists |
| `MAX_DOCUMENT_BYTES` | 256 KiB | The largest document of one device, also for each item of an import |
| `MAX_BROKER_MESSAGE_BYTES` | 1024 bytes | The largest heartbeat, request or acknowledgement; larger messages are ignored |

## Upgrade notes

- **Approvals lapse once.** The approval of a mirror is bound to the hash of its actions, the startup flag, the run mode
  and the circuit breaker limits. Approvals made before the run mode and the limits were part of the hash stop
  matching: every approved mirror stops running once and Repairs asks again, with the full YAML. There is no migration.
  Devices you own are not affected.
- **Extend the broker ACL.** The heartbeat, the re-trigger and the acknowledgements use new topics. An ACL written
  before them has no lines for them: the roster stays empty, a re-trigger reaches nobody and a denied publish is not
  reported visibly. Add the lines of the tested example in [docs/broker-acl.md](broker-acl.md).
- **New entities.** The hub device, the roster sensor, the resync button, the mode selects and the companion devices
  (which end for a device when it switches to the native path) appear after the upgrade. The mode of everything starts as `run`.
- **Native entities.** Since 0.2.0 the Switch, Select and test buttons of a device are native entities of this
  integration, on the same device as the **Mode** select. The upgrade from 0.1.x is automatic and one-way: an instance
  switches when no online instance runs an older version, and Repairs shows `native_cutover_waiting` while it waits.
  There is no rollback, and an older instance that comes online later loses the entities of migrated devices without a
  hint. See the [README](../README.md#upgrading-from-01x).
- **Discovery is optional.** MQTT Discovery stays only for a device on the legacy path and as an optional export for
  other consumers (see the [README](../README.md#mqtt-discovery-export)); the export has no healing and no test
  buttons.
- **Mixed versions.** An instance on an older version sends no heartbeat, so it is not in the roster and not listed in a
  re-trigger, and it ignores the transfer marker.
