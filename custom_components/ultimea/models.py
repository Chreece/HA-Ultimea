"""Data models for ULTIMEA."""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import Brightness, Feature, PromptSound, ScreenTimeout, SoundMode, Source


@dataclass(slots=True)
class UltimeaIdentity:
    model: str | None = None
    serial: str | None = None
    firmware: str | None = None
    protocol_version: int | None = None
    profile: str | None = None
    apk_embedded_model: bool = False


@dataclass(slots=True)
class UltimeaCapabilities:
    features: set[Feature] = field(default_factory=set)
    raw_ability_flags: tuple[int, ...] = ()
    standby_options: tuple[int, ...] = ()
    transport: str | None = None

    def supports(self, feature: Feature) -> bool:
        return feature in self.features


@dataclass(slots=True)
class UltimeaState:
    power: bool | None = None
    raw_volume: int | None = None
    muted: bool | None = None
    source: Source | None = None
    raw_source: int | None = None
    sound_mode: SoundMode | None = None
    raw_sound_mode: int | None = None
    brightness: Brightness | None = None
    screen_on: bool | None = None
    screen_timeout: ScreenTimeout | None = None
    prompt_sound: PromptSound | None = None
    standby_minutes: int | None = None
    xupmix_enabled: bool | None = None
    eq_profile_id: int | None = None
    eq_band_gains_tenths_db: tuple[int, ...] | None = None
