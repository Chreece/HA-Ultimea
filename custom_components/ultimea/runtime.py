"""Runtime lifecycle, safe-code, and hardware-verified D80 advanced audio."""

from __future__ import annotations

import asyncio
import logging
import secrets
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import callback

from .const import (
    CMD_SOUND_MODE,
    CMD_POWER,
    CMD_XUPMIX,
    GROUP_CAPABILITIES,
    GROUP_CONTROL,
    GROUP_INFO,
    INFO_AUTO_STANDBY,
    INFO_BRIGHTNESS,
    INFO_MODEL,
    INFO_MUTE,
    INFO_POWER,
    INFO_PROMPT_SOUND,
    INFO_PROTOCOL,
    INFO_SCREEN_TIMEOUT,
    INFO_SOUND_MODE,
    INFO_SOURCE,
    INFO_VALUE_TO_SOURCE,
    INFO_VOLUME,
    INFO_XUPMIX,
    VALUE_TO_SOUND_MODE,
    Feature,
    SoundMode,
)
from .device import UltimeaCommandError, UltimeaDevice as BaseUltimeaDevice, UltimeaError
from .profiles import profile_for_model
from .eq_style import build_style_payload, parse_d80_profile
from .protocol import (
    EQ_CUSTOM_PROFILE,
    EQ_FREQUENCIES_HZ,
    EQ_GAIN_MAX_TENTHS_DB,
    EQ_GAIN_MIN_TENTHS_DB,
    EQ_STYLE_PROFILE,
    SAFE_CODE_COMMAND,
    build_command,
    build_equalizer_payload,
    build_safe_code_pair,
    UltimeaFrame,
    safe_code_response_complements,
    validate_safe_code_pair,
)

_LOGGER = logging.getLogger(__name__)


class UltimeaDevice(BaseUltimeaDevice):
    """ULTIMEA device with deferred startup and D80 advanced-audio support."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._sound_mode_lock = asyncio.Lock()
        self._safe_code_lock = asyncio.Lock()
        self._session_generation = 0
        self._profile_reply_expected: int | None = None
        self._runtime_ready = False
        self._safe_code_authenticated = False
        self._safe_code_in_progress = False
        self._safe_code_protocol_checked = False
        self.safe_code_last_request: bytes | None = None
        self.safe_code_last_response: bytes | None = None
        self.safe_code_complement_match: bool | None = None

    def restore_capabilities(self, **kwargs: Any) -> None:
        """Restore persisted data and immediately restore verified model features."""
        super().restore_capabilities(**kwargs)
        self.capabilities.features.update(
            profile_for_model(self.identity.model).verified_features
        )

    async def async_start(self) -> None:
        """Prime cached reachability without BLE I/O during HA boot."""
        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        if info is not None:
            self._available = True
            self.rssi = info.rssi
            self.last_seen_name = info.name
            self._async_notify_listeners()

    async def async_post_start(self, *, reprobe_capabilities: bool = True) -> None:
        """Start runtime work and perform the first full refresh after HA started."""
        if self._stopping:
            return
        self._runtime_ready = True
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = self._async_create_runtime_task(
                self._async_heartbeat_loop(),
                "ULTIMEA unavailable heartbeat",
                eager_start=False,
            )
        if not self._available:
            self._heartbeat_wakeup.set()
            return
        try:
            await self.async_ensure_connected()
            await self.async_refresh_all(reprobe_capabilities=reprobe_capabilities)
        finally:
            self._schedule_disconnect()

    async def async_refresh_all(self, *, reprobe_capabilities: bool = False) -> None:
        """Always finish identity/capability refresh with a complete state snapshot."""
        async with self._refresh_lock:
            await self.async_ensure_connected()
            await self.async_refresh_identity()
            if reprobe_capabilities or not self.capabilities.features:
                await self.async_detect_capabilities()
            await self.async_refresh_state()
            self._async_notify_listeners()

    @callback
    def async_handle_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        """Refresh after a real unavailable->available transition, never during boot."""
        was_available = self.available
        self._available = True
        self.rssi = service_info.rssi
        self.last_seen_name = service_info.name
        self.last_heartbeat_error = None
        self._heartbeat_wakeup.set()
        self._async_notify_listeners()
        if self._runtime_ready and not self.connected and not self._stopping:
            if self.keep_connected or not was_available:
                self._schedule_connect_and_refresh()

    async def _async_heartbeat_once(self) -> None:
        if not self._runtime_ready:
            return
        await super()._async_heartbeat_once()

    async def _async_activate_transport(self, transport: str) -> None:
        previous = self._transport
        await super()._async_activate_transport(transport)
        if previous != self._transport:
            self._reset_safe_code_session()

    def _disconnected(self, client: Any) -> None:
        if self._client is not None and client is not self._client:
            return
        self._reset_safe_code_session()
        self._notify_uuid = None
        self._write_uuid = None
        super()._disconnected(client)

    async def async_disconnect(self) -> None:
        self._reset_safe_code_session()
        await super().async_disconnect()
        self._notify_uuid = None
        self._write_uuid = None

    async def async_stop(self) -> None:
        self._runtime_ready = False
        await super().async_stop()

    def _reset_safe_code_session(self) -> None:
        self._session_generation += 1
        self._clear_profile_curve()
        self.state.raw_sound_mode = None
        self.state.sound_mode = None
        self._safe_code_authenticated = False
        self._safe_code_in_progress = False
        self._safe_code_protocol_checked = False
        self.safe_code_last_request = None
        self.safe_code_last_response = None
        self.safe_code_complement_match = None

    async def _async_safe_code_handshake(self, *, timeout: float = 2.0) -> None:
        """Complete one handshake per BLE session before any dependent command."""
        async with self._safe_code_lock:
            if self._safe_code_authenticated:
                return
            generation = self._session_generation
            challenge = secrets.randbelow(0x100)
            request = build_safe_code_pair(challenge)
            self.safe_code_last_request = request
            self._safe_code_in_progress = True
            try:
                if not self._safe_code_protocol_checked:
                    protocol_frame = await super()._async_request(
                        GROUP_INFO, INFO_PROTOCOL, expected_data=None,
                        timeout=min(timeout, 1.5),
                    )
                    if protocol_frame.data:
                        self.identity.protocol_version = int.from_bytes(protocol_frame.data, "little")
                    self._safe_code_protocol_checked = True
                frame = await super()._async_request(
                    GROUP_CAPABILITIES, SAFE_CODE_COMMAND, request,
                    expected_data=None, timeout=timeout,
                )
            finally:
                self._safe_code_in_progress = False

            if generation != self._session_generation:
                raise UltimeaCommandError("Bluetooth session changed during safe-code exchange")
            response = frame.data
            self.safe_code_last_response = response
            if not validate_safe_code_pair(response):
                raise UltimeaCommandError("ULTIMEA safe-code response failed pair-integrity validation")
            self.safe_code_complement_match = safe_code_response_complements(challenge, response)
            if not self.safe_code_complement_match:
                _LOGGER.debug(
                    "Valid safe-code pair without observed D80 complement relation: request=%s response=%s",
                    request.hex(" "), response.hex(" "),
                )
            self._safe_code_authenticated = True

    async def _async_request(
        self,
        group: int,
        command: int,
        data: bytes = b"",
        *,
        expected_data: bytes | None,
        timeout: float = 2.0,
    ):
        bootstrap_query = group == GROUP_INFO and command in (INFO_PROTOCOL, INFO_MODEL)
        safe_code_command = group == GROUP_CAPABILITIES and command == SAFE_CODE_COMMAND
        await self.async_ensure_connected()
        if not bootstrap_query and not safe_code_command:
            await self._async_safe_code_handshake()
        frame = await super()._async_request(
            group, command, data, expected_data=expected_data, timeout=timeout
        )
        if group == GROUP_INFO and command == INFO_PROTOCOL:
            self._safe_code_protocol_checked = True
        return frame

    def _clear_profile_curve(self) -> None:
        """Discard values that must not be reused across modes or BLE sessions."""
        self.state.eq_profile_id = None
        self.state.eq_band_gains_tenths_db = None

    def _apply_sound_mode(self, value: int) -> None:
        if value != self.state.raw_sound_mode or value not in (EQ_CUSTOM_PROFILE, EQ_STYLE_PROFILE):
            self._clear_profile_curve()
        self.state.raw_sound_mode = value
        mode = VALUE_TO_SOUND_MODE.get(value)
        if mode is SoundMode.STYLE and not self.supports(Feature.STYLE):
            mode = None
        self.state.sound_mode = mode

    def _apply_custom_profile(self, profile: int, gains: tuple[int, ...]) -> None:
        """Publish a validated full device curve, never a guessed cached preset."""
        self.state.eq_profile_id = profile
        self.state.eq_band_gains_tenths_db = gains
        self.state.raw_sound_mode = profile
        self.state.sound_mode = SoundMode.STYLE if profile == EQ_STYLE_PROFILE else SoundMode.CUSTOM

    def _resolve_pending(self, frame: UltimeaFrame) -> None:
        """A profile read needs its full matching curve, not a one-byte mode ACK."""
        pending = self._pending
        if (
            self._profile_reply_expected is not None
            and pending is not None
            and pending[:3] == (GROUP_CONTROL, CMD_SOUND_MODE, None)
            and (frame.group, frame.command) == (GROUP_CONTROL, CMD_SOUND_MODE)
        ):
            eq = parse_d80_profile(frame.data)
            if eq is None or eq.profile != self._profile_reply_expected:
                return
        super()._resolve_pending(frame)

    def _handle_control_frame(self, frame: UltimeaFrame) -> bool:
        if frame.command == CMD_POWER and frame.data == b"\x00":
            self._clear_profile_curve()
            self.state.raw_sound_mode = None
            self.state.sound_mode = None
        if frame.command == CMD_SOUND_MODE:
            eq = parse_d80_profile(frame.data)
            if eq is not None:
                feature = Feature.STYLE if eq.profile == EQ_STYLE_PROFILE else Feature.EQUALIZER
                if not self.supports(feature):
                    return False
                self._apply_custom_profile(eq.profile, eq.gains_tenths_db)
                return True
            if len(frame.data) == 1:
                self._apply_sound_mode(frame.data[0])
                return True
            return False
        return super()._handle_control_frame(frame)

    def _handle_info_frame(self, frame: UltimeaFrame) -> bool:
        """Decode GET responses; unknown modes must not retain stale Style state."""
        data = frame.data
        if frame.command == INFO_POWER and data == b"\x00":
            self._clear_profile_curve()
            self.state.raw_sound_mode = None
            self.state.sound_mode = None
        if frame.command == INFO_MUTE and len(data) == 1 and data[0] in (0, 1):
            self.state.muted = data[0] == 0
            return True
        if frame.command == INFO_SOURCE and len(data) == 1:
            self.state.raw_source = data[0]
            self.state.source = INFO_VALUE_TO_SOURCE.get(data[0])
            return True
        if frame.command == INFO_SOUND_MODE and len(data) == 1:
            self._apply_sound_mode(data[0])
            return True
        if frame.command == INFO_XUPMIX and len(data) == 1 and data[0] in (0, 1):
            self.state.xupmix_enabled = bool(data[0])
            return True
        return super()._handle_info_frame(frame)

    async def async_refresh_state(self):
        """Read all exposed statuses without activating a stored sound profile."""
        async with self._sound_mode_lock:
            await self.async_ensure_connected()
            query_for_feature = {
                Feature.POWER: INFO_POWER,
                Feature.MUTE: INFO_MUTE,
                Feature.VOLUME: INFO_VOLUME,
                Feature.SOURCE: INFO_SOURCE,
                Feature.SOUND_MODE: INFO_SOUND_MODE,
                Feature.BRIGHTNESS: INFO_BRIGHTNESS,
                Feature.SCREEN_TIMEOUT: INFO_SCREEN_TIMEOUT,
                Feature.PROMPT_SOUND: INFO_PROMPT_SOUND,
                Feature.AUTO_STANDBY: INFO_AUTO_STANDBY,
                Feature.XUPMIX: INFO_XUPMIX,
            }
            mode_reply = None
            for feature, command in query_for_feature.items():
                if self.supports(feature):
                    reply = await self._async_try_query(command)
                    if command == INFO_SOUND_MODE:
                        mode_reply = reply

            if mode_reply is None or len(mode_reply) != 1:
                self._clear_profile_curve()
                self.state.sound_mode = None
                self.state.raw_sound_mode = None
            elif self.state.power is not False:
                profile = mode_reply[0]
                feature = {EQ_CUSTOM_PROFILE: Feature.EQUALIZER, EQ_STYLE_PROFILE: Feature.STYLE}.get(profile)
                if feature is not None and self.supports(feature):
                    try:
                        # The helper rechecks the current mode immediately before
                        # the profile read. No stale pre-disconnect mode is used.
                        await self._async_read_profile_locked(profile, activate=False)
                    except UltimeaError as err:
                        self._clear_profile_curve()
                        _LOGGER.debug("ULTIMEA profile %02x readback failed: %s", profile, err)
            self._async_notify_listeners()
            self._schedule_disconnect()
            return self.state

    async def async_set_sound_mode(self, mode: SoundMode) -> None:
        async with self._sound_mode_lock:
            if mode in (SoundMode.CUSTOM, SoundMode.STYLE):
                profile = EQ_STYLE_PROFILE if mode is SoundMode.STYLE else EQ_CUSTOM_PROFILE
                await self._async_read_profile_locked(profile, activate=True)
                return
            await super().async_set_sound_mode(mode)

    async def _async_read_profile_locked(self, profile: int, *, activate: bool) -> tuple[int, ...]:
        """Read/select a profile while holding the sound-mode operation lock."""
        feature = {EQ_CUSTOM_PROFILE: Feature.EQUALIZER, EQ_STYLE_PROFILE: Feature.STYLE}.get(profile)
        if feature is None or not self.supports(feature):
            raise UltimeaCommandError("Custom profile is not hardware-verified on this device")
        await self.async_ensure_connected()
        generation = self._session_generation
        if not activate:
            mode = await self.async_query(GROUP_INFO, INFO_SOUND_MODE, timeout=1.5)
            if mode != bytes([profile]) or generation != self._session_generation:
                raise UltimeaCommandError("Custom profile is not confirmed active in this Bluetooth session")
        self._clear_profile_curve()
        self._profile_reply_expected = profile
        try:
            frame = await self._async_request(
                GROUP_CONTROL, CMD_SOUND_MODE, bytes([profile]),
                expected_data=None, timeout=2.5,
            )
            eq = parse_d80_profile(frame.data)
            if eq is None or eq.profile != profile or generation != self._session_generation:
                raise UltimeaCommandError("D80 did not return the expected complete custom profile")
            self._apply_custom_profile(eq.profile, eq.gains_tenths_db)
            self._async_notify_listeners()
            return eq.gains_tenths_db
        finally:
            self._profile_reply_expected = None

    async def async_read_custom_eq(self, *, activate: bool) -> tuple[int, ...]:
        async with self._sound_mode_lock:
            return await self._async_read_profile_locked(EQ_CUSTOM_PROFILE, activate=activate)

    async def async_read_style(self, *, activate: bool) -> tuple[int, ...]:
        async with self._sound_mode_lock:
            return await self._async_read_profile_locked(EQ_STYLE_PROFILE, activate=activate)

    async def async_set_style_preset(self, preset: str) -> None:
        """Apply a labelled captured curve; acknowledge the entire 41-byte echo."""
        if not self.supports(Feature.STYLE):
            raise UltimeaCommandError("Style is not hardware-verified on this device")
        payload = build_style_payload(preset)
        async with self._sound_mode_lock:
            await self.async_ensure_connected()
            generation = self._session_generation
            self._clear_profile_curve()
            frame = await self._async_request(
                GROUP_CONTROL, CMD_SOUND_MODE, payload,
                expected_data=payload, timeout=2.5,
            )
            if frame.data != payload or generation != self._session_generation:
                raise UltimeaCommandError("Style curve was not confirmed by the current Bluetooth session")
            eq = parse_d80_profile(frame.data)
            if eq is None:
                raise UltimeaCommandError("Style response is not a valid D80 profile")
            self._apply_custom_profile(eq.profile, eq.gains_tenths_db)
            self._async_notify_listeners()

    async def async_reset_style(self) -> None:
        """Select Style and reset its curve to the recorded neutral/center values."""
        await self.async_set_style_preset("flat")

    async def async_set_eq_band(self, index: int, gain_tenths_db: int) -> None:
        """Edit Custom EQ only, never silently replace a selected Style curve."""
        if not 0 <= int(index) < len(EQ_FREQUENCIES_HZ):
            raise ValueError(f"Invalid EQ band index: {index}")
        if not self.supports(Feature.EQUALIZER):
            raise UltimeaCommandError("10-band equalizer is not supported by this device")
        gain = max(EQ_GAIN_MIN_TENTHS_DB, min(EQ_GAIN_MAX_TENTHS_DB, int(gain_tenths_db)))
        async with self._sound_mode_lock:
            mode = await self.async_query(GROUP_INFO, INFO_SOUND_MODE, timeout=1.5)
            if mode != bytes([EQ_CUSTOM_PROFILE]):
                raise UltimeaCommandError("Select Custom EQ before changing EQ bands")
            gains = self.state.eq_band_gains_tenths_db
            if gains is None or self.state.eq_profile_id != EQ_CUSTOM_PROFILE:
                gains = await self._async_read_profile_locked(EQ_CUSTOM_PROFILE, activate=False)
            updated = list(gains)
            updated[int(index)] = gain
            payload = build_equalizer_payload(updated, profile=EQ_CUSTOM_PROFILE)
            frame = await self._async_request(
                GROUP_CONTROL, CMD_SOUND_MODE, payload,
                expected_data=payload, timeout=2.5,
            )
            if frame.data != payload:
                raise UltimeaCommandError("Custom EQ write was not confirmed")
            self._apply_custom_profile(EQ_CUSTOM_PROFILE, tuple(updated))
            self._async_notify_listeners()

    async def async_set_xupmix(self, enabled: bool) -> None:
        """Set D80 X-Upmix with 02:16 and verify through authoritative GET 01:18."""
        if not self.supports(Feature.XUPMIX):
            raise UltimeaCommandError("X-Upmix is not hardware-verified on this device")

        await self.async_query(GROUP_INFO, INFO_XUPMIX, timeout=1.5)
        client = await self.async_ensure_connected()
        if self._write_uuid is None:
            raise UltimeaCommandError("No active ULTIMEA write characteristic")
        data = bytes([1 if enabled else 0])
        packet = build_command(GROUP_CONTROL, CMD_XUPMIX, data)

        # Hardware validation shows 02:16 changes state without a dependable
        # same-command ACK. Verify the actual state through 01:18 instead.
        async with self._command_lock:
            try:
                await client.write_gatt_char(self._write_uuid, packet, response=False)
            except Exception as err:
                raise UltimeaCommandError(str(err)) from err

        for _ in range(3):
            await asyncio.sleep(0.25)
            await self._async_try_query(INFO_XUPMIX, timeout=1.2)
            if self.state.xupmix_enabled is enabled:
                self._schedule_disconnect()
                return
        raise UltimeaCommandError("X-Upmix command was sent but 01:18 did not confirm the requested state")
