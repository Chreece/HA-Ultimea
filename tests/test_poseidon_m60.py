"""Wire-verified Poseidon M60 model profile contract."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "ultimea"
PACKAGE = "_ultimea_m60_contract"


def _load(name: str):
    fullname = f"{PACKAGE}.{name}"
    if fullname in sys.modules:
        return sys.modules[fullname]
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(COMPONENT)]
        sys.modules[PACKAGE] = package
    spec = importlib.util.spec_from_file_location(fullname, COMPONENT / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")
profiles = _load("profiles")
protocol = _load("protocol")
fixture = json.loads((ROOT / "tests/fixtures/poseidon_m60_diagnostic.json").read_text())


def test_m60_discovery_fixture_is_sanitized_and_selects_verified_profile():
    assert fixture["model"] == "Poseidon M60"
    assert fixture["firmware"] == "V23"
    assert fixture["transport"] == "common_8d11_8d22"
    assert set(fixture["redactions"].values()) == {"REDACTED"}
    assert "U3721" not in json.dumps(fixture)
    profile = profiles.profile_for_model(fixture["model"])
    assert profile.key == "poseidon_m60"
    assert profile.verified
    assert not profiles.can_turn_on(fixture["model"], profile.verified_features)


def test_m60_decodes_only_the_four_wire_verified_inputs_and_modes():
    sources = {
        const.Source.EARC: 0x10,
        const.Source.OPTICAL: 0x01,
        const.Source.BLUETOOTH: 0x02,
        const.Source.USB: 0x04,
    }
    for source, value in sources.items():
        assert profiles.source_value_for_model("Poseidon M60", source) == value
        assert profiles.decode_source_value("Poseidon M60", value, info=True) is source
    assert profiles.source_value_for_model("Poseidon M60", const.Source.AUX) is None
    assert profiles.decode_source_value("Poseidon M60", 0x03, info=True) is None
    assert profiles.decode_source_value("Poseidon M60", 0x05, info=True) is None
    source_frame = next(protocol.iter_frames(bytes.fromhex("bb0100010610c1")))
    mode_frame = next(protocol.iter_frames(bytes.fromhex("bb0100010804b7")))
    assert profiles.decode_source_value(
        "Poseidon M60", source_frame.data[0], info=True
    ) is const.Source.EARC
    assert profiles.decode_sound_mode_value(
        "Poseidon M60", mode_frame.data[0]
    ) is const.SoundMode.SPORT
    assert profiles.source_options_for_model("Poseidon M60") == (
        "eARC", "Optical", "Bluetooth", "USB"
    )
    assert profiles.decode_sound_mode_value("Poseidon M60", 0x08) is const.SoundMode.CUSTOM
    assert profiles.sound_mode_value_for_model("Poseidon M60", const.SoundMode.CUSTOM) == 0x08
    assert profiles.sound_mode_value_for_model("Poseidon M60", const.SoundMode.STYLE) is None


def test_m60_write_commands_match_the_hci_capture():
    assert protocol.build_command(2, const.CMD_POWER, b"\x00").hex() == "aa0100020900b5"
    assert protocol.build_command(2, const.CMD_POWER, b"\x01").hex() == "aa0100020901b6"
    assert protocol.build_command(2, const.CMD_VOLUME, b"\x20").hex() == "aa0100020320cf"
    assert protocol.build_command(2, const.CMD_VOLUME, b"\x0a").hex() == "aa010002030ab9"
    assert protocol.build_command(2, const.CMD_MUTE, b"\x00").hex() == "aa0100020a00b6"
    assert protocol.build_command(2, const.CMD_MUTE, b"\x01").hex() == "aa0100020a01b7"
    for value, frame in ((1, "aa0100020201af"), (2, "aa0100020202b0"), (4, "aa0100020204b2"), (16, "aa0100020210be")):
        assert protocol.build_command(2, const.CMD_SOURCE, bytes([value])).hex() == frame
    for value in range(1, 7):
        assert protocol.build_command(2, const.CMD_SOUND_MODE, bytes([value]))[5] == value
    assert protocol.build_command(2, const.CMD_SOUND_MODE, b"\x08").hex() == "aa0100020408b8"


def test_m60_writable_surface_excludes_unproven_curve_and_settings_controls():
    verified = profiles.profile_for_model("Poseidon M60").verified_features
    assert profiles.writable_features_for_model("Poseidon M60", verified) == verified
    assert const.Feature.EQUALIZER not in verified
    assert const.Feature.STYLE not in verified
    assert const.Feature.BRIGHTNESS not in verified
