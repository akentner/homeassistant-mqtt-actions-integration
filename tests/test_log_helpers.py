"""The log helper ignores foreign loggers, which made full test runs flaky under load."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from tests.log_helpers import own_warnings

if TYPE_CHECKING:
    import pytest


def test_own_warnings_ignores_the_slow_callback_warning_of_asyncio(caplog: pytest.LogCaptureFixture) -> None:
    """A slow-callback record of asyncio is not a warning of the integration."""
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("asyncio").warning("Executing <Task> took 0.125 seconds")
        logging.getLogger("custom_components.mqtt_actions.manager").warning("own warning")
        logging.getLogger("custom_components.mqtt_actions.manager").error("own error")

    assert [r.getMessage() for r in own_warnings(caplog, exact=True)] == ["own warning"]
    assert [r.getMessage() for r in own_warnings(caplog)] == ["own warning", "own error"]
