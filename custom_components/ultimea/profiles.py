"""APK-derived ULTIMEA model/protocol profiles.

The official Android APK contains two Bluetooth delegate families
(`LegacyDelegate` and `FrontierDelegate`) with a common high-level API, a
`getProtocolVersion`/`fetchAbilities` path, the 8D11/8D22 common transport, and
an additional 8D55/8D66 "custom common" transport.  Only the Poseidon D80 Boom
command values have been verified on hardware, so unknown models are capability
probed and are never rejected merely because their model name is new.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import Feature, VERIFIED_MODEL, VERIFIED_MODEL_NUMBER

# Model strings physically present in the APK snapshot we reverse engineered.
# Presence in the APK proves an app code path exists; it does NOT by itself mean
# this Home Assistant integration has been hardware-verified on that model.
APK_EMBEDDED_MODELS = frozenset(
    {
        "Apollo B60",
        "Apollo B70",
        "Nova S50",
        "Nova S70",
        "Nova S80",
        "Poseidon M70d",
        "Poseidon M80",
        "Poseidon M90V",
    }
)

# Capability/property names found in the APK.  We intentionally do not map
# positions in the raw fetchAbilities byte array until that byte order is proven
# by captures from more than one model.
APK_CAPABILITY_VOCABULARY = frozenset(
    {
        "hasARC",
        "hasAuraCast",
        "hasAuraCastChannelSetting",
        "hasAux",
        "hasBluetooth",
        "hasDisplayScreen",
        "hasDolbyAtmos",
        "hasHDMI",
        "hasHifiMode",
        "hasInfraredTransmission",
        "hasLed",
        "hasMultipleSurroundVolume",
        "hasSingleLed",
        "hasSignalInputSourceGet",
        "hasSurround",
        "hasSurroundVoiceCancelControl",
        "hasSurroundVoiceCancelStrength",
        "hasSurroundVolume",
        "hasThxEqMode",
        "hasToneControl",
        "hasTWS",
        "hasUSB",
        "hasVoiceCancelStrength",
        "hasVoiceEnhance",
        "hasXupMix",
        "isMediaControlSupported",
        "sceneSupported",
        "supportPowerOn",
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
    }
)


@dataclass(frozen=True, slots=True)
class UltimeaModelProfile:
    """How confidently a model is understood."""

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

APK_COMMON_PROFILE = UltimeaModelProfile(
    key="apk_common",
    verified=False,
    apk_embedded=True,
)

GENERIC_COMMON_PROFILE = UltimeaModelProfile(
    key="generic_common",
    verified=False,
)


def profile_for_model(model: str | None) -> UltimeaModelProfile:
    """Return the safest profile for a device-reported model."""
    if model == VERIFIED_MODEL:
        return D80_BOOM_PROFILE
    if model in APK_EMBEDDED_MODELS:
        return APK_COMMON_PROFILE
    return GENERIC_COMMON_PROFILE
