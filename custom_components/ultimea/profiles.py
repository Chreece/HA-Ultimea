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
    INFO_VALUE_TO_SOURCE,
    SOURCE_TO_VALUE,
    VALUE_TO_SOURCE,
    Feature,
    Source,
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

POSEIDON_D70_MODEL = "Poseidon D70"
AURA_A40_MODEL = "Aura A40"

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

VERIFIED_D70_FEATURES = frozenset(
    {
        Feature.VOLUME,
        Feature.SOURCE,
        Feature.MUTE,
        Feature.POWER,
    }
)

DEFAULT_SOURCE_NAMES: Mapping[Source, str] = {
    Source.EARC: "eARC",
    Source.HDMI: "HDMI",
    Source.OPTICAL: "Optical",
    Source.AUX: "AUX",
    Source.BLUETOOTH: "Bluetooth",
    Source.USB: "USB",
}

# D70-specific CONTROL source enum, captured by the reporter in issue #4.
# The follow-up confirms BT=02 and USB=04; ARC remains 00, not D80's 10.
D70_SOURCE_CONTROL_VALUES: Mapping[Source, int] = {
    Source.EARC: 0x00,
    Source.OPTICAL: 0x01,
    Source.BLUETOOTH: 0x02,
    Source.AUX: 0x03,
    Source.USB: 0x04,
}
D70_SOURCE_NAMES: Mapping[Source, str] = {
    Source.EARC: "ARC",
    Source.OPTICAL: "Optical",
    Source.AUX: "AUX",
}

# The PCAP confirms INFO source 00=ARC and that D70 has no HDMI.
# Remaining labels follow the app's common INFO enum for the supported
# input family; no HDMI value is accepted by this model.
D70_INFO_SOURCE_VALUES: Mapping[int, Source] = {
    0x00: Source.EARC,
    0x01: Source.OPTICAL,
    0x02: Source.BLUETOOTH,
    0x03: Source.AUX,
    0x04: Source.USB,
}

# Aura A40 V56: INFO source 01 = Optical was observed in issue #5.
# Other values follow the app-derived common INFO enum; their physical inputs
# are corroborated by the A40 ability flags and manufacturer documentation.
# No A40 CONTROL/SET command has been captured.
A40_INFO_SOURCE_VALUES: Mapping[int, Source] = {
    0x01: Source.OPTICAL,
    0x02: Source.BLUETOOTH,
    0x03: Source.AUX,
    0x04: Source.USB,
}


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
# Reporter-confirmed Poseidon D70 writes from issue #4. The submitted
# packet archive could not be independently downloaded; do not infer other
# controls or INFO read mappings from the write samples.
D70_WIRE_FEATURES: Mapping[Feature, FeatureWireSpec] = {
    Feature.VOLUME: FeatureWireSpec(write=_control(CMD_VOLUME)),
    Feature.SOURCE: FeatureWireSpec(write=_control(CMD_SOURCE)),
    Feature.MUTE: FeatureWireSpec(write=_control(CMD_MUTE)),
    Feature.POWER: FeatureWireSpec(write=_control(CMD_POWER)),
}

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
    source_control_values: Mapping[Source, int] = field(default_factory=dict)
    source_info_values: Mapping[int, Source] = field(default_factory=dict)
    source_names: Mapping[Source, str] = field(default_factory=dict)
    power_on_supported: bool = True
    # Preserve D80's legacy disconnect fallback. D70's captured ACK is
    # authoritative and must not be replaced by a guessed OFF state.
    power_off_disconnect_fallback: bool = True

    def wire_spec(self, feature: Feature) -> FeatureWireSpec | None:
        """Return an explicitly proven wire mapping, never a numeric guess."""
        return self.wire_features.get(feature)

    def encode_source(self, source: Source) -> int | None:
        """Return this profile's proven CONTROL source value."""
        return self.source_control_values.get(source)

    def decode_control_source(self, value: int) -> Source | None:
        """Decode one profile-specific CONTROL source value."""
        return next(
            (
                source
                for source, wire_value in self.source_control_values.items()
                if wire_value == value
            ),
            None,
        )

    def decode_info_source(self, value: int) -> Source | None:
        """Decode one profile-specific INFO source value."""
        return self.source_info_values.get(value)

    def source_name(self, source: Source) -> str:
        """Return the Home Assistant label for one semantic source."""
        return self.source_names.get(source, DEFAULT_SOURCE_NAMES[source])

    def source_options(self) -> tuple[str, ...]:
        """Return writable source labels in stable semantic order."""
        return tuple(
            self.source_name(source)
            for source in DEFAULT_SOURCE_NAMES
            if source in self.source_control_values
        )

    def source_for_name(self, name: str) -> Source | None:
        """Resolve a Home Assistant source label accepted by this profile."""
        return next(
            (
                source
                for source in self.source_control_values
                if self.source_name(source) == name
            ),
            None,
        )


D80_BOOM_PROFILE = UltimeaModelProfile(
    key="poseidon_d80_boom",
    verified=True,
    model_number=VERIFIED_MODEL_NUMBER,
    verified_features=VERIFIED_D80_FEATURES,
    wire_features=D80_WIRE_FEATURES,
    source_control_values=SOURCE_TO_VALUE,
    source_info_values=INFO_VALUE_TO_SOURCE,
    source_names=DEFAULT_SOURCE_NAMES,
)
D70_PROFILE = UltimeaModelProfile(
    key="poseidon_d70",
    verified=True,
    verified_features=VERIFIED_D70_FEATURES,
    wire_features=D70_WIRE_FEATURES,
    source_control_values=D70_SOURCE_CONTROL_VALUES,
    # INFO 01:06 = 00 (ARC) is confirmed in the actual PCAP.
    source_info_values=D70_INFO_SOURCE_VALUES,
    source_names=D70_SOURCE_NAMES,
    # The soundbar cannot receive Bluetooth power-on after shutdown.
    power_on_supported=False,
    # Actual PCAP packet 249 acknowledges 02:09:00, so any missing ACK,
    # rejected GATT write or premature disconnect must remain an error.
    power_off_disconnect_fallback=False,
)
APK_COMMON_PROFILE = UltimeaModelProfile(
    key="apk_common", verified=False, apk_embedded=True
)
A40_PROFILE = UltimeaModelProfile(
    key="aura_a40",
    verified=False,
    # Explicit INFO read mapping only. No feature is proven writable on A40.
    source_info_values=A40_INFO_SOURCE_VALUES,
)
GENERIC_COMMON_PROFILE = UltimeaModelProfile(key="generic_common", verified=False)


def profile_for_model(model: str | None) -> UltimeaModelProfile:
    normalized = (model or "").strip().casefold()
    if normalized == VERIFIED_MODEL.casefold():
        return D80_BOOM_PROFILE
    if normalized == POSEIDON_D70_MODEL.casefold():
        return D70_PROFILE
    if normalized == AURA_A40_MODEL.casefold():
        return A40_PROFILE
    if model in APK_EMBEDDED_MODELS:
        return APK_COMMON_PROFILE
    return GENERIC_COMMON_PROFILE


def decode_source_value(
    model: str | None,
    value: int,
    *,
    info: bool,
) -> Source | None:
    """Decode source values without mixing CONTROL and INFO enums."""
    profile = profile_for_model(model)
    if info:
        # Explicit model read enums override generic mappings. In particular,
        # never mislabel unsupported HDMI/ARC values on the Aura A40.
        if profile.source_info_values:
            return profile.decode_info_source(value)
        return INFO_VALUE_TO_SOURCE.get(value)
    return profile.decode_control_source(value) or VALUE_TO_SOURCE.get(value)


def source_value_for_model(model: str | None, source: Source) -> int | None:
    """Return a proven CONTROL source value for this exact model."""
    return profile_for_model(model).encode_source(source)


def source_name_for_model(model: str | None, source: Source) -> str:
    """Return the model-appropriate Home Assistant source label."""
    return profile_for_model(model).source_name(source)


def source_options_for_model(model: str | None) -> tuple[str, ...]:
    """Return source labels that have proven setters on this model."""
    return profile_for_model(model).source_options()


def source_for_name_for_model(model: str | None, name: str) -> Source | None:
    """Resolve a source label through the exact model profile."""
    return profile_for_model(model).source_for_name(name)


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


def can_turn_on(
    model: str | None,
    supported_features: Iterable[Feature],
) -> bool:
    """Allow power-on only when the soundbar stays BLE reachable while off."""
    return (
        profile_for_model(model).power_on_supported
        and can_write_feature(model, Feature.POWER, supported_features)
    )


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
