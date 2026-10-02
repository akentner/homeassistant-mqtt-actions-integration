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
| `<base topic>/v1/instances/<instance id>/availability` | that instance only | yes | every instance |
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
topic readwrite homeassistant/#
topic read mqtt_actions/v1/instances/+/availability
topic write mqtt_actions/v1/instances/<instance-id-one>/availability

# Home Assistant instance two
user ha_two
topic readwrite mqtt_actions/v1/devices/+/config
topic readwrite mqtt_actions/v1/devices/+/state
topic readwrite mqtt_actions/v1/devices/+/test
topic readwrite homeassistant/#
topic read mqtt_actions/v1/instances/+/availability
topic write mqtt_actions/v1/instances/<instance-id-two>/availability

# External publisher: may set a device state and nothing else
user bridge
topic readwrite mqtt_actions/v1/devices/+/state
```

Use it with `allow_anonymous false`, a `password_file` and `acl_file <path to the file>` in `mosquitto.conf`. A user
without a block has no access at all, so a client that is not listed cannot read or write any of these topics.

What it enforces:

- Each instance writes only its own availability topic: `ha_two` cannot announce `ha_one` online or offline.
- The external publisher can write the state topic and read it back. It cannot write config, test, discovery or any
  availability topic, and it cannot read the config documents that carry the actions.
- Only Home Assistant users reach the test topic and the discovery prefix.

## Limits

The ACL cannot do everything, and the example does not pretend to:

- **Ownership is cooperative within the group of Home Assistant users.** The topic of a config document contains the
  device uuid, not the owner, and device uuids are random and unknown when you write the ACL. The ACL therefore cannot
  say "only the owner of this device writes this config topic". Any Home Assistant instance with the access above can
  overwrite the config topic of any device, including by writing an empty retained message (a forged tombstone).
  Instances pin the first owner they saw and republish their own documents, and they raise Repairs issues for a
  conflict, but that is cooperation, not enforcement. Put only instances you trust into the Home Assistant group.
- **The approval gate is the real control.** A document from another instance never runs on an instance before the user
  approved its exact actions there. A forged document can make approval requests appear or make mirrors disappear and
  reappear, which forces a new approval, but it cannot run an action.
- **Home Assistant instances need write access to the discovery prefix.** Core MQTT clears the retained discovery topic
  when a user deletes an entity, and the owner republishes it. With a read-only prefix that clearing is denied and
  the entity stays gone for everyone. Core MQTT also publishes its birth and will messages below `homeassistant/`.
- **The test topic is a trigger source** next to the state topic. Do not grant it to external publishers unless you
  want them to run actions.
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
