"""Aura A40 V56 evidence contract. Read replies are not authorization to write."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "ultimea"
PACKAGE = "_aura_a40_contract"


def _load_module(name: str):
    full_name = f"{PACKAGE}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(INTEGRATION)]
        sys.modules[PACKAGE] = package
    spec = importlib.util.spec_from_file_location(full_name, INTEGRATION / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


const = _load_module("const")
profiles = _load_module("profiles")
EVIDENCE = json.loads(
    (ROOT / "tests" / "fixtures" / "aura_a40_v56_diagnostic.json").read_text(
        encoding="utf-8"
    )
)


def test_a40_report_selects_read_only_profile():
    p = profiles.profile_for_model(EVIDENCE["model"])
    assert p.key == "aura_a40"
    assert profiles.profile_for_model("  aura A40  ") is p
    assert not p.verified
    assert not p.verified_features
    assert not p.wire_features
    assert not p.source_control_values
    assert EVIDENCE["firmware"] == "V56"
    assert EVIDENCE["protocol_version"] == 1
    assert EVIDENCE["transport"] == const.TRANSPORT_COMMON


def test_a40_read_features_never_enable_writes():
    observed = {const.Feature(name) for name in EVIDENCE["features"]}
    assert len(observed) == 8
    assert not profiles.writable_features_for_model("Aura A40", observed)
    assert not profiles.source_options_for_model("Aura A40")
    for feature in const.Feature:
        assert not profiles.can_write_feature("Aura A40", feature, set(const.Feature))
    assert profiles.source_value_for_model("Aura A40", const.Source.OPTICAL) is None


def test_a40_source_info_does_not_invent_hdmi_arc():
    assert EVIDENCE["observed_state"]["raw_source"] == 1
    assert EVIDENCE["observed_state"]["source"] == "optical"
    expected = {1: const.Source.OPTICAL, 2: const.Source.BLUETOOTH,
                3: const.Source.AUX, 4: const.Source.USB}
    for raw, source in expected.items():
        assert profiles.decode_source_value("Aura A40", raw, info=True) is source
    for raw in (0, 5, 16, 255):
        assert profiles.decode_source_value("Aura A40", raw, info=True) is None


def test_a40_capability_flags_match_physical_inputs():
    raw = EVIDENCE["raw_ability_flags"]
    assert len(raw) == 18
    abilities = dict(zip(const.ABILITY_FIELD_NAMES, raw))
    assert all(abilities[key] for key in ("has_bluetooth", "has_aux", "has_usb"))
    assert not any(abilities[key] for key in ("has_earc", "has_arc", "has_hdmi"))
    assert abilities["has_display_screen"] == 1
    assert abilities["has_custom_standby_time"] == 0


def test_d80_d70_source_values_and_writes_unchanged():
    assert profiles.profile_for_model("Poseidon D80 Boom").key == "poseidon_d80_boom"
    assert profiles.profile_for_model("Poseidon D70").key == "poseidon_d70"
    assert profiles.source_value_for_model("Poseidon D80 Boom", const.Source.EARC) == 0x10
    assert profiles.source_value_for_model("Poseidon D70", const.Source.EARC) == 0
    assert profiles.decode_source_value("Poseidon D80 Boom", 0, info=True) is const.Source.EARC
    assert profiles.decode_source_value("Poseidon D70", 0, info=True) is const.Source.EARC
    assert profiles.can_write_feature("Poseidon D70", const.Feature.VOLUME, {const.Feature.VOLUME})


def test_runtime_diagnostics_and_sensor_guards_present():
    runtime = (INTEGRATION / "runtime.py").read_text(encoding="utf-8")
    sensor = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    diagnostics = (INTEGRATION / "diagnostics.py").read_text(encoding="utf-8")
    assert "decode_source_value(self.identity.model, data[0], info=True)" in runtime
    assert "INFO_VALUE_TO_SOURCE.get(data[0])" not in runtime
    assert 'profile_for_model(runtime.device.identity.model).key == "aura_a40"' in sensor
    for key in ("observed_volume", "observed_source", "observed_sound_mode"):
        assert key in sensor
    assert "writable_features_for_model" in sensor
    assert '"writable_features"' in diagnostics
