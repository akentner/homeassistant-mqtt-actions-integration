"""
The fixable issues of the integration as Repairs fix flows (D-02, D-07, D-09, TRU-02).

Core finds this module by its name `repairs` and calls `async_create_fix_flow` for a fixable issue of this domain; the
issue id decides the flow. `approval_<device id>` is the approval of a mirror: the dialog shows what the manager would
run, binds the hash it showed and approves exactly that hash, never "whatever is current" (T-03-29).
`duplicate_instance_id` is the fix for a clone that shares the instance id: it forgets the local devices and rotates
the id after one confirmation. `transferred_<device id>` lets an old owner follow the instance that adopted its device.
"""

from typing import TYPE_CHECKING

import probatio
from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.config_entries import ConfigEntryState

from .const import DOMAIN, ISSUE_DUPLICATE_INSTANCE_ID, ISSUE_TRANSFERRED_PREFIX
from .document import escape_markdown

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
                data_schema=probatio.Schema({}),
                description_placeholders={
                    "device": view.device_name,
                    "owner": view.owner_name,
                    "hash": view.short_hash,
                    "actions": view.actions_yaml,
                    "startup": str(view.run_on_startup).lower(),
                    "run_mode": view.run_mode,
                    "breaker_max_runs": str(view.breaker_max_runs),
                    "breaker_window": str(view.breaker_window),
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


class DuplicateIdRepairFlow(RepairsFlow):
    """Gives this instance a new instance id after forgetting its own devices locally (D-08)."""

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:  # noqa: ARG002
        """Handle the first step of a fix flow; core passes the init data here, which is never a submit."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """
        Show what the fix does, and on submit run it for the instance id the issue reported.

        Both the form and the submit check the id again, so a fix that was reported for an earlier id never acts.
        """
        if (manager := _loaded_manager(self.hass)) is None:
            return self.async_abort(reason="not_loaded")
        if (self.data or {}).get("instance_id") != manager.instance_id:
            return self.async_abort(reason="changed")
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=probatio.Schema({}),
                description_placeholders={
                    "instance": escape_markdown(manager.instance_name),
                    "devices": str(len(manager.devices)),
                },
            )
        await manager.async_resolve_duplicate_id()
        return self.async_create_entry(data={})


class TransferredRepairFlow(RepairsFlow):
    """Lets an old owner forget a device that another instance adopted and follow the adopter as a mirror (D-09)."""

    async def async_step_init(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:  # noqa: ARG002
        """Handle the first step of a fix flow; core passes the init data here, which is never a submit."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, str] | None = None) -> RepairsFlowResult:
        """
        Show what the release does, and on submit run it for the device and claimant the issue reported.

        The form and the submit both require that the device is still owned here and that the adopter recognized now
        is the one in the issue, so a stale issue never releases anything (T-04-59).
        """
        if (manager := _loaded_manager(self.hass)) is None:
            return self.async_abort(reason="not_loaded")
        data = self.data or {}
        device_id, claimant = data.get("device_id"), data.get("claimant")
        info = manager.sync.transfer_info(device_id) if isinstance(device_id, str) else None
        if info is None or info.claimant != claimant or (device := manager.devices.get(device_id)) is None:
            return self.async_abort(reason="changed")
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=probatio.Schema({}),
                description_placeholders={
                    "device": escape_markdown(device.name),
                    "claimant": escape_markdown(info.claimant_name),
                },
            )
        if not await manager.async_release_device_locally(device_id):
            return self.async_abort(reason="changed")
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant,  # noqa: ARG001
    issue_id: str,
    data: dict[str, str | int | float | None] | None,  # noqa: ARG001
) -> RepairsFlow:
    """Create the fix flow of an issue; the issue id decides which one, and the approval flow is the default."""
    if issue_id == ISSUE_DUPLICATE_INSTANCE_ID:
        return DuplicateIdRepairFlow()
    if issue_id.startswith(ISSUE_TRANSFERRED_PREFIX):
        return TransferredRepairFlow()
    return ApprovalRepairFlow()
