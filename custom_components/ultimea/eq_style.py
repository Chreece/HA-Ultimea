"""Captured D80 Style curves; no inferred XY interpolation or neutral fallback."""

from __future__ import annotations

from types import MappingProxyType

from .protocol import (
    EQ_CUSTOM_PROFILE,
    EQ_FREQUENCIES_HZ,
    EQ_GAIN_MAX_TENTHS_DB,
    EQ_GAIN_MIN_TENTHS_DB,
    EQ_STYLE_PROFILE,
    UltimeaEqualizerPayload,
    build_equalizer_payload,
    parse_equalizer_payload,
)

# d80-postaction-decoded-20260905-110322.json: explicitly labelled corner
# actions, each with an identical 02:04 device echo. Units are 0.1 dB.
# These are the captured corner curves, NOT a reconstructed continuous XY pad.
STYLE_PRESETS = MappingProxyType({
    "bass": (55, 50, 25, 0, 0, -35, -50, -50, 0, 0),
    "rock": (50, 35, -30, 50, -20, 15, 35, 40, 45, 45),
    "pop": (40, 35, 20, 0, -20, 0, 25, 35, 35, 40),
    "classical": (0, 0, 0, 35, 35, 35, 0, -20, -25, -25),
    "flat": (0,) * 10,
})


def build_style_payload(preset: str) -> bytes:
    """Build exactly one recorded Style curve; reject unknown names."""
    try:
        gains = STYLE_PRESETS[preset]
    except KeyError as err:
        raise ValueError(f"Unknown ULTIMEA Style preset: {preset}") from err
    return build_equalizer_payload(gains, profile=EQ_STYLE_PROFILE)


def identify_style_preset(gains: tuple[int, ...]) -> str | None:
    """Name exact captured curves only; never guess from a nearest curve."""
    return next((name for name, curve in STYLE_PRESETS.items() if gains == curve), None)


def parse_d80_profile(data: bytes) -> UltimeaEqualizerPayload | None:
    """Validate the complete known D80 custom profile before exposing its state."""
    eq = parse_equalizer_payload(data)
    if (
        eq is None
        or eq.profile not in (EQ_CUSTOM_PROFILE, EQ_STYLE_PROFILE)
        or eq.frequencies_hz != EQ_FREQUENCIES_HZ
        or any(not EQ_GAIN_MIN_TENTHS_DB <= gain <= EQ_GAIN_MAX_TENTHS_DB
               for gain in eq.gains_tenths_db)
    ):
        return None
    return eq
