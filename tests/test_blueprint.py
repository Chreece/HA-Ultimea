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
        "quiet_start",
        "quiet_end",
        "transition_before",
        "transition_after",
        "min_volume_helper",
        "max_volume_helper",
        "low_volume_binary_entities",
        "list_state_entities",
        "tts_media_players",
        "voice_assistants",
        "night_mode_entities",
        "connected_media_players",
        "content_classifier_entities",
        "ai_content_actions",
        "apply_volume_follow",
        "apply_night_mode",
        "apply_eq_follow",
    }
    assert required <= inputs.keys()

    ultimea_filter = inputs["ultimea_players"]["selector"]["entity"]["filter"]
    assert {"integration": "ultimea", "domain": "media_player"} in ultimea_filter

    assert inputs["min_volume_helper"]["selector"]["entity"]["filter"] == [
        {"domain": "input_number"}
    ]
    assert inputs["max_volume_helper"]["selector"]["entity"]["filter"] == [
        {"domain": "input_number"}
    ]


def test_blueprint_contains_learning_transition_and_audio_actions() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    for action in (
        "input_number.set_value",
        "media_player.volume_set",
        "media_player.select_sound_mode",
    ):
        assert action in text

    for mode in ("Night", "Movie", "Music", "Voice", "Sport", "Game"):
        assert mode in text

    assert "seconds: \"/5\"" in text
    assert "manual_differs_from_expected" in text
    assert "area_id(" in text
    assert "states(holder).split(',')" in text
    assert "sound_mode_list" in text
    assert "quiet_hours_enabled" in text


def test_blueprint_does_not_hardcode_user_entity_ids() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")
    assert "media_player.living_room" not in text
    assert "input_number.ultimea" not in text
    assert "binary_sensor." not in text
