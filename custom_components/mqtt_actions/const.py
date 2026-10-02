"""Constants for the MQTT Actions integration."""

import logging
from typing import Final

DOMAIN: Final = "mqtt_actions"
LOGGER: Final = logging.getLogger(__package__)

# Hub config entry data
CONF_BASE_TOPIC: Final = "base_topic"
CONF_INSTANCE_NAME: Final = "instance_name"
CONF_INSTANCE_ID: Final = "instance_id"
DEFAULT_BASE_TOPIC: Final = "mqtt_actions"
# Hub config entry option (D-11): delete every owned device from the broker when the hub is removed; default keep
CONF_DELETE_DEVICES_ON_REMOVE: Final = "delete_devices_on_remove"

# Protocol path segment of every topic (D-01); bumping it is a breaking protocol change
TOPIC_VERSION: Final = "v1"
# Version of the central config document (D-12, D-14); a reader rejects a higher one and migrates a lower one
SCHEMA_VERSION: Final = 1

# Subentry types and subentry data keys (D-03)
SUBENTRY_SWITCH: Final = "switch"
SUBENTRY_SELECT: Final = "select"
CONF_DEVICE_ID: Final = "device_id"
CONF_ON_CHANGE_TO_ON: Final = "on_change_to_on"
CONF_ON_CHANGE_TO_OFF: Final = "on_change_to_off"
CONF_RUN_ON_STARTUP: Final = "run_on_startup"
CONF_OPTIONS: Final = "options"
CONF_STATE_VALUE: Final = "state_value"
CONF_FRIENDLY_NAME: Final = "friendly_name"
CONF_ACTIONS: Final = "actions"

# Run mode and circuit breaker settings of a device (D-10, D-14); missing keys in stored data mean the defaults
CONF_RUN_MODE: Final = "run_mode"
RUN_MODE_SERIAL: Final = "serial"
RUN_MODE_RESTART: Final = "restart"
CONF_BREAKER_MAX_RUNS: Final = "breaker_max_runs"
CONF_BREAKER_WINDOW: Final = "breaker_window"
DEFAULT_BREAKER_MAX_RUNS: Final = 5
DEFAULT_BREAKER_WINDOW: Final = 10
# Serial runs queue up to this many per device; more are dropped and logged. Fixed, not user-configurable (D-12)
SERIAL_QUEUE_LIMIT: Final = 10

# Select option limits enforced by the UI flow (A1, T-02-20): a Select needs at least two options to be a choice
MIN_OPTIONS: Final = 2
MAX_OPTIONS: Final = 50
MAX_TEXT_LENGTH: Final = 64
# Ranges accepted for the breaker settings in the UI flow (A7, T-02-21)
BREAKER_MAX_RUNS_LIMIT: Final = 100
BREAKER_WINDOW_LIMIT: Final = 3600

# Limits on a config document received from the broker (D-06, T-03-02): measured in UTF-8 bytes before it is parsed,
# and in container levels (list and dict nesting, not action steps) of an action list; a nested choose costs about four
MAX_DOCUMENT_BYTES: Final = 256 * 1024
MAX_ACTION_DEPTH: Final = 32

# A follower mirrors at most this many foreign devices; worst-case Store growth is MAX_MIRRORS * MAX_DOCUMENT_BYTES
# (A2, T-03-16)
MAX_MIRRORS: Final = 100

# Services that actions received from the broker may never call (D-03); owned actions stay unrestricted. A fixed
# constant the user cannot change. Whole domains, then exact service names; all lower case, as core normalizes them.
DENIED_DOMAINS: Final = frozenset(
    {"shell_command", "python_script", "rest_command", "command_line", "hassio", "backup"}
)
DENIED_SERVICES: Final = frozenset(
    {
        "homeassistant.restart",
        "homeassistant.stop",
        "homeassistant.reload_all",
        "homeassistant.reload_core_config",
        "homeassistant.reload_config_entry",
        "homeassistant.set_location",
        "homeassistant.save_persistent_states",
        "mqtt.publish",
        "mqtt.dump",
        "recorder.purge",
        "recorder.purge_entities",
        "recorder.disable",
        "update.install",
        "downloader.download_file",
        "logger.set_level",
        "logger.set_default_level",
        "system_log.clear",
    }
)
# Services the denylist cannot judge because they act on whatever entity they target (a script, scene or button, or an
# update or restart entity); they are never denied, but the approval view flags them as residual risk. Calls into the
# `script` domain are flagged as well. Best effort, like the denylist itself (WR-03).
RESIDUAL_SERVICES: Final = frozenset(
    {
        "automation.trigger",
        "button.press",
        "homeassistant.toggle",
        "homeassistant.turn_off",
        "homeassistant.turn_on",
        "scene.turn_on",
    }
)

# Component key prefix of the test button of a trigger; the key of the trigger follows (D-13)
BUTTON_KEY_PREFIX: Final = "test_"

# Switch payload contract (D-02)
PAYLOAD_ON: Final = "ON"
PAYLOAD_OFF: Final = "OFF"

# Persistent store
STORE_KEY: Final = f"{DOMAIN}.state"
STORE_VERSION: Final = 1
STORE_LAST_ACTED: Final = "last_acted"
STORE_PUBLISHED: Final = "published"
STORE_TRIPPED: Final = "tripped"
# device id -> {"rev": int, "hash": str}: the rev last published for a device and the content hash it belongs to (D-15)
STORE_REVS: Final = "revs"
# device id -> the received document text of a mirror; parsed again at every load, never trusted (D-08, T-03-19)
STORE_MIRRORS: Final = "mirrors"
# device id -> the actions hash the user approved on this instance; separate from the mirror records (D-02, A10)
STORE_APPROVALS: Final = "approvals"
# The mode of this instance and the modes of single devices (D-14): local words, only entries other than run are saved,
# never part of a config document or a hash
STORE_INSTANCE_MODE: Final = "instance_mode"
STORE_DEVICE_MODES: Final = "device_modes"
STORE_SAVE_DELAY: Final = 5.0

# Owner-side defense of the published truth (D-15, D-17, D-18): how many published content hashes per device count as
# the owner's own echo, and the minimum time between two republishes caused by foreign writes of one device
PUBLISHED_HASH_HISTORY: Final = 8
REPUBLISH_THROTTLE_SECONDS: Final = 60.0
# A follower deleting mirrored entities again and again is explained in Repairs after this many removals in the window
DISCOVERY_REMOVAL_HINT_COUNT: Final = 3
DISCOVERY_REMOVAL_HINT_WINDOW_SECONDS: Final = 600.0

# Instance presence tracked from the availability wildcard is capped so broker traffic with random ids cannot grow it
# without bound (D-16, A2, T-03-12)
MAX_TRACKED_INSTANCES: Final = 256

# Presence (D-05): every instance publishes a non-retained heartbeat this often, and a peer counts as offline after
# this long without one. The retained availability alone cannot show a crash, so the timeout is the liveness signal
HEARTBEAT_INTERVAL_SECONDS: Final = 30.0
HEARTBEAT_OFFLINE_SECONDS: Final = 90.0
# Largest accepted broker message of the operations protocol (heartbeat, re-trigger request and acknowledgement),
# measured in characters and in UTF-8 bytes before anything is parsed (D-05, T-04-11)
MAX_BROKER_MESSAGE_BYTES: Final = 1024
# Largest device count a heartbeat may claim; anything above is not a heartbeat of this integration (D-05)
MAX_HEARTBEAT_DEVICES: Final = 10000
# Dispatcher signal sent when the roster changed; formatted with the config entry id (D-05, D-06)
SIGNAL_ROSTER_UPDATED: Final = f"{DOMAIN}_roster_updated_{{}}"

# Per-device and per-instance mode (D-14): run is normal, observe tracks the baseline and logs what would have run, and
# disabled ignores the state topic completely. The effective mode is the most restrictive of the two. The existing
# run_mode (serial or restart) is a different thing and is untouched.
MODE_RUN: Final = "run"
MODE_OBSERVE: Final = "observe"
MODE_DISABLED: Final = "disabled"
MODES: Final = (MODE_RUN, MODE_OBSERVE, MODE_DISABLED)
# Dispatcher signals formatted with the config entry id: a mode changed (selects write their state again), and an owned
# device appeared or disappeared (the select platform adds or forgets its entity) (D-14, D-15)
SIGNAL_MODES_CHANGED: Final = f"{DOMAIN}_modes_changed_{{}}"
SIGNAL_DEVICES_CHANGED: Final = f"{DOMAIN}_devices_changed_{{}}"

# Names of the services of the integration, registered once at the integration setup (D-12)
SERVICE_RESYNC: Final = "resync"
SERVICE_EXPORT_DEVICES: Final = "export_devices"
SERVICE_IMPORT_DEVICES: Final = "import_devices"

# Export document (D-11): the format name and version let a later reader tell versions apart; the file lives only in
# this directory below the configuration directory, never in www, which Home Assistant serves without authentication
EXPORT_FORMAT: Final = "mqtt_actions_export"
EXPORT_VERSION: Final = 1
EXPORT_DIRECTORY: Final = "mqtt_actions"

# Minimum time between two accepted resyncs (D-12): a held button or a looping automation cannot queue unbounded
# republishes; measured on Manager.clock
RESYNC_MIN_INTERVAL_SECONDS: Final = 5.0

# A mirror whose config document was not seen again within this window after setup, a reconnect or the owner coming
# online is pruned, but only when its owner's availability says online (D-10, A2)
PRUNE_GRACE_SECONDS: Final = 30.0

# Logging: unknown payloads are logged as a truncated repr so a payload cannot grow or forge a log line
MAX_LOGGED_PAYLOAD_LENGTH: Final = 40

# Trigger names shown in Repairs issues (same labels as the action fields of the subentry dialog)
TRIGGER_ON: Final = "onChangeToOn"
TRIGGER_OFF: Final = "onChangeToOff"
TRIGGER_SETUP: Final = "setup"

# Repairs issues
ISSUE_ACTION_FAILED_PREFIX: Final = "action_failed_"
ISSUE_CIRCUIT_BREAKER_PREFIX: Final = "circuit_breaker_"
ISSUE_DOC_OVERWRITTEN_PREFIX: Final = "doc_overwritten_"
ISSUE_OWNERSHIP_CLAIM_PREFIX: Final = "ownership_claim_"
ISSUE_DISCOVERY_REMOVED_PREFIX: Final = "discovery_removed_"
# Follower side, D-17 and D-14: a second owner claims a mirrored device; a document has a newer schema than this
# integration understands
ISSUE_OWNER_CONFLICT_PREFIX: Final = "owner_conflict_"
ISSUE_SCHEMA_TOO_NEW_PREFIX: Final = "schema_too_new_"
# Too-new documents of devices without a mirror raise at most this many issues, so broker noise cannot flood Repairs
MAX_SCHEMA_TOO_NEW_ISSUES: Final = 10
# Approval view limits (A2): the YAML of the approval dialog is refused above this many characters instead of being
# shown truncated, at most this many templated service names are listed, and this many characters of the hash show
APPROVAL_YAML_MAX_CHARS: Final = 20000
APPROVAL_TEMPLATED_MAX_LINES: Final = 20
APPROVAL_HASH_PREFIX_LENGTH: Final = 12
# The blocked issue of a mirror names at most this many denied services
BLOCKED_SERVICES_MAX_SHOWN: Final = 10
# Approval of a mirror (D-02) and its blocked state (A6); both are deleted with the device
ISSUE_APPROVAL_PREFIX: Final = "approval_"
ISSUE_BLOCKED_PREFIX: Final = "blocked_"
# A templated service name of a mirror resolved to a denied service at run time (D-05)
ISSUE_DENIED_CALL_PREFIX: Final = "denied_call_"
ISSUE_DISCOVERY_DISABLED: Final = "mqtt_discovery_disabled"
# Every Repairs issue whose id is a prefix plus a device id; deleted with the device and with the hub. Later issue
# families of a device append their prefix here.
ISSUE_DEVICE_PREFIXES: Final = (
    ISSUE_ACTION_FAILED_PREFIX,
    ISSUE_CIRCUIT_BREAKER_PREFIX,
    ISSUE_DOC_OVERWRITTEN_PREFIX,
    ISSUE_OWNERSHIP_CLAIM_PREFIX,
    ISSUE_DISCOVERY_REMOVED_PREFIX,
    ISSUE_OWNER_CONFLICT_PREFIX,
    ISSUE_SCHEMA_TOO_NEW_PREFIX,
    ISSUE_DENIED_CALL_PREFIX,
    ISSUE_APPROVAL_PREFIX,
    ISSUE_BLOCKED_PREFIX,
)
MAX_ISSUE_ERROR_LENGTH: Final = 500
