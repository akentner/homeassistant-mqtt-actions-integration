# MQTT Actions 1.0.1

A hardening release for 1.0.0. It fixes how mirrored devices that run as native entities behave after a restart and after a
replay of old MQTT Discovery messages, and it adds a guard against MQTT duplicates of native devices.

## Fixes

- A mirrored device that runs as a native entity stays native after a restart, also when the central config document is near
  its size limit.
- A retained legacy MQTT Discovery message that the broker replays at start no longer leaves a working `_2` duplicate entity.
  Entity ids and registry ids of the migrated entities are kept.
- The start-up replay now also cleans up when earlier MQTT duplicates of the same devices were already disabled. Leftover
  disabled `_2` entities and the old MQTT device entries are removed at the next start.
- A duplicate guard runs on every instance with native devices: an enabled core MQTT entity created for a native device (for
  example from a Discovery export on the `homeassistant` prefix) is disabled, and entries you customized are kept.

## Behavior change

- Core MQTT duplicates of native devices are disabled automatically. A duplicate that you re-enable is
  disabled again at the next start.
- At start, an instance removes the disabled MQTT duplicates of its native devices when nothing is retained on their Discovery
  topic, and keeps them while a Discovery export sits on that topic. While the old Discovery message is still retained, only
  the instance that owns the device removes its duplicates and clears the message, and only when no online instance still
  keeps a renamed or otherwise customized MQTT entity of that device; instances announce such entities in their heartbeat.
- Instances that follow the device keep their disabled duplicates until the owner has cleared the old message and then remove
  them in the same run. A customized MQTT entity is kept on every instance.

## Known limitations

- A live replay of legacy Discovery, published while Home Assistant runs, creates `_2` entities that disappear
  only after the next start.
- If a broker restart without persistence and a Home Assistant start fall into the same few seconds, another instance's
  Discovery export on the core prefix can be cleared until that instance publishes it again.
- While an instance that is online runs a version older than 1.0.1, the old Discovery message and the disabled duplicates
  stay, because that instance does not announce which MQTT entities it keeps. They go once every online instance runs 1.0.1.
- While the instance that owns a device is offline, its old Discovery message and the disabled duplicates on the other
  instances stay.
- An MQTT entity that you customize at the very moment the owner clears the old Discovery message is not protected.
- The one-time clear of the old Discovery message when the owner switches a device to native entities, and its retry after a
  reconnect or a resync, is not held back by customized MQTT entities on other instances; such an entity then stays in the
  entity registry without a state until that instance takes it over.

## Upgrade

No breaking change. Update from 1.0.0 through HACS. The minimum Home Assistant version is still 2026.9.0.

**Full changelog:** https://github.com/akentner/homeassistant-mqtt-actions-integration/compare/v1.0.0...v1.0.1

