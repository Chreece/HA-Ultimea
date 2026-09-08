"""ULTIMEA Bluetooth integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .blueprint_installer import BLUEPRINT_RELATIVE_PATH, install_bundled_blueprints
from .const import (
    CONF_ABILITY_FLAGS, CONF_CAPABILITIES, CONF_DISCONNECT_DELAY, CONF_FIRMWARE,
    CONF_HEARTBEAT_INTERVAL, CONF_KEEP_CONNECTED, CONF_MODEL, CONF_PROFILE,
    CONF_PROTOCOL_VERSION, CONF_SERIAL, CONF_STANDBY_OPTIONS, CONF_TRANSPORT,
    CONF_VOLUME_MAX, DEFAULT_DISCONNECT_DELAY, DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_KEEP_CONNECTED, DEFAULT_VOLUME_MAX,
)
from .device import UltimeaError
from .runtime import UltimeaDevice

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BUTTON,
]

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class UltimeaRuntimeData:
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
    if not device.available:
        return
    fresh = _capability_updates(device)
    merged = {**entry.data, **{k: v for k, v in fresh.items() if v is not None}}
    if merged != dict(entry.data):
        device.hass.config_entries.async_update_entry(entry, data=merged)


def _remove_legacy_xupmix_sensor(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove the obsolete read-only X-Upmix sensor kept by old entity registries."""
    registry = er.async_get(hass)
    for registry_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        if (
            registry_entry.entity_id.startswith("sensor.")
            and registry_entry.unique_id.endswith("_xupmix")
        ):
            _LOGGER.info(
                "Removing obsolete ULTIMEA X-Upmix sensor %s; the switch now owns state and control",
                registry_entry.entity_id,
            )
            registry.async_remove(registry_entry.entity_id)


async def _async_post_start_refresh(entry: ConfigEntry, device: UltimeaDevice) -> None:
    try:
        await device.async_post_start(reprobe_capabilities=True)
    except UltimeaError as err:
        _LOGGER.debug("Post-start ULTIMEA full status refresh failed: %s", err)
        return
    _store_runtime_probe(entry, device)


async def _async_reload_blueprint_automations(
    hass: HomeAssistant,
    *,
    full_reload: bool,
) -> None:
    """Reload live automations after the bundled blueprint changed on disk."""
    if "automation" not in hass.config.components:
        return
    if not hass.services.has_service("automation", "reload"):
        _LOGGER.warning(
            "ULTIMEA blueprint changed but automation.reload is unavailable; "
            "reload automations manually to activate the new blueprint"
        )
        return

    automation_ids: list[str] = []
    automation_entities: list[str] = []

    if not full_reload:
        # Home Assistant expands blueprint triggers when an automation is loaded.
        # Resetting the blueprint cache alone does not replace those live triggers,
        # so reload only automations that actually reference our blueprint.
        from homeassistant.components.automation import (  # noqa: PLC0415
            automations_with_blueprint,
        )

        automation_entities = automations_with_blueprint(hass, BLUEPRINT_RELATIVE_PATH)
        if not automation_entities:
            return

        registry = er.async_get(hass)
        for entity_id in automation_entities:
            registry_entry = registry.async_get(entity_id)
            if registry_entry is None or not registry_entry.unique_id:
                # A YAML automation without a stable ID cannot be targeted by the
                # 2026.9 automation.reload service. Fall back to one full reload.
                full_reload = True
                automation_ids.clear()
                break
            automation_ids.append(registry_entry.unique_id)

    try:
        if full_reload:
            _LOGGER.info(
                "Reloading automations after ULTIMEA blueprint installation/update"
            )
            await hass.services.async_call("automation", "reload", blocking=True)
            return

        _LOGGER.info(
            "Reloading %d automation(s) using updated ULTIMEA blueprint: %s",
            len(automation_entities),
            ", ".join(automation_entities),
        )
        for automation_id in automation_ids:
            await hass.services.async_call(
                "automation",
                "reload",
                {"id": automation_id},
                blocking=True,
            )
    except HomeAssistantError:
        # Blueprint delivery must never prevent the integration from loading.
        _LOGGER.exception(
            "Unable to reload automations using the updated ULTIMEA blueprint; "
            "reload automations manually"
        )


def _schedule_blueprint_automation_reload(
    hass: HomeAssistant,
    *,
    full_reload: bool,
) -> None:
    """Reload blueprint users after startup, never in the middle of HA setup."""

    @callback
    def _schedule(_event: Event | None = None) -> None:
        hass.async_create_task(
            _async_reload_blueprint_automations(hass, full_reload=full_reload),
            "ULTIMEA updated blueprint automation reload",
        )

    if hass.state is CoreState.running:
        _schedule()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _schedule)


async def async_setup(hass: HomeAssistant, _config: ConfigType) -> bool:
    """Set up integration-wide resources before config entries are loaded."""
    try:
        result = await hass.async_add_executor_job(
            install_bundled_blueprints,
            Path(hass.config.config_dir),
        )
    except OSError:
        # A blueprint installation problem must never prevent the soundbar
        # integration itself from loading.
        _LOGGER.exception("Unable to install bundled ULTIMEA automation blueprint")
        return True

    if result.installed:
        _LOGGER.info("Installed ULTIMEA automation blueprint: %s", ", ".join(result.installed))
    if result.updated:
        _LOGGER.info("Updated managed ULTIMEA automation blueprint: %s", ", ".join(result.updated))
    if result.preserved:
        _LOGGER.debug(
            "Preserved user-modified/unmanaged ULTIMEA blueprint: %s",
            ", ".join(result.preserved),
        )

    # If Automation already loaded before ULTIMEA replaced the blueprint file,
    # its existing automation entities still contain the old expanded triggers.
    # Reset the blueprint cache and reload those live automations after startup.
    # A newly installed blueprint needs a full reload because an automation that
    # previously failed on a missing blueprint cannot be discovered by reference.
    if result.changed and "automation" in hass.config.components:
        from homeassistant.components.automation.helpers import (  # noqa: PLC0415
            async_get_blueprints,
        )

        await async_get_blueprints(hass).async_reset_cache()
        _schedule_blueprint_automation_reload(
            hass,
            full_reload=bool(result.installed),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    address = entry.data[CONF_ADDRESS].upper()
    options = entry.options

    if entry.unique_id != address:
        conflict = next(
            (other for other in hass.config_entries.async_entries(entry.domain)
             if other.entry_id != entry.entry_id and other.unique_id == address),
            None,
        )
        if conflict is None:
            hass.config_entries.async_update_entry(entry, unique_id=address)

    # Old development builds exposed X-Upmix twice: a read-only sensor plus the
    # real switch. Current code only creates the switch, so clean the orphaned
    # sensor registry entry automatically on setup/reload.
    _remove_legacy_xupmix_sensor(hass, entry)

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
        bluetooth.async_track_unavailable(hass, device.async_handle_unavailable, address, connectable=True)
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Cache visibility only; absolutely no BLE connection/query during HA boot.
    await device.async_start()

    @callback
    def _schedule_post_start_refresh(_event: Event | None = None) -> None:
        if device._stopping:
            return
        entry.async_create_background_task(
            hass,
            _async_post_start_refresh(entry, device),
            "ULTIMEA post-start full status refresh",
        )

    already_running = hass.state is CoreState.running
    if not already_running:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _schedule_post_start_refresh)
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if already_running:
        _schedule_post_start_refresh()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        runtime: UltimeaRuntimeData = entry.runtime_data
        await runtime.device.async_stop()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
