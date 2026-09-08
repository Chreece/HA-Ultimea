from __future__ import annotations

from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "blueprints" / "automation" / "ultimea" / "adaptive_room_audio.yaml"


class BlueprintLoader(yaml.SafeLoader):
    """YAML loader that preserves Home Assistant's !input tag."""


def _unique_mapping(loader: BlueprintLoader, node: yaml.MappingNode, deep: bool = False):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise AssertionError(f"Duplicate YAML key: {key!r}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


BlueprintLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)
BlueprintLoader.add_constructor("!input", lambda loader, node: {"!input": loader.construct_scalar(node)})


def _load_blueprint() -> dict:
    return yaml.load(BLUEPRINT.read_text(encoding="utf-8"), Loader=BlueprintLoader)


def _walk_templates(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_templates(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_templates(item)
    elif isinstance(value, str) and ("{{" in value or "{%" in value):
        yield value


def _inputs(data: dict) -> dict:
    return {
        key: value
        for section in data["blueprint"]["input"].values()
        for key, value in section["input"].items()
    }


def test_adaptive_audio_blueprint_yaml_and_jinja_are_valid() -> None:
    data = _load_blueprint()
    assert data["blueprint"]["domain"] == "automation"
    assert data["blueprint"]["homeassistant"]["min_version"] == "2026.7.0"
    env = jinja2.Environment()
    for template in _walk_templates(data):
        env.parse(template)


def test_blueprint_exposes_policy_engine_inputs() -> None:
    inputs = _inputs(_load_blueprint())
    required = {
        "ultimea_players", "min_volume_value", "min_volume_helper",
        "max_volume_value", "max_volume_helper", "quiet_start", "quiet_end",
        "low_volume_binary_entities", "list_state_entities", "global_list_state_entities",
        "minimum_ha_conditions", "minimum_condition_template",
        "zero_binary_entities", "zero_room_list_entities", "zero_global_list_entities",
        "zero_ha_conditions", "zero_condition_template", "zero_effect", "zero_extra_actions",
        "boost_binary_entities", "boost_room_list_entities", "boost_global_list_entities",
        "boost_ha_conditions", "boost_condition_template", "boost_amount_value",
        "boost_amount_entity", "boost_apply_when", "boost_cap",
        "night_mode_entities", "night_room_list_entities", "night_global_list_entities",
        "night_ha_conditions", "night_condition_template", "night_conditions_request_minimum",
        "connected_activity_mode", "connected_activity_ha_conditions", "connected_activity_template",
        "inactive_policy_behavior", "extra_policy_trigger_entities",
        "connected_media_players", "connected_devices", "connected_labels",
        "eq_follow_ha_conditions", "eq_follow_template", "ai_content_actions",
        "learn_manual_volume_changes", "manual_learning_ha_conditions", "manual_learning_template",
        "apply_volume_follow", "apply_night_mode", "apply_eq_follow",
    }
    assert required <= inputs.keys()


def test_every_policy_condition_family_has_rich_and_template_paths() -> None:
    inputs = _inputs(_load_blueprint())
    pairs = (
        ("minimum_ha_conditions", "minimum_condition_template"),
        ("zero_ha_conditions", "zero_condition_template"),
        ("boost_ha_conditions", "boost_condition_template"),
        ("night_ha_conditions", "night_condition_template"),
        ("connected_activity_ha_conditions", "connected_activity_template"),
        ("eq_follow_ha_conditions", "eq_follow_template"),
        ("manual_learning_ha_conditions", "manual_learning_template"),
    )
    for rich, template in pairs:
        assert "condition" in inputs[rich]["selector"]
        assert "template" in inputs[template]["selector"]


def test_rich_connected_selectors_and_room_list_modes_exist() -> None:
    inputs = _inputs(_load_blueprint())
    assert inputs["connected_devices"]["selector"]["device"]["multiple"] is True
    assert inputs["connected_labels"]["selector"]["label"]["multiple"] is True
    for key in (
        "list_state_entities", "global_list_state_entities",
        "zero_room_list_entities", "zero_global_list_entities",
        "boost_room_list_entities", "boost_global_list_entities",
        "night_room_list_entities", "night_global_list_entities",
    ):
        assert inputs[key]["selector"]["entity"]["multiple"] is True


def test_policy_actions_include_priority_boost_gate_and_manual_guard() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")
    for expected in (
        "zero_effect", "media_player.volume_mute", "zero_extra_actions",
        "boost_delta", "boost_cap", "boost_apply_when",
        "connected_builtin_gate", "connected_active_count", "connected_playing_count",
        "label_entities(", "label_devices(", "device_entities(",
        "minimum_global_area_ids", "zero_global_area_ids", "boost_global_area_ids", "night_global_area_ids",
        "fade_interrupted_by_manual_volume", "previous_scheduled_volume",
        "manual_learning_base", "manual_learning_ha_conditions",
        "number.set_value", "input_number.set_value",
        "media_player.select_sound_mode", "eq_follow_ha_conditions",
    ):
        assert expected in text


def test_blueprint_does_not_hardcode_private_policy_entities() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "binary_sensor.abwesend", "sensor.sleeprooms", "fritzbox_callmonitor",
        "eingang_people_counter", "input_number.tv_min_vol", "input_number.tv_max_vol",
        "chreece", "dehumidifier", "3d_printer",
    ):
        assert forbidden not in text
