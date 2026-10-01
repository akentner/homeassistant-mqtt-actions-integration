"""Fixtures for tests against a real Mosquitto broker (no Home Assistant involved)."""

import shutil
import socket
import subprocess
import time
from contextlib import ExitStack, contextmanager
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
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


@contextmanager
def _run_broker(config: Path, port: int) -> Iterator[None]:
    """Run a Mosquitto with the given config file until the block ends."""
    executable = shutil.which("mosquitto")
    if executable is None:
        pytest.skip("mosquitto is not installed")
    process = subprocess.Popen(  # noqa: S603
        [executable, "-c", str(config)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for_port(port, process)
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


@pytest.fixture
def mosquitto_port(socket_enabled: None, tmp_path: Path) -> Iterator[int]:
    """
    Start a throwaway anonymous Mosquitto on a free local port; skip when mosquitto is not installed.

    The Home Assistant test plugin blocks sockets by default, so the pytest-socket fixture enables them here.
    """
    port = _free_port()
    config = tmp_path / "mosquitto.conf"
    config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
    with _run_broker(config, port):
        yield port


@pytest.fixture
def start_acl_broker(socket_enabled: None, tmp_path: Path) -> Iterator[Callable[[str, Mapping[str, str]], int]]:
    """
    Return a factory that starts a Mosquitto with a password file and an ACL file; skips without the binaries.

    The factory takes the ACL text and a mapping of user name to password and returns the port. Every broker it started
    is stopped at teardown. Anonymous access is off, so the ACL is the only thing that decides what a user may do.
    """
    if shutil.which("mosquitto") is None or shutil.which("mosquitto_passwd") is None:
        pytest.skip("mosquitto or mosquitto_passwd is not installed")
    stack = ExitStack()

    def _start(acl_text: str, users: Mapping[str, str]) -> int:
        port = _free_port()
        passwords = tmp_path / f"passwords-{port}"
        acl = tmp_path / f"acl-{port}"
        acl.write_text(acl_text)
        acl.chmod(0o600)
        for index, (name, password) in enumerate(users.items()):
            # The first call creates the file (-c), the others add to it
            flags = ["-b", "-c"] if index == 0 else ["-b"]
            subprocess.run(  # noqa: S603
                ["mosquitto_passwd", *flags, str(passwords), name, password],  # noqa: S607
                check=True,
                capture_output=True,
            )
        passwords.chmod(0o600)
        config = tmp_path / f"mosquitto-{port}.conf"
        config.write_text(
            f"listener {port} 127.0.0.1\n"
            "allow_anonymous false\n"
            "persistence false\n"
            f"password_file {passwords}\n"
            f"acl_file {acl}\n"
        )
        stack.enter_context(_run_broker(config, port))
        return port

    with stack:
        yield _start
