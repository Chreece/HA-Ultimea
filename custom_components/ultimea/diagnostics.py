"""Diagnostics for ULTIMEA."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import UltimeaRuntimeData
from .const import CONF_SERIAL

TO_REDACT = {"address", CONF_SERIAL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics."""
    runtime: UltimeaRuntimeData = entry.runtime_data
    device = runtime.device
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "runtime": async_redact_data(
            {
                "address": device.address,
                "connected": device.connected,
                "available": device.available,
                "rssi": device.rssi,
                "identity": asdict(device.identity),
                "state": asdict(device.state),
            },
            TO_REDACT,
        ),
    }
