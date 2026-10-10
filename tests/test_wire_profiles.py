from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_universal_wire_profiles_present():
    profiles = (ROOT / "custom_components" / "ultimea" / "profiles.py").read_text(encoding="utf-8")
    const = (ROOT / "custom_components" / "ultimea" / "const.py").read_text(encoding="utf-8")
    assert "D80_WIRE_FEATURES" in profiles
    assert "FRONTIER_STATIC_WIRE_FEATURES" in profiles
    assert "can_write_feature" in profiles
    assert 'AUDIO_SIGNAL_FORMAT = "audio_signal_format"' in const
    assert 'SINGLE_LED_BRIGHTNESS = "single_led_brightness"' in const


def test_d80_does_not_inherit_frontier_020f():
    profiles = (ROOT / "custom_components" / "ultimea" / "profiles.py").read_text(encoding="utf-8")
    d80 = profiles.split("D80_WIRE_FEATURES", 1)[1].split("FRONTIER_STATIC_WIRE_FEATURES", 1)[0]
    assert "_control(0x0F)" not in d80
    assert "Feature.SINGLE_LED_BRIGHTNESS" not in d80


def test_frontier_led_static_map_is_unassigned():
    profiles = (ROOT / "custom_components" / "ultimea" / "profiles.py").read_text(encoding="utf-8")
    assert "Feature.SINGLE_LED_SHUTDOWN_TIME: FeatureWireSpec" in profiles
    assert "_info(0x16), _control(0x14)" in profiles
    assert "_info(0x11), _control(0x0F)" in profiles
    assert "_info(0x12), _control(0x10)" in profiles
    selector = profiles.split("def profile_for_model", 1)[1].split("def can_write_feature", 1)[0]
    assert "FRONTIER_STATIC_WIRE_FEATURES" not in selector


def test_writable_ha_surfaces_are_profile_gated():
    for filename in ("media_player.py", "select.py", "number.py", "switch.py", "button.py"):
        source = (ROOT / "custom_components" / "ultimea" / filename).read_text(encoding="utf-8")
        assert "can_write_feature" in source


def test_d70_profile_is_evidence_limited():
    profiles = (ROOT / "custom_components" / "ultimea" / "profiles.py").read_text(encoding="utf-8")
    assert 'POSEIDON_D70_MODEL = "Poseidon D70"' in profiles
    assert "D70_WIRE_FEATURES" in profiles
    assert "Feature.VOLUME: FeatureWireSpec(write=_control(CMD_VOLUME))" in profiles
    assert "Feature.SOURCE: FeatureWireSpec(write=_control(CMD_SOURCE))" in profiles
    assert "Source.EARC: 0x00" in profiles
    assert "Source.OPTICAL: 0x01" in profiles
    assert "Source.AUX: 0x03" in profiles
    d70_map = profiles.split("D70_SOURCE_CONTROL_VALUES", 1)[1].split("D70_SOURCE_NAMES", 1)[0]
    assert "Source.USB: 0x04" in d70_map
    assert "Source.BLUETOOTH: 0x02" in d70_map
    assert 'Source.EARC: "ARC"' in profiles
    assert "Feature.POWER: FeatureWireSpec(write=_control(CMD_POWER))" in profiles
    assert "Feature.MUTE: FeatureWireSpec(write=_control(CMD_MUTE))" in profiles
    assert "power_on_supported=False" in profiles
    assert "power_off_disconnect_fallback=False" in profiles
    assert "source_info_values=D70_INFO_SOURCE_VALUES" in profiles


def test_source_values_and_labels_are_profile_specific():
    profiles = (ROOT / "custom_components" / "ultimea" / "profiles.py").read_text(encoding="utf-8")
    media_player = (ROOT / "custom_components" / "ultimea" / "media_player.py").read_text(encoding="utf-8")
    device = (ROOT / "custom_components" / "ultimea" / "device.py").read_text(encoding="utf-8")
    assert "source_control_values" in profiles
    assert "source_info_values" in profiles
    assert "source_options_for_model" in profiles
    assert "source_name_for_model" in media_player
    assert "source_for_name_for_model" in media_player
    assert "source_value_for_model" in device
    assert "decode_source_value(self.identity.model, data[0], info=False)" in device
    assert "decode_source_value(self.identity.model, data[0], info=True)" in device
