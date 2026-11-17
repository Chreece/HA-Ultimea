"""Replay issue #40's read-only A60 Pro evidence through the production runtime."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_style import Peer, code, device_with_peer


EVIDENCE = json.loads(
    (Path(__file__).parent / "fixtures/aura_a60_pro_v57_diagnostic.json").read_text()
)


def a60_with_peer(code):
    dev, _ = device_with_peer(code)
    dev.identity.model = EVIDENCE["model"]
    dev.restore_capabilities()
    replies = {
        getattr(code.const, f"INFO_{name.upper()}"): bytes.fromhex(value)
        for name, value in EVIDENCE["info_replies"].items()
    }

    class A60Peer(Peer):
        async def write_gatt_char(self, uuid, packet, response=False):
            group, command = packet[3:5]
            data = bytes(packet[5:-1])
            self.trace.append((group, command, data))
            if group == code.const.GROUP_CONTROL:
                raise AssertionError("Read-only A60 Pro must never send CONTROL")
            if group == code.const.GROUP_CAPABILITIES:
                if command == code.protocol.SAFE_CODE_COMMAND:
                    assert data == bytes.fromhex(EVIDENCE["safe_code"]["request"])
                    reply = bytes.fromhex(EVIDENCE["safe_code"]["response"])
                else:
                    assert command == code.const.CAP_FETCH_ABILITIES
                    reply = bytes(EVIDENCE["raw_ability_flags"])
            else:
                assert group == code.const.GROUP_INFO and not data
                reply = {
                    code.const.INFO_PROTOCOL: b"\x01\x00",
                    code.const.INFO_MODEL: EVIDENCE["model"].encode(),
                    code.const.INFO_SERIAL: b"",  # No reporter identifier retained.
                    code.const.INFO_FIRMWARE: b"\x39\x00",
                    **replies,
                }[command]
            self.rx(group, command, reply)

    peer = A60Peer(code, dev)
    dev._client = peer
    return dev, peer


def test_a60_profile_decodes_only_observed_earc_and_has_no_writes(code):
    c = code.const
    profile = code.profiles.profile_for_model(EVIDENCE["model"])
    assert profile.key == "aura_a60_pro"
    assert code.profiles.profile_for_model("  AURA a60 PRO  ") is profile
    assert not profile.verified
    assert not profile.verified_features
    assert not profile.wire_features
    assert not profile.source_control_values
    for value in range(256):
        expected = c.Source.EARC if value == 0x10 else None
        assert code.profiles.decode_source_value(EVIDENCE["model"], value, info=True) is expected
    assert not code.profiles.writable_features_for_model(EVIDENCE["model"], set(c.Feature))
    assert not code.profiles.can_turn_on(EVIDENCE["model"], set(c.Feature))
    assert not code.profiles.source_options_for_model(EVIDENCE["model"])


def test_a60_runtime_reads_reported_states_with_noncomplement_handshake(code, monkeypatch):
    monkeypatch.setattr(code.runtime.secrets, "randbelow", lambda _: 0xAA)

    async def run():
        dev, peer = a60_with_peer(code)
        await dev.async_refresh_all(reprobe_capabilities=True)
        assert dev.identity.profile == "aura_a60_pro"
        assert dev.identity.firmware == EVIDENCE["firmware"]
        assert dev.identity.protocol_version == EVIDENCE["protocol_version"]
        assert dev.transport == EVIDENCE["transport"]
        assert dev._safe_code_authenticated
        assert dev.safe_code_complement_match is False
        assert dev.capabilities.raw_ability_flags == tuple(EVIDENCE["raw_ability_flags"])
        assert {feature.value for feature in dev.capabilities.features} == set(EVIDENCE["info_replies"])
        assert dev.capabilities.standby_options == (0, 15, 30, 60, 1440, 2880, 240)
        state = dev.state
        assert state.power is True and state.muted is False
        assert state.raw_volume == 42
        assert state.raw_source == 0x10 and state.source is code.const.Source.EARC
        assert state.sound_mode is code.const.SoundMode.MOVIE
        assert state.brightness is code.const.Brightness.DIM
        assert state.screen_timeout is code.const.ScreenTimeout.SECONDS_30
        assert state.prompt_sound is code.const.PromptSound.NONE
        assert state.standby_minutes == 15
        assert all(group != code.const.GROUP_CONTROL for group, _, _ in peer.trace)
        attrs = code.sensor.UltimeaCapabilitiesSensor(dev).extra_state_attributes
        assert attrs["raw_ability_flags"] == EVIDENCE["raw_ability_flags"]
        assert attrs["writable_features"] == []
        assert not dev.supports(code.const.Feature.XUPMIX)
        assert not dev.supports(code.const.Feature.EQUALIZER)
        assert not dev.supports(code.const.Feature.STYLE)

        sensors = []
        entry = SimpleNamespace(runtime_data=SimpleNamespace(device=dev))
        await code.sensor.async_setup_entry(None, entry, sensors.extend)
        observed = {sensor._feature: sensor for sensor in sensors if hasattr(sensor, "_feature")}
        assert set(observed) == {code.const.Feature.VOLUME, code.const.Feature.SOURCE, code.const.Feature.SOUND_MODE}
        assert observed[code.const.Feature.VOLUME].native_value == 42
        assert getattr(observed[code.const.Feature.VOLUME], "_attr_native_unit_of_measurement", None) is None
        assert observed[code.const.Feature.SOURCE].native_value == "eARC"
        assert observed[code.const.Feature.SOUND_MODE].native_value == "Movie"
        player = code.media_player.UltimeaMediaPlayer(dev, 100)
        assert player.source == "eARC"
        assert not player.supported_features
        assert player.source_list is None and player.sound_mode_list is None
        numbers, buttons = [], []
        await code.number.async_setup_entry(None, entry, numbers.extend)
        await code.button.async_setup_entry(None, entry, buttons.extend)
        assert not numbers and not buttons
        peer.rx(1, code.const.INFO_SOURCE, b"\x05")
        assert dev.state.raw_source == 5 and dev.state.source is None
        assert observed[code.const.Feature.SOURCE].native_value is None
        assert player.source is None

    asyncio.run(run())


def test_a60_direct_setters_reject_without_ble_io(code):
    async def run():
        dev, peer = a60_with_peer(code)
        c = code.const
        dev.restore_capabilities(features=EVIDENCE["info_replies"])
        calls = (
            (dev.async_set_power, True), (dev.async_set_power, False),
            (dev.async_set_volume, 42), (dev.async_set_mute, True),
            (dev.async_set_source, c.Source.EARC),
            (dev.async_set_sound_mode, c.SoundMode.MOVIE),
            (dev.async_set_sound_mode, c.SoundMode.CUSTOM),
            (dev.async_set_sound_mode, c.SoundMode.STYLE),
            (dev.async_set_brightness, c.Brightness.DIM),
            (dev.async_set_screen_timeout, c.ScreenTimeout.SECONDS_30),
            (dev.async_set_prompt_sound, c.PromptSound.NONE),
            (dev.async_set_standby_minutes, 15),
            (dev.async_set_xupmix, True), (dev.async_set_style_preset, "flat"),
        )
        for method, value in calls:
            with pytest.raises(code.device.UltimeaCommandError):
                await method(value)
        with pytest.raises(code.device.UltimeaCommandError):
            await dev.async_set_eq_band(0, 0)
        assert peer.trace == []
        assert dev.state.power is True

    asyncio.run(run())
