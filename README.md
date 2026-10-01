# MQTT Actions

A Home Assistant custom integration that runs a sequence of actions on this Home Assistant instance when an MQTT
state changes. You create a Switch device or a Select device in the UI, give it actions, and the integration
publishes the entity through MQTT Discovery. A Switch has actions for "switched on" and "switched off"; a Select
device has several options, each with its own actions. Every real change of the device's state topic then runs the
matching actions locally, without any YAML automation.

Several Home Assistant instances on the same broker share their devices: a device you create on one instance appears
on all the others as a read-only mirror, and every instance runs the actions locally once its user approved them. See
[Multiple instances](#multiple-instances) and [Trust model and approval](#trust-model-and-approval).

## Requirements

- Home Assistant 2026.9.0 or newer (Python 3.14).
- The built-in MQTT integration, connected to a broker, with MQTT discovery enabled (the default).

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

Each switch device appears as a Switch entity and each select device as a Select entity through MQTT Discovery.
Toggling or choosing in Home Assistant publishes the new state, which runs the matching actions like any other state
change. You can change a device later from the three-dot menu of the device entry in the integration page.

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

## Run mode, test buttons and the circuit breaker

Every device, Switch and Select, has these settings in its dialog:

- **Run mode**: `serial` (the default) queues runs and executes them one after another, at most 10 runs per device
  (running and waiting together); further runs are dropped and logged. `restart` cancels the running actions of the
  device when a new change arrives and starts the new run.
- **Run actions on startup**, as described under Behavior.
- **Circuit breaker**: a device may run its actions at most 5 runs in 10 seconds by default. Both numbers are
  configurable, from 1 to 100 runs and from 1 to 3600 seconds.

Test buttons: every trigger of a device gets a button entity, `Test ON` and `Test OFF` for a Switch and one
`Test <friendly name>` per option for a Select (listed under Configuration). Pressing a test button runs that trigger's
actions locally, publishes the press on `<base topic>/v1/devices/<device uuid>/test` (not retained), and never changes
the state, the baseline or the state topic. Existing Switch devices get their two test buttons after the upgrade;
there is no opt-out. A retained message on the test topic is ignored. Every instance that follows the device sees the
press: a test button press runs the actions on every instance that approved the device, and never on an instance that
did not (see [Trust model and approval](#trust-model-and-approval)).

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
  is not a device entry of the integration page, it has no edit dialog, and only the owner edits or deletes the device.
  Its entities come from the owner's MQTT Discovery, so they appear on the follower like the owner's own.
- A follower pins the first owner it saw for a device. A document of another owner for the same device is ignored and
  Home Assistant Repairs shows an issue naming both claims. An owner that finds its own device claimed by another
  instance publishes its document again and raises an issue as well. There is no takeover.
- The owner publishes its documents again on every start and on every MQTT reconnect, in this order: config documents,
  discovery, then `online`. A broker that lost its retained messages is healed this way. If something other than the
  owner changes or clears a document, the owner publishes it again (at most once per 60 seconds per device, plus one
  trailing publish) and raises a Repairs issue.
- A follower never deletes a mirror because a message is missing. A mirror is removed on a tombstone (an empty retained
  message on the config topic), or when the owner announces `online`, the mirror's document was not seen again within
  30 seconds after the follower connected: the owner must have deleted the device while the follower was away.
  An owner that is offline or unknown keeps all its mirrors.
- The mirrored entities use the owner's availability. While the owner is offline they are `unavailable`; an approved
  mirror still runs its actions for external changes of the state topic.
- If you delete a mirrored entity on a follower, core MQTT clears the retained discovery of the whole device. The
  owner publishes it again (at most once per 60 seconds per device, plus one trailing publish) and repeated removals
  raise a Repairs hint. The recreated entities start without the customizations you gave the old ones.

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
- The approval is bound to the hash of the actions. If the owner changes them, the approval lapses, the mirror stops
  running, and Repairs asks again with the new YAML. A tombstone or a pruned mirror also drops the approval. A forged tombstone from anyone with write access to the config topic therefore forces a new approval
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

## Deleting devices and removing the integration

- Deleting a device in the device dialog of this integration asks for a confirmation that names **all connected
  instances**: the device disappears there as well, and instances that were offline remove it when they connect again.
  The entity, the retained discovery, the config document (replaced by a tombstone) and the retained state are removed
  from the broker.
- The generic Home Assistant delete dialog of a device entry cannot be changed by an integration. It cannot ask this
  confirmation and it deletes the device everywhere too.
- Removing the integration (the hub) keeps every device on the broker by default. Their retained messages stay, the
  other instances keep the devices as orphaned mirrors that show as unavailable, and nothing is pruned because the
  owner is offline. Only if you switched on **Delete all devices when this integration is removed** in the options of
  the hub before you remove it, the integration deletes all devices created on this instance from the broker, and
  every connected instance removes them. Either way the local storage and the integration's Repairs issues of this instance are removed.

## Topic and payload contract

Every device gets a random UUID. Its state topic, which is also its command topic, is:

```
<base topic>/v1/devices/<device uuid>/state
```

- Messages are retained. Published values of a Switch are upper case `ON` and `OFF`; for a Select they are the state
  values of its options, exactly as created.
- Inbound values are trimmed and read case-insensitively, so `on`, `On` and `ON` are equal. Any other payload is
  ignored and logged. For a Select, the accepted values are the state values of its options.
- Test buttons publish the state value of their trigger, not retained, to a second topic per device:

  ```
  <base topic>/v1/devices/<device uuid>/test
  ```
- The config document of a device is one retained message on `<base topic>/v1/devices/<device uuid>/config`, written
  only by its owner; an empty retained message there is the tombstone of a deleted device.
- Discovery is published as one device-based MQTT Discovery payload per device under the discovery prefix configured
  in the MQTT integration (default `homeassistant`), and availability of this instance under
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
- Deleting a device removes its entity on all connected instances and clears its retained discovery, config and state
  topics. See [Deleting devices and removing the integration](#deleting-devices-and-removing-the-integration).
- A device of another instance runs its actions here only after you approved them. See
  [Trust model and approval](#trust-model-and-approval).

## Limitations

- A crash of Home Assistant leaves a retained `online` availability on the broker, so the entity can appear available
  until this instance connects again. Availability is set to `offline` only on a clean unload.
- There is no Last Will: an owner that crashed leaves `online` on the broker, so its mirrors look available and are not
  pruned until it connects again.
- A foreign write to a config topic that was made before the owner started is caught on a best-effort basis. A write
  made while the owner runs is always caught and healed.
- Changing the discovery prefix of the MQTT integration needs a reload of this integration.
- Healing a removed discovery recreates the mirrored entities and loses the customizations a user made to them.
- A forged tombstone removes the mirrors of a device until the owner publishes it again, and forces a new approval.
- A follower mirrors at most 100 devices of other instances, and a config document may be at most 256 KiB.
- Actions are readable by every client that can read the config topic. Do not put secrets into actions.
- A test button press runs the actions on every instance that approved the device.
- Only Switch and Select devices exist in this release.
- Actions that target a `device_id` work only on the instance where they were created, because device IDs differ
  between instances. Prefer entity, area or label targets.

## Security

Actions run on this Home Assistant instance with full access to its services. Actions you author here are checked
against the Home Assistant action schema before they are stored or run. Actions that arrive in a config document from
the broker are validated against the same schema, stay inactive until you approved their exact content in Repairs,
and are checked against a fixed denylist. See [Trust model and approval](#trust-model-and-approval).

The trust boundary is the state topic: **anyone with write access to a device's state topic can trigger that device's
actions**. The test topic is a second way to trigger them: a message on `<base topic>/v1/devices/<device uuid>/test`
runs the actions of a trigger without changing the state. The broker ACL for `<base topic>/v1/devices/#` must cover
both topics. Restrict who can publish there, and allow only Home Assistant (and the clients you trust) to publish.
Wildcards are rejected in the base topic. Do not use `device_id` targets in actions you want to share between
instances.

Ownership of a config document is cooperative: the broker cannot bind a device to its owner, because device UUIDs are
random and unknown when you write an ACL, so any Home Assistant user of the broker can overwrite any config topic. The
approval is the real control, and the ACL keeps everyone else out. [docs/broker-acl.md](docs/broker-acl.md) has a
Mosquitto ACL example that the test suite enforces on a real broker, the topic table, the limits and the advice on TLS
and on keeping secrets out of actions.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The broker tests, including the ACL tests, start a throwaway `mosquitto` (and `mosquitto_passwd`) and are skipped when
it is not installed. Every push runs hassfest,
HACS validation, Ruff and pytest in GitHub Actions; all third-party actions are pinned by commit SHA.

## License

[MIT](LICENSE)
