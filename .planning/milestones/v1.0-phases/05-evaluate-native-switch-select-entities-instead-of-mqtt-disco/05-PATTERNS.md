# Phase 5: Native switch/select entities instead of MQTT Discovery - Pattern Map

**Mapped:** 2026-10-03
**Files analyzed:** 16 (new and modified)
**Analogs found:** 15 / 16
**Tracked-source gate:** every analog below was listed by `git ls-files` (all under `custom_components/mqtt_actions/` and `tests/`); no gitignored mirror path is used.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `custom_components/mqtt_actions/switch.py` (NEW) | entity platform | event-driven + request-response (publish command) | `select.py` (`DeviceModeSelect` + `async_setup_entry`) | exact (platform scaffold), role-match (publish) |
| `custom_components/mqtt_actions/select.py` (MOD: add native device select) | entity platform | event-driven + request-response | same file: `DeviceModeSelect` | exact |
| `custom_components/mqtt_actions/button.py` (MOD: test buttons) | entity platform | request-response | same file: `ResyncButton` | exact |
| `custom_components/mqtt_actions/entities.py` (MOD: merge companion info, D-08) | entity base / utility | transform | same file: `companion_device_info`, `MqttActionsEntity` | exact |
| `custom_components/mqtt_actions/takeover.py` (NEW) | service (registry logic) | batch / transform | `Manager._clean_registry` (`manager.py:1256-1281`) | role-match |
| `custom_components/mqtt_actions/__init__.py` (MOD: PLATFORMS, takeover before forward) | config / setup | request-response | same file: `async_setup_entry` | exact |
| `custom_components/mqtt_actions/manager.py` (MOD: `Device.value`, signal, test press, cutover gate) | service | event-driven | same file: `_on_message`, `_on_test_message`, line 597 signal send | exact |
| `custom_components/mqtt_actions/const.py` (MOD: new signal, cap key, option) | config | n/a | same file: `SIGNAL_DEVICES_CHANGED` (line 173) | exact |
| `custom_components/mqtt_actions/discovery.py` (MOD: reduce to optional export) | service | pub-sub | same file | exact |
| `custom_components/mqtt_actions/sync.py` (MOD: drop heal block, D-11) | service | event-driven | same file `_on_discovery_message` (removal target) | exact |
| `custom_components/mqtt_actions/document.py` (MOD: additive unhashed marker) | model | transform | same file: `transferred_from` / `TRANSFER_KEY` (lines 150-175) | exact |
| `custom_components/mqtt_actions/presence.py` (MOD: heartbeat capability key) | model / service | pub-sub | same file: `parse_heartbeat` (line 124) | exact |
| `tests/test_takeover.py` (NEW) | test | event-driven | `tests/test_companions.py` + spike skeleton in RESEARCH | role-match |
| `tests/test_native_entities.py` (NEW) | test | event-driven | `tests/test_companions.py`, `tests/test_hub_entities.py` | role-match |
| `tests/test_cutover.py` (NEW) | test | pub-sub | `tests/test_multi_instance.py`, `tests/fake_broker.py` | role-match |
| `tests/fake_broker.py` (MOD: Instance runs real `async_setup_entry`) | test util | pub-sub | same file | exact |
| `docs/adr` or ADR file (NEW, DEC-01) | doc | n/a | none | no analog |

## Pattern Assignments

### `custom_components/mqtt_actions/switch.py` (entity platform)

**Analog:** `custom_components/mqtt_actions/select.py` (platform scaffold) and `button.py` (small platform file).

**Imports pattern** (`select.py` lines 3-19): `TYPE_CHECKING` block for `ConfigEntry`, `HomeAssistant`, `AddConfigEntryEntitiesCallback`, `Manager`; runtime imports from `.const` and `.entities`.
```python
from homeassistant.components.select import SelectEntity
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import MODES, SIGNAL_DEVICES_CHANGED, SIGNAL_MODES_CHANGED
from .entities import MqttActionsEntity, companion_device_info
```

**Per-device entity pattern** (`select.py` lines 45-64): unique id bound to device, device info per device, `available` from manager.
```python
class DeviceModeSelect(_ModeSelect):
    _signals = (SIGNAL_MODES_CHANGED, SIGNAL_DEVICES_CHANGED)

    def __init__(self, manager: Manager, device_id: str) -> None:
        super().__init__(manager)
        device = manager.devices.get(device_id) or manager.mirrors[device_id]
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_mode"
        self._attr_device_info = companion_device_info(
            device_id, device.name, device.spec.kind, mirror=device.mirror is not None, sw_version=manager.version
        )

    @property
    def available(self) -> bool:
        return self._manager.has_device(self._device_id)
```
New switch: `_attr_name = None`, `unique_id = device_id` (must equal `discovery.py:57`), `is_on` from `Device.value` (upper/trim compare like the tracker), `async_turn_on/off` publish `PAYLOAD_ON`/`PAYLOAD_OFF` to `state_topic(base, device_id)` with `retain=True, qos=1` via `manager.gateway.async_publish` (see `DiscoveryPublisher.async_publish_device`, `discovery.py:158-162`, for the gateway call shape). No optimistic state. Let `HomeAssistantError` propagate (same style as `_ModeSelect.async_select_option`, `select.py:33-38`).

**Platform setup + late device additions** (`select.py` lines 94-120): copy verbatim, replacing the entity class. Owned device goes under its subentry, mirror directly under the entry.
```python
added: set[str] = set()

@callback
def _add_new_devices() -> None:
    added.intersection_update(manager.devices.keys() | manager.mirrors.keys())
    for device_id in [*manager.devices, *manager.mirrors]:
        if device_id in added:
            continue
        added.add(device_id)
        async_add_entities([DeviceModeSelect(manager, device_id)], config_subentry_id=manager.subentry_id_of(device_id))

_add_new_devices()
entry.async_on_unload(
    async_dispatcher_connect(hass, SIGNAL_DEVICES_CHANGED.format(entry.entry_id), _add_new_devices)
)
```
Filter by kind (`device.spec.kind == SUBENTRY_SWITCH`, as in `discovery.py:125`).

**Availability parity:** discovery used the owner availability topic (`discovery.py:136`). Native: available when owned, or when the owner instance is online for a mirror; add `SIGNAL_ROSTER_UPDATED` to `_signals` (`sensor.py:25` shows `_signals = (SIGNAL_ROSTER_UPDATED,)`).

---

### `custom_components/mqtt_actions/select.py` (native device select, modify)

**Analog:** same file.
- Reuse `_ModeSelect`/`DeviceModeSelect` untouched except `companion_device_info` is replaced by the merged device info (D-08) and unique id `f"{device_id}_mode"` stays.
- New `DeviceSelect(MqttActionsEntity, SelectEntity)`: `unique_id = device_id`, `_attr_name = None`; `options` built from `spec.triggers.values()` as in `discovery.py:73-82` (`friendly_name` shown, `trigger.value` published). `current_option` computed live from `Device.value` mapped through `build_value_template` semantics (`value.strip().lower()` lookup in `spec.accepted`, `discovery.py:40`); HA returns None for an option not in `options`.
- `async_select_option` maps friendly name back to StateValue (`discovery.py:47-50` semantics) and publishes retained qos 1 to the state topic.

---

### `custom_components/mqtt_actions/button.py` (native test buttons, modify)

**Analog:** same file, `ResyncButton` (lines 19-33), plus `_button_component` (`discovery.py:93-110`) for identity values.
```python
class ResyncButton(MqttActionsEntity, ButtonEntity):
    _attr_translation_key = "resync"
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        if not await self._manager.async_resync():
            LOGGER.debug("The resync was ignored because it is throttled or the manager is not running")
```
New `DeviceTestButton`: `unique_id = f"{device_id}_test_{trigger.key}"`, name `f"Test {trigger.friendly_name}"`, `entity_category CONFIG` (keep names for migrated entries, Open Question 5). `async_press` calls a new `Manager` method extracted from `_on_test_message` (`manager.py:1724-1752`): mode gate `effective_mode == MODE_RUN`, `runner.can_run`, `runner.enqueue(..., test=True)`. No test topic.

---

### `custom_components/mqtt_actions/entities.py` (modify)

**Analog:** same file. `companion_device_info` (lines 37-52) becomes the single native device info builder: identifiers `{(DOMAIN, device_id)}`, `model` with `(mirror)` suffix, plus an owner marker for mirrors (D-07). Keep `MqttActionsEntity` base (lines 55-79) and its `_signals` mechanism unchanged.
```python
return DeviceInfo(
    identifiers={(DOMAIN, device_id)},
    name=name,
    manufacturer=HUB_MANUFACTURER,
    model=f"{model} (mirror)" if mirror else model,
    sw_version=sw_version,
)
```

---

### `custom_components/mqtt_actions/takeover.py` (NEW, registry logic)

**Analog:** `Manager._clean_registry` (`manager.py:1256-1281`) for the identity lookup form; ordering rules from RESEARCH Pattern 3 (no code analog for platform/device move).
```python
if (mqtt_entry_id := self.gateway.mqtt_entry_id()) is None:
    return
device_registry = dr.async_get(self._hass)
device = device_registry.async_get_device_by_identifier(("mqtt", f"{DOMAIN}_{device_id}"), mqtt_entry_id)
if device is None:
    return
entities = er.async_entries_for_device(er.async_get(self._hass), device.id, include_disabled_entities=True)
```
Copy: `mqtt_entry_id()` None guard, `async_get_device_by_identifier` with the `("mqtt", f"{DOMAIN}_{id}")` identifier, `async_entries_for_device(..., include_disabled_entities=True)`. Add `_is_legacy_entity` identity check from RESEARCH "Registry-only identity check". Fixed order: migrate payload, bounded retry on `ValueError("Only entities that haven't been loaded...")`, `er.async_update_entity_platform`, guarded by `async_get_entity_id` (Pitfall 4), then `dr.async_update_device(new_config_entry_id=..., new_config_subentry_id=...)`, merge companion, `new_identifiers`, empty clear last. Use `dr.async_entries_for_config_entry`, never `device_registry.devices` mapping, and not `merge_identifiers`.

---

### `custom_components/mqtt_actions/__init__.py` (modify)

**Analog:** same file lines 22, 54-60.
```python
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.SELECT]   # add Platform.SWITCH
...
# The entities read the running manager, so the platforms come last; a failure here must not leave it running
try:
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
except BaseException:
    await manager.async_stop()
    raise
```
Insert the takeover step between `manager.async_start()` and the forward (D-12: entities first, then device, then clear). Keep the `except BaseException: await manager.async_stop(); raise` rollback shape around it. `async_unload_entry` (lines 68-79) is unchanged.

---

### `custom_components/mqtt_actions/manager.py` (modify)

**Analog:** same file.
- `Device.value` update at top of `_on_message` (line 1594-1599) before the disabled early return:
```python
@callback
def _on_message(self, device_id: str, msg: IncomingMessage) -> None:
    if (device := self._device(device_id)) is None or self.effective_mode(device_id) == MODE_DISABLED:
        return
```
- Signal dispatch: `async_dispatcher_send(self._hass, SIGNAL_DEVICES_CHANGED.format(self._entry.entry_id))` (line 597); add a per-entry state-changed signal template in `const.py` next to line 173 (`f"{DOMAIN}_..._{{}}"` style).
- Live cutover reload: `self._hass.config_entries.async_schedule_reload(self._entry.entry_id)` (line 1099).
- Remove or shrink `_clean_registry` and companion split when native.

---

### `custom_components/mqtt_actions/document.py` and `presence.py` (additive markers)

**document.py** analog lines 150-175: optional key written only when set, never hashed.
```python
if transferred_from:
    document[TRANSFER_KEY] = list(transferred_from)
```
Add the native marker the same way (outside `content`, so `content_hash` is unchanged). Parse strictly (only the expected string). Keep `SCHEMA_VERSION = 1` (D-09).

**presence.py** analog line 124: `parse_heartbeat` reads exactly `("name", "version", "devices", "session")`. Add an optional capability key read with a default of legacy; a v0.1.0-shaped heartbeat must parse as legacy.

---

### `custom_components/mqtt_actions/discovery.py` and `sync.py` (reduce)

- `discovery.py`: keep `_switch_component` (53-68), `_select_component` (71-85), `build_discovery` (113-137); drop `_button_component` and `test_topic` from export, drop `retired` tombstones; add `"enabled_by_default": False` to each component and a configurable prefix (D-11). `DiscoveryPublisher` (140-182): keep `async_publish_device`/`async_clear_device`, config/state/availability methods unchanged.
- `sync.py`: remove `_on_discovery_message` heal (about lines 670-700), `_note_removal`, `ISSUE_DISCOVERY_REMOVED_PREFIX` use; `_raise_once` (lines 640-665) stays as the generic issue helper (reuse for a cutover Repairs hint naming blocking legacy peers).

---

### `tests/test_takeover.py` (NEW)

**Analog:** `tests/test_companions.py` (helpers) and the spike skeleton in RESEARCH "Code Examples".

**Imports/helpers pattern** (`test_companions.py` lines 1-80):
```python
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry, async_fire_mqtt_message, async_fire_time_changed, async_mock_service,
)
from custom_components.mqtt_actions.discovery import build_discovery
from custom_components.mqtt_actions.topics import availability_topic, config_topic, discovery_topic, state_topic
from tests.documents import FOREIGN_OWNER, document_payload, make_spec

async def _setup(hass, entry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry

def _mode_entity_id(hass, device_id):
    return er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{device_id}_mode")

def _companion(hass, entry, device_id):
    return dr.async_get(hass).async_get_device_by_identifier((DOMAIN, device_id), entry.entry_id)
```
Fixtures `make_hub_entry`, `make_switch_subentry`, `make_select_subentry`, `fake_broker`, `make_instance` come from `tests/conftest.py` (lines 60-160). First discovery message `retain=True`, later ones `retain=False` (Pitfall 7).

---

### `tests/fake_broker.py` (modify, Wave 0)

**Analog:** same file (`InstanceFactory`, `FakeGateway`). Make `Instance` run the real `async_setup_entry` with `custom_components.mqtt_actions.MqttGateway` and `manager.MqttGateway` patched to the fake (Pitfall 8). Read the file before planning; I did not extract it line by line.

## Shared Patterns

### Entity base and signals
**Source:** `custom_components/mqtt_actions/entities.py:55-79`. **Apply to:** `switch.py`, new select/button classes. Subclass `MqttActionsEntity`, declare `_signals = (...)` with format-templates from `const.py` (`SIGNAL_ROSTER_UPDATED` 161, `SIGNAL_MODES_CHANGED` 172, `SIGNAL_DEVICES_CHANGED` 173); the base connects them and calls `async_write_ha_state`.

### Platform setup with late devices
**Source:** `select.py:94-120`. **Apply to:** `switch.py`, select and button device entities. `added` set plus `_add_new_devices` plus `async_on_unload(async_dispatcher_connect(...))`; `config_subentry_id=manager.subentry_id_of(device_id)` (None for mirrors).

### Registry identity (MQTT device lookup)
**Source:** `manager.py:1268`. **Apply to:** `takeover.py`. Identifier `("mqtt", f"{DOMAIN}_{device_id}")` with `mqtt_entry_id`; never match on unique_id alone (T-5-01).

### Additive, unhashed, ignored-by-old-parsers keys
**Source:** `document.py:150-175`, `presence.py:124`. **Apply to:** native marker and heartbeat capability.

### Publishing through the gateway
**Source:** `discovery.py:158-162` and `mqtt_gateway.py`. **Apply to:** native commands. `await gateway.async_publish(topic, payload, retain=True)`; add `qos=1` for commands (see RESEARCH Pattern 2).

### Failure rollback in setup
**Source:** `__init__.py:45-60`. **Apply to:** the takeover insertion in `async_setup_entry`.

### Docs, translations, tests pinned together
**Source:** RESEARCH Pitfall 9. `tests/test_docs.py`, `tests/test_translations.py`, `tests/test_repo_structure.py`; update README, `docs/broker-acl.md`, `translations/en.json` and `de.json` together.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| ADR / decision record (DEC-01) | doc | n/a | Check `docs/` and prior phase artifacts for an ADR style; none found in code scan |
| Registry platform/device move logic in `takeover.py` | service | batch | No existing code moves registry entries between integrations; use RESEARCH Pattern 3 and spike skeleton |
| Cutover state machine (roster gate) | service | event-driven | Closest is `presence.py` roster plus `sync.py` issue helpers; the gate itself is new (RESEARCH Pattern 4) |

## Metadata

**Analog search scope:** `custom_components/mqtt_actions/`, `tests/`
**Files read:** entities.py, select.py, button.py, sensor.py, `__init__.py`, discovery.py, test_companions.py (1-80), conftest.py, mqtt_gateway.py (1-60), targeted ranges of manager.py, sync.py, document.py, presence.py
**Pattern extraction date:** 2026-10-03
