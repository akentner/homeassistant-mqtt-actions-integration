# Stack Research

**Domain:** HA custom integration `mqtt_actions`, milestone v1.1. New: MIR-01 (per-instance local actions on mirrored devices), Repairs hint for customized duplicates, guard test for the private registry API.
**Researched:** 2026-10-11
**Confidence:** HIGH for every core API claim. Each one was checked in the installed HA 2026.9.4 source (`.venv`) and diffed against the HA 2026.10.1 wheel. MEDIUM for the frontend and UX claims, which come from `home-assistant/frontend` main via `gh api`.

## Headline Decisions

1. **No new dependencies.** Everything MIR-01 needs ships with HA core 2026.9.x. Keep `requirements: []` and keep the `hacs.json` floor at `2026.9.0`.
2. **Where the user edits local actions:** turn the hub **options flow** into a menu with a "local actions" branch (mirror chooser, then trigger chooser, then a form). Do not create subentries for mirrors, do not use a Repairs fix flow, and do not invent a device-page action. Optionally, set the mirror's `configuration_url` to a `homeassistant://` deep link to the integration page.
3. **Where local actions are stored:** the existing integration `Store` (`mqtt_actions.state`), in a new optional key `local_actions`. Not in `entry.options` and not in subentries.
4. **How they are validated:** the existing `actions.async_validate_actions()` (`cv.SCRIPT_SCHEMA` + `script.async_validate_actions_config`), both at flow submit and at Script build. Skip the device_id portability warning, because these actions never leave the instance. No restricted build and no `guard_actions`.
5. **How they run:** a **second, separate `Script` per mirror** (a "local lane"). It is unrestricted and has its own issue ids. Do not merge local actions into the owner's restricted Script.
6. **Registry flush:** neither 2026.9.4 nor 2026.10.1 has a public API that writes the entity or device registry immediately. Keep `registry._store.async_save(registry._data_to_save())` and add a loud test that pins it.
7. **Repairs hint:** `ir.async_create_issue(..., is_fixable=False, is_persistent=False, severity=WARNING, learn_more_url=...)`. Use one aggregated issue, recomputed at each start and after each guard pass, and deleted when the condition clears.

## Recommended Stack

### Core Technologies (all bundled with HA, no install)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| HA Core | floor 2026.9.0. Dev/CI on 2026.9.4 today; 2026.10.1 is out (2026-10-10) | Host | Every API below exists in 2026.9.0. All of them are unchanged in 2026.10.1: `registry.py` only gained `NextNamePart`, and `issue_registry.py`, `storage.py`, `ConfigSubentryFlow` and `OptionsFlow` diff empty. Raising the floor brings nothing for MIR-01. |
| `homeassistant.config_entries.OptionsFlow` + `FlowHandler.async_show_menu(step_id=, menu_options=, description_placeholders=)` | core | UI entry point for local actions | The only per-entry UI door that does not need a subentry. `HubOptionsFlow` already exists (`config_flow.py:141`). `init` becomes a menu: `settings` (today's form) and `local_actions` (shown only when the entry is LOADED and `manager.mirrors` is not empty). Verified: `async_show_menu` in `data_entry_flow.py:878`. |
| `OptionsFlow.async_create_entry(data=dict(self.config_entry.options))` | core | Finish the local-actions branch without side effects | `async_update_entry` fires update listeners **only when something changed** (`config_entries.py` `_async_update_entry`: "If the entry was not changed, the update_listeners are not fired"). Returning the unchanged options closes the dialog with the standard success text and does not trigger `_async_entry_updated` → `async_reconcile`. The local actions themselves are saved through a manager method. |
| `homeassistant.helpers.storage.Store` (existing `STORE_KEY = "mqtt_actions.state"`, `STORE_VERSION = 1`) | core | Persist local actions | Local actions are per-instance mirror state, like `approvals`, `device_modes` and `native.mirrors`, which already live there. The lifecycle is bound to the mirror: drop them in `async_remove_mirror` and prune them through the `kept` set at start (`manager.py:777-790`), in one place. Add the key optionally and write it only when non-empty, the same pattern as `STORE_NATIVE`/`STORE_PREVIOUS_STATES` (`manager.py:1387-1406`). That needs **no version bump and no migrator**. Save with `await self._store.async_save(...)` on user edits, not `async_delay_save`. |
| `actions.async_validate_actions()` = `cv.SCRIPT_SCHEMA` + `helpers.script.async_validate_actions_config(hass, actions)` | core | Validate local sequences | Reuse it unchanged. Signature verified: `async_validate_actions_config(hass, actions: list[ConfigType]) -> list[ConfigType]` (`script.py:323`). Persist the RAW selector output, never the validated form (Template objects), as the docstring already says. |
| `helpers.script.Script(hass, sequence, name, domain, *, script_mode, max_runs, max_exceeded, logger, ...)` | core | Run local actions | Signature verified at `script.py:1505`. A second instance per mirror, named e.g. `f"{spec.name} (local)"` so traces and logs tell the lanes apart. Same `script_mode` mapping (`queued`/`restart`) and `SERIAL_QUEUE_LIMIT` as the device. |
| `helpers.selector.ActionSelector` / `SelectSelector` / `BooleanSelector` | core | Form fields: actions per trigger plus "in addition to / instead of" | `ActionSelector.__call__` returns data unvalidated (`selector.py`, 2026.10.1), so the flow keeps validating. Render the mode as a `SelectSelector` with `translation_key` (two options: `add`, `replace`). This is the pattern already used for `run_mode`. |
| `homeassistant.data_entry_flow.section` (+ `SectionConfig(collapsed=...)`) | core | Group per-trigger fields on one form (Switch: ON and OFF) | Verified at `data_entry_flow.py:939`. One form per Switch mirror with two sections (mode plus actions each). For a Select mirror, use the existing chooser-then-details pattern (`SelectSubentryFlow.edit_option` → `edit_option_details`), because the option count is dynamic. Submitted section values arrive as nested dicts. |
| `helpers.issue_registry.async_create_issue` / `async_delete_issue` | core | Local-lane failure issues and the duplicate hint | Signature verified (`issue_registry.py:339`): `is_fixable`, `is_persistent=False`, `learn_more_url`, `severity`, `translation_key`, `translation_placeholders`. `IssueSeverity` has only CRITICAL, ERROR and WARNING (there is no INFO), so use WARNING for the hint. |

### Supporting APIs

| API | Version | Purpose | When to Use |
|-----|---------|---------|-------------|
| `DeviceInfo(configuration_url="homeassistant://config/integrations/integration/mqtt_actions")` | core: `CONFIGURATION_URL_SCHEMES = {"http","https","homeassistant"}` (`device_registry.py:115`) | Optional "open configuration" cog on the mirror's device page | Only if a device-page path is wanted. The frontend turns `homeassistant://` into an in-app path in the same tab (`sanitizeLinkUrl` / `homeAssistantUrlToPath`, frontend main). The integration page highlights an entry from the hash parameter `#config_entry=<id>`. **No URL opens an options flow directly**, so the user still clicks "Configure". MEDIUM, from frontend main, not pinned to the 2026.9 frontend. |
| `entry.async_create_background_task` | core | Start local-lane runs | Same as the owner lane (`runner.py:427`). |
| `homeassistant.helpers.storage.Store(..., minor_version=)` | core | Only if a later schema change is incompatible | Not needed for an additive optional key. |
| PHACC `hass_storage` fixture | `pytest-homeassistant-custom-component` 0.13.367 pinned (0.13.372 is current, 2026-10-11) | Registry-flush guard test and Store assertions | `plugins.py:535`. Assert that after `async_flush_registries(hass)` the keys `core.entity_registry` and `core.device_registry` in `hass_storage` hold the new data **without** advancing time. |

### Development Tools

No change. uv, Ruff 0.16.x, PHACC, hassfest, and the HACS action stay as in `.claude/CLAUDE.md`. If CI moves to HA 2026.10, bump PHACC in lockstep (0.13.372 pairs with 2026.10.1).

## Integration Points (where the new stack touches existing code)

| Point | File:line | Change |
|-------|-----------|--------|
| Options flow entry | `config_flow.py:141` `HubOptionsFlow.async_step_init` | `init` becomes a menu when mirrors exist. Keep the settings form reachable as its own step. The existing tests target the `init` form, so either keep `init` as the form when there are no mirrors, or update the tests. |
| Store schema | `manager.py:1365` `_async_load_store`, `:1387` `_data_to_save`, `const.py:119+` | New `STORE_LOCAL_ACTIONS = "local_actions"`: `{device_id: {trigger_key: {"mode": "add" \| "replace", "actions": [raw...]}}}`. Parse defensively (drop malformed entries, as the other `_parse_*` helpers do). Key it by `trigger_key`, because a StateValue is immutable, so the key is stable. |
| Lifecycle | `manager.py:777-790` (prune at start), `:1877` `async_remove_mirror`, `:1515` `async_adopt` | Prune with the mirror. **Adoption needs an owner decision:** drop the local actions, or fold them into the new owned subentry. Do not leave them dangling. |
| Runner | `runner.py:281` `ActionRunner` | Add a local lane: a second `_scripts`, `_runnable` and `_generation` map (or a parameterized second runner instance) with an **issue id prefix of its own**, e.g. `local_action_failed_`. Otherwise `clear_issue` on one lane deletes the other lane's failure issue (`runner.py:279`). |
| Issue cleanup | `const.py:294` `ISSUE_DEVICE_PREFIXES`, `manager.py:428-433` | Register the new local-failure prefix and the duplicate-hint id, so entry removal deletes them. |
| Dispatch | `manager.py:2448` `_run_trigger`, `:2596` (startup/test), `retrigger.py:440` | All three gate on `runner.can_run()` and call `enqueue` directly. Put the plan in one helper (owner lane yes/no, local lane yes/no per trigger and mode), so "replace" skips the owner lane and local runs even when the owner lane has no Script. The breaker and observe mode count **one** run per change, not one per lane. Whether a broker re-trigger also runs local actions is an owner decision. |
| Mirror Script gate | `manager.py:1847` `_async_refresh_mirror_script` | Keep the owner-lane gate untouched (no Script until approved and unblocked). Build the local lane independently whenever local actions exist. For "replace" triggers, leave the trigger out of the owner build, so a replaced trigger never needs approval. |
| Approval issue | `manager.py:1829` | Optional refinement: skip `approval_required` when every owner trigger with actions is replaced locally. Design call, not stack. |
| Diagnostics | `diagnostics.py:77` | Add counts or flags only (`local_triggers: n`), never the local action content. The row is already allow-listed. |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Options-flow menu | **Subentry type `local_actions`** (user adds one per mirror and edits it with subentry reconfigure) | Use it if per-mirror rows with reconfigure and delete buttons on the integration page matter more than lifecycle simplicity. Costs: (a) the frontend always shows an "Add local actions" button, because supported types carry only a `supports_reconfigure` flag (`config_entries.py:623-644`); (b) orphan subentries after an owner tombstone or an adoption have to be removed programmatically, which fires the update listener and the reconcile; (c) every `entry.subentries` consumer needs a type filter (today `_device_subentries` already filters, `manager.py:191`); (d) **never bind the mirror device to that subentry** (`new_config_subentry_id`), because removing a subentry removes the devices bound to it, which would kill the mirror and its entities. |
| Options-flow menu | Repairs fix flow as the editor | Never. Repairs is for problems; an editor there disappears when the issue is deleted and is not discoverable. |
| Options-flow menu | Programmatic per-mirror subentries, auto-created | Never. This is the risk of the user-added subentry type plus registry churn on every mirror add or remove, and it collides with the takeover/native registry logic. |
| Store key | `entry.options["local_actions"]` | Use it only if local actions must survive deleting and re-adding the hub entry, and they should not (the Store is removed with the entry too, `async_remove_local_state`). Options are replaced wholesale on each options-flow finish, and every change fires the update listener → full `async_reconcile` plus a re-apply of the discovery export. |
| Separate local Script | One combined Script (owner branch guarded, local branch not) | Use it only if "in addition" must run **strictly after** the owner's actions in one ordered run. Costs: guarding only a subtree means assembling an already-validated tree by hand (the outer `choose` conditions need Template objects); an owner action failure or `DeniedServiceCallError` aborts the local part; and the approval gate "no Script until approved" (TRU-01) stops being literally true. With separate lanes, "in addition" runs **concurrently**. A user who needs ordering can choose "instead of" and copy the owner's actions locally. |
| Keep the private flush plus a guard test | Rely on `registry.async_schedule_save()` (public) | Use it if the private API ever disappears. It is the fallback the flush should degrade to. Note: before `CoreState.running` the delay is `SAVE_DELAY_LONG = 180 s` (`registry.py`). That is exactly the boot takeover window, so the private flush still earns its place. `EVENT_HOMEASSISTANT_FINAL_WRITE` covers a clean shutdown only, not a crash. |
| Aggregated non-fixable hint | Fixable issue whose flow removes the customized duplicates | Never. Removing a row lets core clear a retained topic, which is the reason v1.0.1 disables instead of removing (Key Decision 06-02/08-12/08-17). The user deletes rows by hand after reading the hint. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Any new PyPI requirement | Not needed. It also breaks the "core provides it" rule (probatio, paho). | Core helpers listed above |
| `guard_actions` / `_refuse_denied` / `restricted=True` on local actions | Local actions are user-authored on this instance, the same trust level as owned devices. Restricting them would block legitimate local services. | Unrestricted build. Still pass `escape=True` to issues, because the device name comes from the broker. |
| `find_device_ids` warning in the local-actions form | The warning exists because device ids break **cross-instance** sync (D-10). Local actions never leave the instance, so `device_id` targets are fine there. | Validation errors only |
| Publishing local actions or folding them into `actions_hash` / the document | Violates MIR-01 ("never enter the central config"), and it would change the hash, which revokes approvals on every follower. | Store only |
| Sharing the owner lane's issue id (`action_failed_<id>`) for local failures | A successful run of one lane would clear the other lane's failure (`runner.py:481`). | Own prefix, e.g. `local_action_failed_<id>` |
| `async_delay_save` for a user's local-action edit | A 5 s window loses the edit on a crash, and the flow already told the user it was saved. | `await self._store.async_save(self._data_to_save())` |
| `async_abort(..., translation_domain=...)` | New in 2026.10 (central abort reasons), and options flows cannot use it anyway (blog 2026-09-28: no `options` section in `homeassistant`). It breaks the 2026.9.0 floor. | Local `options.abort.*` keys in `translations/{en,de}.json` |
| `DeviceEntry.config_entries` / `config_entries_subentries` / `primary_config_entry`, `async_get_device`, `add_/remove_config_entry_id` | Deprecated since 2026.8. 2026.10 logs warnings for custom integrations, and support ends with 2027.10. A grep shows the codebase is already clean; keep it that way in the duplicate-hint code. | `config_entry_id`, `config_subentry_id`, `async_get_device_by_identifier`, `new_config_subentry_id` |
| `is_persistent=True` for the duplicate hint | The condition is recomputed from the registry at each start. A persistent issue would outlive a fix done while HA was down. "Ignore" (`dismissed_version`) survives restarts either way, because a re-created issue keeps it. | `is_persistent=False` and re-create at start |

## Stack Patterns by Variant

**Switch mirror:**
- One options-flow form with two `section`s (ON, OFF), each holding `mode` (`SelectSelector` add/replace) and `actions` (`ActionSelector`).
- Reason: there are exactly two triggers, matching the owned Switch form.

**Select mirror:**
- Chooser step (`SelectSelector` LIST over `spec.triggers`, value = `trigger_key`, label = friendly name, escaped), then a details form (mode plus actions), then back to a small menu (`edit trigger`, `save`).
- Reason: the option count is dynamic. Reuse the `SelectSubentryFlow` draft-and-done pattern so nothing is stored before Save.

**Owner removes a Select option that has local actions:**
- Keep or prune the orphaned `trigger_key` entry. Recommendation: prune on mirror apply, because the key only returns if the owner re-adds the same StateValue. Flag this for FEATURES and PITFALLS.

**Duplicate hint (customized core-prefix rows kept enabled or disabled):**
- One issue id (e.g. `customized_duplicates`) with a capped, escaped placeholder list and `learn_more_url` pointing to the README section. Create or update it after each guard pass and at start; delete it when the list is empty.

**Registry-API guard test:**
- In PHACC, assert `isinstance(er.async_get(hass)._store, storage.Store)`, `callable(er.async_get(hass)._data_to_save)` (same for `dr`), and that `async_flush_registries(hass)` returns `True` and updates `hass_storage["core.entity_registry"]` / `["core.device_registry"]` without `async_fire_time_changed`.
- Reason: today the broad `except Exception` in `takeover.py:321` would swallow an `AttributeError` silently in production. The test makes the disappearance loud in CI. Optionally degrade at runtime to `registry.async_schedule_save()` when the attributes are missing.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| HA 2026.9.0+ | All APIs above | `section`, `async_show_menu`, `OptionsFlow.config_entry`, `Store(minor_version=)`, `ir.async_create_issue(learn_more_url=, is_persistent=)` long predate 2026.9. |
| HA 2026.10.1 | Same | Diffed: `registry._store` / `_data_to_save` still present (`registry.py:81,105`; `entity_registry.py:1310,2492`; `device_registry.py:1895,4435`). `issue_registry.py` and `storage.py` are identical. `ConfigSubentryFlow` and `OptionsFlow` are unchanged. New in 2026.10: device registry v3 migration backup (`_async_backup_store`), irrelevant here. |
| PHACC 0.13.367 ↔ HA 2026.9.4 | pinned today | Moving to 0.13.372 ↔ 2026.10.1 is optional for this milestone. Do it as its own commit, not mixed into MIR-01. |
| Store written by v1.1 ↔ v1.0.x code | forward: OK; downgrade: lossy | v1.0.x ignores `local_actions` on load and drops it on its next save. Document this in the release notes. `STORE_VERSION` stays 1. |

## Sources

- HA core 2026.9.4 installed source (`.venv/lib/python3.14/site-packages/homeassistant`): `helpers/registry.py` (`async_schedule_save`, `SAVE_DELAY`/`SAVE_DELAY_LONG`, `_store`, `_data_to_save`), `helpers/entity_registry.py`, `helpers/device_registry.py` (`CONFIGURATION_URL_SCHEMES`), `helpers/storage.py` (`Store.__init__`, `async_save`, `async_delay_save`, final-write listener), `helpers/issue_registry.py` (`IssueSeverity`, `async_create_issue`, `async_get_or_create`, `async_ignore`), `helpers/script.py` (`Script.__init__`, `async_validate_actions_config`), `config_entries.py` (`supported_subentry_types`, `ConfigSubentryFlow`, `_async_update_entry` listener rule, `OptionsFlowManager.async_finish_flow`), `data_entry_flow.py` (`async_show_menu`, `section`). HIGH.
- HA core 2026.10.1 wheel from PyPI (released 2026-10-10), diffed for the same files. HIGH.
- PyPI JSON: homeassistant 2026.10.1, pytest-homeassistant-custom-component 0.13.372 (2026-10-11). HIGH.
- PHACC `plugins.py:535` `hass_storage` fixture. HIGH.
- `home-assistant/frontend` main via `gh api`: `src/panels/config/devices/ha-config-device-page.ts` (`_getDeviceActions`, configuration_url cog), `src/common/url/sanitize-http-url.ts` (`homeassistant://` handling), `src/panels/config/integrations/ha-config-integration-page.ts` (`#config_entry` hash parameter). MEDIUM (main branch, not pinned to the 2026.9 frontend build).
- https://developers.home-assistant.io/blog/2026/07/21/device-registry-single-config-entry: one config entry and at most one subentry per device; deprecated `async_update_device` parameters. MEDIUM per seam, consistent with source.
- https://developers.home-assistant.io/blog/2026/09/15/device-entry-config-entries-deprecation: enforced in 2026.10, custom support until 2027.10. MEDIUM.
- developers.home-assistant.io `blog/2026-09-28-central-config-flow-abort-reasons.md` (via `gh api`): `translation_domain` on aborts in 2026.10, not usable in options flows. MEDIUM.
- Project code read: `config_flow.py`, `runner.py`, `actions.py`, `model.py`, `repairs.py`, `takeover.py:303-326`, `manager.py` (store, mirror Script gate, `_run_trigger`, adoption, issue cleanup), `const.py`, `entities.py`, `diagnostics.py`.

---
*Stack research for: HA custom integration, milestone v1.1 (MIR-01 local actions on mirrors)*
*Researched: 2026-10-11*
