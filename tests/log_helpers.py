"""Helpers to read the log records of a test without picking up foreign loggers."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

OWN_LOGGER = "custom_components.mqtt_actions"


def own_warnings(caplog: pytest.LogCaptureFixture, *, exact: bool = False) -> list[logging.LogRecord]:
    """
    Return the WARNING (exact) or WARNING-and-above records of the integration's own loggers.

    A full test run under load makes asyncio log "Executing <task> took 0.1 seconds" at WARNING; those records belong
    to no code under test and must never decide an assertion about what the integration logged.
    """
    return [
        record
        for record in caplog.records
        if record.name.startswith(OWN_LOGGER)
        and (record.levelno == logging.WARNING if exact else record.levelno >= logging.WARNING)
    ]
