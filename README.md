# MQTT Actions

A Home Assistant custom integration that runs a sequence of actions on this Home Assistant instance when an MQTT
state changes. You create a Switch device or a Select device in the UI, give it actions, and the integration
publishes the entity through MQTT Discovery. A Switch has actions for "switched on" and "switched off"; a Select
device has several options, each with its own actions. Every real change of the device's state topic then runs the
matching actions locally, without any YAML automation.

This release (0.1.0) works on a single Home Assistant instance. Syncing devices between several instances through
the broker is planned and not part of this release.

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
there is no opt-out. A retained message on the test topic is ignored.

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
- Deleting a device removes its entity and clears its retained discovery and state topics.

## Limitations

- A crash of Home Assistant leaves a retained `online` availability on the broker, so the entity can appear available
  until this instance connects again. Availability is set to `offline` only on a clean unload.
- Removing the integration (the hub) deletes all discovery and state topics this instance published, including on a
  shared broker. A confirmed, multi-instance-aware delete is planned.
- This release works on a single instance. There is no synchronization between instances yet. A test button press
  runs the actions on every instance that subscribes to the test topic; with one instance that is this instance.
- Only Switch and Select devices exist in this release.
- Actions that target a `device_id` work only on the instance where they were created, because device IDs differ
  between instances. Prefer entity, area or label targets.

## Security

Actions run on this Home Assistant instance with full access to its services. Actions are authored locally in the
Home Assistant UI, and they are checked against the Home Assistant action schema before they are stored or run. They
are never taken from a broker message.

The trust boundary is the state topic: **anyone with write access to a device's state topic can trigger that device's
actions**. The test topic is a second way to trigger them: a message on `<base topic>/v1/devices/<device uuid>/test`
runs the actions of a trigger without changing the state. The broker ACL for `<base topic>/v1/devices/#` must cover
both topics. Restrict who can publish there, and allow only Home Assistant (and the clients you trust) to publish.
Wildcards are rejected in the base topic. Do not use `device_id` targets in actions you want to share between
instances.

## Development

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

The broker tests start a throwaway `mosquitto` and are skipped when it is not installed. Every push runs hassfest,
HACS validation, Ruff and pytest in GitHub Actions; all third-party actions are pinned by commit SHA.

## License

[MIT](LICENSE)
