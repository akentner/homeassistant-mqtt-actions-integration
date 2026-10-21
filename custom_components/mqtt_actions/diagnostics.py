"""
Diagnostics of the hub entry: structure, never content (OPS-04, D-17).

The file is meant to be attached to a bug report, so the result is built from an allow-list: every key is written here
by name and the builder never reads actions, options, state values, entity ids, service data, device names or the MQTT
config entry. Instance ids are cut to their first characters. `async_redact_data` runs over the finished result as a
safety net for a key that someone adds to the allow-list by mistake.

The local actions of mirrors appear as integers only (D-04, D-14): the builder takes the Manager's counts and never
receives a record, a label, a StateValue, an action, a Template, an error or a trace, so nothing depends on redaction.
"""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .document import build_content, content_hash

if TYPE_CHECKING:
    from collections.abc import Mapping

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .local_actions import LocalActionCounts
    from .manager import Device, Manager

# An instance id is shown by its first characters only; enough to tell instances apart, too short to be a handle
INSTANCE_ID_SHORT_LENGTH = 8

# Safety net, not the mechanism: the keys that carry action content, names or broker settings. They are not part of the
# result, and one that shows up anyway is replaced by the redaction marker
TO_REDACT = frozenset(
    {
        "actions",
        "on_change_to_on",
        "on_change_to_off",
        "options",
        "state_value",
        "friendly_name",
        "entity_id",
        "service",
        "data",
        "target",
        "password",
        "username",
        "host",
        "broker",
        "port",
    }
)


def _short(instance_id: str) -> str:
    """Return the shortened form of an instance id."""
    return instance_id[:INSTANCE_ID_SHORT_LENGTH]


def _hub(manager: Manager) -> dict[str, Any]:
    return {
        "base_topic": manager.base_topic,
        "instance_name": manager.instance_name,
        "instance_id": _short(manager.instance_id),
        "instance_mode": manager.instance_mode,
    }


def _roster(manager: Manager) -> list[dict[str, Any]]:
    """Return this instance and every known peer, online or not, by the documented fields only."""
    return [
        {
            "id": _short(row["id"]),
            "name": row["name"],
            "version": row["version"],
            "last_seen": row["last_seen"],
            "online": row["online"],
        }
        for row in manager.presence.rows()
    ]


def _local_actions(manager: Manager) -> dict[str, int]:
    """Return the instance-wide local action counts; devices without a mirror (orphan-only) are included."""
    counts = manager.local_action_counts()
    return {
        "devices": int(counts.devices),
        "triggers": int(counts.records),
        "orphaned_triggers": int(counts.inactive),
        "orphan_only_devices": int(counts.orphan_only_devices),
    }


def _device_row(manager: Manager, device: Device, local: Mapping[str, LocalActionCounts]) -> dict[str, Any]:
    """Return the allow-listed row of an owned device or a mirror; no name and no action content."""
    info = device.mirror
    counts = local.get(device.device_id)
    return {
        "uuid": device.device_id,
        "kind": device.spec.kind,
        "origin": "owned" if info is None else "mirror",
        "owner": _short(manager.instance_id if info is None else info.owner),
        "mode": manager.device_mode(device.device_id),
        "effective_mode": manager.effective_mode(device.device_id),
        "approval": str(manager.approval_state(device.device_id)),
        "breaker": "tripped" if device.breaker.tripped else "ok",
        # The content hash of the shared content, never the approval hash and never any action text
        "rev": manager.revision(device.device_id) if info is None else info.rev,
        "hash": content_hash(build_content(device.spec)) if info is None else info.content_hash,
        # How many triggers carry a local customization here, and how many of those match no current trigger
        "local_action_triggers": 0 if counts is None else int(counts.records),
        "local_action_orphans": 0 if counts is None else int(counts.inactive),
    }


def _devices(manager: Manager) -> list[dict[str, Any]]:
    local = manager.local_action_counts_by_device()
    return [_device_row(manager, device, local) for device in (*manager.devices.values(), *manager.mirrors.values())]


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:  # noqa: ARG001
    """Return the diagnostics of the hub entry: hub options, roster, device rows and the local action counts."""
    manager: Manager | None = getattr(entry, "runtime_data", None)
    if manager is None:
        return {"loaded": False}
    result = {
        "integration_version": manager.version,
        "hub": _hub(manager),
        "roster": _roster(manager),
        "devices": _devices(manager),
        "local_actions": _local_actions(manager),
    }
    return async_redact_data(result, TO_REDACT)
