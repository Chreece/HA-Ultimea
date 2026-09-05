"""Explicit actions for the D80's captured Style corners and neutral center."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UltimeaRuntimeData
from .const import Feature
from .device import UltimeaError
from .entity import UltimeaEntity
from .eq_style import STYLE_PRESETS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    if runtime.device.supports(Feature.STYLE):
        async_add_entities([UltimeaStyleButton(runtime.device, name) for name in STYLE_PRESETS])


class UltimeaStyleButton(UltimeaEntity, ButtonEntity):
    """Stateless preset application; never claim a selection survived reconnect."""

    _attr_icon = "mdi:equalizer"

    def __init__(self, device, preset: str) -> None:
        super().__init__(device)
        self._preset = preset
        self._attr_unique_id = f"{device.identity.serial or device.address}_style_{preset}"
        self._attr_translation_key = "style_reset" if preset == "flat" else f"style_{preset}"
        if preset == "flat":
            self._attr_icon = "mdi:restore"

    @property
    def available(self) -> bool:
        return super().available and self.device.state.power is not False

    async def async_press(self) -> None:
        try:
            if self._preset == "flat":
                await self.device.async_reset_style()
            else:
                await self.device.async_set_style_preset(self._preset)
        except UltimeaError as err:
            raise HomeAssistantError(str(err)) from err
