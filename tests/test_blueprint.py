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


BlueprintLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping
)


def _input(loader: BlueprintLoader, node: yaml.Node) -> dict[str, str]:
    return {"!input": loader.construct_scalar(node)}


BlueprintLoader.add_constructor("!input", _input)


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


def test_adaptive_audio_blueprint_yaml_and_jinja_are_valid() -> None:
    data = _load_blueprint()
    assert data["blueprint"]["domain"] == "automation"
    assert data["blueprint"]["homeassistant"]["min_version"] == "2026.7.0"

    env = jinja2.Environment()
    for template in _walk_templates(data):
        env.parse(template)


def test_blueprint_exposes_requested_control_inputs() -> None:
    data = _load_blueprint()
    sections = data["blueprint"]["input"]
    inputs = {
        key: value
        for section in sections.values()
        for key, value in section["input"].items()
    }

    required = {
        "ultimea_players",
        "audio_input_selectors",
        "quiet_start",
        "quiet_end",
        "transition_before",
        "transition_after",
        "handoff_transition",
        "min_volume_value",
        "min_volume_helper",
        "max_volume_value",
        "max_volume_helper",
        "zone_volume_entities",
        "low_volume_binary_entities",
        "list_state_entities",
        "tts_media_players",
        "voice_assistants",
        "night_mode_entities",
        "connected_media_players",
        "content_classifier_entities",
        "ai_content_actions",
        "apply_volume_follow",
        "learn_manual_volume_changes",
        "apply_night_mode",
        "apply_eq_follow",
    }
    assert required <= inputs.keys()

    ultimea_filter = inputs["ultimea_players"]["selector"]["entity"]["filter"]
    assert {"integration": "ultimea", "domain": "media_player"} in ultimea_filter

    assert inputs["min_volume_value"]["selector"]["number"]["min"] == 0
    assert inputs["min_volume_value"]["selector"]["number"]["max"] == 100
    assert inputs["max_volume_value"]["selector"]["number"]["min"] == 0
    assert inputs["max_volume_value"]["selector"]["number"]["max"] == 100

    for key in ("min_volume_helper", "max_volume_helper", "zone_volume_entities"):
        selector = inputs[key]["selector"]["entity"]
        assert selector["multiple"] is True
        assert inputs[key]["default"] == []
        domains = selector["filter"][0]["domain"]
        assert domains == ["input_number", "number", "sensor"]

    source_selector = inputs["audio_input_selectors"]["selector"]["entity"]
    assert source_selector["multiple"] is True
    assert source_selector["filter"][0]["domain"] == ["input_select", "select"]
    assert inputs["audio_input_selectors"]["default"] == []
    assert inputs["handoff_transition"]["default"]["seconds"] == 15


def test_blueprint_contains_learning_transition_and_audio_actions() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    for action in (
        "input_number.set_value",
        "media_player.volume_set",
        "media_player.select_sound_mode",
        "media_player.select_source",
    ):
        assert action in text

    for mode in ("Night", "Movie", "Music", "Voice", "Sport", "Game"):
        assert mode in text

    assert "seconds: \"/5\"" in text
    assert "manual_differs_from_expected" in text
    assert "learn_manual_volume_changes" in text
    assert "number.set_value" in text
    assert "min_volume_value" in text
    assert "max_volume_value" in text
    assert "obj.attributes.values()" in text
    assert "value is iterable" in text
    assert "value is string and ',' in value" in text
    assert "room_list_area_ids" in text
    assert "previous_scheduled_volume" in text
    assert "fade_interrupted_by_manual_volume" in text
    assert "fade_can_adjust" in text
    assert "audio_input_change" in text
    assert "matching_audio_selectors" in text
    assert "requested_source" in text
    assert "source_list" in text
    assert "bar_volume_trigger_is_current" in text
    assert "guarded_handoff_required" in text
    assert "guarded_handoff_steps" in text
    assert "handoff_expected_before" in text
    assert "boundary_retake_allowed" in text
    assert "boundary_guarded_handoff_required" in text
    assert "boundary_handoff_target" in text
    assert "handoff_list_low_now" in text
    assert "zone_volume_matches" in text
    assert "zone_volume_entity" in text
    assert "manual_zone_volume_entity" in text
    assert "manual_zone_max_candidate" in text
    assert "bar_max_volume" in text
    assert "bar_scheduled_volume" in text
    assert "manual_scheduled_volume" in text
    assert "delay: \"00:00:05\"" in text
    assert "manual_in_time_transition" in text
    assert "area_id(" in text
    assert "sound_mode_list" in text
    assert "quiet_hours_enabled" in text


def test_blueprint_does_not_hardcode_user_entity_ids() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")
    assert "media_player.living_room" not in text
    assert "input_number.ultimea" not in text
    assert "binary_sensor." not in text
