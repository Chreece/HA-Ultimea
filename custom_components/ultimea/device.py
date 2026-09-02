"""Bluetooth client for app-capable ULTIMEA soundbars."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Iterable
from contextlib import suppress
from datetime import datetime, timezone
import logging
from typing import Any

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    BRIGHTNESS_TO_VALUE,
    CAP_FETCH_ABILITIES,
    CMD_AUTO_STANDBY,
    CMD_BRIGHTNESS,
    CMD_MUTE,
    CMD_POWER,
    CMD_PROMPT_SOUND,
    CMD_SCREEN_TIMEOUT,
    CMD_SOUND_MODE,
    CMD_SOURCE,
    CMD_VOLUME,
    GROUP_CAPABILITIES,
    GROUP_CONTROL,
    GROUP_INFO,
    INFO_AUTO_STANDBY,
    INFO_BRIGHTNESS,
    INFO_FIRMWARE,
    INFO_MODEL,
    INFO_MUTE,
    INFO_POWER,
    INFO_PROMPT_SOUND,
    INFO_PROTOCOL,
    INFO_SCREEN_TIMEOUT,
    INFO_SERIAL,
    INFO_SOUND_MODE,
    INFO_SOURCE,
    INFO_VOLUME,
    MINUTES_TO_STANDBY,
    PROMPT_SOUND_TO_VALUE,
    SCREEN_TIMEOUT_TO_VALUE,
    SOUND_MODE_TO_VALUE,
    SOURCE_TO_VALUE,
    TRANSPORT_COMMON,
    TRANSPORT_UUIDS,
    VALUE_TO_BRIGHTNESS,
    VALUE_TO_PROMPT_SOUND,
    VALUE_TO_SCREEN_TIMEOUT,
    VALUE_TO_SOUND_MODE,
    VALUE_TO_SOURCE,
    Brightness,
    Feature,
    PromptSound,
    ScreenTimeout,
    SoundMode,
    Source,
)
from .models import UltimeaCapabilities, UltimeaIdentity, UltimeaState
from .profiles import profile_for_model
from .protocol import UltimeaFrame, build_command, decode_ascii, iter_frames

_LOGGER = logging.getLogger(__name__)


class UltimeaError(Exception):
    """Base ULTIMEA error."""


class UltimeaConnectionError(UltimeaError):
    """Raised when no connection can be established."""


class UltimeaUnsupportedDeviceError(UltimeaError):
    """Raised when a BLE device does not expose the supported app protocol."""


class UltimeaCommandError(UltimeaError):
    """Raised when a command is rejected or times out."""


class UltimeaDevice:
    """One ULTIMEA soundbar speaking the app's AA/BB BLE protocol."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        *,
        keep_connected: bool = True,
        disconnect_delay: int = 15,
        heartbeat_interval: int = 30,
        preferred_transport: str | None = None,
        config_entry: ConfigEntry | None = None,
    ) -> None:
        self.hass = hass
        self.address = address.upper()
        self.name = name
        self.keep_connected = keep_connected
        self.disconnect_delay = disconnect_delay
        self.heartbeat_interval = max(10, int(heartbeat_interval))
        self._config_entry = config_entry

        self.identity = UltimeaIdentity()
        self.capabilities = UltimeaCapabilities()
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
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._heartbeat_wakeup = asyncio.Event()
        self._available = False
        self._stopping = False
        self._transport_candidates: list[str] = []
        self._transport = preferred_transport
        self._write_uuid: str | None = None
        self._notify_uuid: str | None = None
        self.last_heartbeat_success: str | None = None
        self.last_heartbeat_error: str | None = None
        self.heartbeat_attempts = 0

    @property
    def available(self) -> bool:
        """Return whether HA can currently see or talk to the soundbar."""
        return self._available or bool(self._client and self._client.is_connected)

    @property
    def connected(self) -> bool:
        """Return connection state."""
        return bool(self._client and self._client.is_connected)

    @property
    def transport(self) -> str | None:
        """Return the APK common/custom transport selected for this device."""
        return self._transport

    def supports(self, feature: Feature) -> bool:
        """Return whether a feature passed profile/capability validation."""
        return self.capabilities.supports(feature)

    def restore_capabilities(
        self,
        *,
        features: Iterable[str] = (),
        raw_ability_flags: Iterable[int] = (),
        standby_options: Iterable[int] = (),
        transport: str | None = None,
        protocol_version: int | None = None,
        profile: str | None = None,
    ) -> None:
        """Restore probe results from the config entry for offline startup."""
        parsed: set[Feature] = set()
        for value in features:
            try:
                parsed.add(Feature(value))
            except ValueError:
                continue
        self.capabilities.features = parsed
        self.capabilities.raw_ability_flags = tuple(int(x) & 0xFF for x in raw_ability_flags)
        self.capabilities.standby_options = tuple(int(x) for x in standby_options)
        if transport in TRANSPORT_UUIDS:
            self._transport = transport
            self.capabilities.transport = transport
        self.identity.protocol_version = protocol_version
        self.identity.profile = profile

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
    def _async_create_runtime_task(
        self,
        target: Coroutine[object, object, None],
        name: str,
        *,
        eager_start: bool = True,
    ) -> asyncio.Task[None]:
        """Create an integration-lifecycle background task.

        Runtime/recovery tasks must never enter Home Assistant's normal startup
        task bucket.  Config-entry background tasks are cancelled automatically
        on unload and, unlike ``hass.async_create_task``, do not block startup or
        ``async_block_till_done``.  Probe-only device instances have no config
        entry and use HA's equivalent background-task API.
        """
        if self._config_entry is not None:
            return self._config_entry.async_create_background_task(
                self.hass,
                target,
                name,
                eager_start=eager_start,
            )
        return self.hass.async_create_background_task(
            target,
            name,
            eager_start=eager_start,
        )

    @callback
    def async_handle_advertisement(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        _change: bluetooth.BluetoothChange,
    ) -> None:
        """Update reachability from Home Assistant's shared Bluetooth manager."""
        self._available = True
        self.rssi = service_info.rssi
        self.last_seen_name = service_info.name
        self.last_heartbeat_error = None
        self._heartbeat_wakeup.set()
        self._async_notify_listeners()
        if self.keep_connected and not self.connected and not self._stopping:
            self._schedule_connect_and_refresh()

    @callback
    def async_handle_unavailable(self, _service_info: bluetooth.BluetoothServiceInfoBleak) -> None:
        """Handle device no longer being visible to connectable scanners."""
        if not self.connected:
            changed = self._available
            self._available = False
            self._heartbeat_wakeup.set()
            if changed:
                self._async_notify_listeners()

    @callback
    def _schedule_connect_and_refresh(self) -> None:
        if self._connect_refresh_task and not self._connect_refresh_task.done():
            return
        self._connect_refresh_task = self._async_create_runtime_task(
            self._async_connect_and_refresh_background(),
            "ULTIMEA connect and refresh",
        )

    async def _async_connect_and_refresh_background(self) -> None:
        try:
            await self.async_ensure_connected()
            await self.async_refresh_all()
        except UltimeaError as err:
            _LOGGER.debug("ULTIMEA background connect/refresh failed: %s", err)
        finally:
            self._connect_refresh_task = None

    async def async_start(self) -> None:
        """Start runtime behavior and obtain an initial state snapshot."""
        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        if info is not None:
            self._available = True
            self.rssi = info.rssi
            self.last_seen_name = info.name
            self._async_notify_listeners()
            try:
                await self.async_ensure_connected()
                await self.async_refresh_all(reprobe_capabilities=True)
            except UltimeaError as err:
                _LOGGER.debug("Initial ULTIMEA state refresh failed: %s", err)
            finally:
                self._schedule_disconnect()
        else:
            self._heartbeat_wakeup.set()

        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = self._async_create_runtime_task(
                self._async_heartbeat_loop(),
                "ULTIMEA unavailable heartbeat",
                eager_start=False,
            )

    async def async_stop(self) -> None:
        """Stop and release the BLE connection."""
        self._stopping = True
        if self._disconnect_task:
            self._disconnect_task.cancel()
            self._disconnect_task = None
        if self._connect_refresh_task:
            self._connect_refresh_task.cancel()
            self._connect_refresh_task = None
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
        await self.async_disconnect()

    def _disconnected(self, _client: BleakClient) -> None:
        """Bleak disconnected callback."""
        self._client = None
        if self._pending is not None:
            future = self._pending[3]
            if not future.done():
                future.set_exception(UltimeaConnectionError("ULTIMEA device disconnected"))
            self._pending = None
        if self.keep_connected and not self._stopping:
            self._available = False
            self._heartbeat_wakeup.set()
        self._async_notify_listeners()

    async def _async_heartbeat_loop(self) -> None:
        """Recover an unavailable device without touching global scanning."""
        immediate = True
        try:
            while not self._stopping:
                needs_probe = (not self._available) or (
                    self.keep_connected and not self.connected
                )
                if not needs_probe:
                    self._heartbeat_wakeup.clear()
                    await self._heartbeat_wakeup.wait()
                    immediate = True
                    continue

                if not immediate:
                    self._heartbeat_wakeup.clear()
                    try:
                        await asyncio.wait_for(
                            self._heartbeat_wakeup.wait(),
                            timeout=self.heartbeat_interval,
                        )
                    except TimeoutError:
                        pass
                    if self._stopping:
                        return
                    if self._available and (not self.keep_connected or self.connected):
                        immediate = True
                        continue

                immediate = False
                await self._async_heartbeat_once()
        except asyncio.CancelledError:
            return

    async def _async_heartbeat_once(self) -> None:
        """Perform one lightweight unavailable-device recovery attempt."""
        if self._stopping:
            return
        if self._connect_refresh_task and not self._connect_refresh_task.done():
            return

        self.heartbeat_attempts += 1
        was_available = self.available
        try:
            await self.async_ensure_connected()
            heartbeat_command = INFO_POWER if self.supports(Feature.POWER) else INFO_MODEL
            await self.async_query(GROUP_INFO, heartbeat_command, timeout=1.5)
            self._available = True
            self.last_heartbeat_success = datetime.now(timezone.utc).isoformat()
            self.last_heartbeat_error = None
            if not was_available:
                await self.async_refresh_all()
        except UltimeaError as err:
            self.last_heartbeat_error = str(err)
            if not self.connected:
                self._available = False
            _LOGGER.debug(
                "ULTIMEA unavailable heartbeat attempt %d failed: %s",
                self.heartbeat_attempts,
                err,
            )
        finally:
            if not self.keep_connected:
                self._schedule_disconnect()
            if was_available != self.available:
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

    def _find_transport_candidates(self, client: BleakClient) -> list[str]:
        char_uuids = {
            str(char.uuid).lower()
            for service in client.services
            for char in service.characteristics
        }
        candidates = [
            name
            for name, (write_uuid, notify_uuid) in TRANSPORT_UUIDS.items()
            if write_uuid in char_uuids and notify_uuid in char_uuids
        ]
        if self._transport in candidates:
            candidates.remove(self._transport)
            candidates.insert(0, self._transport)
        elif TRANSPORT_COMMON in candidates:
            candidates.remove(TRANSPORT_COMMON)
            candidates.insert(0, TRANSPORT_COMMON)
        return candidates

    async def _async_activate_transport(self, transport: str) -> None:
        """Subscribe to one APK common/custom characteristic pair."""
        client = self._client
        if client is None or not client.is_connected:
            raise UltimeaConnectionError("Bluetooth client is not connected")
        if transport not in self._transport_candidates:
            raise UltimeaUnsupportedDeviceError(f"Transport {transport!r} is not present")

        write_uuid, notify_uuid = TRANSPORT_UUIDS[transport]
        if self._notify_uuid and self._notify_uuid != notify_uuid:
            with suppress(Exception):
                await client.stop_notify(self._notify_uuid)
        if self._notify_uuid != notify_uuid:
            await client.start_notify(notify_uuid, self._notification)

        self._transport = transport
        self._write_uuid = write_uuid
        self._notify_uuid = notify_uuid
        self.capabilities.transport = transport

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

            self._client = client
            self._transport_candidates = self._find_transport_candidates(client)
            if not self._transport_candidates:
                self._client = None
                await client.disconnect()
                raise UltimeaUnsupportedDeviceError(
                    "No ULTIMEA common (8D11/8D22) or custom-common (8D55/8D66) "
                    "characteristic pair was found"
                )

            try:
                await self._async_activate_transport(self._transport_candidates[0])
            except Exception:
                self._client = None
                await client.disconnect()
                raise

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
            if client.is_connected and self._notify_uuid:
                await client.stop_notify(self._notify_uuid)
        with suppress(Exception):
            if client.is_connected:
                await client.disconnect()
        self._async_notify_listeners()

    def _schedule_disconnect(self) -> None:
        if self.keep_connected or self._stopping:
            return
        if self._disconnect_task:
            self._disconnect_task.cancel()
        self._disconnect_task = self._async_create_runtime_task(
            self._async_delayed_disconnect(),
            "ULTIMEA delayed disconnect",
        )

    async def _async_delayed_disconnect(self) -> None:
        try:
            await asyncio.sleep(self.disconnect_delay)
            await self.async_disconnect()
        except asyncio.CancelledError:
            return
        finally:
            self._disconnect_task = None

    def _notification(self, _sender: Any, payload: bytearray) -> None:
        """Handle one BLE notification from either app control transport."""
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
        """Apply a control push or official-app GET response to state."""
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
            self.state.muted = data[0] == 0
            return True
        if frame.command == CMD_SOURCE and len(data) == 1:
            self.state.raw_source = data[0]
            source = VALUE_TO_SOURCE.get(data[0])
            if source is not None:
                self.state.source = source
            return True
        if frame.command == CMD_SOUND_MODE and len(data) == 1:
            self.state.raw_sound_mode = data[0]
            mode = VALUE_TO_SOUND_MODE.get(data[0])
            if mode is not None:
                self.state.sound_mode = mode
            return True
        if frame.command == CMD_BRIGHTNESS and len(data) == 1:
            if data[0] == 0:
                self.state.screen_on = False
                return True
            brightness = VALUE_TO_BRIGHTNESS.get(data[0])
            if brightness is not None:
                self.state.brightness = brightness
                self.state.screen_on = True
            return True
        if frame.command == CMD_SCREEN_TIMEOUT and len(data) == 1:
            timeout = VALUE_TO_SCREEN_TIMEOUT.get(data[0])
            if timeout is not None:
                self.state.screen_timeout = timeout
            return True
        if frame.command == CMD_PROMPT_SOUND and len(data) == 1:
            prompt = VALUE_TO_PROMPT_SOUND.get(data[0])
            if prompt is not None:
                self.state.prompt_sound = prompt
            return True
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
            self.state.muted = bool(data[0])
            return True
        if frame.command == INFO_VOLUME and len(data) == 1:
            self.state.raw_volume = data[0]
            return True
        if frame.command == INFO_SOURCE and len(data) == 1:
            self.state.raw_source = data[0]
            source = VALUE_TO_SOURCE.get(data[0])
            if source is not None:
                self.state.source = source
            return True
        if frame.command == INFO_SOUND_MODE and len(data) == 1:
            self.state.raw_sound_mode = data[0]
            mode = VALUE_TO_SOUND_MODE.get(data[0])
            if mode is not None:
                self.state.sound_mode = mode
            return True
        if frame.command == INFO_PROMPT_SOUND and len(data) == 1:
            prompt = VALUE_TO_PROMPT_SOUND.get(data[0])
            if prompt is not None:
                self.state.prompt_sound = prompt
            return True
        if frame.command == INFO_BRIGHTNESS and len(data) == 1:
            brightness = VALUE_TO_BRIGHTNESS.get(data[0])
            if brightness is not None:
                self.state.brightness = brightness
                self.state.screen_on = True
            return True
        if frame.command == INFO_SCREEN_TIMEOUT and len(data) == 1:
            timeout = VALUE_TO_SCREEN_TIMEOUT.get(data[0])
            if timeout is not None:
                self.state.screen_timeout = timeout
            return True
        if frame.command == INFO_AUTO_STANDBY and len(data) >= 2:
            self.state.standby_minutes = int.from_bytes(data[:2], "little")
            options = self._parse_standby_options(data)
            if options:
                self.capabilities.standby_options = options
            return True
        return False

    @staticmethod
    def _parse_standby_options(data: bytes) -> tuple[int, ...]:
        """Parse current uint16 + count + supported uint16 list when present."""
        if len(data) < 3:
            return ()
        count = data[2]
        need = 3 + (count * 2)
        if count == 0 or len(data) < need:
            return ()
        return tuple(
            int.from_bytes(data[3 + i * 2 : 5 + i * 2], "little")
            for i in range(count)
        )

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
        if self._write_uuid is None:
            raise UltimeaConnectionError("No active ULTIMEA write characteristic")
        packet = build_command(group, command, data)

        async with self._command_lock:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[UltimeaFrame] = loop.create_future()
            self._pending = (group, command, expected_data, future)
            try:
                await client.write_gatt_char(self._write_uuid, packet, response=False)
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

    async def async_query(
        self, group: int, command: int, *, timeout: float = 3.0
    ) -> bytes:
        """Send a zero-payload query and return response data."""
        frame = await self._async_request(
            group, command, expected_data=None, timeout=timeout
        )
        return frame.data

    async def _async_try_query(self, command: int, *, timeout: float = 1.2) -> bytes | None:
        """Query one state item without making a whole refresh fail."""
        try:
            return await self.async_query(GROUP_INFO, command, timeout=timeout)
        except UltimeaError as err:
            _LOGGER.debug("ULTIMEA state query 0x%02X failed: %s", command, err)
            return None

    async def _async_read_model_on_current_transport(self) -> str:
        return decode_ascii(await self.async_query(GROUP_INFO, INFO_MODEL, timeout=1.5))

    async def async_refresh_identity(self) -> UltimeaIdentity:
        """Read identity and auto-select the working APK transport."""
        await self.async_ensure_connected()

        # If both APK transport pairs are present, prove which one actually
        # carries the AA/BB control protocol by issuing only the safe model GET.
        model = ""
        last_error: UltimeaError | None = None
        for transport in list(self._transport_candidates):
            try:
                if self._transport != transport:
                    await self._async_activate_transport(transport)
                model = await self._async_read_model_on_current_transport()
                if model:
                    break
            except UltimeaError as err:
                last_error = err
                continue
        if not model:
            raise UltimeaUnsupportedDeviceError(
                "ULTIMEA GATT transport was found, but the app model query did not respond"
            ) from last_error

        protocol_raw = await self._async_try_query(INFO_PROTOCOL, timeout=1.2)
        protocol_version = (
            int.from_bytes(protocol_raw, "little") if protocol_raw else None
        )
        serial_raw = await self._async_try_query(INFO_SERIAL, timeout=1.5)
        firmware_raw = await self._async_try_query(INFO_FIRMWARE, timeout=1.2)

        serial = decode_ascii(serial_raw or b"") or None
        firmware = (
            f"V{int.from_bytes(firmware_raw, 'little')}" if firmware_raw else None
        )

        profile = profile_for_model(model)
        self.identity = UltimeaIdentity(
            model=model,
            serial=serial,
            firmware=firmware,
            protocol_version=protocol_version,
            profile=profile.key,
            apk_embedded_model=profile.apk_embedded,
        )
        self.capabilities.transport = self._transport
        self._async_notify_listeners()
        return self.identity

    async def async_detect_capabilities(self) -> UltimeaCapabilities:
        """Capability-probe a model instead of relying on a marketing allow-list."""
        await self.async_ensure_connected()
        profile = profile_for_model(self.identity.model)

        # The app exposes fetchAbilities on both LegacyDelegate and
        # FrontierDelegate. Keep the byte array raw until field ordering is
        # proven across models; never assign guessed semantic indexes.
        try:
            raw = await self.async_query(
                GROUP_CAPABILITIES, CAP_FETCH_ABILITIES, timeout=1.2
            )
            self.capabilities.raw_ability_flags = tuple(raw)
        except UltimeaError as err:
            _LOGGER.debug("ULTIMEA fetchAbilities not available: %s", err)

        features = set(profile.verified_features)
        probes: tuple[tuple[Feature, int, Callable[[bytes], bool]], ...] = (
            (Feature.POWER, INFO_POWER, lambda d: len(d) == 1 and d[0] in (0, 1)),
            (Feature.MUTE, INFO_MUTE, lambda d: len(d) == 1 and d[0] in (0, 1)),
            (Feature.VOLUME, INFO_VOLUME, lambda d: len(d) == 1),
            (Feature.SOURCE, INFO_SOURCE, lambda d: len(d) == 1 and d[0] in VALUE_TO_SOURCE),
            (Feature.SOUND_MODE, INFO_SOUND_MODE, lambda d: len(d) == 1 and d[0] in VALUE_TO_SOUND_MODE),
            (Feature.BRIGHTNESS, INFO_BRIGHTNESS, lambda d: len(d) == 1 and d[0] in VALUE_TO_BRIGHTNESS),
            (Feature.SCREEN_TIMEOUT, INFO_SCREEN_TIMEOUT, lambda d: len(d) == 1 and d[0] in VALUE_TO_SCREEN_TIMEOUT),
            (Feature.PROMPT_SOUND, INFO_PROMPT_SOUND, lambda d: len(d) == 1 and d[0] in VALUE_TO_PROMPT_SOUND),
            (Feature.AUTO_STANDBY, INFO_AUTO_STANDBY, lambda d: len(d) >= 2),
        )
        for feature, command, validator in probes:
            data = await self._async_try_query(command, timeout=0.9)
            if data is not None and validator(data):
                features.add(feature)

        self.capabilities.features = features
        self.capabilities.transport = self._transport
        self._async_notify_listeners()
        return self.capabilities

    async def async_refresh_state(self) -> UltimeaState:
        """Actively read every capability-proven state."""
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
        }
        for feature, command in query_for_feature.items():
            if self.supports(feature):
                await self._async_try_query(command)
        self._async_notify_listeners()
        self._schedule_disconnect()
        return self.state

    async def async_refresh_all(self, *, reprobe_capabilities: bool = False) -> None:
        """Refresh identity plus capability-proven state as one snapshot.

        Capability probes are read-only.  Re-probe on each Home Assistant setup
        so a firmware update or a newly supported APK-compatible model can gain
        entities without deleting the config entry.  Recovery heartbeats keep
        using the cached feature set for a fast reconnect.
        """
        async with self._refresh_lock:
            await self.async_ensure_connected()
            await self.async_refresh_identity()
            if reprobe_capabilities or not self.capabilities.features:
                await self.async_detect_capabilities()
            else:
                # Once learned, recovery should be fast and should not spend
                # seconds timing out on features already known to be absent.
                await self.async_refresh_state()
            self._async_notify_listeners()

    async def async_refresh_volume(self) -> int | None:
        """Read the current absolute volume."""
        await self._async_try_query(INFO_VOLUME)
        return self.state.raw_volume

    async def _async_write_verified(
        self,
        command: int,
        data: bytes,
        *,
        feature: Feature,
        refresh: Callable[[], Awaitable[Any]],
        is_expected: Callable[[], bool],
        timeout: float = 2.0,
    ) -> None:
        """Write a capability-proven control and verify missed ACKs by GET."""
        if not self.supports(feature):
            raise UltimeaCommandError(
                f"{feature.value.replace('_', ' ')} is not reported as supported by this ULTIMEA device"
            )
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
                "ULTIMEA ACK missed for command 0x%02X; verifying resulting state",
                command,
            )
            await asyncio.sleep(0.15)
            try:
                await refresh()
            except UltimeaError:
                raise ack_error
            if is_expected():
                return
            raise ack_error

    async def async_set_volume(self, raw_volume: int) -> None:
        raw_volume = max(0, min(255, int(raw_volume)))
        await self._async_write_verified(
            CMD_VOLUME,
            bytes([raw_volume]),
            feature=Feature.VOLUME,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_VOLUME),
            is_expected=lambda: self.state.raw_volume == raw_volume,
        )

    async def async_set_power(self, enabled: bool) -> None:
        data = bytes([1 if enabled else 0])
        try:
            await self._async_write_verified(
                CMD_POWER,
                data,
                feature=Feature.POWER,
                refresh=lambda: self.async_query(GROUP_INFO, INFO_POWER),
                is_expected=lambda: self.state.power is enabled,
                timeout=3.0,
            )
        except UltimeaCommandError:
            if not enabled and not self.connected:
                self.state.power = False
                self._async_notify_listeners()
                return
            raise
        if enabled:
            self.state.power = True
            self._async_notify_listeners()
            self._async_create_runtime_task(
                self._async_delayed_post_power_refresh(),
                "ULTIMEA post-power refresh",
            )

    async def _async_delayed_post_power_refresh(self) -> None:
        await asyncio.sleep(0.8)
        try:
            await self.async_refresh_state()
        except UltimeaError as err:
            _LOGGER.debug("Post-power ULTIMEA refresh failed: %s", err)

    async def async_set_mute(self, muted: bool) -> None:
        data = bytes([0 if muted else 1])
        await self._async_write_verified(
            CMD_MUTE,
            data,
            feature=Feature.MUTE,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_MUTE),
            is_expected=lambda: self.state.muted is muted,
        )

    async def async_set_source(self, source: Source) -> None:
        data = bytes([SOURCE_TO_VALUE[source]])
        await self._async_write_verified(
            CMD_SOURCE,
            data,
            feature=Feature.SOURCE,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_SOURCE),
            is_expected=lambda: self.state.source is source,
        )

    async def async_set_sound_mode(self, mode: SoundMode) -> None:
        data = bytes([SOUND_MODE_TO_VALUE[mode]])
        await self._async_write_verified(
            CMD_SOUND_MODE,
            data,
            feature=Feature.SOUND_MODE,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_SOUND_MODE),
            is_expected=lambda: self.state.sound_mode is mode,
        )

    async def async_set_brightness(self, brightness: Brightness) -> None:
        data = bytes([BRIGHTNESS_TO_VALUE[brightness]])
        await self._async_write_verified(
            CMD_BRIGHTNESS,
            data,
            feature=Feature.BRIGHTNESS,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_BRIGHTNESS),
            is_expected=lambda: self.state.brightness is brightness,
        )

    async def async_set_screen_timeout(self, timeout: ScreenTimeout) -> None:
        data = bytes([SCREEN_TIMEOUT_TO_VALUE[timeout]])
        await self._async_write_verified(
            CMD_SCREEN_TIMEOUT,
            data,
            feature=Feature.SCREEN_TIMEOUT,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_SCREEN_TIMEOUT),
            is_expected=lambda: self.state.screen_timeout is timeout,
        )

    async def async_set_prompt_sound(self, prompt: PromptSound) -> None:
        data = bytes([PROMPT_SOUND_TO_VALUE[prompt]])
        await self._async_write_verified(
            CMD_PROMPT_SOUND,
            data,
            feature=Feature.PROMPT_SOUND,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_PROMPT_SOUND),
            is_expected=lambda: self.state.prompt_sound is prompt,
        )

    async def async_set_standby_minutes(self, minutes: int) -> None:
        allowed = self.capabilities.standby_options
        if allowed and minutes not in allowed:
            raise ValueError(f"Unsupported standby value for this device: {minutes}")
        if not allowed and minutes not in MINUTES_TO_STANDBY:
            raise ValueError(f"Unsupported standby value: {minutes}")
        data = int(minutes).to_bytes(2, "little")
        await self._async_write_verified(
            CMD_AUTO_STANDBY,
            data,
            feature=Feature.AUTO_STANDBY,
            refresh=lambda: self.async_query(GROUP_INFO, INFO_AUTO_STANDBY),
            is_expected=lambda: self.state.standby_minutes == minutes,
        )


async def async_probe_device(
    hass: HomeAssistant, address: str, name: str
) -> tuple[UltimeaIdentity, UltimeaCapabilities]:
    """Connect once and prove an ULTIMEA app-protocol implementation."""
    device = UltimeaDevice(
        hass,
        address,
        name,
        keep_connected=False,
        disconnect_delay=1,
    )
    try:
        await device.async_ensure_connected()
        await device.async_refresh_identity()
        await device.async_detect_capabilities()
        # A model string plus at least one safe control-state GET prevents a
        # random device with coincidentally matching UUIDs from being accepted.
        if not device.identity.model or not device.capabilities.features:
            raise UltimeaUnsupportedDeviceError(
                "Device did not expose enough of the ULTIMEA app protocol"
            )
        return device.identity, device.capabilities
    finally:
        await device.async_disconnect()
