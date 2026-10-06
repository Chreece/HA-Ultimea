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
        "source_players_earc",
        "source_players_hdmi",
        "source_players_optical",
        "source_players_aux",
        "source_players_bluetooth",
        "source_players_usb",
        "handoff_players_earc",
        "handoff_players_hdmi",
        "handoff_players_optical",
        "handoff_players_aux",
        "handoff_players_bluetooth",
        "handoff_players_usb",
        "source_assistants",
        "assistant_source",
        "source_fallback",
        "sound_mode_earc",
        "sound_mode_hdmi",
        "sound_mode_optical",
        "sound_mode_aux",
        "sound_mode_bluetooth",
        "sound_mode_usb",
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

    for key in (
        "source_players_earc",
        "source_players_hdmi",
        "source_players_optical",
        "source_players_aux",
        "source_players_bluetooth",
        "source_players_usb",
        "handoff_players_earc",
        "handoff_players_hdmi",
        "handoff_players_optical",
        "handoff_players_aux",
        "handoff_players_bluetooth",
        "handoff_players_usb",
    ):
        selector = inputs[key]["selector"]["entity"]
        assert selector["multiple"] is True
        assert selector["filter"][0]["domain"] == "media_player"
        assert inputs[key]["default"] == []

    assert inputs["source_fallback"]["default"] == "No change"
    assert inputs["source_fallback"]["selector"]["select"]["options"] == [
        "No change",
        "eARC",
        "HDMI",
        "Optical",
        "AUX",
        "Bluetooth",
        "USB",
    ]

    assistant_selector = inputs["source_assistants"]["selector"]["entity"]
    assert assistant_selector["multiple"] is True
    assert assistant_selector["filter"][0]["domain"] == "assist_satellite"
    assert inputs["source_assistants"]["default"] == []
    assert inputs["assistant_source"]["default"] == "No change"
    assert inputs["assistant_source"]["selector"]["select"]["options"] == [
        "No change",
        "eARC",
        "HDMI",
        "Optical",
        "AUX",
        "Bluetooth",
        "USB",
    ]

    expected_input_modes = [
        "Automatic / no input default",
        "Movie",
        "Music",
        "Voice",
        "Sport",
        "Night",
        "Game",
    ]
    for key in (
        "sound_mode_earc",
        "sound_mode_hdmi",
        "sound_mode_optical",
        "sound_mode_aux",
        "sound_mode_bluetooth",
        "sound_mode_usb",
    ):
        assert inputs[key]["default"] == "Automatic / no input default"
        assert inputs[key]["selector"]["select"]["options"] == expected_input_modes

    assert inputs["handoff_transition"]["default"]["seconds"] == 15


def test_new_mapped_source_start_wakes_off_bar_before_policy_calculations() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    wake_var = text.index("source_start_wake_bars")
    wake_action = text.index("action: media_player.turn_on", wake_var)
    policy_calculations = text.index("now_seconds:")

    assert "source_start_trigger_active and source_start_requested_source != ''" in text
    assert "and is_state(candidate_bar, 'off')" in text
    assert 'for_each: "{{ source_start_wake_bars }}"' in text
    assert wake_var < wake_action < policy_calculations


def test_real_source_stop_is_not_delayed_by_transient_pause_guard() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")
    guard = text.index("Transient source-player pause from input handoff ignored.")
    prefix = text[max(0, guard - 1800):guard]

    assert "trigger.from_state.state == 'playing'" in prefix
    assert "trigger.to_state.state == 'paused'" in prefix
    assert "trigger.to_state.state != 'playing'" not in prefix
    assert 'delay: "00:00:10"' in prefix


def test_source_routing_triggers_only_on_playback_state_edges() -> None:
    data = _load_blueprint()
    triggers = data["triggers"]

    source_inputs = {
        "source_media_earc": "source_players_earc",
        "source_media_hdmi": "source_players_hdmi",
        "source_media_optical": "source_players_optical",
        "source_media_aux": "source_players_aux",
        "source_media_bluetooth": "source_players_bluetooth",
        "source_media_usb": "source_players_usb",
    }

    for trigger_id, input_name in source_inputs.items():
        matches = [
            trigger
            for trigger in triggers
            if trigger.get("id") == trigger_id
            and trigger.get("entity_id") == {"!input": input_name}
        ]
        assert len(matches) == 2
        assert any(trigger.get("to") == "playing" for trigger in matches)
        assert any(trigger.get("from") == "playing" for trigger in matches)

        for trigger in matches:
            assert trigger.get("trigger") == "state"
            assert trigger.get("from") == "playing" or trigger.get("to") == "playing"


def test_blueprint_contains_learning_transition_and_audio_actions() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")

    for action in (
        "input_number.set_value",
        "media_player.volume_set",
        "media_player.select_sound_mode",
        "media_player.select_source",
        "media_player.turn_on",
        "media_player.media_pause",
        "media_player.media_play",
    ):
        assert action in text

    for mode in ("Night", "Movie", "Music", "Voice", "Sport", "Game"):
        assert mode in text

    assert "trigger: time_pattern" not in text
    assert "transition_before_start" in text
    assert "trigger_variables:" in text
    assert "fade_held_bars" in text
    assert "fade_endpoint_stop_bars" in text
    assert "fade_recent_policy_change" in text
    assert "mode: parallel" in text
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
    for trigger_id in (
        "source_media_earc",
        "source_media_hdmi",
        "source_media_optical",
        "source_media_aux",
        "source_media_bluetooth",
        "source_media_usb",
    ):
        assert trigger_id in text
    assert "latest_playing_source" in text
    assert "latest_playing_entity" in text
    assert "source_start_trigger_active" in text
    assert "trigger.from_state.state != 'playing'" in text
    assert "Source routing ignored media-player attribute-only update." in text
    assert "trigger.from_state.state == trigger.to_state.state" in text
    assert "source_start_wake_bars" in text
    assert "source_start_handoff_needed" in text
    assert "source_start_handoff_players" in text
    assert "configured_handoff_players" in text
    assert "eligible_handoff_players" in text
    assert "has_configured_handoff_players" in text
    assert "handoff_players_to_pause" in text
    assert "media_source_handoff_required" in text
    assert "assistant_source_active" in text
    assert "bar_became_available" in text
    assert "trigger.from_state.state in ['unknown', 'unavailable']" in text
    assert "trigger.to_state.state not in ['unknown', 'unavailable']" in text
    assert "routing_activity_active" in text
    assert "wake_for_active_route" in text
    assert "and is_state(bar, 'off')" in text
    assert "not wake_for_active_route" in text
    assert "source_assistant_change" in text
    assert "obj.state not in ['idle', 'unknown', 'unavailable']" in text
    assert "{% if assistant_source_active %}" in text
    assert "{{ assistant_source }}" in text
    assert "as_timestamp(obj.last_changed, 0)" in text
    assert "ultimea_players is string or ultimea_players | length == 1" in text
    assert "source_fallback" in text
    assert "immediate_restore_required" in text
    assert "handoff_transition_seconds <= 0" in text
    assert "trigger_id != 'bar_volume_change'" in text
    assert "conditional_source_room_change" not in text
    assert "conditional_source_area_ids" not in text
    assert "matching_audio_selectors" in text
    assert "selector_requested_source" in text
    assert "requested_source" in text
    assert "effective_requested_source" in text
    assert "requested_source == 'eARC'" in text
    assert "'ARC' in supported_sources" in text
    assert "source_list" in text
    assert "Transient source-player pause from input handoff ignored." in text
    assert "trigger.from_state.state == 'playing'" in text
    assert "trigger.to_state.state == 'paused'" in text
    assert "trigger.to_state.state != 'playing'" not in text
    # The transient-pause observer must outlive the worst-case protected
    # handoff budget: 2 s pause confirmation + 150 ms pre-source settle +
    # 3 s source confirmation + 500 ms source settle + 2 s DSP settle = 7.65 s.
    # Otherwise the observer can wrongly route the fallback source before the
    # original handoff has resumed playback, producing an AUX/eARC ping-pong.
    assert 'delay: "00:00:10"' in text
    assert 'delay: "00:00:06"' not in text
    assert 'milliseconds: 150' in text
    assert 'milliseconds: 500' in text
    assert 'milliseconds: 2000' in text
    assert 'timeout: "00:00:02"' in text
    assert "state_attr(bar, 'source') == effective_requested_source" in text
    assert "handoff_players_to_pause" in text
    assert 'entity_id: "{{ repeat.item }}"' in text
    assert "Source handoff aborted because no active pause/resume controller is available." in text
    assert "Source handoff aborted because the pause/resume controller did not confirm paused." in text
    assert "Source handoff stopped with the media player paused because the soundbar did not confirm the requested input." in text
    assert "{% if has_configured_handoff_players %}" in text
    assert "{% set ns.players = [latest_playing_entity] %}" in text
    assert 'for_each: "{{ handoff_players_to_pause }}"' in text

    pause_action = text.index("action: media_player.media_pause")
    policy_calculations = text.index("now_seconds:")
    assert pause_action < policy_calculations

    pause_confirm = text.index("{% set ns = namespace(all_paused=true) %}", pause_action)
    pause_abort = text.index(
        "Source handoff aborted because the pause/resume controller did not confirm paused.",
        pause_confirm,
    )
    source_action = text.index("action: media_player.select_source", pause_abort)
    source_confirm = text.index(
        "{{ state_attr(bar, 'source') == effective_requested_source }}",
        source_action,
    )
    source_abort = text.index(
        "Source handoff stopped with the media player paused because the soundbar did not confirm the requested input.",
        source_confirm,
    )
    resume_action = text.index("action: media_player.media_play", source_abort)
    assert pause_action < pause_confirm < pause_abort < source_action
    assert source_action < source_confirm < source_abort < resume_action

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
    assert "[zone_max_candidate, max_volume] | min" in text
    assert "[manual_zone_max_candidate, max_volume] | min" in text
    assert "[fade_zone_max_candidate, fade_live_global_max] | min" in text
    assert "[final_zone_max_candidate, final_live_global_max] | min" in text
    assert "bar_scheduled_volume" in text
    assert "bar_source_change" in text
    assert "source_effective_max" in text
    assert "source_live_volume - source_effective_max > 0.009" in text
    assert "source_input_sound_mode" in text
    assert "source_requested_sound_mode" in text
    assert "routed_input_sound_mode" in text
    assert "routed_requested_sound_mode" in text
    assert "routed_supported_sound_modes" in text
    assert "routed_current_sound_mode" in text
    assert "Automatic / no input default" in text
    assert "source_input_sound_mode != 'Automatic / no input default'" in text
    assert "ULTIMEA source default sound mode handled." in text
    assert "'bar_source_change'" in text
    assert "source_night_override_active" in text
    assert "source_supported_sound_modes" in text
    assert "source_requested_sound_mode in source_supported_sound_modes" in text
    assert "sound_mode: \"{{ source_requested_sound_mode }}\"" in text
    assert "sound_mode: \"{{ routed_requested_sound_mode }}\"" in text
    assert "Seed the default only after the source request has had a" in text
    assert "current_source_key" in text
    assert "current_input_players" in text
    assert "eq_connected_players" in text
    assert "eq_input_has_connected_player" in text
    assert "trigger_entity in eq_connected_players" in text
    assert "and eq_input_has_connected_player" in text
    assert "wait_template:" in text
    assert "timeout: \"00:00:03\"" in text
    assert "continue_on_timeout: true" in text
    assert "live == ns.target" in text
    assert "trigger_id == 'connected_change'" in text
    assert "{% for entity in eq_connected_players %}" in text
    assert "trigger_entity in mapped" in text
    assert "manual_scheduled_volume" in text
    assert "manual_settled_volume" in text
    assert "manual_volume_stable_after_delay" in text
    assert "manual_settled_learning_value" in text
    assert 'delay: "00:00:03"' in text
    assert "manual_learning_value" not in text
    assert "volume_source_is_learning_echo" in text
    assert "volume_source_context_is_bar_child" in text
    assert "volume_source_matches_live_volume" in text
    assert "volume_source_recent_bar_update" in text
    assert "trigger.to_state.context.parent_id == obj.context.id" in text
    assert "delay: \"00:00:05\"" in text
    assert "manual_in_time_transition" in text
    assert "manual_transition_learns_min" in text
    assert "manual_transition_learns_max" in text
    assert "manual_should_learn_endpoint" in text
    assert "manual_user_raised" in text
    assert "manual_user_lowered" in text
    assert "fade_live_min_volume" in text
    assert "fade_live_global_max" in text
    assert "fade_new_manual_hold" in text
    assert "fade_new_endpoint_stop" in text
    assert "fade_hold_should_release" in text
    assert "fade_scheduled_volume" in text
    assert "< fade_current_volume - 0.009" in text
    assert "> fade_current_volume + 0.009" in text
    assert "bar not in fade_endpoint_stop_bars" in text
    assert "area_id(" in text
    assert "sound_mode_list" in text
    assert "quiet_hours_enabled" in text


def test_blueprint_does_not_hardcode_user_entity_ids() -> None:
    text = BLUEPRINT.read_text(encoding="utf-8")
    assert "media_player.living_room" not in text
    assert "input_number.ultimea" not in text
    assert "binary_sensor." not in text


def test_blueprint_has_no_periodic_automation_triggers() -> None:
    data = _load_blueprint()
    triggers = data["triggers"]
    assert all(item["trigger"] != "time_pattern" for item in triggers)

    state_trigger = next(item for item in triggers if item.get("id") == "bar_state_change")
    assert "to" in state_trigger and state_trigger["to"] is None

    volume_trigger = next(item for item in triggers if item.get("id") == "bar_volume_change")
    assert volume_trigger["attribute"] == "volume_level"
    assert volume_trigger["enabled"] == {"!input": "learn_manual_volume_changes"}

    source_trigger = next(item for item in triggers if item.get("id") == "bar_source_change")
    assert source_trigger["attribute"] == "source"

    expected_source_triggers = {
        "source_media_earc": "source_players_earc",
        "source_media_hdmi": "source_players_hdmi",
        "source_media_optical": "source_players_optical",
        "source_media_aux": "source_players_aux",
        "source_media_bluetooth": "source_players_bluetooth",
        "source_media_usb": "source_players_usb",
        "source_assistant_change": "source_assistants",
    }
    for trigger_id, input_name in expected_source_triggers.items():
        source_trigger = next(item for item in triggers if item.get("id") == trigger_id)
        assert source_trigger["entity_id"] == {"!input": input_name}
