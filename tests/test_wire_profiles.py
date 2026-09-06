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
