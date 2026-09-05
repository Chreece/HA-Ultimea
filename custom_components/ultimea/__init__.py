"""ULTIMEA Bluetooth integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant, callback

from .const import (
    CONF_ABILITY_FLAGS,
    CONF_CAPABILITIES,
    CONF_DISCONNECT_DELAY,
    CONF_FIRMWARE,
    CONF_KEEP_CONNECTED,
    CONF_HEARTBEAT_INTERVAL,
    CONF_MODEL,
    CONF_PROFILE,
    CONF_PROTOCOL_VERSION,
    CONF_SERIAL,
    CONF_STANDBY_OPTIONS,
    CONF_TRANSPORT,
    CONF_VOLUME_MAX,
    DEFAULT_DISCONNECT_DELAY,
    DEFAULT_KEEP_CONNECTED,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_VOLUME_MAX,
)
from .device import UltimeaError
from .runtime import UltimeaDevice

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SELECT]

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class UltimeaRuntimeData:
    """Runtime data for one config entry."""

    device: UltimeaDevice
    volume_max: int


def _capability_updates(device: UltimeaDevice) -> dict:
    return {
        CONF_MODEL: device.identity.model,
        CONF_SERIAL: device.identity.serial,
        CONF_FIRMWARE: device.identity.firmware,
        CONF_PROTOCOL_VERSION: device.identity.protocol_version,
        CONF_PROFILE: device.identity.profile,
        CONF_CAPABILITIES: sorted(f.value for f in device.capabilities.features),
        CONF_ABILITY_FLAGS: list(device.capabilities.raw_ability_flags),
        CONF_STANDBY_OPTIONS: list(device.capabilities.standby_options),
        CONF_TRANSPORT: device.transport,
    }


def _store_runtime_probe(entry: ConfigEntry, device: UltimeaDevice) -> None:
    """Persist successful identity/capability data without overwriting with None."""
    if not device.available:
        return
    fresh = _capability_updates(device)
    merged = {**entry.data, **{k: v for k, v in fresh.items() if v is not None}}
    if merged != dict(entry.data):
        device.hass.config_entries.async_update_entry(entry, data=merged)


async def _async_post_start_refresh(entry: ConfigEntry, device: UltimeaDevice) -> None:
    """Perform the first full device refresh only after Home Assistant is running."""
    try:
        await device.async_post_start(reprobe_capabilities=True)
    except UltimeaError as err:
        _LOGGER.debug("Post-start ULTIMEA full status refresh failed: %s", err)
        return
    _store_runtime_probe(entry, device)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a configured ULTIMEA soundbar."""
    address = entry.data[CONF_ADDRESS].upper()
    options = entry.options

    if entry.unique_id != address:
        conflict = next(
            (
                other
                for other in hass.config_entries.async_entries(entry.domain)
                if other.entry_id != entry.entry_id and other.unique_id == address
            ),
            None,
        )
        if conflict is None:
            hass.config_entries.async_update_entry(entry, unique_id=address)

    device = UltimeaDevice(
        hass,
        address,
        entry.title,
        keep_connected=options.get(CONF_KEEP_CONNECTED, DEFAULT_KEEP_CONNECTED),
        disconnect_delay=options.get(CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY),
        heartbeat_interval=options.get(CONF_HEARTBEAT_INTERVAL, DEFAULT_HEARTBEAT_INTERVAL),
        preferred_transport=entry.data.get(CONF_TRANSPORT),
        config_entry=entry,
    )
    device.identity.model = entry.data.get(CONF_MODEL)
    device.identity.serial = entry.data.get(CONF_SERIAL)
    device.identity.firmware = entry.data.get(CONF_FIRMWARE)
    device.identity.protocol_version = entry.data.get(CONF_PROTOCOL_VERSION)
    device.identity.profile = entry.data.get(CONF_PROFILE)
    device.restore_capabilities(
        features=entry.data.get(CONF_CAPABILITIES, ()),
        raw_ability_flags=entry.data.get(CONF_ABILITY_FLAGS, ()),
        standby_options=entry.data.get(CONF_STANDBY_OPTIONS, ()),
        transport=entry.data.get(CONF_TRANSPORT),
        protocol_version=entry.data.get(CONF_PROTOCOL_VERSION),
        profile=entry.data.get(CONF_PROFILE),
    )

    entry.runtime_data = UltimeaRuntimeData(
        device=device,
        volume_max=options.get(CONF_VOLUME_MAX, DEFAULT_VOLUME_MAX),
    )

    entry.async_on_unload(
        bluetooth.async_register_callback(
            hass,
            device.async_handle_advertisement,
            {"address": address, "connectable": True},
            bluetooth.BluetoothScanningMode.PASSIVE,
            replay=bluetooth.BluetoothCallbackReplay.NEWEST_FIRST,
        )
    )
    entry.async_on_unload(
        bluetooth.async_track_unavailable(
            hass,
            device.async_handle_unavailable,
            address,
            connectable=True,
        )
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # This method only restores cached reachability. It deliberately performs no
    # BLE connection/query while Home Assistant is still starting.
    await device.async_start()

    @callback
    def _schedule_post_start_refresh(_event: Event | None = None) -> None:
        if device._stopping:  # lifecycle guard; task itself is config-entry owned
            return
        entry.async_create_background_task(
            hass,
            _async_post_start_refresh(entry, device),
            "ULTIMEA post-start full status refresh",
        )

    already_running = hass.state is CoreState.running
    if not already_running:
        entry.async_on_unload(
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED,
                _schedule_post_start_refresh,
            )
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reloading the integration while HA is already running is not a restart, so
    # there is no reason to wait for an event that has already happened.
    if already_running:
        _schedule_post_start_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload ULTIMEA."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime: UltimeaRuntimeData = entry.runtime_data
        await runtime.device.async_stop()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
