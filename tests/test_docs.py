"""Documentation checks: the README says what the code does (D-16)."""

import re
from pathlib import Path

README = Path(__file__).resolve().parent.parent / "README.md"


def _normalize(text: str) -> str:
    """Return text with whitespace collapsed and lower-cased."""
    return re.sub(r"\s+", " ", text).lower()


def _bullets(text: str) -> list[str]:
    """Return the list items of a markdown text: a line starting with a dash plus the indented lines after it."""
    items: list[str] = []
    for line in text.splitlines():
        if line.startswith("- "):
            items.append(line)
        elif items and line.startswith("  ") and line.strip():
            items[-1] += f" {line.strip()}"
    return [_normalize(item) for item in items]


def test_readme_states_what_the_approval_hash_binds() -> None:
    """The approval bullet names the startup flag, run mode and circuit breaker limits, and the one-time lapse."""
    text = README.read_text(encoding="utf-8")
    bullet = next((item for item in _bullets(text) if "bound to the hash" in item), None)
    assert bullet is not None, "the README has no bullet that says the approval is bound to the hash"
    for phrase in ("actions", "startup flag", "run mode", "circuit breaker limits"):
        assert phrase in bullet, f"the approval bullet never names {phrase}"
    assert "lapse once" in _normalize(text)
