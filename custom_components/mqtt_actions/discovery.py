"""MQTT Discovery payloads and their publisher."""

from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.json import json_dumps

from .const import BUTTON_KEY_PREFIX, DOMAIN, PAYLOAD_OFF, PAYLOAD_ON, SUBENTRY_SELECT
from .topics import availability_topic, config_topic, discovery_topic, state_topic, test_topic

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence

    from .model import DeviceSpec, TriggerSpec
    from .mqtt_gateway import MqttGateway


class AvailabilityState(StrEnum):
    """Payload of the retained instance availability topic; the empty payload removes the topic."""

    ONLINE = "online"
    OFFLINE = "offline"
    CLEARED = ""


def _literal(text: str) -> str:
    """
    Return a user string as a template string literal.

    JSON string escapes are valid Jinja string escapes, so hostile text (quotes, backslashes, braces, template
    delimiters, non-ASCII) stays data. User text is never concatenated into a template raw (T-02-01).
    """
    return json_dumps(text)


def build_value_template(options: Sequence[tuple[str, str]]) -> str:
    """
    Build the template that maps a broker payload (StateValue) to the friendly name shown in the UI.

    The payload is trimmed and lower-cased exactly like the tracker does (str.strip().lower()); an unknown payload
    renders empty, which core MQTT ignores without a warning, so the entity keeps its state (STA-07).
    """
    body = ", ".join(f"{_literal(value.lower())}: {_literal(friendly)}" for value, friendly in options)
    return "{{ {" + body + "}.get(value | trim | lower, '') }}"


def build_command_template(options: Sequence[tuple[str, str]]) -> str:
    """Build the template that maps the chosen friendly name back to the exact StateValue that is published (D-06)."""
    body = ", ".join(f"{_literal(friendly)}: {_literal(value)}" for value, friendly in options)
    return "{{ {" + body + "}.get(value, value) }}"


def _switch_component(topic: str, device_id: str) -> dict[str, Any]:
    """Return the switch component of a Switch device."""
    return {
        "platform": "switch",
        "unique_id": device_id,
        "name": None,
        # Command topic equals state topic: the state subscription is the only trigger source
        "state_topic": topic,
        "command_topic": topic,
        "retain": True,
        "qos": 1,
        "payload_on": PAYLOAD_ON,
        "payload_off": PAYLOAD_OFF,
        # Core compares the payload exactly; the tracker is case-insensitive, so the entity must be too
        "value_template": "{{ value | upper }}",
    }


def _select_component(topic: str, spec: DeviceSpec) -> dict[str, Any]:
    """Return the select component of a Select device: friendly names in the UI, StateValues on the broker (D-07)."""
    pairs = [(trigger.value, trigger.friendly_name) for trigger in spec.triggers.values()]
    return {
        "platform": "select",
        "unique_id": spec.device_id,
        "name": None,
        "state_topic": topic,
        "command_topic": topic,
        "retain": True,
        "qos": 1,
        "options": [friendly for _value, friendly in pairs],
        "value_template": build_value_template(pairs),
        "command_template": build_command_template(pairs),
    }


def button_component_key(key: str) -> str:
    """Return the component key of a trigger's test button; it contains no spaces, core splits ids on one."""
    return BUTTON_KEY_PREFIX + key


def _button_component(topic: str, device_id: str, trigger: TriggerSpec) -> dict[str, Any]:
    """
    Return the test button of a trigger.

    The button carries no logic: it publishes the exact StateValue, not retained, to the test topic and the manager
    runs that trigger's actions itself. The unique id derives from the immutable StateValue, so it survives renames.
    """
    return {
        "platform": "button",
        "unique_id": f"{device_id}_test_{trigger.key}",
        "name": f"Test {trigger.friendly_name}",
        "command_topic": topic,
        "payload_press": trigger.value,
        "retain": False,
        "qos": 1,
        # Keeps the buttons off auto-generated dashboards and lists them under Configuration (A4)
        "entity_category": "config",
    }


def build_discovery(
    *, spec: DeviceSpec, base_topic: str, instance_id: str, sw_version: str, retired: Collection[str] = ()
) -> dict[str, Any]:
    """
    Build the device-based discovery payload of a Switch or Select device (D-01, D-03, D-05).

    A component that is merely omitted is not removed by core MQTT discovery; only an explicit empty component
    config is. Every retired component key therefore gets the tombstone {"platform": "button"}.
    """
    topic = state_topic(base_topic, spec.device_id)
    components: dict[str, Any] = (
        {"select": _select_component(topic, spec)}
        if spec.kind == SUBENTRY_SELECT
        else {"switch": _switch_component(topic, spec.device_id)}
    )
    button_topic = test_topic(base_topic, spec.device_id)
    for trigger in spec.triggers.values():
        components[button_component_key(trigger.key)] = _button_component(button_topic, spec.device_id, trigger)
    components.update({key: {"platform": "button"} for key in sorted(retired)})
    return {
        "device": {"identifiers": [f"{DOMAIN}_{spec.device_id}"], "name": spec.name},
        "origin": {"name": "MQTT Actions", "sw_version": sw_version},
        "components": components,
        "availability": [{"topic": availability_topic(base_topic, instance_id)}],
    }


def build_export(*, spec: DeviceSpec, base_topic: str, instance_id: str, sw_version: str) -> dict[str, Any]:
    """
    Build the optional discovery export of a native device for external consumers (D-03, D-11).

    The same device block, origin and availability as the legacy payload, but one component only: no test buttons, no
    test topic and no tombstones. The component is disabled by default, so a Home Assistant that happens to listen to
    the export prefix creates a disabled duplicate instead of a second working entity.
    """
    topic = state_topic(base_topic, spec.device_id)
    if spec.kind == SUBENTRY_SELECT:
        key, component = "select", _select_component(topic, spec)
    else:
        key, component = "switch", _switch_component(topic, spec.device_id)
    component["enabled_by_default"] = False
    return {
        "device": {"identifiers": [f"{DOMAIN}_{spec.device_id}"], "name": spec.name},
        "origin": {"name": "MQTT Actions", "sw_version": sw_version},
        "components": {key: component},
        "availability": [{"topic": availability_topic(base_topic, instance_id)}],
    }


class DiscoveryPublisher:
    """Publishes discovery and availability messages through the gateway."""

    def __init__(self, gateway: MqttGateway, base_topic: str, sw_version: str) -> None:
        """Initialize the publisher."""
        self._gateway = gateway
        self._base_topic = base_topic
        self._sw_version = sw_version

    async def async_publish_device(self, *, spec: DeviceSpec, instance_id: str, retired: Collection[str] = ()) -> None:
        """Publish the retained discovery message of a Switch or Select device, tombstones included."""
        payload = build_discovery(
            spec=spec,
            base_topic=self._base_topic,
            instance_id=instance_id,
            sw_version=self._sw_version,
            retired=retired,
        )
        await self._gateway.async_publish(
            discovery_topic(self._gateway.discovery_prefix(), spec.device_id),
            json_dumps(payload),
            retain=True,
        )

    @property
    def discovery_prefix(self) -> str:
        """Return the discovery prefix core MQTT listens to."""
        return self._gateway.discovery_prefix()

    async def async_publish_export(self, *, spec: DeviceSpec, instance_id: str, prefix: str) -> None:
        """Publish the retained export of a native device on the export prefix; nothing ever heals it (D-11)."""
        payload = build_export(
            spec=spec, base_topic=self._base_topic, instance_id=instance_id, sw_version=self._sw_version
        )
        await self._gateway.async_publish(discovery_topic(prefix, spec.device_id), json_dumps(payload), retain=True)

    async def async_clear_export(self, device_id: str, prefix: str) -> None:
        """Clear the retained export of a device with the empty retained payload; a topic without one is a no-op."""
        await self._gateway.async_publish(discovery_topic(prefix, device_id), "", retain=True)

    async def async_publish_migrate(self, device_id: str) -> None:
        """
        Publish the live migrate payload that makes every core MQTT instance unload the entities of a device (D-12).

        Not retained, so a later subscriber never replays it. It goes out before the registry takeover; the empty
        retained clear follows only after, because on a loaded entity the clear alone deletes its registry entry.
        """
        await self._gateway.async_publish(
            discovery_topic(self._gateway.discovery_prefix(), device_id),
            json_dumps({"migrate_discovery": True}),
            retain=False,
        )

    async def async_clear_device(self, device_id: str) -> None:
        """Remove the device: an empty retained discovery payload makes core MQTT drop the entity (DSC-02)."""
        await self._gateway.async_publish(discovery_topic(self._gateway.discovery_prefix(), device_id), "", retain=True)

    async def async_publish_config(self, device_id: str, payload: str) -> None:
        """Publish the retained config document of an owned device (D-12)."""
        await self._gateway.async_publish(config_topic(self._base_topic, device_id), payload, retain=True)

    async def async_clear_config(self, device_id: str) -> None:
        """Clear the retained config document of a deleted device: the empty payload is the tombstone (D-09)."""
        await self._gateway.async_publish(config_topic(self._base_topic, device_id), "", retain=True)

    async def async_clear_state(self, device_id: str) -> None:
        """Clear the retained state of a deleted device so no stale ON or OFF stays on the broker."""
        await self._gateway.async_publish(state_topic(self._base_topic, device_id), "", retain=True)

    async def async_publish_availability(self, instance_id: str, state: AvailabilityState) -> None:
        """Publish the retained availability of this instance: online, offline or cleared."""
        await self._gateway.async_publish(availability_topic(self._base_topic, instance_id), str(state), retain=True)
