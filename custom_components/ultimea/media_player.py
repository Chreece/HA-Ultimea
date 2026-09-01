"""Media player platform for ULTIMEA Poseidon D80 Boom."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UltimeaRuntimeData
from .const import (
    CONF_VOLUME_MAX,
    DEFAULT_VOLUME_MAX,
    SoundMode,
    Source,
)
from .device import UltimeaError
from .entity import UltimeaEntity

SOURCE_NAMES = {
    Source.EARC: "eARC",
    Source.HDMI: "HDMI",
    Source.OPTICAL: "Optical",
    Source.AUX: "AUX",
    Source.BLUETOOTH: "Bluetooth",
    Source.USB: "USB",
}
NAME_TO_SOURCE = {value: key for key, value in SOURCE_NAMES.items()}

SOUND_MODE_NAMES = {
    SoundMode.MOVIE: "Movie",
    SoundMode.MUSIC: "Music",
    SoundMode.VOICE: "Voice",
    SoundMode.SPORT: "Sport",
    SoundMode.NIGHT: "Night",
    SoundMode.GAME: "Game",
}
NAME_TO_SOUND_MODE = {value: key for key, value in SOUND_MODE_NAMES.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    async_add_entities([UltimeaMediaPlayer(runtime.device, runtime.volume_max)])


class UltimeaMediaPlayer(UltimeaEntity, MediaPlayerEntity):
    """Poseidon D80 Boom media player."""

    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_source_list = list(NAME_TO_SOURCE)
    _attr_sound_mode_list = list(NAME_TO_SOUND_MODE)

    def __init__(self, device, volume_max: int) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.identity.serial or device.address}_media_player"
        self._volume_max = max(1, volume_max)

    @property
    def state(self) -> MediaPlayerState | None:
        if self.device.state.power is False:
            return MediaPlayerState.OFF
        if self.device.state.power is True:
            return MediaPlayerState.ON
        return None

    @property
    def volume_level(self) -> float | None:
        raw = self.device.state.raw_volume
        if raw is None:
            return None
        return max(0.0, min(1.0, raw / self._volume_max))

    @property
    def is_volume_muted(self) -> bool | None:
        return self.device.state.muted

    @property
    def source(self) -> str | None:
        source = self.device.state.source
        return SOURCE_NAMES.get(source) if source is not None else None

    @property
    def sound_mode(self) -> str | None:
        mode = self.device.state.sound_mode
        return SOUND_MODE_NAMES.get(mode) if mode is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, int] | None:
        raw = self.device.state.raw_volume
        return {"raw_volume": raw} if raw is not None else None

    async def _run(self, coro) -> None:
        try:
            await coro
        except UltimeaError as err:
            raise HomeAssistantError(str(err)) from err

    async def async_turn_on(self) -> None:
        await self._run(self.device.async_set_power(True))

    async def async_turn_off(self) -> None:
        await self._run(self.device.async_set_power(False))

    async def async_set_volume_level(self, volume: float) -> None:
        raw = round(max(0.0, min(1.0, volume)) * self._volume_max)
        await self._run(self.device.async_set_volume(raw))

    async def async_volume_up(self) -> None:
        raw = self.device.state.raw_volume
        if raw is None:
            raw = await self.device.async_refresh_volume()
        if raw is None:
            raise HomeAssistantError("Unable to read the current D80 volume")
        await self._run(self.device.async_set_volume(min(self._volume_max, raw + 1)))

    async def async_volume_down(self) -> None:
        raw = self.device.state.raw_volume
        if raw is None:
            raw = await self.device.async_refresh_volume()
        if raw is None:
            raise HomeAssistantError("Unable to read the current D80 volume")
        await self._run(self.device.async_set_volume(max(0, raw - 1)))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._run(self.device.async_set_mute(mute))

    async def async_select_source(self, source: str) -> None:
        try:
            target = NAME_TO_SOURCE[source]
        except KeyError as err:
            raise HomeAssistantError(f"Unsupported D80 source: {source}") from err
        await self._run(self.device.async_set_source(target))

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        try:
            target = NAME_TO_SOUND_MODE[sound_mode]
        except KeyError as err:
            raise HomeAssistantError(f"Unsupported D80 sound mode: {sound_mode}") from err
        await self._run(self.device.async_set_sound_mode(target))
