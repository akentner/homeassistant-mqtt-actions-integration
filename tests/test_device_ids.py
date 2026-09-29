"""Detection of instance-local device_ids in raw action sequences (D-10)."""

from custom_components.mqtt_actions import actions


def test_entity_area_and_label_targets_have_no_device_ids() -> None:
    raw = [
        {"action": "light.turn_on", "target": {"entity_id": "light.a"}},
        {"action": "light.turn_off", "target": {"area_id": "kitchen"}},
        {"action": "light.toggle", "target": {"label_id": "night"}},
    ]
    assert actions.find_device_ids(raw) == []


def test_empty_and_non_container_input() -> None:
    assert actions.find_device_ids([]) == []
    assert actions.find_device_ids(None) == []
    assert actions.find_device_ids("abc123") == []


def test_target_device_id() -> None:
    raw = [{"action": "light.turn_on", "target": {"device_id": "abc123"}}]
    assert actions.find_device_ids(raw) == ["abc123"]


def test_device_id_inside_data() -> None:
    raw = [{"action": "notify.send", "data": {"device_id": "abc123"}}]
    assert actions.find_device_ids(raw) == ["abc123"]


def test_device_id_list_yields_both_ids() -> None:
    raw = [{"action": "light.turn_on", "target": {"device_id": ["a1", "b2"]}}]
    assert actions.find_device_ids(raw) == ["a1", "b2"]


def test_device_action_mapping() -> None:
    raw = [{"type": "turn_on", "device_id": "dev9", "domain": "light", "entity_id": "abc"}]
    assert actions.find_device_ids(raw) == ["dev9"]


def test_ids_nested_in_control_flow_blocks() -> None:
    raw = [
        {
            "choose": [
                {
                    "conditions": [],
                    "sequence": [{"action": "a.b", "target": {"device_id": "in-choose"}}],
                }
            ],
            "default": [{"action": "a.b", "target": {"device_id": "in-default"}}],
        },
        {"sequence": [{"action": "a.b", "target": {"device_id": "in-sequence"}}]},
        {"parallel": [{"action": "a.b", "target": {"device_id": "in-parallel"}}]},
        {"repeat": {"count": 2, "sequence": [{"action": "a.b", "target": {"device_id": "in-repeat"}}]}},
        {
            "if": [],
            "then": [{"action": "a.b", "target": {"device_id": "in-then"}}],
            "else": [{"action": "a.b", "target": {"device_id": "in-else"}}],
        },
    ]
    assert actions.find_device_ids(raw) == [
        "in-choose",
        "in-default",
        "in-sequence",
        "in-parallel",
        "in-repeat",
        "in-then",
        "in-else",
    ]


def test_ids_are_unique_in_first_seen_order() -> None:
    raw = [
        {"action": "a.b", "target": {"device_id": ["z9", "a1"]}},
        {"action": "a.b", "target": {"device_id": "a1"}},
        {"action": "a.b", "data": {"device_id": "m5"}},
    ]
    assert actions.find_device_ids(raw) == ["z9", "a1", "m5"]


def test_non_string_and_template_values_are_ignored() -> None:
    raw = [
        {"action": "a.b", "target": {"device_id": 42}},
        {"action": "a.b", "target": {"device_id": None}},
        {"action": "a.b", "target": {"device_id": "{{ states('input_text.dev') }}"}},
        {"action": "a.b", "target": {"device_id": "{% if true %}x{% endif %}"}},
        {"action": "a.b", "target": {"device_id": ["{{ x }}", 7, "real"]}},
    ]
    assert actions.find_device_ids(raw) == ["real"]
