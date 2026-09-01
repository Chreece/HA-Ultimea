"""Data models for ULTIMEA."""

from __future__ import annotations

from dataclasses import dataclass

from .const import Brightness, PromptSound, ScreenTimeout, SoundMode, Source


@dataclass(slots=True)
class UltimeaIdentity:
    """Identity returned by the soundbar itself."""

    model: str | None = None
    serial: str | None = None
    firmware: str | None = None


@dataclass(slots=True)
class UltimeaState:
    """Last known D80 state."""

    power: bool | None = None
    raw_volume: int | None = None
    muted: bool | None = None
    source: Source | None = None
    sound_mode: SoundMode | None = None
    brightness: Brightness | None = None
    screen_on: bool | None = None
    screen_timeout: ScreenTimeout | None = None
    prompt_sound: PromptSound | None = None
    standby_minutes: int | None = None
