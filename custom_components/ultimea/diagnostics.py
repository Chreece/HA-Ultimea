"""Diagnostics for ULTIMEA."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import UltimeaRuntimeData
from .const import CONF_SERIAL
from .profiles import APK_CAPABILITY_VOCABULARY, APK_EMBEDDED_MODELS

TO_REDACT = {"address", CONF_SERIAL}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics useful for adding new ULTIMEA model profiles."""
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
                "transport": device.transport,
                "heartbeat_interval": device.heartbeat_interval,
                "heartbeat_attempts": device.heartbeat_attempts,
                "last_heartbeat_success": device.last_heartbeat_success,
                "last_heartbeat_error": device.last_heartbeat_error,
                "identity": asdict(device.identity),
                "features": sorted(f.value for f in device.capabilities.features),
                "raw_ability_flags": list(device.capabilities.raw_ability_flags),
                "standby_options": list(device.capabilities.standby_options),
                "state": asdict(device.state),
            },
            TO_REDACT,
        ),
        "apk_reverse_engineering": {
            "embedded_model_strings": sorted(APK_EMBEDDED_MODELS),
            "capability_vocabulary": sorted(APK_CAPABILITY_VOCABULARY),
            "raw_ability_indexes_semantically_mapped": False,
        },
    }
