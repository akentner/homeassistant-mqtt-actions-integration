# Troubleshooting MQTT Actions

Start with Home Assistant Repairs: MQTT Actions explains what it noticed there, and this page has one entry for every
kind of issue it raises. The second part covers the operating problems that do not raise an issue.

Related pages: [docs/operations.md](operations.md) describes the tools that are used below,
[docs/diagnostics.md](diagnostics.md) describes the file you can attach to a bug report,
[docs/broker-acl.md](broker-acl.md) has the broker access rules, and the [README](../README.md) is the entry point.

Two limits apply to everything on this page. **Acknowledgements are advisory:** an answer to a re-trigger comes from any
instance of the broker group and can be forged, and `executed` only means that the actions were started. **Ownership is
cooperative:** the broker cannot bind a device to its owner, so the approval on each instance is the real control.

## Operating problems

### Entities are unavailable

The entities of a mirror use the availability of the owner instance, so a mirror is `unavailable` while its owner is
offline. Check these in order:

1. **The owner is offline.** Open the sensor **Instances online** of the hub device, whose attribute `instances` shows
   every instance with `online` and `last_seen`. An instance that shut down cleanly turns offline at once. An instance
   that crashed turns offline in the roster after 90 seconds, while its retained availability on the broker can stay
   `online` for good, because Home Assistant owns the MQTT connection and there is no Last Will. In that case the
   entities can look available although the owner is gone. If the owner is gone for good, you can
   [adopt](operations.md#adoption) its devices.
2. **MQTT is not connected** in this instance, or the broker is down. Fix the MQTT integration first.
3. **MQTT discovery is disabled** in the MQTT integration, which raises the issue `mqtt_discovery_disabled`.
4. **The ACL denies the discovery prefix** to this instance (see A denied publish is not reported below).

### Approvals lapsed after an upgrade

This is expected once. The approval of a mirror is bound to the hash of its actions, the startup flag, the run mode and
the circuit breaker limits. Approvals made before the run mode and the limits were part of the hash no longer match, so
every approved mirror stops running once and Repairs asks again with the new YAML (the issue `approval_required`).
Read the actions and approve them again. Nothing is migrated and the devices you own are not affected. The same lapse
happens at any time when the owner changes the actions, the startup flag, the run mode or a breaker limit. A rename
does not change the hash.

### A denied publish is not reported

A broker may acknowledge a QoS 1 publish that its ACL denied like an accepted one, and Home Assistant shows nothing in
its log. The symptoms are quiet: a device does not appear on another instance, the roster is empty, a re-trigger
returns `no_answer` for an instance that is online, or the entities of a deleted device stay. Do not wait for an
error. Read the retained state back with a second client, for example
`mosquitto_sub -v -t 'mqtt_actions/v1/#'` with the credentials of the instance in question, and compare the topics with
the table of [docs/broker-acl.md](broker-acl.md). After an upgrade, check that the heartbeat, re-trigger and
acknowledgement lines are in your ACL.

### Adoption or ownership conflicts

- **The adoption was refused.** The error names the reason. *The owner is not known to be offline:* wait until the
  roster shows it offline (a clean shutdown shows at once, a crash after 90 seconds), or call `adopt_device` again with
  `force: true` when you are sure it is gone. *The actions are not approved, or the device is blocked:* approve the
  device in Repairs first; a device that the denylist blocks cannot be adopted, not even with `force`. *Not a mirror:*
  pick a device that this instance mirrors from another instance.
- **The old owner came back.** It raises `transferred` and stays quiet about the device. Until you confirm the fix of
  that issue, it still owns the device locally and runs its own actions for it. Confirming makes it follow the adopter,
  and the new mirror needs an approval there.
- **The two overlap for a moment.** When the old owner starts, it can publish before it heard the adopter's document. The
  adopter then sees a foreign write to a device it owns (`doc_overwritten` or `ownership_claim`) and publishes its
  own document again, at most once per 60 seconds per device. The discovery of the adopter can briefly carry the old
  owner's availability topic; press **Resync** on the adopter to restore it.
- **The recognition is only in memory.** After a restart of the old owner it can overwrite the document of the adopter
  once more and the issue `transferred` returns; confirm it again, or resync on the adopter.
- **A follower shows an owner conflict after an adoption.** A follower honors the transfer marker only when its roster
  shows the old owner offline. If it still shows it online when the adopter's document arrives, it raises
  `owner_conflict` and moves on with the next document of the adopter. A resync on the adopter closes the gap.
- **An instance on an older version** ignores the marker, keeps following the old owner and raises the conflict. Update
  it.

### A new instance id and the ACL

The fix of `duplicate_instance_id` gives the copy a new random instance id. If your broker restricts the availability,
heartbeat and acknowledgement topics per instance, the new id is not in the ACL, so the copy can read but not write
its own topics: it does not appear in the roster of the others and cannot answer a re-trigger. Add the new id to the
ACL lines of that instance (see [docs/broker-acl.md](broker-acl.md)). Read the full id from the availability topics,
`mosquitto_sub -v -t 'mqtt_actions/v1/instances/+/availability'`; the diagnostics file shows only the first eight
characters.

### A device exists twice on the integration page

This is not a duplicate. Every device has two devices of the same name on purpose: the **core MQTT device** that holds
its entities (the Switch or Select and the test buttons), and the **companion device** of MQTT Actions, which holds the
**Mode** select and sits under the subentry of an owned device or alone for a mirror. Do not delete either to tidy up:
deleting an owned device deletes it on every instance, and deleting an entity of a mirror makes the owner publish it
again (see `discovery_removed` below).

### Resync did not restore the entities

Resync republishes what this instance **owns**: the config documents, the discovery and the online availability. It never
deletes anything. So:

- The entities of a **mirror** come from its owner; press **Resync** on the owner's instance.
- A second resync inside 5 seconds is refused with an error; wait and try again.
- If the publish is denied by the ACL, nothing is reported (see A denied publish is not reported above).
- If MQTT discovery is disabled in the MQTT integration, no entity appears until it is enabled again.
- Entities that were recreated start without the customizations (names, icons, areas) of the old ones.

## Repairs issues

Each entry gives what the issue means, why it appears and what to do. The issue ids carry the device id or instance id
after the key shown here.

### `action_failed`

**Meaning:** the actions of a trigger of a device failed. The issue names the device, the trigger, the time and the
error, and there is one issue per device. **Why:** an action raised an error, for example an entity that no longer
exists. **What to do:** read the error, correct the actions of the device, and the issue disappears after the next
successful run. The log has more detail.

### `mqtt_discovery_disabled`

**Meaning:** MQTT Actions creates its entities through MQTT discovery, but discovery is disabled in the MQTT integration.
**What to do:** enable discovery again in the options of the MQTT integration. No entity appears before that.

### `circuit_breaker_tripped`

**Meaning:** a device ran its actions more often than its limit allows within the window, by default more than 5 times
in 10 seconds. **Why:** usually an action changes the state of its own device and triggers itself again. The running and
queued runs were stopped and the device is paused: state changes still update the entity and the baseline, but no
actions run, and the test buttons keep working. **What to do:** break the loop, then release the device by changing any
setting of it or by reloading the integration. Saving it without a change does not release it.

### `doc_overwritten`

**Meaning:** something other than this instance changed or cleared the shared configuration of a device that this
instance owns, and the instance published it again (at most once per 60 seconds per device). **Why:** another client with
write access to the config topics, a forged tombstone, or the overlap of an old and a new owner (see Adoption above).
**What to do:** restrict who can write the topics of MQTT Actions in the ACL. Ownership is cooperative, so the ACL can
only keep clients that are not Home Assistant instances out.

### `ownership_claim`

**Meaning:** another instance published a configuration for a device that this instance owns. This instance stays the
owner and published its own document again. There is no takeover. **What to do:** find the claimant named in the issue;
it is usually a restored backup or a clone (see `duplicate_instance_id`), or an instance that adopted the device (see
`transferred`).

### `discovery_removed`

**Meaning:** the entities of a device were removed three times within ten minutes, for example by deleting an entity on
another Home Assistant instance. Each time, this instance published the discovery again. **Why:** deleting an entity of
a mirror makes core MQTT clear the discovery of the whole device on the broker. **What to do:** delete the device
itself on its owner if you no longer want it. Deleting a single entity does not stay deleted.

### `owner_conflict`

**Meaning:** this instance follows a device whose owner was pinned, and another instance named in the issue also
published a configuration for it. This instance keeps following the pinned owner and ignores the other claim. **What
to do:** check the ACL so that each instance can only write its own devices. If the claimant adopted the device, see
Adoption or ownership conflicts above.

### `schema_too_new`

**Meaning:** the shared configuration of a device uses a newer format version than this integration understands. The
device keeps its last known settings. **What to do:** update MQTT Actions on this instance.

### `approval_required`

**Meaning:** a device from another instance wants to run actions here, and nothing runs before you approve. **What to
do:** open the repair, read the full YAML, the startup flag, the run mode and the breaker limits, and approve only
what you trust. The approval is bound to the hash shown and lapses when the owner changes any of it. Mirrors can call
scripts, scenes and other things the denylist cannot see inside, so reading the YAML is the control.

### `mirror_blocked`

**Meaning:** a device from another instance calls services that are never allowed for actions received from other
instances. It is paused and cannot be approved or adopted. **What to do:** ask the owner to remove the services named in
the issue from the device.

### `denied_service_call`

**Meaning:** a run of a device from another instance was stopped because a templated service name resolved to a
forbidden service when the actions ran. **What to do:** ask the owner to correct the template. The run is aborted every
time it resolves to that service.

### `duplicate_instance_id`

**Meaning:** another instance sends heartbeats with the same instance id as this one, usually because a backup was
restored on a second machine or a clone was started. **What to do:** on the **copy** only, open the repair and confirm
the fix. It forgets the copy's own devices locally, changes nothing on the broker and continues under a new id; the
original keeps everything. Devices the copy should own have to be created again or imported. Then see A new instance id
and the ACL above.

### `transferred`

**Meaning:** another instance adopted a device that this instance owned, so this instance stopped publishing it. It
still owns the device locally and runs its own actions until you release it. **What to do:** open the repair and confirm
to follow the adopter instead. Nothing is cleared on the broker; the device appears here as a mirror, which needs an
approval. See Adoption or ownership conflicts above for the cases where the issue returns.
