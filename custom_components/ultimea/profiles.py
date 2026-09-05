"""APK-derived ULTIMEA model/protocol profiles."""

from __future__ import annotations

from dataclasses import dataclass

from .const import Feature, VERIFIED_MODEL, VERIFIED_MODEL_NUMBER

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
class UltimeaModelProfile:
    key: str
    verified: bool
    model_number: str | None = None
    apk_embedded: bool = False
    verified_features: frozenset[Feature] = frozenset()


D80_BOOM_PROFILE = UltimeaModelProfile(
    key="poseidon_d80_boom",
    verified=True,
    model_number=VERIFIED_MODEL_NUMBER,
    verified_features=VERIFIED_D80_FEATURES,
)
APK_COMMON_PROFILE = UltimeaModelProfile(key="apk_common", verified=False, apk_embedded=True)
GENERIC_COMMON_PROFILE = UltimeaModelProfile(key="generic_common", verified=False)


def profile_for_model(model: str | None) -> UltimeaModelProfile:
    if model == VERIFIED_MODEL:
        return D80_BOOM_PROFILE
    if model in APK_EMBEDDED_MODELS:
        return APK_COMMON_PROFILE
    return GENERIC_COMMON_PROFILE
