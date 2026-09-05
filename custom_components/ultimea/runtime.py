"""Runtime lifecycle and safe-code session handling for ULTIMEA devices."""

from __future__ import annotations

import logging
import secrets
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import callback

from .const import GROUP_CAPABILITIES, GROUP_INFO, INFO_MODEL, INFO_PROTOCOL
from .device import UltimeaCommandError, UltimeaDevice as BaseUltimeaDevice, UltimeaError
from .protocol import (
    SAFE_CODE_COMMAND,
    build_safe_code_pair,
    safe_code_response_complements,
    validate_safe_code_pair,
)

_LOGGER = logging.getLogger(__name__)


class UltimeaDevice(BaseUltimeaDevice):
    """ULTIMEA device with post-start refresh and per-session safe-code setup."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._runtime_ready = False
        self._safe_code_authenticated = False
        self._safe_code_in_progress = False
        self._safe_code_protocol_checked = False
        self.safe_code_last_request: bytes | None = None
        self.safe_code_last_response: bytes | None = None
        self.safe_code_complement_match: bool | None = None

    async def async_start(self) -> None:
        """Prime cached reachability without performing BLE I/O during HA boot."""
        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        if info is not None:
            self._available = True
            self.rssi = info.rssi
            self.last_seen_name = info.name
            self._async_notify_listeners()

    async def async_post_start(self, *, reprobe_capabilities: bool = True) -> None:
        """Start recovery work and refresh all statuses after HA has started."""
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
            # Persistent mode reconnects whenever its BLE link is gone. On-demand
            # mode refreshes once when the bar actually reappears after being
            # unavailable, then may disconnect again after the configured delay.
            if self.keep_connected or not was_available:
                self._schedule_connect_and_refresh()

    async def _async_heartbeat_once(self) -> None:
        """Never let heartbeat probing start until Home Assistant is running."""
        if not self._runtime_ready:
            return
        await super()._async_heartbeat_once()

    async def _async_activate_transport(self, transport: str) -> None:
        """Reset safe-code state whenever the active protocol transport changes."""
        previous = self._transport
        await super()._async_activate_transport(transport)
        if previous != self._transport:
            self._reset_safe_code_session()

    def _disconnected(self, client: Any) -> None:
        """Reset per-BLE-session authentication before normal disconnect handling."""
        self._reset_safe_code_session()
        super()._disconnected(client)

    async def async_disconnect(self) -> None:
        """Disconnect and clear the per-session safe-code state."""
        self._reset_safe_code_session()
        await super().async_disconnect()

    async def async_stop(self) -> None:
        """Stop runtime work and prevent reconnect refreshes during unload."""
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
        """Perform the official APP->firmware 00:01 safe-code exchange."""
        if self._safe_code_authenticated:
            return
        if self._safe_code_in_progress:
            return

        challenge = secrets.randbelow(0x100)
        request = build_safe_code_pair(challenge)
        self.safe_code_last_request = request
        self._safe_code_in_progress = True
        try:
            # The official app reads protocol version immediately before the
            # safe-code exchange. Avoid duplicating it when identity refresh has
            # already performed that query on this exact BLE transport/session.
            if not self._safe_code_protocol_checked:
                protocol_frame = await super()._async_request(
                    GROUP_INFO,
                    INFO_PROTOCOL,
                    expected_data=None,
                    timeout=min(timeout, 1.5),
                )
                if protocol_frame.data:
                    self.identity.protocol_version = int.from_bytes(
                        protocol_frame.data, "little"
                    )
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

        self.safe_code_complement_match = safe_code_response_complements(
            challenge, response
        )
        if not self.safe_code_complement_match:
            _LOGGER.debug(
                "ULTIMEA safe-code response pair is valid but does not use the "
                "observed D80 complement relation: request=%s response=%s",
                request.hex(" "),
                response.hex(" "),
            )

        self._safe_code_authenticated = True
        _LOGGER.debug(
            "ULTIMEA safe-code session established: request=%s response=%s",
            request.hex(" "),
            response.hex(" "),
        )

    async def _async_request(
        self,
        group: int,
        command: int,
        data: bytes = b"",
        *,
        expected_data: bytes | None,
        timeout: float = 2.0,
    ):
        """Require safe-code setup before non-bootstrap protocol commands."""
        bootstrap_query = group == GROUP_INFO and command in (INFO_PROTOCOL, INFO_MODEL)
        safe_code_command = (
            group == GROUP_CAPABILITIES and command == SAFE_CODE_COMMAND
        )

        if (
            not self._safe_code_in_progress
            and not self._safe_code_authenticated
            and not bootstrap_query
            and not safe_code_command
        ):
            await self.async_ensure_connected()
            try:
                await self._async_safe_code_handshake()
            except UltimeaError:
                # A malformed/failed safe-code exchange must never be hidden by
                # the command that would otherwise follow it.
                raise

        frame = await super()._async_request(
            group,
            command,
            data,
            expected_data=expected_data,
            timeout=timeout,
        )
        if group == GROUP_INFO and command == INFO_PROTOCOL:
            self._safe_code_protocol_checked = True
        return frame
