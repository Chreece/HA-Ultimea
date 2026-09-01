"""Configuration select entities for ULTIMEA."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Awaitable, Callable

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UltimeaRuntimeData
from .const import (
    Brightness,
    PromptSound,
    ScreenTimeout,
    Standby,
    STANDBY_TO_MINUTES,
    MINUTES_TO_STANDBY,
)
from .device import UltimeaDevice, UltimeaError
from .entity import UltimeaEntity


@dataclass(frozen=True, kw_only=True)
class UltimeaSelectDescription(SelectEntityDescription):
    """Description of a D80 select entity."""

    getter: Callable[[UltimeaDevice], str | None]
    setter: Callable[[UltimeaDevice, str], Awaitable[None]]


async def _set_brightness(device: UltimeaDevice, value: str) -> None:
    await device.async_set_brightness(Brightness(value))


async def _set_screen_timeout(device: UltimeaDevice, value: str) -> None:
    await device.async_set_screen_timeout(ScreenTimeout(value))


async def _set_prompt_sound(device: UltimeaDevice, value: str) -> None:
    await device.async_set_prompt_sound(PromptSound(value))


async def _set_standby(device: UltimeaDevice, value: str) -> None:
    await device.async_set_standby_minutes(STANDBY_TO_MINUTES[Standby(value)])


SELECTS = (
    UltimeaSelectDescription(
        key="display_brightness",
        translation_key="display_brightness",
        entity_category=EntityCategory.CONFIG,
        options=[item.value for item in Brightness],
        getter=lambda d: d.state.brightness.value if d.state.brightness else None,
        setter=_set_brightness,
    ),
    UltimeaSelectDescription(
        key="screen_timeout",
        translation_key="screen_timeout",
        entity_category=EntityCategory.CONFIG,
        options=[item.value for item in ScreenTimeout],
        getter=lambda d: d.state.screen_timeout.value if d.state.screen_timeout else None,
        setter=_set_screen_timeout,
    ),
    UltimeaSelectDescription(
        key="prompt_sound",
        translation_key="prompt_sound",
        entity_category=EntityCategory.CONFIG,
        options=[item.value for item in PromptSound],
        getter=lambda d: d.state.prompt_sound.value if d.state.prompt_sound else None,
        setter=_set_prompt_sound,
    ),
    UltimeaSelectDescription(
        key="auto_standby",
        translation_key="auto_standby",
        entity_category=EntityCategory.CONFIG,
        options=[item.value for item in Standby],
        getter=lambda d: (
            standby.value
            if (standby := MINUTES_TO_STANDBY.get(d.state.standby_minutes)) is not None
            else None
        ),
        setter=_set_standby,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    async_add_entities(
        [UltimeaSelect(runtime.device, description) for description in SELECTS]
    )


class UltimeaSelect(UltimeaEntity, SelectEntity):
    """One D80 configuration select."""

    entity_description: UltimeaSelectDescription

    def __init__(self, device: UltimeaDevice, description: UltimeaSelectDescription) -> None:
        super().__init__(device)
        self.entity_description = description
        self._attr_unique_id = (
            f"{device.identity.serial or device.address}_{description.key}"
        )

    @property
    def current_option(self) -> str | None:
        return self.entity_description.getter(self.device)

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            raise HomeAssistantError(f"Unsupported option: {option}")
        try:
            await self.entity_description.setter(self.device, option)
        except UltimeaError as err:
            raise HomeAssistantError(str(err)) from err
