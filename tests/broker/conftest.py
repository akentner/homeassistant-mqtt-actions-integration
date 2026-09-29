"""Fixtures for tests against a real Mosquitto broker (no Home Assistant involved)."""

import shutil
import socket
import subprocess
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

STARTUP_TIMEOUT = 5.0


def _free_port() -> int:
    """Return a TCP port on 127.0.0.1 that is free right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_port(port: int, process: subprocess.Popen[bytes]) -> None:
    """Poll until the broker accepts connections; fail early when the process exits."""
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(f"mosquitto exited early with code {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    pytest.fail(f"mosquitto did not accept connections on port {port} within {STARTUP_TIMEOUT} seconds")


@pytest.fixture
def mosquitto_port(socket_enabled: None, tmp_path: Path) -> Iterator[int]:
    """
    Start a throwaway anonymous Mosquitto on a free local port; skip when mosquitto is not installed.

    The Home Assistant test plugin blocks sockets by default, so the pytest-socket fixture enables them here.
    """
    executable = shutil.which("mosquitto")
    if executable is None:
        pytest.skip("mosquitto is not installed")
    port = _free_port()
    config = tmp_path / "mosquitto.conf"
    config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
    process = subprocess.Popen(  # noqa: S603
        [executable, "-c", str(config)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(port, process)
        yield port
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
