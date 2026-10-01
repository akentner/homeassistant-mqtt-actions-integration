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

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.template import Template

from .document import is_denied

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
