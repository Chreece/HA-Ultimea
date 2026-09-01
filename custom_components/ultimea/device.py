"""Bluetooth client for ULTIMEA Poseidon D80 Boom."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.core import HomeAssistant, callback

from .const import (
    BRIGHTNESS_TO_VALUE,
    CMD_AUTO_STANDBY,
    CMD_BRIGHTNESS,
    CMD_MUTE,
    CMD_POWER,
    CMD_PROMPT_SOUND,
    CMD_SCREEN_TIMEOUT,
    CMD_SOUND_MODE,
    CMD_SOURCE,
    CMD_VOLUME,
    COMMON_SERVICE_UUID,
    GROUP_CONTROL,
    GROUP_INFO,
    INFO_AUTO_STANDBY,
    INFO_BRIGHTNESS,
    INFO_FIRMWARE,
    INFO_MODEL,
    INFO_MUTE,
    INFO_POWER,
    INFO_PROMPT_SOUND,
    INFO_SCREEN_TIMEOUT,
    INFO_SERIAL,
    INFO_SOUND_MODE,
    INFO_SOURCE,
    INFO_VOLUME,
    MINUTES_TO_STANDBY,
    NOTIFY_UUID,
    PROMPT_SOUND_TO_VALUE,
    SCREEN_TIMEOUT_TO_VALUE,
    SOUND_MODE_TO_VALUE,
    SOURCE_TO_VALUE,
    SUPPORTED_MODEL,
    VALUE_TO_BRIGHTNESS,
    VALUE_TO_PROMPT_SOUND,
    VALUE_TO_SCREEN_TIMEOUT,
    VALUE_TO_SOUND_MODE,
    VALUE_TO_SOURCE,
    WRITE_UUID,
    Brightness,
    PromptSound,
    ScreenTimeout,
    SoundMode,
    Source,
)
from .models import UltimeaIdentity, UltimeaState
from .protocol import UltimeaFrame, build_command, decode_ascii, iter_frames

_LOGGER = logging.getLogger(__name__)


class UltimeaError(Exception):
    """Base ULTIMEA error."""


class UltimeaConnectionError(UltimeaError):
    """Raised when no connection can be established."""


class UltimeaUnsupportedDeviceError(UltimeaError):
    """Raised when a BLE device is not a supported D80 Boom."""


class UltimeaCommandError(UltimeaError):
    """Raised when a command is rejected or times out."""


class UltimeaDevice:
    """One Poseidon D80 Boom."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        *,
        keep_connected: bool = True,
        disconnect_delay: int = 15,
    ) -> None:
        self.hass = hass
        self.address = address.upper()
        self.name = name
        self.keep_connected = keep_connected
        self.disconnect_delay = disconnect_delay

        self.identity = UltimeaIdentity(model=SUPPORTED_MODEL)
        self.state = UltimeaState()
        self.rssi: int | None = None
        self.last_seen_name: str | None = None

        self._client: BleakClient | None = None
        self._connection_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()
        self._refresh_lock = asyncio.Lock()
        self._listeners: set[Callable[[], None]] = set()
        self._pending: tuple[int, int, bytes | None, asyncio.Future[UltimeaFrame]] | None = None
        self._disconnect_task: asyncio.Task[None] | None = None
        self._connect_refresh_task: asyncio.Task[None] | None = None
        self._available = False
        self._stopping = False

    @property
    def available(self) -> bool:
        """Return whether HA can currently see or talk to the soundbar."""
        return self._available or bool(self._client and self._client.is_connected)

    @property
    def connected(self) -> bool:
        """Return connection state."""
        return bool(self._client and self._client.is_connected)

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe to device state changes."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _async_notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    @callback
    def async_handle_advertisement(self, service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        """Update reachability from Home Assistant's shared Bluetooth manager."""
        self._available = True
        self.rssi = service_info.rssi
        self.last_seen_name = service_info.name
        self._async_notify_listeners()

        if self.keep_connected and not self.connected and not self._stopping:
            self._schedule_connect_and_refresh()

    @callback
    def async_handle_unavailable(self, _service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        """Handle device no longer being visible to connectable scanners."""
        if not self.connected:
            self._available = False
            self._async_notify_listeners()

    @callback
    def _schedule_connect_and_refresh(self) -> None:
        if self._connect_refresh_task and not self._connect_refresh_task.done():
            return
        self._connect_refresh_task = self.hass.async_create_task(
            self._async_connect_and_refresh_background()
        )

    async def _async_connect_and_refresh_background(self) -> None:
        try:
            await self.async_ensure_connected()
            await self.async_refresh_all()
        except UltimeaError as err:
            _LOGGER.debug("D80 background connect/refresh failed: %s", err)
        finally:
            self._connect_refresh_task = None

    async def async_start(self) -> None:
        """Start runtime behavior and obtain an initial state snapshot."""
        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        if info is not None:
            # Seed reachability without scheduling a second background refresh;
            # async_start performs the initial refresh itself below.
            self._available = True
            self.rssi = info.rssi
            self.last_seen_name = info.name
            self._async_notify_listeners()
            try:
                # Even in on-demand mode, connect once during setup so entities do
                # not start as unknown when the D80 is currently reachable.
                await self.async_ensure_connected()
                await self.async_refresh_all()
            except UltimeaError as err:
                _LOGGER.debug("Initial D80 state refresh failed: %s", err)
            finally:
                self._schedule_disconnect()

    async def async_stop(self) -> None:
        """Stop and release the BLE connection."""
        self._stopping = True
        if self._disconnect_task:
            self._disconnect_task.cancel()
            self._disconnect_task = None
        if self._connect_refresh_task:
            self._connect_refresh_task.cancel()
            self._connect_refresh_task = None
        await self.async_disconnect()

    def _disconnected(self, _client: BleakClient) -> None:
        """Bleak disconnected callback."""
        self._client = None
        if self._pending is not None:
            future = self._pending[3]
            if not future.done():
                future.set_exception(UltimeaConnectionError("D80 disconnected"))
            self._pending = None
        self._async_notify_listeners()

    async def _async_get_ble_device(self) -> BLEDevice:
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            reason = bluetooth.async_address_reachability_diagnostics(
                self.hass,
                self.address,
                BluetoothReachabilityIntent.CONNECTION,
            )
            raise UltimeaConnectionError(reason)
        return ble_device

    async def async_ensure_connected(self) -> BleakClient:
        """Ensure a connection using HA's best local/proxy path."""
        if self._client and self._client.is_connected:
            return self._client

        async with self._connection_lock:
            if self._client and self._client.is_connected:
                return self._client

            ble_device = await self._async_get_ble_device()
            try:
                client = await establish_connection(
                    BleakClient,
                    ble_device,
                    self.name,
                    disconnected_callback=self._disconnected,
                    max_attempts=4,
                )
            except Exception as err:
                raise UltimeaConnectionError(str(err)) from err

            char_uuids = {
                str(char.uuid).lower()
                for service in client.services
                for char in service.characteristics
            }
            service_uuids = {str(service.uuid).lower() for service in client.services}
            if (
                COMMON_SERVICE_UUID not in service_uuids
                or WRITE_UUID not in char_uuids
                or NOTIFY_UUID not in char_uuids
            ):
                await client.disconnect()
                raise UltimeaUnsupportedDeviceError(
                    "Required Poseidon D80 Boom GATT characteristics were not found"
                )

            try:
                await client.start_notify(NOTIFY_UUID, self._notification)
            except Exception:
                await client.disconnect()
                raise

            self._client = client
            self._available = True
            self._async_notify_listeners()
            return client

    async def async_disconnect(self) -> None:
        """Disconnect only this soundbar."""
        client = self._client
        self._client = None
        if not client:
            return
        with suppress(Exception):
            if client.is_connected:
                await client.stop_notify(NOTIFY_UUID)
        with suppress(Exception):
            if client.is_connected:
                await client.disconnect()
        self._async_notify_listeners()

    def _schedule_disconnect(self) -> None:
        if self.keep_connected or self._stopping:
            return
        if self._disconnect_task:
            self._disconnect_task.cancel()
        self._disconnect_task = self.hass.async_create_task(self._async_delayed_disconnect())

    async def _async_delayed_disconnect(self) -> None:
        try:
            await asyncio.sleep(self.disconnect_delay)
            await self.async_disconnect()
        except asyncio.CancelledError:
            return
        finally:
            self._disconnect_task = None

    def _notification(self, _sender: Any, payload: bytearray) -> None:
        """Handle one BLE notification from 8D22."""
        self._available = True
        changed = False
        for frame in iter_frames(bytes(payload)):
            changed |= self._handle_frame(frame)
            self._resolve_pending(frame)
        if changed:
            self._async_notify_listeners()

    def _resolve_pending(self, frame: UltimeaFrame) -> None:
        pending = self._pending
        if pending is None:
            return
        group, command, expected_data, future = pending
        if frame.group != group or frame.command != command:
            return
        if expected_data is not None and frame.data != expected_data:
            return
        if not future.done():
            future.set_result(frame)

    def _handle_frame(self, frame: UltimeaFrame) -> bool:
        """Apply a control push or an official app GET response to state."""
        if frame.group == GROUP_CONTROL:
            return self._handle_control_frame(frame)
        if frame.group == GROUP_INFO:
            return self._handle_info_frame(frame)
        return False

    def _handle_control_frame(self, frame: UltimeaFrame) -> bool:
        data = frame.data
        if frame.command == CMD_VOLUME and len(data) == 1:
            self.state.raw_volume = data[0]
            return True

        if frame.command == CMD_POWER and len(data) == 1:
            self.state.power = bool(data[0])
            return True

        if frame.command == CMD_MUTE and len(data) == 1:
            # SET/notification encoding: 0 = mute on, 1 = mute off.
            self.state.muted = data[0] == 0
            return True

        if frame.command == CMD_SOURCE and len(data) == 1:
            source = VALUE_TO_SOURCE.get(data[0])
            if source is not None:
                self.state.source = source
                return True
            return False

        if frame.command == CMD_SOUND_MODE and len(data) == 1:
            mode = VALUE_TO_SOUND_MODE.get(data[0])
            if mode is not None:
                self.state.sound_mode = mode
                return True
            return False

        if frame.command == CMD_BRIGHTNESS and len(data) == 1:
            if data[0] == 0:
                # 0 is a runtime screen-off event after the configured timeout,
                # not a sixth brightness setting.
                self.state.screen_on = False
                return True
            brightness = VALUE_TO_BRIGHTNESS.get(data[0])
            if brightness is not None:
                self.state.brightness = brightness
                self.state.screen_on = True
                return True
            return False

        if frame.command == CMD_SCREEN_TIMEOUT and len(data) == 1:
            timeout = VALUE_TO_SCREEN_TIMEOUT.get(data[0])
            if timeout is not None:
                self.state.screen_timeout = timeout
                return True
            return False

        if frame.command == CMD_PROMPT_SOUND and len(data) == 1:
            prompt = VALUE_TO_PROMPT_SOUND.get(data[0])
            if prompt is not None:
                self.state.prompt_sound = prompt
                return True
            return False

        if frame.command == CMD_AUTO_STANDBY and len(data) == 2:
            self.state.standby_minutes = int.from_bytes(data, "little")
            return True

        return False

    def _handle_info_frame(self, frame: UltimeaFrame) -> bool:
        """Decode zero-payload GET responses used by the official app."""
        data = frame.data

        if frame.command == INFO_POWER and len(data) == 1:
            self.state.power = bool(data[0])
            return True

        if frame.command == INFO_MUTE and len(data) == 1:
            # GET encoding is a normal boolean: 0 = not muted, 1 = muted.
            self.state.muted = bool(data[0])
            return True

        if frame.command == INFO_VOLUME and len(data) == 1:
            self.state.raw_volume = data[0]
            return True

        if frame.command == INFO_SOURCE and len(data) == 1:
            source = VALUE_TO_SOURCE.get(data[0])
            if source is not None:
                self.state.source = source
                return True
            return False

        if frame.command == INFO_SOUND_MODE and len(data) == 1:
            mode = VALUE_TO_SOUND_MODE.get(data[0])
            if mode is not None:
                self.state.sound_mode = mode
                return True
            return False

        if frame.command == INFO_PROMPT_SOUND and len(data) == 1:
            prompt = VALUE_TO_PROMPT_SOUND.get(data[0])
            if prompt is not None:
                self.state.prompt_sound = prompt
                return True
            return False

        if frame.command == INFO_BRIGHTNESS and len(data) == 1:
            brightness = VALUE_TO_BRIGHTNESS.get(data[0])
            if brightness is not None:
                self.state.brightness = brightness
                self.state.screen_on = True
                return True
            return False

        if frame.command == INFO_SCREEN_TIMEOUT and len(data) == 1:
            timeout = VALUE_TO_SCREEN_TIMEOUT.get(data[0])
            if timeout is not None:
                self.state.screen_timeout = timeout
                return True
            return False

        if frame.command == INFO_AUTO_STANDBY and len(data) >= 2:
            # The D80 returns current minutes in the first uint16, followed by
            # the supported option count/list. Example captured response:
            # 0f 00 09 00 00 0f 00 1e 00 3c 00 ... 40 0b
            self.state.standby_minutes = int.from_bytes(data[:2], "little")
            return True

        return False

    async def _async_request(
        self,
        group: int,
        command: int,
        data: bytes = b"",
        *,
        expected_data: bytes | None,
        timeout: float = 2.0,
    ) -> UltimeaFrame:
        client = await self.async_ensure_connected()
        packet = build_command(group, command, data)

        async with self._command_lock:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[UltimeaFrame] = loop.create_future()
            self._pending = (group, command, expected_data, future)
            try:
                await client.write_gatt_char(WRITE_UUID, packet, response=False)
                frame = await asyncio.wait_for(future, timeout=timeout)
            except TimeoutError as err:
                raise UltimeaCommandError(
                    f"Timed out waiting for group 0x{group:02X} command 0x{command:02X}"
                ) from err
            except Exception as err:
                if isinstance(err, UltimeaError):
                    raise
                raise UltimeaCommandError(str(err)) from err
            finally:
                if self._pending and self._pending[3] is future:
                    self._pending = None

        self._schedule_disconnect()
        return frame

    async def async_query(self, group: int, command: int) -> bytes:
        """Send a zero-payload query and return response data."""
        frame = await self._async_request(
            group, command, expected_data=None, timeout=3.0
        )
        return frame.data

    async def _async_try_query(self, command: int) -> bool:
        """Query one state item without making the whole refresh fail."""
        try:
            await self.async_query(GROUP_INFO, command)
            return True
        except UltimeaError as err:
            _LOGGER.debug("D80 state query 0x%02X failed: %s", command, err)
            return False

    async def async_refresh_identity(self) -> UltimeaIdentity:
        """Read identity using official app query commands."""
        await self.async_ensure_connected()

        model = decode_ascii(await self.async_query(GROUP_INFO, INFO_MODEL))
        if model != SUPPORTED_MODEL:
            raise UltimeaUnsupportedDeviceError(
                f"Expected {SUPPORTED_MODEL!r}, got {model!r}"
            )

        serial = decode_ascii(await self.async_query(GROUP_INFO, INFO_SERIAL))
        firmware_raw = await self.async_query(GROUP_INFO, INFO_FIRMWARE)

        firmware = None
        if firmware_raw:
            firmware = f"V{int.from_bytes(firmware_raw, 'little')}"

        self.identity = UltimeaIdentity(
            model=model,
            serial=serial or None,
            firmware=firmware,
        )
        self._async_notify_listeners()
        return self.identity

    async def async_refresh_state(self) -> UltimeaState:
        """Actively read every supported D80 state from the soundbar."""
        await self.async_ensure_connected()

        # These are the zero-payload GETs emitted by the official ULTIMEA app.
        # Query each separately so one firmware variation cannot leave all
        # entities unknown merely because a single optional setting fails.
        for command in (
            INFO_POWER,
            INFO_MUTE,
            INFO_VOLUME,
            INFO_SOURCE,
            INFO_SOUND_MODE,
            INFO_BRIGHTNESS,
            INFO_SCREEN_TIMEOUT,
            INFO_PROMPT_SOUND,
            INFO_AUTO_STANDBY,
        ):
            await self._async_try_query(command)

        self._async_notify_listeners()
        self._schedule_disconnect()
        return self.state

    async def async_refresh_all(self) -> None:
        """Refresh identity and complete runtime state as one serialized snapshot."""
        async with self._refresh_lock:
            await self.async_ensure_connected()
            await self.async_refresh_identity()
            await self.async_refresh_state()

    async def async_refresh_volume(self) -> int | None:
        """Read the current absolute volume."""
        await self._async_try_query(INFO_VOLUME)
        return self.state.raw_volume

    async def _async_write_verified(
        self,
        command: int,
        data: bytes,
        *,
        refresh: Callable[[], Awaitable[Any]],
        is_expected: Callable[[], bool],
        timeout: float = 2.0,
    ) -> None:
        """Write a control and verify the resulting state if its ACK is missed.

        The D80 can occasionally apply a control while its immediate 8D22 ACK is
        missed by the connection path. v0.1.0 incorrectly surfaced that as an HA
        action failure even though the soundbar had changed. We now fall back to
        the official GET command for that state and accept the operation when the
        D80 reports the requested value.
        """
        try:
            await self._async_request(
                GROUP_CONTROL,
                command,
                data,
                expected_data=data,
                timeout=timeout,
            )
            return
        except UltimeaCommandError as ack_error:
            _LOGGER.debug(
                "D80 ACK missed for command 0x%02X; verifying resulting state",
                command,
            )
            await asyncio.sleep(0.15)
            try:
                await refresh()
            except UltimeaError:
                raise ack_error
            if is_expected():
                _LOGGER.debug(
                    "D80 command 0x%02X verified by state query after missed ACK",
                    command,
                )
                return
            raise ack_error

    async def async_set_volume(self, raw_volume: int) -> None:
        raw_volume = max(0, min(255, int(raw_volume)))
        await self._async_write_verified(
            CMD_VOLUME,
            bytes([raw_volume]),
            refresh=lambda: self.async_query(GROUP_INFO, INFO_VOLUME),
            is_expected=lambda: self.state.raw_volume == raw_volume,
        )

    async def async_set_power(self, enabled: bool) -> None:
        data = bytes([1 if enabled else 0])
        try:
            await self._async_write_verified(
                CMD_POWER,
                data,
                refresh=lambda: self.async_query(GROUP_INFO, INFO_POWER),
                is_expected=lambda: self.state.power is enabled,
                timeout=3.0,
            )
        except UltimeaCommandError:
            # Power-off can legitimately tear down BLE before the ACK/query makes
            # it back to HA. If the link disappeared after asking for OFF, the
            # requested end state has effectively been reached.
            if not enabled and not self.connected:
                self.state.power = False
                self._async_notify_listeners()
                return
            raise

        if enabled:
            self.state.power = True
            self._async_notify_listeners()
            self.hass.async_create_task(self._async_delayed_post_power_refresh())

    async def _async_delayed_post_power_refresh(self) -> None:
        await asyncio.sleep(0.8)
        try:
            await self.async_refresh_state()
        except UltimeaError as err:
            _LOGGER.debug("Post-power D80 refresh failed: %s", err)

    async def async_set_mute(self, muted: bool) -> None:
        data = bytes([0 if muted else 1])
        await self._async_write_verified(
            CMD_MUTE,
            data,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_MUTE),
            is_expected=lambda: self.state.muted is muted,
        )

    async def async_set_source(self, source: Source) -> None:
        data = bytes([SOURCE_TO_VALUE[source]])
        await self._async_write_verified(
            CMD_SOURCE,
            data,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_SOURCE),
            is_expected=lambda: self.state.source is source,
        )

    async def async_set_sound_mode(self, mode: SoundMode) -> None:
        data = bytes([SOUND_MODE_TO_VALUE[mode]])
        await self._async_write_verified(
            CMD_SOUND_MODE,
            data,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_SOUND_MODE),
            is_expected=lambda: self.state.sound_mode is mode,
        )

    async def async_set_brightness(self, brightness: Brightness) -> None:
        data = bytes([BRIGHTNESS_TO_VALUE[brightness]])
        await self._async_write_verified(
            CMD_BRIGHTNESS,
            data,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_BRIGHTNESS),
            is_expected=lambda: self.state.brightness is brightness,
        )

    async def async_set_screen_timeout(self, timeout: ScreenTimeout) -> None:
        data = bytes([SCREEN_TIMEOUT_TO_VALUE[timeout]])
        await self._async_write_verified(
            CMD_SCREEN_TIMEOUT,
            data,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_SCREEN_TIMEOUT),
            is_expected=lambda: self.state.screen_timeout is timeout,
        )

    async def async_set_prompt_sound(self, prompt: PromptSound) -> None:
        data = bytes([PROMPT_SOUND_TO_VALUE[prompt]])
        await self._async_write_verified(
            CMD_PROMPT_SOUND,
            data,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_PROMPT_SOUND),
            is_expected=lambda: self.state.prompt_sound is prompt,
        )

    async def async_set_standby_minutes(self, minutes: int) -> None:
        if minutes not in MINUTES_TO_STANDBY:
            raise ValueError(f"Unsupported standby value: {minutes}")
        data = int(minutes).to_bytes(2, "little")
        await self._async_write_verified(
            CMD_AUTO_STANDBY,
            data,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_AUTO_STANDBY),
            is_expected=lambda: self.state.standby_minutes == minutes,
        )


async def async_probe_device(
    hass: HomeAssistant, address: str, name: str
) -> UltimeaIdentity:
    """Connect once and prove that the device is a Poseidon D80 Boom."""
    device = UltimeaDevice(
        hass,
        address,
        name,
        keep_connected=False,
        disconnect_delay=1,
    )
    try:
        await device.async_ensure_connected()
        return await device.async_refresh_identity()
    finally:
        await device.async_disconnect()
