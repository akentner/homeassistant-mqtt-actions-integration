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

# Adoption of an orphaned device (D-09): the transfer marker of a document lists at most this many previous owners,
# newest last; older ones fall off. An absent marker means the device was never adopted
MAX_TRANSFER_HISTORY: Final = 8

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
# device id -> the instance ids that owned an adopted device before, newest last; published as `transferred_from` with
# every document of the device so a follower that missed the adoption learns it (D-09)
STORE_TRANSFERS: Final = "transfers"
# The native entity switch of Phase 5 (D-03): a dict with `instance` (bool, the owned devices of this instance are
# native), `pending` (owned device ids whose takeover is still to run) and `devices` (owned device ids that are native
# although the instance flag is not set); local to this instance, never part of a document
STORE_NATIVE: Final = "native"
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
# Duplicate instance id (D-07, assumption A12): this many heartbeats with this instance's own id and another session,
# heard within HEARTBEAT_OFFLINE_SECONDS, confirm that a clone or a restored copy shares the id; at most this many
# observations are kept, so a flood of forged heartbeats cannot grow the record
DUPLICATE_ID_CONFIRMATIONS: Final = 2
MAX_DUPLICATE_OBSERVATIONS: Final = 8
# Largest accepted broker message of the operations protocol (heartbeat, re-trigger request and acknowledgement),
# measured in characters and in UTF-8 bytes before anything is parsed (D-05, T-04-11)
MAX_BROKER_MESSAGE_BYTES: Final = 1024
# Largest device count a heartbeat may claim; anything above is not a heartbeat of this integration (D-05)
MAX_HEARTBEAT_DEVICES: Final = 10000
# Dispatcher signal sent when the roster changed; formatted with the config entry id (D-05, D-06)
SIGNAL_ROSTER_UPDATED: Final = f"{DOMAIN}_roster_updated_{{}}"

# Native cutover (D-09, D-10, MIG-02): this long after the start, and again whenever the roster changes, an instance
# that still uses MQTT Discovery checks whether any online peer is a legacy instance. The time only has to cover the
# replay of the retained availability messages at subscribe; the capability itself is read from the heartbeats
CUTOVER_SETTLE_SECONDS: Final = 5.0
# One warning issue on the waiting instance names the peers that keep it from switching; at most this many are named
ISSUE_NATIVE_CUTOVER_WAITING: Final = "native_cutover_waiting"
CUTOVER_HINT_MAX_NAMES: Final = 5

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
# The accepted state of one device changed (native entities write their state); formatted with the entry id and the
# device id
SIGNAL_DEVICE_STATE: Final = f"{DOMAIN}_device_state_{{}}_{{}}"

# Names of the services of the integration, registered once at the integration setup (D-12)
SERVICE_RESYNC: Final = "resync"
SERVICE_EXPORT_DEVICES: Final = "export_devices"
SERVICE_IMPORT_DEVICES: Final = "import_devices"
SERVICE_RETRIGGER: Final = "retrigger"
SERVICE_ADOPT_DEVICE: Final = "adopt_device"
# Reason codes of a refused adoption (D-10); the service turns each into the translated error `adopt_<reason>`
ADOPT_NOT_A_MIRROR: Final = "not_a_mirror"
ADOPT_NOT_APPROVED: Final = "not_approved"
ADOPT_OWNER_NOT_OFFLINE: Final = "owner_not_offline"

# Export document (D-11): the format name and version let a later reader tell versions apart; the file lives only in
# this directory below the configuration directory, never in www, which Home Assistant serves without authentication
EXPORT_FORMAT: Final = "mqtt_actions_export"
EXPORT_VERSION: Final = 1
EXPORT_DIRECTORY: Final = "mqtt_actions"

# Limits of one import call (D-11, T-04-38): the device count matches MAX_MIRRORS, the byte cap holds for the whole JSON
# and each device is still capped by MAX_DOCUMENT_BYTES
MAX_IMPORT_DEVICES: Final = 100
MAX_IMPORT_BYTES: Final = 4 * 1024 * 1024

# Minimum time between two accepted resyncs (D-12): a held button or a looping automation cannot queue unbounded
# republishes; measured on Manager.clock
RESYNC_MIN_INTERVAL_SECONDS: Final = 5.0

# Re-trigger (D-01 to D-04): the caller collects acknowledgements for at most this long and leaves early when every
# expected instance answered; one accepted request per device per interval on the caller and on a receiver; a receiver
# remembers this many request ids; a request older than the maximum age, or sent that far into the future, is dropped
# (which is also the clock-skew tolerance between instances). All fixed, none user-configurable.
RETRIGGER_ACK_WINDOW_SECONDS: Final = 5.0
RETRIGGER_DEVICE_INTERVAL_SECONDS: Final = 5.0
RETRIGGER_SEEN_LIMIT: Final = 128
RETRIGGER_MAX_AGE_SECONDS: Final = 60.0
# Status words of an acknowledgement; no_answer is only ever produced by the caller and never sent on the wire (D-03)
ACK_EXECUTED: Final = "executed"
ACK_NOT_APPROVED: Final = "not_approved"
ACK_PAUSED: Final = "paused"
ACK_OBSERVING: Final = "observing"
ACK_DISABLED: Final = "disabled"
ACK_ERROR: Final = "error"
ACK_NO_ANSWER: Final = "no_answer"
# Reason words that accompany a status; short codes, never free text
REASON_UNKNOWN_DEVICE: Final = "unknown_device"
REASON_BAD_STATE: Final = "bad_state"
REASON_NO_ACTIONS: Final = "no_actions"
REASON_NOT_RUNNABLE: Final = "not_runnable"
REASON_OFFLINE: Final = "offline"
# Reasons the caller refuses a re-trigger with, before anything is sent; they never appear on the wire
REASON_RATE_LIMITED: Final = "rate_limited"
REASON_NO_STATE: Final = "no_state"

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
# Another instance shares this instance's id, for example a clone or a restored backup; fixable, one per instance (D-07)
ISSUE_DUPLICATE_INSTANCE_ID: Final = "duplicate_instance_id"
# An old owner recognized that another instance adopted one of its devices; fixable, one per device (D-09)
ISSUE_TRANSFERRED_PREFIX: Final = "transferred_"
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
    ISSUE_TRANSFERRED_PREFIX,
)
MAX_ISSUE_ERROR_LENGTH: Final = 500
