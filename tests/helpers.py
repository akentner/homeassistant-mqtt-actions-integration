"""
Helpers shared by several test modules (D-11).

Test modules import shared helpers only from here, never from each other.
"""

from __future__ import annotations

# The documented diagnostics key sets; an unknown key fails the test, which is the point (D-17)
TOP_KEYS = {"integration_version", "hub", "roster", "devices"}
HUB_KEYS = {"base_topic", "instance_name", "instance_id", "instance_mode"}
ROSTER_KEYS = {"id", "name", "version", "last_seen", "online"}
DEVICE_KEYS = {"uuid", "kind", "origin", "owner", "mode", "effective_mode", "approval", "breaker", "rev", "hash"}
