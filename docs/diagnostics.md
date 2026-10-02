# Diagnostics of MQTT Actions

MQTT Actions can produce a diagnostics file for a bug report. It describes the structure of your setup, never its
content: which devices exist, who owns them, in which mode they are and whether they are approved, but not what their
actions do. This page lists exactly what the file contains and what it never contains.

Related pages: [docs/operations.md](operations.md) explains the tools the file reports on,
[docs/troubleshooting.md](troubleshooting.md) helps when something looks wrong, and the [README](../README.md) is the
entry point.

## How to get the file

1. Open **Settings > Devices & services** and choose **MQTT Actions**.
2. Open the three-dot menu of the integration entry (the hub) and choose **Download diagnostics**.

An entry that is not loaded has nothing to report: the file then holds only `loaded` with the value `false`.

## What the file contains

The file is built from an allow-list. Every key is written into the code by name, so a value that is not on this page
is not in the file.

| Key | Meaning |
|-----|---------|
| `integration_version` | The version of MQTT Actions on this instance |
| `hub` | The settings of this instance, see below |
| `roster` | This instance and every peer it heard a heartbeat from, online or not, see below |
| `devices` | One row for every device this instance owns and every mirror it holds, see below |

The `hub` section:

| Key | Meaning |
|-----|---------|
| `base_topic` | The base topic of the integration |
| `instance_name` | The name of this instance |
| `instance_id` | The instance id, shortened |
| `instance_mode` | The mode of the whole instance: `run`, `observe` or `disabled` |

Each row of `roster`:

| Key | Meaning |
|-----|---------|
| `id` | The instance id, shortened |
| `name` | The instance name from its heartbeat |
| `version` | The integration version from its heartbeat |
| `last_seen` | When the last heartbeat was heard |
| `online` | Whether the instance counts as online; see [Roster and heartbeat](operations.md#roster-and-heartbeat) |

Each row of `devices`:

| Key | Meaning |
|-----|---------|
| `uuid` | The random id of the device on the broker |
| `kind` | `switch` or `select` |
| `origin` | `owned` when this instance owns the device, `mirror` when it follows another instance |
| `owner` | The instance id of the owner, shortened |
| `mode` | The mode of this device on this instance |
| `effective_mode` | The mode that applies: the most restrictive of the instance mode and the device mode |
| `approval` | `owned`, `approved`, `pending`, `blocked`, `no_actions` or `unknown` |
| `breaker` | `ok`, or `tripped` when the circuit breaker paused the device |
| `rev` | The revision of the shared configuration |
| `hash` | The content hash of the shared configuration, not the approval hash and never any action text |

## What the file never contains

Instance ids are shortened to eight characters. That is enough to tell instances apart and too short to name one in a
broker ACL, so read the full id from the availability topic when you need it.

The file never contains actions, whether as YAML, templates, entity ids or service data. It never contains the options
or the state values of a device, and it never contains device names. It never contains broker credentials or host names,
because the settings of the MQTT integration are not read at all.

The file does contain the names of the instances and the base topic, because it shows the structure of the setup and
those are the labels a reader needs to follow it. If your instance names or your base topic reveal something you do not
want to share, change them in your copy of the file before you attach it.

The mechanism is an allow-list, not a filter. A second pass replaces the value of any key that could carry content
(`actions`, `options`, `entity_id`, `service`, `data`, `target`, `password`, `username`, `host`, `broker`, `port` and a few
more) with a redaction marker. It exists as a safety net for a key that someone adds to the allow-list by mistake; no
such key is part of the file today.

The file is meant to be attached to a bug report. Take a quick look at it before you do, as you would with any file that
leaves your system.

## Next steps

If the file shows a device in `pending` or `blocked`, an instance that is `online: false` or a `tripped` breaker, the
[troubleshooting page](troubleshooting.md) explains each case.
