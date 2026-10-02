"""
The execution-time half of the trust gate: a guard on the resolved service names of mirrored actions (D-03, D-05).

Static analysis cannot judge a templated service name, so a mirror's Script is built from a tree in which every
service-name template is a `GuardedTemplate`. Core renders that template through `Template.async_render` when it
prepares a service call (`helpers.service.async_prepare_call_from_config`), and the guard raises when the result is on
the denylist.

Version coupling, pinned by `test_denied_call_aborts_the_run_even_with_continue_on_error`: this works because core calls
`async_render` on the validated `Template` object of the step and lets an exception that is neither a
`HomeAssistantError` nor a `TemplateError` pass `continue_on_error`. If a future core stops doing either, that test
fails loudly; the documented fallback is to reject templated service names in mirrors altogether.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.template import Template
from homeassistant.util.yaml import dump as yaml_dump

from .const import APPROVAL_HASH_PREFIX_LENGTH, APPROVAL_TEMPLATED_MAX_LINES, APPROVAL_YAML_MAX_CHARS
from .document import approval_sections, canonical_json, escape_markdown, is_denied

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .manager import MirrorInfo
    from .model import DeviceSpec

# Shown in place of an empty list in the approval dialog; a dash is language neutral
EMPTY_LIST_TEXT = "\u2014"
# One templated name, residual kind or label is cut after this many characters in the approval dialog
_ITEM_MAX_CHARS = 200
# Character categories that never reach the approval dialog: control, format (bidi marks), surrogate, line and
# paragraph separators; newline and tab survive only inside the YAML
_DROPPED_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})
_FENCE_RUN = re.compile(r"`{3,}")

# Keys whose Template value is a service name; `service` is the legacy spelling that validation renames to `action`
GUARDED_KEYS = ("action", "service", "service_template")


class DeniedServiceCallError(Exception):
    """
    A templated service name resolved to a denied service.

    A plain `Exception` on purpose: core lets `continue_on_error` swallow a `HomeAssistantError`, including the one it
    builds from a `TemplateError`, but re-raises everything else. The denial must abort the run, so it derives from
    neither.
    """

    def __init__(self, service: str) -> None:
        """Initialize the error with the normalized name of the denied service."""
        super().__init__(f"service {service[:80]} is not allowed for mirrored actions")
        self.service = service


class GuardedTemplate(Template):
    """A service-name template that refuses to resolve to a denied service."""

    __slots__ = ()

    @callback
    def async_render(self, *args: Any, **kwargs: Any) -> Any:
        """Render like the parent and raise DeniedServiceCallError when the result is a denied service name."""
        result = super().async_render(*args, **kwargs)
        if isinstance(result, str):
            name = result.strip().lower()
            if is_denied(name):
                raise DeniedServiceCallError(name)
        return result


def guard_actions(node: Any) -> Any:
    """
    Return a copy of a validated action tree in which every service-name template is a GuardedTemplate.

    Dicts and lists are copied, everything else is shared; the input is never mutated, so the owner-side tree of the
    same validation stays unrestricted. A Template under one of the service keys anywhere in the tree is wrapped, which
    also catches a payload key of that name; the guard only ever acts on a result that is a denied service name.
    """
    if isinstance(node, dict):
        return {
            key: GuardedTemplate(value.template, value.hass)
            if key in GUARDED_KEYS and isinstance(value, Template) and not isinstance(value, GuardedTemplate)
            else guard_actions(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [guard_actions(item) for item in node]
    return node


# --- the approval view (D-02, T-03-28) -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ApprovalView:
    """
    Everything the approval dialog shows about a mirror; every text is safe to put into a markdown description.

    Names are markdown-escaped, `actions_yaml` has no control character and no run of three backticks, and `truncated`
    says the YAML was cut at the cap, which the flow answers with a refusal instead of showing a partial review.
    `run_on_startup`, `run_mode`, `breaker_max_runs` and `breaker_window` are part of what the approval hash binds, so
    the dialog states them next to the actions (D-16). The run mode is one of two validated words and the limits are
    validated integers, so none of them needs escaping.
    """

    device_id: str
    device_name: str
    owner_name: str
    actions_hash: str
    short_hash: str
    actions_yaml: str
    run_on_startup: bool
    run_mode: str
    breaker_max_runs: int
    breaker_window: int
    truncated: bool
    templated: str
    residual: str
    invalid: str


def _clean(text: str, *, keep_layout: bool = False) -> str:
    """Return text without control, format and separator characters; the layout ones survive on request."""
    return "".join(
        char
        for char in text
        if (keep_layout and char in "\n\t") or unicodedata.category(char) not in _DROPPED_CATEGORIES
    )


def _one_line(text: str) -> str:
    """Return broker text as one short, cleaned and markdown-escaped line."""
    line = " ".join(_clean(text, keep_layout=True).split())
    if len(line) > _ITEM_MAX_CHARS:
        line = f"{line[:_ITEM_MAX_CHARS]}\u2026"
    return escape_markdown(line)


def _bullets(items: Iterable[str], limit: int | None = None) -> str:
    """Return a markdown bullet list of one-line texts, capped at `limit` with the rest counted; a dash when empty."""
    entries = list(items)
    if not entries:
        return EMPTY_LIST_TEXT
    shown = entries if limit is None else entries[:limit]
    lines = [f"- {_one_line(item)}" for item in shown]
    if len(shown) < len(entries):
        lines.append(f"- \u2026 (+{len(entries) - len(shown)})")
    return "\n".join(lines)


def _actions_yaml(spec: DeviceSpec) -> tuple[str, bool]:
    """Return the sanitized YAML of every non-empty action list under its label, and whether it was cut at the cap."""
    # A list of single-key mappings, never one dict: two labels may be equal (a hostile Select option pair) and a dict
    # would silently drop all but one action list from the review
    sections = [{label: actions} for label, actions in approval_sections(spec)]
    try:
        text = yaml_dump(sections)
    except Exception:  # noqa: BLE001 - whatever the dumper cannot represent is still shown, as JSON
        text = canonical_json(sections)
    text = _FENCE_RUN.sub(lambda match: " ".join(match.group()), _clean(text, keep_layout=True))
    return text[:APPROVAL_YAML_MAX_CHARS], len(text) > APPROVAL_YAML_MAX_CHARS


def build_approval_view(spec: DeviceSpec, info: MirrorInfo, deep_invalid_labels: Iterable[str]) -> ApprovalView:
    """
    Build the approval view of a mirror from its spec, the recorded analysis and the labels that fail deep validation.

    Nothing from the broker is shown raw: names go through `escape_markdown`, the YAML through the dumper (which quotes
    hostile strings) and a character and fence filter, and the lists through one-line cleaning with a cap.
    """
    actions, truncated = _actions_yaml(spec)
    return ApprovalView(
        device_id=spec.device_id,
        device_name=escape_markdown(_clean(spec.name)),
        owner_name=escape_markdown(_clean(info.owner_name)),
        actions_hash=info.actions_hash,
        short_hash=info.actions_hash[:APPROVAL_HASH_PREFIX_LENGTH],
        actions_yaml=actions,
        run_on_startup=spec.run_on_startup,
        run_mode=spec.run_mode,
        breaker_max_runs=spec.breaker_max_runs,
        breaker_window=spec.breaker_window,
        truncated=truncated,
        templated=_bullets(info.templated, APPROVAL_TEMPLATED_MAX_LINES),
        residual=_bullets(info.residual, APPROVAL_TEMPLATED_MAX_LINES),
        invalid=_bullets(deep_invalid_labels, APPROVAL_TEMPLATED_MAX_LINES),
    )
