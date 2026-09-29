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
CONF_DEVICE_ID: Final = "device_id"
CONF_ON_CHANGE_TO_ON: Final = "on_change_to_on"
CONF_ON_CHANGE_TO_OFF: Final = "on_change_to_off"
CONF_RUN_ON_STARTUP: Final = "run_on_startup"

# Switch payload contract (D-02)
PAYLOAD_ON: Final = "ON"
PAYLOAD_OFF: Final = "OFF"

# Persistent store
STORE_KEY: Final = f"{DOMAIN}.state"
STORE_VERSION: Final = 1
STORE_LAST_ACTED: Final = "last_acted"
STORE_PUBLISHED: Final = "published"
STORE_SAVE_DELAY: Final = 5.0

# Logging: unknown payloads are logged as a truncated repr so a payload cannot grow or forge a log line
MAX_LOGGED_PAYLOAD_LENGTH: Final = 40

# Repairs issues
ISSUE_ACTION_FAILED_PREFIX: Final = "action_failed_"
ISSUE_DISCOVERY_DISABLED: Final = "mqtt_discovery_disabled"
MAX_ISSUE_ERROR_LENGTH: Final = 500
