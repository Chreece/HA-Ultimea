"""Diagnostic sensors for decoded ULTIMEA capabilities."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UltimeaRuntimeData
from .const import ABILITY_FIELD_NAMES, ABILITY_INTEGER_FIELDS, Feature, SoundMode
from .entity import UltimeaEntity
from .eq_style import identify_style_preset
from .protocol import EQ_FREQUENCIES_HZ, EQ_STYLE_PROFILE


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    entities: list[SensorEntity] = [UltimeaCapabilitiesSensor(runtime.device)]
    if runtime.device.supports(Feature.STYLE):
        entities.extend(UltimeaStyleBand(runtime.device, i, hz) for i, hz in enumerate(EQ_FREQUENCIES_HZ))
    async_add_entities(entities)


class UltimeaCapabilitiesSensor(UltimeaEntity, SensorEntity):
    _attr_translation_key = "capabilities"
    _attr_icon = "mdi:list-status"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.identity.serial or device.address}_capabilities"

    @property
    def native_value(self) -> int:
        return len(self.device.capabilities.raw_ability_flags)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        raw = self.device.capabilities.raw_ability_flags
        attrs: dict[str, object] = {
            "raw_ability_flags": list(raw),
            "safe_features": sorted(x.value for x in self.device.capabilities.features),
        }
        for index, value in enumerate(raw):
            if index >= len(ABILITY_FIELD_NAMES):
                break
            name = ABILITY_FIELD_NAMES[index]
            attrs[name] = int(value) if name in ABILITY_INTEGER_FIELDS else bool(value)
        if self.device.identity.protocol_version is not None:
            attrs["protocol_version"] = self.device.identity.protocol_version
        if self.device.transport:
            attrs["ble_transport"] = self.device.transport
        return attrs


class UltimeaStyleBand(UltimeaEntity, SensorEntity):
    """One confirmed Style gain; unknown is never displayed as zero."""

    _attr_translation_key = "style_band"
    _attr_icon = "mdi:equalizer"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "dB"
    _attr_suggested_display_precision = 1

    def __init__(self, device, index: int, frequency: int) -> None:
        super().__init__(device)
        self._index = index
        self._frequency = frequency
        self._attr_unique_id = f"{device.identity.serial or device.address}_style_{frequency}hz"
        label = f"{frequency // 1000} kHz" if frequency >= 1000 else f"{frequency} Hz"
        self._attr_translation_placeholders = {"frequency": label}

    @property
    def available(self) -> bool:
        return (
            super().available
            and self.device.state.power is not False
            and self.device.state.sound_mode is SoundMode.STYLE
            and self.device.state.eq_profile_id == EQ_STYLE_PROFILE
            and self.device.state.eq_band_gains_tenths_db is not None
        )

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        gains = self.device.state.eq_band_gains_tenths_db
        return gains[self._index] / 10.0 if gains is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        attrs: dict[str, object] = {"frequency_hz": self._frequency, "eq_profile_id": EQ_STYLE_PROFILE}
        if self.available:
            gains = self.device.state.eq_band_gains_tenths_db
            if gains is not None:
                attrs["style_preset"] = identify_style_preset(gains) or "custom"
        return attrs
