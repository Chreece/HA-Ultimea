"""Reporter-confirmed Poseidon D70 controls from HA-Ultimea issue #4.

The GitHub attachment ZIP was not independently accessible to this
environment, so these tests are limited to the explicit command bytes
provided by the D70 hardware owner. They make no INFO/EQ claims.
"""

from __future__ import annotations

import ast
import asyncio
import copy
import importlib.util
from enum import IntFlag
import json
from pathlib import Path
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "ultimea"
PACKAGE = "_ultimea_d70_contract"


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
    mod = importlib.util.module_from_spec(spec)
    sys.modules[fullname] = mod
    spec.loader.exec_module(mod)
    return mod


const = _load("const")
profiles = _load("profiles")
protocol = _load("protocol")
evidence = json.loads((ROOT / "tests/fixtures/d70_reporter_commands.json").read_text())
pcap = json.loads((ROOT / "tests/fixtures/d70_pcap_evidence.json").read_text())


def test_reporter_model_and_every_source_setter():
    assert evidence["model"] == "Poseidon D70"
    assert profiles.profile_for_model(evidence["model"]).key == "poseidon_d70"
    samples = {
        const.Source.EARC: 0,
        const.Source.OPTICAL: 1,
        const.Source.BLUETOOTH: 2,
        const.Source.AUX: 3,
        const.Source.USB: 4,
    }
    for source, value in samples.items():
        assert profiles.source_value_for_model("Poseidon D70", source) == value
        assert profiles.decode_source_value("Poseidon D70", value, info=False) is source
        assert protocol.build_command(2, const.CMD_SOURCE, bytes([value])).hex() == (
            evidence["source_frames"][source.value]
        )
    assert profiles.source_value_for_model("Poseidon D70", const.Source.HDMI) is None
    assert profiles.source_options_for_model("Poseidon D70") == (
        "ARC", "Optical", "AUX", "Bluetooth", "USB"
    )


def test_mute_and_poweroff_captured_frames():
    assert protocol.build_command(2, const.CMD_MUTE, b"\x00").hex() == evidence["mute_on"]
    assert protocol.build_command(2, const.CMD_MUTE, b"\x01").hex() == evidence["mute_off"]
    assert protocol.build_command(2, const.CMD_POWER, b"\x00").hex() == evidence["power_off"]
    supported = set(profiles.VERIFIED_D70_FEATURES)
    assert {const.Feature.POWER, const.Feature.MUTE, const.Feature.SOURCE, const.Feature.VOLUME} <= supported
    for feature in (const.Feature.POWER, const.Feature.MUTE, const.Feature.SOURCE, const.Feature.VOLUME):
        assert profiles.can_write_feature("Poseidon D70", feature, supported)
    for feature in (const.Feature.SOUND_MODE, const.Feature.EQUALIZER, const.Feature.STYLE, const.Feature.XUPMIX):
        assert not profiles.can_write_feature("Poseidon D70", feature, set(const.Feature))


def test_power_on_not_advertised_when_d70_is_ble_unreachable():
    supported = set(profiles.VERIFIED_D70_FEATURES)
    d70 = profiles.profile_for_model("Poseidon D70")
    assert not d70.power_on_supported
    assert not d70.power_off_disconnect_fallback
    assert not profiles.can_turn_on("Poseidon D70", supported)
    assert profiles.can_turn_on(
        "Poseidon D80 Boom", {const.Feature.POWER}
    )
    assert not profiles.can_turn_on("Aura A40", set(const.Feature))


def test_d80_and_a40_safety_regression():
    assert profiles.source_value_for_model("Poseidon D80 Boom", const.Source.EARC) == 0x10
    assert profiles.source_value_for_model("Poseidon D70", const.Source.EARC) == 0x00
    assert profiles.source_value_for_model("Aura A40", const.Source.BLUETOOTH) is None
    assert not profiles.writable_features_for_model("Aura A40", set(const.Feature))
    assert profiles.profile_for_model("Poseidon D80 Boom").power_off_disconnect_fallback


def _isolated_methods(method_names: tuple[str, ...], *, player: bool = False):
    """Execute real production method AST without importing Home Assistant."""
    source_path = COMPONENT / ("media_player.py" if player else "device.py")
    parsed = ast.parse(source_path.read_text(encoding="utf-8"))
    target = "UltimeaMediaPlayer" if player else "UltimeaDevice"
    cls = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == target)
    methods = [
        copy.deepcopy(node) for node in cls.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in method_names
    ]
    assert len(methods) == len(method_names)
    isolated = ast.ClassDef(
        name=target, bases=[], keywords=[], body=methods, decorator_list=[]
    )
    ex = ast.Module(body=[
        ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
        isolated,
    ], type_ignores=[])
    return compile(ast.fix_missing_locations(ex), str(source_path), "exec"), target


def _device_scope():
    error = type("UltimeaCommandError", (Exception,), {})
    connection_error = type("UltimeaConnectionError", (error,), {})
    return {
        "asyncio": asyncio,
        "Feature": const.Feature,
        "GROUP_CONTROL": const.GROUP_CONTROL,
        "CMD_POWER": const.CMD_POWER,
        "CMD_MUTE": const.CMD_MUTE,
        "GROUP_INFO": const.GROUP_INFO,
        "INFO_POWER": const.INFO_POWER,
        "INFO_MUTE": const.INFO_MUTE,
        "can_write_feature": profiles.can_write_feature,
        "can_turn_on": profiles.can_turn_on,
        "profile_for_model": profiles.profile_for_model,
        "build_command": protocol.build_command,
        "UltimeaCommandError": error,
        "UltimeaConnectionError": connection_error,
        "UltimeaError": error,
        "_LOGGER": SimpleNamespace(debug=lambda *args, **kwargs: None),
    }


def _poweroff_peer(*, write_error: Exception | None = None, send_ack: bool = True):
    """Execute the actual production ACK dispatcher with a simulated BLE peer."""
    source, name = _isolated_methods(
        ("_async_request", "_async_write_verified", "async_set_power")
    )
    scope = _device_scope()
    exec(source, scope)
    obj = scope[name]()
    obj.identity = SimpleNamespace(model="Poseidon D70")
    obj.capabilities = SimpleNamespace(features=set(profiles.VERIFIED_D70_FEATURES))
    obj.supports = lambda feature: feature in obj.capabilities.features
    obj.state = SimpleNamespace(power=True)
    obj._write_uuid = "test-write-uuid"
    obj._command_lock = asyncio.Lock()
    obj._pending = None
    obj._schedule_disconnect = lambda: None
    obj._async_notify_listeners = lambda: None
    obj.connected = False  # Power-off path must not fake success on disconnect.

    async def on_write(uuid, packet, response=False):
        assert uuid == "test-write-uuid"
        assert not response
        assert packet.hex() == pcap["transactions"]["power_off"]["tx"]
        assert obj._pending is not None
        group, command, expected_data, future = obj._pending
        assert (group, command, expected_data) == (
            const.GROUP_CONTROL, const.CMD_POWER, b"\x00"
        )
        if write_error is not None:
            raise write_error
        if send_ack:
            reply = next(protocol.iter_frames(
                bytes.fromhex(pcap["transactions"]["power_off"]["rx"])
            ))
            assert reply.data == expected_data
            future.set_result(reply)

    peer = SimpleNamespace(write_gatt_char=AsyncMock(side_effect=on_write))
    obj.async_ensure_connected = AsyncMock(return_value=peer)
    return obj, peer, scope


def test_d70_poweroff_waits_for_pcap_confirmed_ack():
    obj, peer, scope = _poweroff_peer()
    asyncio.run(obj.async_set_power(False))
    peer.write_gatt_char.assert_awaited_once()
    assert obj.state.power is False
    assert obj._pending is None
    obj.async_ensure_connected.assert_awaited_once()


def test_d70_poweroff_rejected_gatt_never_fakes_state_even_if_disconnected():
    obj, peer, scope = _poweroff_peer(write_error=OSError("GATT rejected"))
    with pytest.raises(scope["UltimeaCommandError"], match="GATT rejected"):
        asyncio.run(obj.async_set_power(False))
    assert obj.state.power is True
    assert obj._pending is None
    peer.write_gatt_char.assert_awaited_once()


def test_d70_poweroff_missing_ack_never_fakes_state():
    source, name = _isolated_methods(("async_set_power",))
    scope = _device_scope()
    exec(source, scope)
    obj = scope[name]()
    obj.identity = SimpleNamespace(model="Poseidon D70")
    obj.capabilities = SimpleNamespace(features=set(profiles.VERIFIED_D70_FEATURES))
    obj.state = SimpleNamespace(power=True)
    obj.connected = False
    obj._async_write_verified = AsyncMock(
        side_effect=scope["UltimeaCommandError"]("missing ACK")
    )
    with pytest.raises(scope["UltimeaCommandError"], match="missing ACK"):
        asyncio.run(obj.async_set_power(False))
    obj._async_write_verified.assert_awaited_once()
    assert obj._async_write_verified.await_args.kwargs["refresh"] is None
    assert obj.state.power is True


def test_actual_pcap_frames_confirm_all_supported_d70_controls():
    assert pcap["model"] == "Poseidon D70"
    assert pcap["firmware"] == "V50"
    assert pcap["capture_packets"] == 249
    assert pcap["protocol_frames"] == 139
    for name, pair in pcap["transactions"].items():
        sent = bytes.fromhex(pair["tx"])
        replied = bytes.fromhex(pair["rx"])
        assert sent[0] == 0xAA
        assert replied[0] == 0xBB
        assert sent[1:] == replied[1:]
        group, command, value = sent[3], sent[4], sent[5:-1]
        assert protocol.build_command(group, command, value) == sent
        parsed = list(protocol.iter_frames(replied))
        assert len(parsed) == 1
        assert (parsed[0].group, parsed[0].command, parsed[0].data) == (
            group, command, value
        )
    assert pcap["transactions"]["power_off"]["ack_delay_ms"] > 0
    assert pcap["transactions"]["power_off"]["ack_delay_ms"] < 300


def test_pcap_verifies_arc_info_and_no_d70_hdmi_input():
    flags = pcap["capabilities_flags"]
    assert len(flags) == 17
    assert flags[4] == 1  # ARC
    assert flags[5] == 0  # HDMI
    assert flags[6:9] == [1, 1, 1]  # BT, AUX, USB
    decoded = list(protocol.iter_frames(bytes.fromhex(pcap["info_source_arc"])))
    assert len(decoded) == 1
    assert decoded[0].group == const.GROUP_INFO
    assert decoded[0].command == const.INFO_SOURCE
    assert profiles.decode_source_value(
        "Poseidon D70", decoded[0].data[0], info=True
    ) is const.Source.EARC
    assert profiles.decode_source_value("Poseidon D70", 0x05, info=True) is None


def test_d70_poweron_rejected_without_bluetooth_io():
    source, name = _isolated_methods(("async_set_power",))
    scope = _device_scope()
    exec(source, scope)
    obj = scope[name]()
    obj.identity = SimpleNamespace(model="Poseidon D70")
    obj.capabilities = SimpleNamespace(features=set(profiles.VERIFIED_D70_FEATURES))
    obj.state = SimpleNamespace(power=False)
    obj._async_request = AsyncMock(side_effect=AssertionError("Unexpected Bluetooth write"))
    obj._async_write_verified = AsyncMock(side_effect=AssertionError("Unexpected Bluetooth write"))

    with pytest.raises(scope["UltimeaCommandError"], match="power-on"):
        asyncio.run(obj.async_set_power(True))
    assert obj.state.power is False
    obj._async_request.assert_not_awaited()
    obj._async_write_verified.assert_not_awaited()


def test_d70_mute_on_off_use_reported_payloads():
    source, name = _isolated_methods(("async_set_mute",))
    scope = _device_scope()
    exec(source, scope)
    obj = scope[name]()
    obj._async_write_verified = AsyncMock(return_value=None)
    asyncio.run(obj.async_set_mute(True))
    asyncio.run(obj.async_set_mute(False))
    calls = obj._async_write_verified.await_args_list
    assert len(calls) == 2
    assert [call.args[:2] for call in calls] == [
        (const.CMD_MUTE, b"\x00"), (const.CMD_MUTE, b"\x01")
    ]
    assert all(call.kwargs["feature"] is const.Feature.MUTE for call in calls)


def test_d70_media_player_exposes_only_turnoff():
    source, name = _isolated_methods(("supported_features",), player=True)
    class Flags(IntFlag):
        TURN_ON=1; TURN_OFF=2; VOLUME_SET=4; VOLUME_STEP=8
        VOLUME_MUTE=16; SELECT_SOURCE=32; SELECT_SOUND_MODE=64
    scope = {
        "Feature": const.Feature,
        "MediaPlayerEntityFeature": Flags,
        "can_turn_on": profiles.can_turn_on,
    }
    exec(source, scope)
    media = scope[name]()
    media.device = SimpleNamespace(
        identity=SimpleNamespace(model="Poseidon D70"),
        capabilities=SimpleNamespace(features=set(profiles.VERIFIED_D70_FEATURES)),
    )
    media._can_write = lambda feature: profiles.can_write_feature(
        media.device.identity.model, feature, media.device.capabilities.features
    )
    flags = media.supported_features
    assert flags & Flags.TURN_OFF
    assert not flags & Flags.TURN_ON
    assert flags & Flags.VOLUME_SET
    assert flags & Flags.VOLUME_MUTE
    assert flags & Flags.SELECT_SOURCE
    assert not flags & Flags.SELECT_SOUND_MODE
