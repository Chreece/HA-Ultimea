"""ULTIMEA Bluetooth integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DISCONNECT_DELAY,
    CONF_FIRMWARE,
    CONF_KEEP_CONNECTED,
    CONF_MODEL,
    CONF_SERIAL,
    CONF_VOLUME_MAX,
    DEFAULT_DISCONNECT_DELAY,
    DEFAULT_KEEP_CONNECTED,
    DEFAULT_VOLUME_MAX,
    SUPPORTED_MODEL,
)
from .device import UltimeaDevice

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SELECT]


@dataclass(slots=True)
class UltimeaRuntimeData:
    """Runtime data for one config entry."""

    device: UltimeaDevice
    volume_max: int


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a configured D80 Boom."""
    address = entry.data[CONF_ADDRESS].upper()
    options = entry.options

    # v0.1.0/v0.1.1 promoted the device serial to config-entry unique_id after
    # setup. Bluetooth discovery only knows the address, which caused HA to
    # surface the already-configured D80 as a second discovery. Migrate existing
    # entries back to the Bluetooth address; the serial remains in entry data
    # and in the Device Registry identifiers.
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
        disconnect_delay=options.get(
            CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY
        ),
    )
    device.identity.model = entry.data.get(CONF_MODEL) or SUPPORTED_MODEL
    device.identity.serial = entry.data.get(CONF_SERIAL)
    device.identity.firmware = entry.data.get(CONF_FIRMWARE)

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

    # Connect once when reachable and actively read the complete D80 state before
    # entities are created. This prevents every entity starting as ``unknown``.
    await device.async_start()

    if device.available:
        identity = device.identity
        updates = {}
        if identity.model and identity.model != entry.data.get(CONF_MODEL):
            updates[CONF_MODEL] = identity.model
        if identity.serial and identity.serial != entry.data.get(CONF_SERIAL):
            updates[CONF_SERIAL] = identity.serial
        if identity.firmware and identity.firmware != entry.data.get(CONF_FIRMWARE):
            updates[CONF_FIRMWARE] = identity.firmware
        if updates:
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, **updates}
            )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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
