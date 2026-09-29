"""Smoke tests proving the dev toolchain resolved to the supported floor versions."""

import sys
from typing import TYPE_CHECKING

from homeassistant.const import __version__ as ha_version

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def test_python_floor() -> None:
    """Python must satisfy the Home Assistant 2026.9 requirement."""
    assert sys.version_info >= (3, 14, 2)


def test_home_assistant_floor() -> None:
    """Home Assistant must be at least the 2026.9.0 floor (tuple compare survives 2026.10)."""
    version = tuple(int(part) for part in ha_version.split(".")[:3])
    assert version >= (2026, 9, 0)


def test_probatio_importable() -> None:
    """Schema validation uses probatio, provided by Home Assistant core."""
    import probatio

    assert probatio is not None


async def test_hass_fixture_boots(hass: HomeAssistant) -> None:
    """The PHACC hass fixture starts a running Home Assistant instance."""
    assert hass.is_running
