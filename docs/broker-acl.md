# Broker ACL for MQTT Actions

MQTT has no per-message authentication. The only real access control between the clients of a broker is the broker's
own access control list (ACL). This page gives a Mosquitto example, states what it can and cannot enforce, and lists
what to do besides it.

The example below is not just prose: the broker test suite (`tests/broker/test_acl.py`) starts a real Mosquitto with
exactly this block, with the two instance id markers replaced, and checks that the allowed publishes arrive and the
denied ones reach nobody. The text you copy is the text that was tested.

## Why an ACL matters

- Anyone who can publish to a device's **state topic** can trigger the actions of that device on every Home Assistant
  instance that approved the device.
- The **test topic** (`<base topic>/v1/devices/<device uuid>/test`) is a second way to trigger them: a message there
  runs the actions of a trigger without changing the state. Every instance that approved the device runs them.
- The **re-trigger topic** (`<base topic>/v1/devices/<device uuid>/retrigger`) is a third way: a message there runs the
  actions of a device again on every instance that approved it, like the test topic, and every instance answers on the
  acknowledgement topic of the requester. It carries a state of the device, never actions.
- Anyone who can write a **config topic** can make a device appear on the other instances. A foreign device is only a
  read-only mirror that runs nothing until a user approved its exact actions on that instance, but the user still
  gets an approval request they never expected.
- Anyone who can write the **discovery prefix** can create, change or remove entities of every instance that listens
  to MQTT Discovery.
- Anyone who can **read** a config topic can read the actions of every device (see the limits below).

## Topics

| Topic | Written by | Retained | Read by |
|-------|------------|----------|---------|
| `<base topic>/v1/devices/<device uuid>/config` | the owner instance only (a tombstone is an empty retained message) | yes | every instance |
| `<base topic>/v1/devices/<device uuid>/state` | any instance, and external publishers you trust | yes | every instance |
| `<base topic>/v1/devices/<device uuid>/test` | any instance (test buttons) | no | every instance |
| `<base topic>/v1/devices/<device uuid>/retrigger` | any instance (the re-trigger service) | no | every instance |
| `<base topic>/v1/instances/<instance id>/availability` | that instance only | yes | every instance |
| `<base topic>/v1/instances/<instance id>/heartbeat` | that instance only (every 30 seconds) | no | every instance |
| `<base topic>/v1/instances/<requester id>/acks` | any instance (its answer to a re-trigger of that requester) | no | the requester only |
| `<discovery prefix>/device/<device uuid>/config` | the owner instance, and core MQTT of any instance that deletes the entity | yes | every instance |

The base topic is `mqtt_actions` by default, the discovery prefix is `homeassistant` by default. Adjust both lines if you
changed them. The instance id of an instance is the segment of its retained availability topic
(`mosquitto_sub -v -t 'mqtt_actions/v1/instances/+/availability'` lists them) and the `instance_id` value in the data
of its hub entry. The example uses one MQTT user per instance.

## Example (Mosquitto)

Each Home Assistant instance gets its own MQTT user, here `ha_one` and `ha_two`, and an external publisher such as a
bridge or a sensor gateway gets the user `bridge`. Replace the two markers `<instance-id-one>` and
`<instance-id-two>` with the instance ids of your instances and add one block per further instance.

```acl
# Home Assistant instance one
user ha_one
topic readwrite mqtt_actions/v1/devices/+/config
topic readwrite mqtt_actions/v1/devices/+/state
topic readwrite mqtt_actions/v1/devices/+/test
topic readwrite mqtt_actions/v1/devices/+/retrigger
topic readwrite homeassistant/#
topic read mqtt_actions/v1/instances/+/availability
topic write mqtt_actions/v1/instances/<instance-id-one>/availability
topic read mqtt_actions/v1/instances/+/heartbeat
topic write mqtt_actions/v1/instances/<instance-id-one>/heartbeat
topic read mqtt_actions/v1/instances/<instance-id-one>/acks
topic write mqtt_actions/v1/instances/+/acks

# Home Assistant instance two
user ha_two
topic readwrite mqtt_actions/v1/devices/+/config
topic readwrite mqtt_actions/v1/devices/+/state
topic readwrite mqtt_actions/v1/devices/+/test
topic readwrite mqtt_actions/v1/devices/+/retrigger
topic readwrite homeassistant/#
topic read mqtt_actions/v1/instances/+/availability
topic write mqtt_actions/v1/instances/<instance-id-two>/availability
topic read mqtt_actions/v1/instances/+/heartbeat
topic write mqtt_actions/v1/instances/<instance-id-two>/heartbeat
topic read mqtt_actions/v1/instances/<instance-id-two>/acks
topic write mqtt_actions/v1/instances/+/acks

# External publisher: may set a device state and nothing else
user bridge
topic readwrite mqtt_actions/v1/devices/+/state
```

Use it with `allow_anonymous false`, a `password_file` and `acl_file <path to the file>` in `mosquitto.conf`. A user
without a block has no access at all, so a client that is not listed cannot read or write any of these topics.

What it enforces:

- Each instance writes only its own availability topic: `ha_two` cannot announce `ha_one` online or offline.
- Each instance writes only its own heartbeat topic and reads all of them. The external publisher has no access to any
  heartbeat topic, in either direction.
- The external publisher can write the state topic and read it back. It cannot write config, test, re-trigger,
  discovery or any availability topic, and it cannot read the config documents that carry the actions.
- Only Home Assistant users reach the test topic, the re-trigger topic and the discovery prefix.
- Each instance reads only the acknowledgement topic of its own instance id, so the answers to a re-trigger of
  `ha_one` are readable by `ha_one` and not by `ha_two`. Every instance may write the acknowledgement topic of any
  requester, because it has to answer whoever asked. The external publisher has no access to any acknowledgement topic.

## Limits

The ACL cannot do everything, and the example does not pretend to:

- **Ownership is cooperative within the group of Home Assistant users.** The topic of a config document contains the
  device uuid, not the owner, and device uuids are random and unknown when you write the ACL. The ACL therefore cannot
  say "only the owner of this device writes this config topic". Any Home Assistant instance with the access above can
  overwrite the config topic of any device, including by writing an empty retained message (a forged tombstone).
  Instances pin the first owner they saw and republish their own documents, and they raise Repairs issues for a
  conflict, but that is cooperation, not enforcement. Put only instances you trust into the Home Assistant group.
- **Adoption and import put content under the administrator's responsibility.** An adopted device and an imported
  device are owned by the instance that took them, so they run there without an approval, and no ACL can judge their
  actions. Read what you adopt or import; see [docs/operations.md](operations.md).
- **The approval gate is the real control.** A document from another instance never runs on an instance before the user
  approved its exact actions there. A forged document can make approval requests appear or make mirrors disappear and
  reappear, which forces a new approval, but it cannot run an action.
- **Home Assistant instances need write access to the discovery prefix.** Core MQTT clears the retained discovery topic
  when a user deletes an entity, and the owner republishes it. With a read-only prefix that clearing is denied and
  the entity stays gone for everyone. Core MQTT also publishes its birth and will messages below `homeassistant/`.
- **The heartbeat shows who is there.** It carries the instance name, the integration version and the number of owned
  devices, and every Home Assistant user of the group can read it, like the availability topic. It is not retained, so
  a late subscriber receives none and a crashed instance cannot look current: a peer counts as offline after 90 seconds
  without a heartbeat. Do not grant the heartbeat topics to external publishers.
- **The test topic is a trigger source** next to the state topic. Do not grant it to external publishers unless you
  want them to run actions.
- **The re-trigger topic is a trigger source** too. It is not retained, so a late subscriber receives nothing and a
  stale request cannot run later; a receiver also drops requests older than 60 seconds, repeated request ids and more
  than one request per device every 5 seconds, and it runs only what its own approval, mode and circuit breaker allow.
  Do not grant it to external publishers.
- **Acknowledgements are advisory.** Any Home Assistant user of the group can write the acknowledgement topic of any
  requester and so can forge an answer. An acknowledgement only shows the requester who answered; it never causes an
  action to run.
- **A denied publish is not reported visibly.** A broker may acknowledge a denied QoS 1 publish like an accepted one, and
  Home Assistant shows nothing in its log. When you verify your ACL, read the retained state back with a second client
  instead of waiting for an error.
- **Changing the MQTT discovery prefix at runtime needs a reload** of the integration, and an ACL change for the new
  prefix.
- The ACL covers the topics of this integration only. Core MQTT and your other integrations need their own entries.

## Transport and secrets

- Use TLS on the broker listener and verify the certificate in the Home Assistant MQTT integration, so credentials and
  documents are not readable on the network.
- Use one MQTT user per instance, as in the example, and never share the password of an instance.
- **Actions are readable by every subscriber of a config topic**, because the document carries the full action
  sequence. Do not put secrets such as tokens or passwords into actions; keep them in the Home Assistant secrets of
  the instance that needs them, or restrict read access to the config topics to the Home Assistant users, as the
  example does.
