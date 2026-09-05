"""Switch entities for hardware-verified ULTIMEA controls."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UltimeaRuntimeData
from .const import Feature
from .device import UltimeaError
from .entity import UltimeaEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    if runtime.device.supports(Feature.XUPMIX):
        async_add_entities([UltimeaXUpmixSwitch(runtime.device)])


class UltimeaXUpmixSwitch(UltimeaEntity, SwitchEntity):
    _attr_translation_key = "xupmix"
    _attr_icon = "mdi:surround-sound"

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.identity.serial or device.address}_xupmix"

    @property
    def is_on(self) -> bool | None:
        return self.device.state.xupmix_enabled

    async def _set(self, enabled: bool) -> None:
        try:
            await self.device.async_set_xupmix(enabled)
        except UltimeaError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)
