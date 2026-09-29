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

# Protocol path segment of every topic (D-01); bumping it is a breaking protocol change
TOPIC_VERSION: Final = "v1"

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
STORE_SAVE_DELAY: Final = 5.0

# Logging: unknown payloads are logged as a truncated repr so a payload cannot grow or forge a log line
MAX_LOGGED_PAYLOAD_LENGTH: Final = 40

# Trigger names shown in Repairs issues (same labels as the action fields of the subentry dialog)
TRIGGER_ON: Final = "onChangeToOn"
TRIGGER_OFF: Final = "onChangeToOff"
TRIGGER_SETUP: Final = "setup"

# Repairs issues
ISSUE_ACTION_FAILED_PREFIX: Final = "action_failed_"
ISSUE_CIRCUIT_BREAKER_PREFIX: Final = "circuit_breaker_"
ISSUE_DISCOVERY_DISABLED: Final = "mqtt_discovery_disabled"
MAX_ISSUE_ERROR_LENGTH: Final = 500
