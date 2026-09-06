"""APK-derived ULTIMEA model/protocol profiles.

Semantic capabilities are intentionally separated from numeric wire IDs.
ULTIMEA reuses command numbers across protocol families, so a command that is
harmless on one profile can be destructive on another. Unknown/APK-common
models therefore remain read-only until their write mapping is explicitly
proven for that wire family.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from .const import (
    CMD_AUTO_STANDBY,
    CMD_BRIGHTNESS,
    CMD_MUTE,
    CMD_POWER,
    CMD_PROMPT_SOUND,
    CMD_SCREEN_TIMEOUT,
    CMD_SOUND_MODE,
    CMD_SOURCE,
    CMD_VOLUME,
    CMD_XUPMIX,
    GROUP_CONTROL,
    GROUP_INFO,
    INFO_AUTO_STANDBY,
    INFO_BRIGHTNESS,
    INFO_MUTE,
    INFO_POWER,
    INFO_PROMPT_SOUND,
    INFO_SCREEN_TIMEOUT,
    INFO_SOUND_MODE,
    INFO_SOURCE,
    INFO_VOLUME,
    INFO_XUPMIX,
    Feature,
    VERIFIED_MODEL,
    VERIFIED_MODEL_NUMBER,
)

APK_EMBEDDED_MODELS = frozenset(
    {
        "Apollo B60", "Apollo B70", "Nova S50", "Nova S70", "Nova S80",
        "Poseidon M70d", "Poseidon M80", "Poseidon M90V",
    }
)

APK_CAPABILITY_VOCABULARY = frozenset(
    {
        "hasARC", "hasAuraCast", "hasAuraCastChannelSetting", "hasAux",
        "hasBluetooth", "hasDisplayScreen", "hasDolbyAtmos", "hasHDMI",
        "hasHifiMode", "hasInfraredTransmission", "hasLed",
        "hasMultipleSurroundVolume", "hasSingleLed", "hasSignalInputSourceGet",
        "hasSurround", "hasSurroundVoiceCancelControl",
        "hasSurroundVoiceCancelStrength", "hasSurroundVolume", "hasThxEqMode",
        "hasToneControl", "hasTWS", "hasUSB", "hasVoiceCancelStrength",
        "hasVoiceEnhance", "hasXupMix", "isMediaControlSupported",
        "sceneSupported", "supportPowerOn",
    }
)

VERIFIED_D80_FEATURES = frozenset(
    {
        Feature.POWER,
        Feature.MUTE,
        Feature.VOLUME,
        Feature.SOURCE,
        Feature.SOUND_MODE,
        Feature.BRIGHTNESS,
        Feature.SCREEN_TIMEOUT,
        Feature.PROMPT_SOUND,
        Feature.AUTO_STANDBY,
        Feature.XUPMIX,
        Feature.EQUALIZER,
        Feature.STYLE,
    }
)


@dataclass(frozen=True, slots=True)
class WireCommand:
    """One profile-specific ULTIMEA command."""

    group: int
    command: int


@dataclass(frozen=True, slots=True)
class FeatureWireSpec:
    """Known read/write path for one semantic capability on one wire family."""

    read: WireCommand | None = None
    write: WireCommand | None = None


def _info(command: int) -> WireCommand:
    return WireCommand(GROUP_INFO, command)


def _control(command: int) -> WireCommand:
    return WireCommand(GROUP_CONTROL, command)


# Hardware-verified Poseidon D80 Boom mappings. In particular, 02:0F is NOT
# present here: on the D80 it is a destructive restore-defaults operation and
# must never be reachable through an ordinary Home Assistant feature write.
D80_WIRE_FEATURES: Mapping[Feature, FeatureWireSpec] = {
    Feature.POWER: FeatureWireSpec(_info(INFO_POWER), _control(CMD_POWER)),
    Feature.MUTE: FeatureWireSpec(_info(INFO_MUTE), _control(CMD_MUTE)),
    Feature.VOLUME: FeatureWireSpec(_info(INFO_VOLUME), _control(CMD_VOLUME)),
    Feature.SOURCE: FeatureWireSpec(_info(INFO_SOURCE), _control(CMD_SOURCE)),
    Feature.SOUND_MODE: FeatureWireSpec(
        _info(INFO_SOUND_MODE), _control(CMD_SOUND_MODE)
    ),
    Feature.BRIGHTNESS: FeatureWireSpec(
        _info(INFO_BRIGHTNESS), _control(CMD_BRIGHTNESS)
    ),
    Feature.SCREEN_TIMEOUT: FeatureWireSpec(
        _info(INFO_SCREEN_TIMEOUT), _control(CMD_SCREEN_TIMEOUT)
    ),
    Feature.PROMPT_SOUND: FeatureWireSpec(
        _info(INFO_PROMPT_SOUND), _control(CMD_PROMPT_SOUND)
    ),
    Feature.AUTO_STANDBY: FeatureWireSpec(
        _info(INFO_AUTO_STANDBY), _control(CMD_AUTO_STANDBY)
    ),
    Feature.XUPMIX: FeatureWireSpec(
        _info(INFO_XUPMIX), _control(CMD_XUPMIX)
    ),
    # Custom EQ and Style are special 02:04 profile transactions handled by
    # runtime.py, but the write command itself is hardware-proven on the D80.
    Feature.EQUALIZER: FeatureWireSpec(write=_control(CMD_SOUND_MODE)),
    Feature.STYLE: FeatureWireSpec(write=_control(CMD_SOUND_MODE)),
}

# Static Frontier-family evidence recovered from the official app. These are
# deliberately NOT assigned to any product model yet. Most importantly,
# Frontier 02:0F means single-LED brightness while D80 02:0F is destructive.
FRONTIER_STATIC_WIRE_FEATURES: Mapping[Feature, FeatureWireSpec] = {
    Feature.SINGLE_LED_SHUTDOWN_TIME: FeatureWireSpec(
        _info(0x16), _control(0x14)
    ),
    Feature.SINGLE_LED_BRIGHTNESS: FeatureWireSpec(
        _info(0x11), _control(0x0F)
    ),
    Feature.SINGLE_LED_POWER: FeatureWireSpec(
        _info(0x12), _control(0x10)
    ),
}


@dataclass(frozen=True, slots=True)
class UltimeaModelProfile:
    key: str
    verified: bool
    model_number: str | None = None
    apk_embedded: bool = False
    verified_features: frozenset[Feature] = frozenset()
    wire_features: Mapping[Feature, FeatureWireSpec] = field(default_factory=dict)

    def wire_spec(self, feature: Feature) -> FeatureWireSpec | None:
        """Return an explicitly proven wire mapping, never a numeric guess."""
        return self.wire_features.get(feature)


D80_BOOM_PROFILE = UltimeaModelProfile(
    key="poseidon_d80_boom",
    verified=True,
    model_number=VERIFIED_MODEL_NUMBER,
    verified_features=VERIFIED_D80_FEATURES,
    wire_features=D80_WIRE_FEATURES,
)
APK_COMMON_PROFILE = UltimeaModelProfile(
    key="apk_common", verified=False, apk_embedded=True
)
GENERIC_COMMON_PROFILE = UltimeaModelProfile(key="generic_common", verified=False)


def profile_for_model(model: str | None) -> UltimeaModelProfile:
    if model == VERIFIED_MODEL:
        return D80_BOOM_PROFILE
    if model in APK_EMBEDDED_MODELS:
        return APK_COMMON_PROFILE
    return GENERIC_COMMON_PROFILE


def can_write_feature(
    model: str | None,
    feature: Feature,
    supported_features: Iterable[Feature],
) -> bool:
    """Return whether this exact model has a proven setter for a supported feature."""
    if feature not in supported_features:
        return False
    spec = profile_for_model(model).wire_spec(feature)
    return spec is not None and spec.write is not None


def writable_features_for_model(
    model: str | None,
    supported_features: Iterable[Feature],
) -> frozenset[Feature]:
    """Return supported capabilities that also have an explicit safe setter."""
    features = frozenset(supported_features)
    return frozenset(
        feature
        for feature in features
        if can_write_feature(model, feature, features)
    )
