# MQTT Actions

A Home Assistant custom integration that runs a sequence of actions on this Home Assistant instance when an MQTT
state changes. You create a Switch device in the UI, give it actions for "switched on" and "switched off", and the
integration publishes the switch through MQTT Discovery. Every real change of the device's state topic then runs the
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
3. On the integration page, choose **Add switch device**, enter a name and build the actions for "switched on" and
   "switched off" with the action editor. Actions are validated when you save.

Each switch device appears as a Switch entity through MQTT Discovery. Toggling the entity in Home Assistant publishes
the new state, which runs the matching actions like any other state change.

## Topic and payload contract

Every device gets a random UUID. Its state topic, which is also its command topic, is:

```
<base topic>/v1/devices/<device uuid>/state
```

- Messages are retained. Published values are upper case `ON` and `OFF`.
- Inbound values are read case-insensitively, so `on`, `On` and `ON` are equal. Any other payload is ignored and
  logged.
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
- This release works on a single instance. There is no synchronization between instances yet.
- Only Switch devices exist in this release.
- Actions that target a `device_id` work only on the instance where they were created, because device IDs differ
  between instances. Prefer entity, area or label targets.

## Security

Actions run on this Home Assistant instance with full access to its services. Actions are authored locally in the
Home Assistant UI, and they are checked against the Home Assistant action schema before they are stored or run. They
are never taken from a broker message.

The trust boundary is the state topic: **anyone with write access to a device's state topic can trigger that device's
actions**. Restrict who can publish to `<base topic>/v1/devices/#` with broker ACLs, and allow only Home Assistant
(and the clients you trust) to publish there. Wildcards are rejected in the base topic. Do not use `device_id`
targets in actions you want to share between instances.

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
