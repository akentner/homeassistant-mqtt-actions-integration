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
- At start, an instance removes the disabled MQTT duplicates of its native devices when the old Discovery message is still
  retained or nothing is retained on that topic. It keeps them while a Discovery export sits on that topic.
- The instance that owns a device clears a stale legacy Discovery message of it. Instances that follow the device then delete
  their remaining MQTT entities of it, customized ones included.

## Known limitations

- A live replay of legacy Discovery, published while Home Assistant runs, creates `_2` entities that disappear
  only after the next start.
- If a broker restart without persistence and a Home Assistant start fall into the same few seconds, another instance's
  Discovery export on the core prefix can be cleared until that instance publishes it again.

## Upgrade

No breaking change. Update from 1.0.0 through HACS. The minimum Home Assistant version is still 2026.9.0.

**Full changelog:** https://github.com/akentner/homeassistant-mqtt-actions-integration/compare/v1.0.0...v1.0.1
