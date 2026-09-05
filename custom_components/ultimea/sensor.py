"""Diagnostic sensors for decoded ULTIMEA capabilities."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UltimeaRuntimeData
from .const import ABILITY_FIELD_NAMES, ABILITY_INTEGER_FIELDS
from .entity import UltimeaEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    async_add_entities([UltimeaCapabilitiesSensor(runtime.device)])


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
