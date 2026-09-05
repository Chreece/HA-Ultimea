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
    Feature,
    SoundMode,
)
from .device import UltimeaCommandError, UltimeaDevice as BaseUltimeaDevice, UltimeaError
from .profiles import profile_for_model
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
    parse_equalizer_payload,
    safe_code_response_complements,
    validate_safe_code_pair,
)

_LOGGER = logging.getLogger(__name__)


class UltimeaDevice(BaseUltimeaDevice):
    """ULTIMEA device with deferred startup and D80 advanced-audio support."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
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
        """Refresh the base snapshot, then every newly exposed state after re-probe."""
        await super().async_refresh_all(reprobe_capabilities=reprobe_capabilities)
        if reprobe_capabilities:
            await self.async_refresh_state()

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
        self._reset_safe_code_session()
        super()._disconnected(client)

    async def async_disconnect(self) -> None:
        self._reset_safe_code_session()
        await super().async_disconnect()

    async def async_stop(self) -> None:
        self._runtime_ready = False
        await super().async_stop()

    def _reset_safe_code_session(self) -> None:
        self._safe_code_authenticated = False
        self._safe_code_in_progress = False
        self._safe_code_protocol_checked = False
        self.safe_code_last_request = None
        self.safe_code_last_response = None
        self.safe_code_complement_match = None

    async def _async_safe_code_handshake(self, *, timeout: float = 2.0) -> None:
        if self._safe_code_authenticated or self._safe_code_in_progress:
            return
        challenge = secrets.randbelow(0x100)
        request = build_safe_code_pair(challenge)
        self.safe_code_last_request = request
        self._safe_code_in_progress = True
        try:
            if not self._safe_code_protocol_checked:
                protocol_frame = await super()._async_request(
                    GROUP_INFO,
                    INFO_PROTOCOL,
                    expected_data=None,
                    timeout=min(timeout, 1.5),
                )
                if protocol_frame.data:
                    self.identity.protocol_version = int.from_bytes(protocol_frame.data, "little")
                self._safe_code_protocol_checked = True
            frame = await super()._async_request(
                GROUP_CAPABILITIES,
                SAFE_CODE_COMMAND,
                request,
                expected_data=None,
                timeout=timeout,
            )
        finally:
            self._safe_code_in_progress = False

        response = frame.data
        self.safe_code_last_response = response
        if not validate_safe_code_pair(response):
            raise UltimeaCommandError(
                "ULTIMEA safe-code response failed pair-integrity validation"
            )
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
        if (
            not self._safe_code_in_progress
            and not self._safe_code_authenticated
            and not bootstrap_query
            and not safe_code_command
        ):
            await self.async_ensure_connected()
            await self._async_safe_code_handshake()
        frame = await super()._async_request(
            group, command, data, expected_data=expected_data, timeout=timeout
        )
        if group == GROUP_INFO and command == INFO_PROTOCOL:
            self._safe_code_protocol_checked = True
        return frame

    def _apply_custom_profile(self, profile: int, gains: tuple[int, ...]) -> None:
        """Apply decoded custom profile state without inventing unsupported HA modes."""
        self.state.eq_profile_id = profile
        self.state.eq_band_gains_tenths_db = gains
        self.state.raw_sound_mode = profile
        if profile == EQ_CUSTOM_PROFILE:
            self.state.sound_mode = SoundMode.CUSTOM
        elif profile == EQ_STYLE_PROFILE:
            # Style is decoded, but no authoritative persistent active-mode getter
            # has been proven. Never leave a previous HA sound mode stale here.
            self.state.sound_mode = None

    def _handle_control_frame(self, frame) -> bool:
        """Decode exact-echo Custom EQ/Style profiles before base controls."""
        if frame.command == CMD_SOUND_MODE:
            eq = parse_equalizer_payload(frame.data)
            if eq is not None and eq.frequencies_hz == EQ_FREQUENCIES_HZ:
                self._apply_custom_profile(eq.profile, eq.gains_tenths_db)
                return True
            if len(frame.data) == 1 and frame.data[0] == EQ_STYLE_PROFILE:
                self.state.raw_sound_mode = EQ_STYLE_PROFILE
                self.state.sound_mode = None
                return True
        return super()._handle_control_frame(frame)

    def _handle_info_frame(self, frame) -> bool:
        """Apply the hardware-proven D80 GET encodings missing from old master."""
        data = frame.data
        if frame.command == INFO_MUTE and len(data) == 1 and data[0] in (0, 1):
            self.state.muted = data[0] == 0
            return True
        if frame.command == INFO_SOURCE and len(data) == 1:
            self.state.raw_source = data[0]
            source = INFO_VALUE_TO_SOURCE.get(data[0])
            if source is not None:
                self.state.source = source
            return True
        if frame.command == INFO_SOUND_MODE and len(data) == 1 and data[0] == EQ_STYLE_PROFILE:
            self.state.raw_sound_mode = EQ_STYLE_PROFILE
            self.state.sound_mode = None
            return True
        if frame.command == INFO_XUPMIX and len(data) == 1 and data[0] in (0, 1):
            self.state.xupmix_enabled = bool(data[0])
            return True
        return super()._handle_info_frame(frame)

    async def async_refresh_state(self):
        """Read every exposed non-mutating state after restart/reconnect."""
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
        for feature, command in query_for_feature.items():
            if self.supports(feature):
                await self._async_try_query(command)

        if self.supports(Feature.EQUALIZER) and self.state.raw_sound_mode == EQ_CUSTOM_PROFILE:
            try:
                await self.async_read_custom_eq(activate=False)
            except UltimeaError as err:
                _LOGGER.debug("ULTIMEA Custom EQ readback failed: %s", err)

        self._async_notify_listeners()
        self._schedule_disconnect()
        return self.state

    async def async_set_sound_mode(self, mode: SoundMode) -> None:
        if mode is SoundMode.CUSTOM:
            if not self.supports(Feature.EQUALIZER):
                raise UltimeaCommandError("Custom EQ is not hardware-verified on this device")
            await self.async_read_custom_eq(activate=True)
            return
        await super().async_set_sound_mode(mode)

    async def async_read_custom_eq(self, *, activate: bool) -> tuple[int, ...]:
        """Load the D80 stored 10-band profile 0x07 without guessing state."""
        if not self.supports(Feature.EQUALIZER):
            raise UltimeaCommandError("10-band equalizer is not supported by this device")
        if not activate and self.state.raw_sound_mode != EQ_CUSTOM_PROFILE:
            raise UltimeaCommandError("Custom EQ is not currently active")
        frame = await self._async_request(
            GROUP_CONTROL,
            CMD_SOUND_MODE,
            bytes([EQ_CUSTOM_PROFILE]),
            expected_data=None,
            timeout=2.5,
        )
        eq = parse_equalizer_payload(frame.data)
        if eq is None or eq.profile != EQ_CUSTOM_PROFILE or eq.frequencies_hz != EQ_FREQUENCIES_HZ:
            raise UltimeaCommandError("D80 did not return the expected Custom EQ payload")
        self._apply_custom_profile(eq.profile, eq.gains_tenths_db)
        self._async_notify_listeners()
        return eq.gains_tenths_db

    async def async_set_eq_band(self, index: int, gain_tenths_db: int) -> None:
        """Set one D80 Custom EQ band while preserving all other bands."""
        if not 0 <= int(index) < len(EQ_FREQUENCIES_HZ):
            raise ValueError(f"Invalid EQ band index: {index}")
        if not self.supports(Feature.EQUALIZER):
            raise UltimeaCommandError("10-band equalizer is not supported by this device")
        gain = max(EQ_GAIN_MIN_TENTHS_DB, min(EQ_GAIN_MAX_TENTHS_DB, int(gain_tenths_db)))
        gains = self.state.eq_band_gains_tenths_db
        if gains is None or self.state.eq_profile_id != EQ_CUSTOM_PROFILE:
            gains = await self.async_read_custom_eq(activate=True)
        updated = list(gains)
        updated[int(index)] = gain
        payload = build_equalizer_payload(updated, profile=EQ_CUSTOM_PROFILE)
        await self._async_request(
            GROUP_CONTROL,
            CMD_SOUND_MODE,
            payload,
            expected_data=payload,
            timeout=2.5,
        )
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
