"""Media player platform for ULTIMEA soundbars."""

from __future__ import annotations

from urllib.parse import quote

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
from .const import Feature, SoundMode, Source
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
    SoundMode.CUSTOM: "Custom EQ",
}
NAME_TO_SOUND_MODE = {value: key for key, value in SOUND_MODE_NAMES.items()}

SOURCE_ICONS = {
    Source.EARC: "mdi:television-speaker",
    Source.HDMI: "mdi:hdmi-port",
    Source.OPTICAL: "mdi:toslink",
    Source.AUX: "mdi:audio-input-stereo-minijack",
    Source.BLUETOOTH: "mdi:bluetooth-audio",
    Source.USB: "mdi:usb-port",
}
SOURCE_BADGES = {
    Source.EARC: "ARC",
    Source.HDMI: "HDMI",
    Source.OPTICAL: "OPT",
    Source.AUX: "AUX",
    Source.BLUETOOTH: "BT",
    Source.USB: "USB",
}
EQ_BADGES = {
    SoundMode.MOVIE: "MOV",
    SoundMode.MUSIC: "MUS",
    SoundMode.VOICE: "VOX",
    SoundMode.SPORT: "SPT",
    SoundMode.NIGHT: "NGT",
    SoundMode.GAME: "GAME",
    SoundMode.CUSTOM: "EQ",
}
EQ_ACCENTS = {
    SoundMode.MOVIE: "#ec407a",
    SoundMode.MUSIC: "#7e57c2",
    SoundMode.VOICE: "#26c6da",
    SoundMode.SPORT: "#66bb6a",
    SoundMode.NIGHT: "#5c6bc0",
    SoundMode.GAME: "#ffa726",
    SoundMode.CUSTOM: "#00acc1",
}


def _dynamic_media_picture(
    source: Source | None,
    sound_mode: SoundMode | None,
    raw_sound_mode: int | None,
) -> str:
    """Build a compact local SVG showing input and EQ mode together."""
    source_badge = SOURCE_BADGES.get(source, "IN")
    if raw_sound_mode == 0x08 and sound_mode is None:
        eq_badge = "STY"
        accent = "#ab47bc"
    else:
        eq_badge = EQ_BADGES.get(sound_mode, "EQ")
        accent = EQ_ACCENTS.get(sound_mode, "#42a5f5")

    svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'>
  <rect width='96' height='96' rx='22' fill='#151a23'/>
  <rect x='8' y='8' width='42' height='22' rx='9' fill='#263241'/>
  <text x='29' y='23' text-anchor='middle' font-family='Arial,sans-serif' font-size='11' font-weight='700' fill='#ffffff'>{source_badge}</text>
  <rect x='49' y='66' width='39' height='22' rx='9' fill='{accent}'/>
  <text x='68.5' y='81' text-anchor='middle' font-family='Arial,sans-serif' font-size='10' font-weight='700' fill='#ffffff'>{eq_badge}</text>
  <path d='M22 43h12l14-12v34L34 53H22z' fill='#ffffff'/>
  <path d='M57 40c5 4 5 12 0 16' fill='none' stroke='{accent}' stroke-width='5' stroke-linecap='round'/>
  <path d='M65 33c10 10 10 20 0 30' fill='none' stroke='{accent}' stroke-width='5' stroke-linecap='round'/>
</svg>""".strip()
    return "data:image/svg+xml," + quote(svg, safe="")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    runtime: UltimeaRuntimeData = entry.runtime_data
    async_add_entities([UltimeaMediaPlayer(runtime.device, runtime.volume_max)])


class UltimeaMediaPlayer(UltimeaEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _unrecorded_attributes = frozenset({"entity_picture"})

    def __init__(self, device, volume_max: int) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.identity.serial or device.address}_media_player"
        self._volume_max = max(1, volume_max)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        features = MediaPlayerEntityFeature(0)
        if self.device.supports(Feature.POWER):
            features |= MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
        if self.device.supports(Feature.VOLUME):
            features |= MediaPlayerEntityFeature.VOLUME_SET | MediaPlayerEntityFeature.VOLUME_STEP
        if self.device.supports(Feature.MUTE):
            features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self.device.supports(Feature.SOURCE):
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self.device.supports(Feature.SOUND_MODE):
            features |= MediaPlayerEntityFeature.SELECT_SOUND_MODE
        return features

    @property
    def source_list(self) -> list[str] | None:
        return list(NAME_TO_SOURCE) if self.device.supports(Feature.SOURCE) else None

    @property
    def sound_mode_list(self) -> list[str] | None:
        if not self.device.supports(Feature.SOUND_MODE):
            return None
        names = [
            name
            for mode, name in SOUND_MODE_NAMES.items()
            if mode is not SoundMode.CUSTOM
        ]
        if self.device.supports(Feature.EQUALIZER):
            names.append(SOUND_MODE_NAMES[SoundMode.CUSTOM])
        return names

    @property
    def state(self) -> MediaPlayerState | None:
        if self.device.state.power is False:
            return MediaPlayerState.OFF
        if self.device.state.power is True:
            return MediaPlayerState.ON
        return None

    @property
    def icon(self) -> str:
        """Provide a source-aware MDI fallback for cards without entity pictures."""
        if self.device.state.power is False:
            return "mdi:speaker-off"
        return SOURCE_ICONS.get(self.device.state.source, "mdi:speaker")

    @property
    def entity_picture(self) -> str | None:
        """Show current input and EQ mode in one dynamically generated icon."""
        if self.device.state.power is False:
            return None
        return _dynamic_media_picture(
            self.device.state.source,
            self.device.state.sound_mode,
            self.device.state.raw_sound_mode,
        )

    @property
    def volume_level(self) -> float | None:
        raw = self.device.state.raw_volume
        return None if raw is None else max(0.0, min(1.0, raw / self._volume_max))

    @property
    def is_volume_muted(self) -> bool | None:
        return self.device.state.muted

    @property
    def source(self) -> str | None:
        return SOURCE_NAMES.get(self.device.state.source)

    @property
    def sound_mode(self) -> str | None:
        return SOUND_MODE_NAMES.get(self.device.state.sound_mode)

    @property
    def extra_state_attributes(self) -> dict[str, int | str | bool] | None:
        attrs: dict[str, int | str | bool] = {}
        for key, value in (
            ("raw_volume", self.device.state.raw_volume),
            ("raw_source", self.device.state.raw_source),
            ("raw_sound_mode", self.device.state.raw_sound_mode),
            ("protocol_version", self.device.identity.protocol_version),
            ("eq_profile_id", self.device.state.eq_profile_id),
        ):
            if value is not None:
                attrs[key] = value
        if self.device.transport:
            attrs["ble_transport"] = self.device.transport
        if self.device.identity.profile:
            attrs["protocol_profile"] = self.device.identity.profile
        return attrs or None

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
        await self._run(
            self.device.async_set_volume(
                round(max(0.0, min(1.0, volume)) * self._volume_max)
            )
        )

    async def async_volume_up(self) -> None:
        raw = self.device.state.raw_volume
        if raw is None:
            raw = await self.device.async_refresh_volume()
        if raw is None:
            raise HomeAssistantError("Unable to read the current ULTIMEA volume")
        await self._run(self.device.async_set_volume(min(self._volume_max, raw + 1)))

    async def async_volume_down(self) -> None:
        raw = self.device.state.raw_volume
        if raw is None:
            raw = await self.device.async_refresh_volume()
        if raw is None:
            raise HomeAssistantError("Unable to read the current ULTIMEA volume")
        await self._run(self.device.async_set_volume(max(0, raw - 1)))

    async def async_mute_volume(self, mute: bool) -> None:
        await self._run(self.device.async_set_mute(mute))

    async def async_select_source(self, source: str) -> None:
        try:
            target = NAME_TO_SOURCE[source]
        except KeyError as err:
            raise HomeAssistantError(f"Unsupported ULTIMEA source: {source}") from err
        await self._run(self.device.async_set_source(target))

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        try:
            target = NAME_TO_SOUND_MODE[sound_mode]
        except KeyError as err:
            raise HomeAssistantError(f"Unsupported ULTIMEA sound mode: {sound_mode}") from err
        await self._run(self.device.async_set_sound_mode(target))
