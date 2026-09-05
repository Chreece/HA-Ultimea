"""10-band Custom EQ number entities for hardware-verified ULTIMEA models."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UltimeaRuntimeData
from .const import Feature
from .device import UltimeaError
from .entity import UltimeaEntity
from .protocol import EQ_CUSTOM_PROFILE, EQ_FREQUENCIES_HZ


def _frequency_label(hz: int) -> str:
    return f"{hz // 1000} kHz" if hz >= 1000 else f"{hz} Hz"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    if runtime.device.supports(Feature.EQUALIZER):
        async_add_entities(
            [UltimeaEqualizerBand(runtime.device, i, hz) for i, hz in enumerate(EQ_FREQUENCIES_HZ)]
        )


class UltimeaEqualizerBand(UltimeaEntity, NumberEntity):
    _attr_native_min_value = -6.0
    _attr_native_max_value = 6.0
    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER
    _attr_translation_key = "equalizer_band"

    def __init__(self, device, index: int, frequency: int) -> None:
        super().__init__(device)
        self._index = index
        self._frequency = frequency
        self._attr_unique_id = f"{device.identity.serial or device.address}_eq_{frequency}hz"
        self._attr_translation_placeholders = {"frequency": _frequency_label(frequency)}

    @property
    def available(self) -> bool:
        return super().available and self.device.state.raw_sound_mode == EQ_CUSTOM_PROFILE

    @property
    def native_value(self) -> float | None:
        gains = self.device.state.eq_band_gains_tenths_db
        if gains is None or self._index >= len(gains):
            return None
        return gains[self._index] / 10.0

    @property
    def extra_state_attributes(self) -> dict[str, int]:
        attrs = {"frequency_hz": self._frequency}
        if self.device.state.eq_profile_id is not None:
            attrs["eq_profile_id"] = self.device.state.eq_profile_id
        return attrs

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self.device.async_set_eq_band(self._index, round(float(value) * 10))
        except UltimeaError as err:
            raise HomeAssistantError(str(err)) from err
