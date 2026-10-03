# MQTT Actions

A Home Assistant custom integration that runs a sequence of actions on this Home Assistant instance when an MQTT
state changes. You create a Switch device or a Select device in the UI, give it actions, and the integration shows it
as a native entity of its own, on every instance. A Switch has actions for "switched on" and "switched off"; a Select
device has several options, each with its own actions. Every real change of the device's state topic then runs the
matching actions locally, without any YAML automation. MQTT Discovery is no longer how the entities come into being: it
is an optional export for other consumers of the broker (see [MQTT Discovery export](#mqtt-discovery-export)) and the
way of an older instance that is still online (see [Upgrading from 0.1.x](#upgrading-from-01x)).

Several Home Assistant instances on the same broker share their devices: a device you create on one instance appears
on all the others as a read-only mirror, and every instance runs the actions locally once its user approved them. See
[Multiple instances](#multiple-instances) and [Trust model and approval](#trust-model-and-approval). What you can do
once it runs, such as re-triggering actions, seeing who is connected and recovering devices, is described under
[Operations](#operations).

## Requirements

- Home Assistant 2026.9.0 or newer (Python 3.14).
- The built-in MQTT integration, connected to a broker. MQTT discovery has to be enabled in it (the default) only while
  an instance on an older version is online, or when you switch on the export on the core prefix.

## Installation

Install it as a custom repository in [HACS](https://hacs.xyz):

1. In HACS, open the menu and choose **Custom repositories**.
2. Add `https://github.com/akentner/homeassistant-mqtt-actions-integration` with the category **Integration**.
3. Download **MQTT Actions** and restart Home Assistant.

## Setup

1. Go to **Settings > Devices & services > Add integration** and choose **MQTT Actions**.
2. Set the **base topic** (default `mqtt_actions`) and the **instance name** of this Home Assistant instance. The base
   topic is written into retained broker messages and cannot be changed later. To use another base topic, remove the
   integration and set it up again.
3. On the integration page, choose **Add switch device** or **Add select device**. A switch needs a name and the
   actions for "switched on" and "switched off", built with the action editor. A select device needs a name and at
   least two options (see [Select devices](#select-devices)). Actions are validated when you save.

Each switch device appears as a Switch entity and each select device as a Select entity of this integration, together
with its test buttons and its mode select on one device of MQTT Actions. Toggling or choosing in Home Assistant
publishes the new state, which runs the matching actions like any other state change; the entity shows the state that
comes back from the broker and never guesses it. You can change a device later from the three-dot menu of the device
entry in the integration page.

## Upgrading from 0.1.x

Version 0.2.0 is the first release in which the entities are native entities of the integration. The upgrade is
automatic and one-way: there is no setting and no step to take.

- **What is kept.** The entity ids, registry ids, device ids, areas, names and history are kept, so dashboards,
  automations and history graphs keep working. The devices and their entities move from the core MQTT integration to
  MQTT Actions and appear on its integration page, on every instance.
- **When it switches.** An instance switches once no online instance runs an older version. While an online instance
  runs an older version, this instance keeps using MQTT Discovery, works as before and shows the Repairs issue
  `native_cutover_waiting` that names the instances it waits for. It switches on its own, without a restart, when they
  are updated or offline. A follower that already mirrors a device switches by itself with one reload of the
  integration.
- **Older instances that come online later.** An instance on 0.1.x that comes online after the switch keeps running
  its actions, because the config document stays valid for it, but it loses the entities of migrated devices without a
  hint. Update it. It is not told by the integration, only by these notes.
- **No rollback.** Rollback to 0.1.x is not supported. After a downgrade, core MQTT creates new entities that cannot
  take the old entity ids and the migrated ones are left behind, so a downgrade creates duplicate `_2` entities. See
  [docs/troubleshooting.md](docs/troubleshooting.md).
- **Test buttons.** A test button that exists already, including the ones moved from core MQTT, keeps its category and
  enabled state. Only new test buttons are diagnostic and disabled by default; nothing is migrated.
- **Removal.** Removing the integration removes the entities, because they belong to it; with core MQTT they belonged to
  the MQTT integration and stayed.
- **Adoption.** Adoption between an old and a new instance should not run concurrently: a native device stays native
  after an adoption, and two instances that adopt the same device at once are a normal ownership conflict.
- **Select entities.** A select whose option was renamed or removed shows `unknown` instead of a stale value.

## MQTT Discovery export

The MQTT Discovery export is optional and off by default. Home Assistant needs no Discovery for the devices of this
integration, so the export is only for other consumers of the broker, for example a second automation system. Switch it
on in the options of the hub:

- **Publish an MQTT Discovery export** (`discovery_export`) turns the export on.
- **Discovery export prefix** (`export_prefix`) is the topic prefix, `mqtt_actions_export` by default. A Home Assistant
  instance does not listen to it.

The export lists the native devices this instance owns, one retained device-based payload per device on
`<export prefix>/device/<device uuid>/config`. Every component has `enabled_by_default` set to false. There are no
test buttons and no healing: nothing publishes the export again if somebody deletes it on the broker, and a resync
does. Switching the export off clears the topics.

If you enter a prefix that Home Assistant listens to, for example `homeassistant`, every instance creates a duplicate
entity of each device. These duplicates are disabled by default, so they do not run anything, but they clutter the
entity list. Use the default prefix unless a consumer needs another one.

## Select devices

A select device has a name and a list of options. Each option has:

- a **state value**: the exact text that arrives on the state topic for this option,
- a **friendly name**: what the Select entity shows in Home Assistant,
- **actions**: optional, run on this instance when the state changes to this option.

How it works:

- The payload is trimmed and matched case-insensitively against the state values. A payload that matches no option is
  ignored and logged.
- The payload published when you choose an option in Home Assistant is the state value exactly as you created it.
- Options keep the order in which you added them, also in the entity's option list.
- A select device needs at least two options. State value and friendly name must be printable, at most 64 characters,
  and different from the other options ignoring case. The state value has no spaces at its start or end, and the
  friendly name cannot be `none`, because Home Assistant shows an unknown state for that value. A device holds at most
  50 options.
- The state value is locked after the option exists. You can change the friendly name and the actions, add options at
  the end, and remove options after a confirmation while at least two remain. Nothing is saved until you choose
  **Save the device**.
- After you rename or remove the option that is currently selected, the entity shows `unknown` until the next valid
  state message arrives. The last acted state is kept: a message that repeats it is not a change. A removed state
  value is treated as unknown from then on.
- The attribute `previous_state` of the Select holds the friendly name of the value that was shown before the current
  one. It is tracked per instance on every change of the shown value, from this instance or another, and kept across
  restarts. It is empty until the value changed once, and when that option was removed.
- The button **Restore previous state** is visible by default and publishes that value exactly like choosing the option:
  retained, at QoS 1, on the shared state topic, so every instance reacts. It does nothing without a previous state.
  Pressing it twice toggles between the two values. It exists for native devices only. On a mirror it needs the owner
  online and no approval, because approval gates only the running of actions on this instance.

## Run mode, test buttons and the circuit breaker

Every device, Switch and Select, has these settings in its dialog:

- **Run mode**: `serial` (the default) queues runs and executes them one after another, at most 10 runs per device
  (running and waiting together); further runs are dropped and logged. `restart` cancels the running actions of the
  device when a new change arrives and starts the new run.
- **Run actions on startup**, as described under Behavior.
- **Circuit breaker**: a device may run its actions at most 5 runs in 10 seconds by default. Both numbers are
  configurable, from 1 to 100 runs and from 1 to 3600 seconds.

Test buttons: every trigger of a device gets a button entity, `Test ON` and `Test OFF` for a Switch and one
`Test <friendly name>` per option for a Select. Pressing a test button runs that trigger's actions, and never changes
the state, the baseline or the state topic. It follows the run mode of the device and passes through the queue and the
circuit breaker like any other run. Test buttons are a tool, not a daily control: a new test button is in the
Diagnostic category and disabled by default, so enable it on its entity page when you need it. This holds for owned
devices and for mirrors. A test button that already exists, including the ones migrated from 0.1.x, keeps its category
and its enabled state: nothing is migrated.

- **Native devices (the default since 0.2.0):** a press runs the actions only on this instance and publishes nothing.
  Pressed on a mirror, it runs the mirrored actions only if this instance approved the device (see
  [Trust model and approval](#trust-model-and-approval)).
- **Devices on the legacy path (an instance on an older version is online):** a press also publishes the trigger's
  state value, not retained, on `<base topic>/v1/devices/<device uuid>/test`, so every instance that approved the
  device runs the actions, and never an instance that did not. A retained message on the test topic is ignored.

Circuit breaker: an action that changes the state of its own device can trigger itself forever. When a device would
exceed its limit, for example the sixth run within 10 seconds, the breaker pauses the device:

- The change that trips the breaker does not run, and the running and queued runs of the device are stopped.
- While paused, changes on the state topic still update the entity and the baseline, but no actions run. The test
  buttons keep working.
- One warning is logged and Home Assistant Repairs shows an issue for the device.
- To release the device, change it (any change to its title or settings) or reload the integration. Saving a device
  without changing anything does not release it.
- The paused state survives a Home Assistant restart, because a restart does not reload the integration. The counting
  window does not survive: after a release or a restart the count starts at zero.
- Only real changes that would run actions count. Test button presses, changes to a trigger without actions and
  changes while paused do not count.

## Multiple instances

All instances that use the same broker and the same base topic take part. Every instance is the **owner** of the devices
created on it and a **follower** of the devices created on the others.

- The owner publishes one retained message per device, its config document, on
  `<base topic>/v1/devices/<device uuid>/config`. The document carries a `schema_version` and holds the name, the kind,
  the options and their actions, the run mode, the startup flag and the breaker limits. The approval, the breaker's
  tripped state and the last acted state are not shared: they are local to each instance.
- A follower validates the document and keeps a **mirror** of the device in its own storage. A mirror is read-only: it
  has no edit dialog, and only the owner edits or deletes the device. It is a device of this integration directly under
  the config entry, named after the device and marked with its owner, and it carries native entities, the test buttons
  and the mode select, so the devices of every instance are on the integration page.
- A follower pins the first owner it saw for a device. A document of another owner for the same device is ignored and
  Home Assistant Repairs shows an issue naming both claims. An owner that finds its own device claimed by another
  instance publishes its document again and raises an issue as well. There is no takeover, with one exception: a device
  whose owner is gone can be adopted by another instance (see [Operations](#operations)).
- The owner publishes its documents again on every start and on every MQTT reconnect, in this order: config documents,
  discovery (only for a device on the legacy path or an enabled export), then `online`. A broker that lost its retained
  messages is healed this way. If something other than the
  owner changes or clears a document, the owner publishes it again (at most once per 60 seconds per device, plus one
  trailing publish) and raises a Repairs issue.
- A follower never deletes a mirror because a message is missing. A mirror is removed on a tombstone (an empty retained
  message on the config topic), or when the owner announces `online`, the mirror's document was not seen again within
  30 seconds after the follower connected: the owner must have deleted the device while the follower was away.
  An owner that is offline or unknown keeps all its mirrors.
- The mirrored entities use the owner's availability. While the owner is offline they are `unavailable`; an approved
  mirror still runs its actions for external changes of the state topic.
- A native device needs no healing: its entities belong to this integration, so nothing on the broker can remove them,
  and deleting the discovery of a device has no effect on them. Only a device that is still on the legacy path (see
  [Upgrading from 0.1.x](#upgrading-from-01x)) is healed as before: if you delete a mirrored entity of such a device,
  core MQTT clears its retained discovery, the owner publishes it again (at most once per 60 seconds per device, plus
  one trailing publish) and repeated removals raise a Repairs hint.
- Every instance publishes a heartbeat, and the sensor **Instances online** of the hub device is the roster: how many
  instances are online and, in its attributes, which. A device on the legacy path additionally has a **companion
  device** with the **Mode** select; a native device has the select on the device that carries its entities. See
  [docs/operations.md](docs/operations.md).

Actions you want to share between instances should use targets that exist on every instance:

```yaml
action: light.turn_on
target:
  area_id: living_room
```

## Trust model and approval

Actions from another instance run with the full access of your Home Assistant, so they never run before you decided:

- A mirror tracks the state of the device, but it runs nothing until you **approve** its actions on this instance. The
  approval request appears in Home Assistant Repairs and shows the device, the owner, the full YAML of the actions and
  a hash. Approving does not run anything retroactively; only a later change of the state runs the actions.
- The approval is bound to the hash of the actions, the startup flag, the run mode and the circuit breaker limits (the
  maximum number of runs and the window); the dialog shows all of them. If the owner changes any of them, the approval
  lapses, the mirror stops running, and Repairs asks again with the new YAML. A rename does not change the hash.
  Approvals made before the run mode and the breaker limits were bound lapse once after the upgrade: every approved
  mirror stops running and Repairs asks again, with no migration. A tombstone or a pruned mirror also drops the approval. A forged tombstone from anyone with write access to the config topic therefore forces a new approval
  and cannot run an action.
- There is no hub-wide switch: no ask or auto mode and no extra opt-in setting. The per-device, per-instance approval
  is the opt-in (the "local opt-in flag" of the project notes). Devices you own never need an approval.
- A fixed denylist applies to every mirror and cannot be changed. It denies the domains `shell_command`,
  `python_script`, `rest_command`, `command_line`, `hassio` and `backup`, and the services `homeassistant.restart`,
  `homeassistant.stop`, `homeassistant.reload_all`, `homeassistant.reload_core_config`,
  `homeassistant.reload_config_entry`, `homeassistant.set_location`, `homeassistant.save_persistent_states`,
  `mqtt.publish`, `mqtt.dump`, `recorder.purge`, `recorder.purge_entities`, `recorder.disable`, `update.install`,
  `downloader.download_file`, `logger.set_level`, `logger.set_default_level` and `system_log.clear`. A mirror with a
  denied call, in any nested step, is blocked: Repairs explains it and it cannot be approved. A templated service name
  is allowed and marked in the approval view; the denylist is checked again when the name is resolved at run time, and
  a denied result aborts the run and raises an issue. The denylist is best effort: it names core services and cannot
  know the services of custom integrations (for example `pyscript`), so a service that is not listed is not safe by
  that fact.
- Residual risk: approved actions can still call local scripts, automations, scenes, device actions and events, and can
  send data out through allowed services such as `notify`. Generic calls act on whatever entity they target, so
  `button.press`, `scene.turn_on`, `homeassistant.turn_on`, `homeassistant.turn_off` and `homeassistant.toggle` on a
  script, scene or button entity (for example one that restarts or updates something) are not restricted either; the
  approval view flags these calls, and calls into the `script` domain and `automation.trigger`, as residual. The
  denylist cannot see inside them. That is why the approval shows the full YAML: approve only what you read and trust.
  Your own devices are not restricted at all.

## Operations

These tools are for running several instances with confidence. Every service is admin only and can return a response.
[docs/operations.md](docs/operations.md) describes each of them, their fields, results and limits.

- **Resync:** the **Resync** button of the hub device and the service `mqtt_actions.resync` publish everything this
  instance owns again (documents and online, plus discovery for legacy devices and an enabled export). It never deletes
  anything.
- **Roster:** the sensor **Instances online** counts the instances that are online by their heartbeat, which is sent
  every 30 seconds; an instance is offline after 90 seconds without one.
- **Modes:** every device and the whole instance can be in `run`, `observe` (track the state, run nothing, log what
  would have run) or `disabled`, chosen with a select on the device or the hub device. A mode is local and never shared.
- **Re-trigger:** `mqtt_actions.retrigger` runs the actions of one device again on every instance that approved it, and
  returns who executed them. It never changes the state. Acknowledgements are advisory.
- **Export and import:** `mqtt_actions.export_devices` returns your devices as JSON, or writes a private file;
  `mqtt_actions.import_devices` creates new devices from it, all or nothing.
- **Adoption:** `mqtt_actions.adopt_device` takes over a device whose owner is offline (or with `force`), if you
  approved its actions on this instance first.
- **Duplicate instance id:** a clone or a restored backup that shares an instance id is reported in Repairs, with a fix
  that gives the copy a new id.
- **Diagnostics:** **Download diagnostics** on the integration entry gives a file with the structure of your setup and
  no action content. See [docs/diagnostics.md](docs/diagnostics.md).

When something looks wrong, start with Repairs and then
[docs/troubleshooting.md](docs/troubleshooting.md), which has an entry for every issue.

## Deleting devices and removing the integration

- Deleting a device in the device dialog of this integration asks for a confirmation that names **all connected
  instances**: the device disappears there as well, and instances that were offline remove it when they connect again.
  The entities, the config document (replaced by a tombstone) and the retained state are removed from the broker, and
  so is the retained discovery of a legacy device or of an enabled export.
- The generic Home Assistant delete dialog of a device entry cannot be changed by an integration. It cannot ask this
  confirmation and it deletes the device everywhere too.
- Removing the integration (the hub) keeps every device on the broker by default. Their retained messages stay, the
  other instances keep the devices as orphaned mirrors that show as unavailable, and nothing is pruned because the
  owner is offline. Only if you switched on **Delete all devices when this integration is removed** in the options of
  the hub before you remove it, the integration deletes all devices created on this instance from the broker, and
  every connected instance removes them. Either way the local storage and the integration's Repairs issues of this
  instance are removed. The entities of the devices are removed with the integration, because they belong to it: after
  a removal they are gone from the integration page, and a new setup creates them again.

## Topic and payload contract

Every device gets a random UUID. Its state topic, which is also its command topic, is:

```
<base topic>/v1/devices/<device uuid>/state
```

- Messages are retained. Published values of a Switch are upper case `ON` and `OFF`; for a Select they are the state
  values of its options, exactly as created.
- Inbound values are trimmed and read case-insensitively, so `on`, `On` and `ON` are equal. Any other payload is
  ignored and logged. For a Select, the accepted values are the state values of its options.
- On the legacy path, test buttons publish the state value of their trigger, not retained, to a second topic per
  device; native devices have no test topic, because their test buttons run locally:

  ```
  <base topic>/v1/devices/<device uuid>/test
  ```
- The config document of a device is one retained message on `<base topic>/v1/devices/<device uuid>/config`, written
  only by its owner; an empty retained message there is the tombstone of a deleted device.
- A device on the legacy path is published as one device-based MQTT Discovery payload per device under the discovery
  prefix configured in the MQTT integration (default `homeassistant`). A native device publishes none; with the export
  on, one payload per device goes to the export prefix instead. The availability of this instance is on
  `<base topic>/v1/instances/<instance id>/availability`.

## Behavior

- Only real changes run actions. A repeated identical value runs nothing.
- Retained state only sets the baseline. After a Home Assistant restart, an integration reload or an MQTT reconnect,
  the retained value is remembered and no action runs.
- A new device that finds an existing retained state on its topic takes it as the baseline without running actions.
- A live message on a device that has no baseline yet, for example the first toggle after creating the device, is a
  real change and runs the actions.
- Each device has a **Run actions on startup** option (off by default). When it is on, the retained state counts as a
  change once after Home Assistant starts or the integration reloads, so the matching actions run even if the value is
  unchanged.
- A failing action is written to the log, and Home Assistant Repairs shows one issue per device with the device,
  trigger, time and error. The issue disappears after the next successful run.
- Deleting a device removes its entities on all connected instances and clears its retained config and state topics
  (and its discovery on the legacy path or the export). See [Deleting devices and removing the integration](#deleting-devices-and-removing-the-integration).
- A device of another instance runs its actions here only after you approved them. See
  [Trust model and approval](#trust-model-and-approval).

## Limitations

- A crash of Home Assistant leaves a retained `online` availability on the broker, so the entity can appear available
  until this instance connects again. Availability is set to `offline` only on a clean unload. There is no Last Will,
  because Home Assistant owns the MQTT connection, and the mirrors of a crashed owner are not pruned until it connects
  again.
- Presence comes from the heartbeat: a crashed owner turns offline in the roster after 90 seconds while its retained
  availability can stay online. The heartbeat does not change the availability of the mirrored entities.
- Adoption needs an approved mirror and an owner that is offline, or `force`. Older versions ignore the transfer marker
  of an adopted device and keep following the old owner. An old owner that returns keeps running its own actions for
  the device until you release it in Repairs.
- The switch to native entities is one-way and is gated on the heartbeats of the other instances, which are not
  authenticated. A forged retained `offline` availability message for an older instance lifts its block, and an older
  instance that is cleanly offline when the cutover is checked is not waited for. Restrict who can publish to the
  instance topics with the per-instance ACL in [docs/broker-acl.md](docs/broker-acl.md).
- A native mirror whose config document is close to the size limit can read as a legacy mirror again after a restart,
  and a retained Discovery replay while Home Assistant starts can briefly create a duplicate entity that the next
  start cleans up.
- A re-trigger reaches only instances that are connected and approved. Acknowledgements are advisory and can be forged,
  and `executed` means started. Requests are delivered at least once; a repeated request id runs nothing.
- Adoption and import put content under the administrator's responsibility: the devices are owned, so they run without
  an approval. Read what you adopt or import.
- A foreign write to a config topic that was made before the owner started is caught on a best-effort basis. A write
  made while the owner runs is always caught and healed.
- Changing the discovery prefix of the MQTT integration needs a reload of this integration; it matters only for devices
  on the legacy path and for an export on that prefix.
- Healing of a removed discovery exists only for devices on the legacy path, where it recreates the mirrored entities
  and loses the customizations a user made to them. Native devices need no healing.
- The upgrade from 0.1.x is one-way and has no rollback. An older instance that comes online after the switch keeps
  running its actions but loses the entities of migrated devices without a hint. Adoption between an old and a new
  instance should not run concurrently. See [Upgrading from 0.1.x](#upgrading-from-01x).
- The export is best effort: nothing heals it, and it has no test buttons.
- A forged tombstone removes the mirrors of a device until the owner publishes it again, and forces a new approval.
- A follower mirrors at most 100 devices of other instances, and a config document may be at most 256 KiB.
- Actions are readable by every client that can read the config topic. Do not put secrets into actions.
- A test button press of a native device runs the actions only on the instance where it is pressed. On the legacy
  path, it runs them on every instance that approved the device.
- Only Switch and Select devices exist in this release.
- Actions that target a `device_id` work only on the instance where they were created, because device IDs differ
  between instances. Prefer entity, area or label targets.

## Security

Actions run on this Home Assistant instance with full access to its services. Actions you author here are checked
against the Home Assistant action schema before they are stored or run. Actions that arrive in a config document from
the broker are validated against the same schema, stay inactive until you approved their exact content in Repairs,
and are checked against a fixed denylist. See [Trust model and approval](#trust-model-and-approval).

The trust boundary is the state topic: **anyone with write access to a device's state topic can trigger that device's
actions**. For a device on the legacy path the test topic is a second way to trigger them: a message on
`<base topic>/v1/devices/<device uuid>/test` runs the actions of a trigger without changing the state. Native devices
have no test topic, because their test buttons run locally. The broker ACL for `<base topic>/v1/devices/#` must cover
both topics while an instance may still be on the legacy path. Restrict who can publish there, and allow only Home Assistant (and the clients you trust) to publish.
Wildcards are rejected in the base topic. Do not use `device_id` targets in actions you want to share between
instances.

Ownership of a config document is cooperative: the broker cannot bind a device to its owner, because device UUIDs are
random and unknown when you write an ACL, so any Home Assistant user of the broker can overwrite any config topic. The
approval is the real control, and the ACL keeps everyone else out. [docs/broker-acl.md](docs/broker-acl.md) has a
Mosquitto ACL example that the test suite enforces on a real broker, the topic table, the limits and the advice on TLS
and on keeping secrets out of actions.

## Releases

A release is made by pushing a tag of the form `vX.Y.Z`; the release workflow runs for `v*.*.*`. The tag has to equal
the `version` in `custom_components/mqtt_actions/manifest.json`, and the workflow fails first when it does not. It then
runs the same checks as every push (Ruff lint and format, the unit tests, the tests against a real Mosquitto broker and
the multi-instance tests) and the validation (hassfest and the HACS validation). Only when all of them passed does it
create the GitHub release with generated notes. A version with a hyphen suffix, for example `v0.2.0-rc1`, becomes a
prerelease. No zip is built, because the repository has the standard layout `custom_components/mqtt_actions/` and HACS
offers the releases as the installable versions.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The test suite has three tiers, selected by pytest markers, and CI runs one job for each:

| Tier | Command | CI job |
|------|---------|--------|
| Unit tests, no broker | `uv run pytest -q -m "not broker and not multi_instance"` | Unit tests |
| Real Mosquitto broker, including the ACL tests | `uv run pytest -q -m broker` | Broker tests (Mosquitto) |
| Several Home Assistant instances on an in-memory broker | `uv run pytest -q -m multi_instance` | Multi-instance tests |

The broker tests start a throwaway `mosquitto` (and `mosquitto_passwd`) and are skipped when it is not installed. Set
`MQTT_ACTIONS_REQUIRE_BROKER=1` to turn that skip into a failure; the CI broker job sets it so that it cannot pass
without a broker. A fourth job runs Ruff. Every push also runs hassfest and the HACS validation, and all third-party
actions are pinned by commit SHA.

## License

[MIT](LICENSE)
