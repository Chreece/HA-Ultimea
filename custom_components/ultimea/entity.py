"""Base entity for ULTIMEA."""

from __future__ import annotations

import re

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER
from .device import UltimeaDevice


def _model_number(serial: str | None) -> str | None:
    """Extract the Uxxxx product prefix used by ULTIMEA serials when present."""
    if not serial:
        return None
    match = re.match(r"^(U[0-9A-Z]{4})", serial.upper())
    return match.group(1) if match else None


class UltimeaEntity(Entity):
    """Base ULTIMEA entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: UltimeaDevice) -> None:
        self.device = device

    @property
    def available(self) -> bool:
        return self.device.available

    @property
    def device_info(self) -> DeviceInfo:
        identifier = self.device.identity.serial or self.device.address
        return DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            connections={(CONNECTION_BLUETOOTH, self.device.address)},
            manufacturer=MANUFACTURER,
            model=self.device.identity.model,
            model_id=_model_number(self.device.identity.serial),
            name=self.device.name,
            serial_number=self.device.identity.serial,
            sw_version=self.device.identity.firmware,
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.device.async_add_listener(self._handle_device_update))

    def _handle_device_update(self) -> None:
        self.async_write_ha_state()
