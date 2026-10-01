"""
The approval of a mirror as a Repairs fix flow (D-02, TRU-02).

Core finds this module by its name `repairs` and calls `async_create_fix_flow` for a fixable issue of this domain.
The only fixable issue is `approval_<device id>`. The dialog shows what the manager would run, binds the hash it showed
and approves exactly that hash; the flow never approves "whatever is current" (T-03-29).
"""

from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .manager import Manager
    from .trust import ApprovalView


def _loaded_manager(hass: HomeAssistant) -> Manager | None:
    """Return the manager of the loaded hub entry, or None while the integration is not loaded."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            manager: Manager = entry.runtime_data
            return manager
    return None


class ApprovalRepairFlow(RepairsFlow):
    """Shows the actions of a mirrored device and approves the exact hash that was shown."""

    def __init__(self) -> None:
        """Initialize the flow; nothing is bound until the form was shown."""
        self._shown_hash: str | None = None

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:  # noqa: ARG002
        """Handle the first step of a fix flow; core passes the init data here, which is never a submit."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """
        Show the approval view, and on submit approve the hash that was displayed.

        Every abort keeps the issue: when the owner changed the document the replacement request already exists.
        """
        if (manager := _loaded_manager(self.hass)) is None:
            return self.async_abort(reason="not_loaded")
        data = self.data or {}
        device_id, requested = data.get("device_id"), data.get("actions_hash")
        view = (
            await manager.async_approval_view(device_id)
            if isinstance(device_id, str) and isinstance(requested, str)
            else None
        )
        if view is None or view.actions_hash != requested:
            return self.async_abort(reason="changed")
        if view.truncated:
            return self.async_abort(reason="too_large")
        if user_input is None:
            self._shown_hash = view.actions_hash
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({}),
                description_placeholders={
                    "device": view.device_name,
                    "owner": view.owner_name,
                    "hash": view.short_hash,
                    "actions": view.actions_yaml,
                    "startup": str(view.run_on_startup).lower(),
                    "templated": view.templated,
                    "residual": view.residual,
                    "invalid": view.invalid,
                },
            )
        return await self._async_submit(manager, view)

    async def _async_submit(self, manager: Manager, view: ApprovalView) -> RepairsFlowResult:
        """Approve the hash that was displayed; a submit without a shown form or for another hash approves nothing."""
        if self._shown_hash is None or view.actions_hash != self._shown_hash:
            return self.async_abort(reason="changed")
        if not await manager.async_approve(view.device_id, self._shown_hash):
            return self.async_abort(reason="changed")
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,  # noqa: ARG001
    issue_id: str,  # noqa: ARG001
    data: dict[str, str | int | float | None] | None,  # noqa: ARG001
) -> RepairsFlow:
    """Create the fix flow of an approval issue."""
    return ApprovalRepairFlow()
