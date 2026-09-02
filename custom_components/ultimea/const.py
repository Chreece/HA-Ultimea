"""Constants for the ULTIMEA integration."""

from __future__ import annotations

from enum import StrEnum

DOMAIN = "ultimea"
MANUFACTURER = "ULTIMEA"
VERIFIED_MODEL = "Poseidon D80 Boom"
DEFAULT_DISCOVERY_NAME = "ULTIMEA soundbar"
VERIFIED_MODEL_NUMBER = "U2623"

ULTIMEA_MANUFACTURER_ID = 0x0D8C
DISCOVERY_SERVICE_UUID = "0000260a-0000-1000-8000-00805f9b34fb"
COMMON_SERVICE_UUID = "27758daa-bf3a-4ac6-bee5-6259ccb7c9b7"
WRITE_UUID = "27758d11-bf3a-4ac6-bee5-6259ccb7c9b7"
NOTIFY_UUID = "27758d22-bf3a-4ac6-bee5-6259ccb7c9b7"
# The official APK contains a second "custom common" characteristic pair.
CUSTOM_WRITE_UUID = "27758d55-bf3a-4ac6-bee5-6259ccb7c9b7"
CUSTOM_NOTIFY_UUID = "27758d66-bf3a-4ac6-bee5-6259ccb7c9b7"
OTA_SERVICE_UUID = "27758dff-bf3a-4ac6-bee5-6259ccb7c9b7"
OTA_WRITE_UUID = "27758d33-bf3a-4ac6-bee5-6259ccb7c9b7"
OTA_NOTIFY_UUID = "27758d44-bf3a-4ac6-bee5-6259ccb7c9b7"

TRANSPORT_COMMON = "common_8d11_8d22"
TRANSPORT_CUSTOM = "custom_8d55_8d66"
TRANSPORT_UUIDS = {
    TRANSPORT_COMMON: (WRITE_UUID, NOTIFY_UUID),
    TRANSPORT_CUSTOM: (CUSTOM_WRITE_UUID, CUSTOM_NOTIFY_UUID),
}

CONF_MODEL = "model"
CONF_SERIAL = "serial"
CONF_FIRMWARE = "firmware"
CONF_PROTOCOL_VERSION = "protocol_version"
CONF_PROFILE = "profile"
CONF_CAPABILITIES = "capabilities"
CONF_ABILITY_FLAGS = "ability_flags"
CONF_STANDBY_OPTIONS = "standby_options"
CONF_TRANSPORT = "transport"
CONF_KEEP_CONNECTED = "keep_connected"
CONF_DISCONNECT_DELAY = "disconnect_delay"
CONF_VOLUME_MAX = "volume_max"
CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"

DEFAULT_KEEP_CONNECTED = True
DEFAULT_DISCONNECT_DELAY = 15
DEFAULT_VOLUME_MAX = 100
DEFAULT_HEARTBEAT_INTERVAL = 30

# Frame groups observed in the official app traffic.
GROUP_CAPABILITIES = 0x00
GROUP_INFO = 0x01
GROUP_CONTROL = 0x02

# The app has both LegacyDelegate.fetchAbilities and FrontierDelegate.fetchAbilities.
CAP_FETCH_ABILITIES = 0x00

# Safe read/query commands observed in the official ULTIMEA app.
INFO_PROTOCOL = 0x01
INFO_MODEL = 0x02
INFO_SERIAL = 0x04
INFO_FIRMWARE = 0x05
INFO_MUTE = 0x06
INFO_VOLUME = 0x07
INFO_SOURCE = 0x08
INFO_PROMPT_SOUND = 0x0A
INFO_BRIGHTNESS = 0x0C
INFO_POWER = 0x0D
INFO_SOUND_MODE = 0x0E
INFO_SCREEN_TIMEOUT = 0x0F
INFO_AUTO_STANDBY = 0x17

CMD_SOURCE = 0x02
CMD_VOLUME = 0x03
CMD_SOUND_MODE = 0x04
CMD_PROMPT_SOUND = 0x06
CMD_SCREEN_TIMEOUT = 0x08
CMD_POWER = 0x09
CMD_MUTE = 0x0A
CMD_BRIGHTNESS = 0x0C
CMD_AUTO_STANDBY = 0x15


class Feature(StrEnum):
    """Operational features whose safe read path has been confirmed."""

    POWER = "power"
    MUTE = "mute"
    VOLUME = "volume"
    SOURCE = "source"
    SOUND_MODE = "sound_mode"
    BRIGHTNESS = "brightness"
    SCREEN_TIMEOUT = "screen_timeout"
    PROMPT_SOUND = "prompt_sound"
    AUTO_STANDBY = "auto_standby"


class Source(StrEnum):
    """Input-source values shared by the app protocol we have decoded."""

    OPTICAL = "optical"
    BLUETOOTH = "bluetooth"
    AUX = "aux"
    USB = "usb"
    HDMI = "hdmi"
    EARC = "earc"


SOURCE_TO_VALUE: dict[Source, int] = {
    Source.OPTICAL: 0x01,
    Source.BLUETOOTH: 0x02,
    Source.AUX: 0x03,
    Source.USB: 0x04,
    Source.HDMI: 0x05,
    Source.EARC: 0x10,
}
VALUE_TO_SOURCE = {value: key for key, value in SOURCE_TO_VALUE.items()}


class SoundMode(StrEnum):
    """Standard EQ/sound modes present in the ULTIMEA app."""

    MOVIE = "movie"
    MUSIC = "music"
    VOICE = "voice"
    SPORT = "sport"
    NIGHT = "night"
    GAME = "game"


SOUND_MODE_TO_VALUE: dict[SoundMode, int] = {
    SoundMode.MOVIE: 0x01,
    SoundMode.MUSIC: 0x02,
    SoundMode.VOICE: 0x03,
    SoundMode.SPORT: 0x04,
    SoundMode.NIGHT: 0x05,
    SoundMode.GAME: 0x06,
}
VALUE_TO_SOUND_MODE = {value: key for key, value in SOUND_MODE_TO_VALUE.items()}


class Brightness(StrEnum):
    """Configured front-display brightness."""

    DIM = "dim"
    LOW = "low"
    MEDIUM = "medium"
    NORMAL = "normal"
    HIGH = "high"


BRIGHTNESS_TO_VALUE: dict[Brightness, int] = {
    Brightness.DIM: 0x01,
    Brightness.LOW: 0x02,
    Brightness.MEDIUM: 0x03,
    Brightness.NORMAL: 0x04,
    Brightness.HIGH: 0x05,
}
VALUE_TO_BRIGHTNESS = {value: key for key, value in BRIGHTNESS_TO_VALUE.items()}


class ScreenTimeout(StrEnum):
    """Automatic front-display timeout."""

    NEVER = "never"
    SECONDS_5 = "5_seconds"
    SECONDS_30 = "30_seconds"
    SECONDS_60 = "60_seconds"


SCREEN_TIMEOUT_TO_VALUE: dict[ScreenTimeout, int] = {
    ScreenTimeout.NEVER: 0x00,
    ScreenTimeout.SECONDS_5: 0x01,
    ScreenTimeout.SECONDS_30: 0x02,
    ScreenTimeout.SECONDS_60: 0x03,
}
VALUE_TO_SCREEN_TIMEOUT = {value: key for key, value in SCREEN_TIMEOUT_TO_VALUE.items()}


class PromptSound(StrEnum):
    """Prompt sound level."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


PROMPT_SOUND_TO_VALUE: dict[PromptSound, int] = {
    PromptSound.NONE: 0x00,
    PromptSound.LOW: 0x01,
    PromptSound.MEDIUM: 0x02,
    PromptSound.HIGH: 0x03,
}
VALUE_TO_PROMPT_SOUND = {value: key for key, value in PROMPT_SOUND_TO_VALUE.items()}


class Standby(StrEnum):
    """Known automatic-standby selections (D80 verified)."""

    NEVER = "never"
    MINUTES_15 = "15_minutes"
    MINUTES_30 = "30_minutes"
    MINUTES_60 = "60_minutes"
    HOURS_4 = "4_hours"
    HOURS_8 = "8_hours"
    HOURS_12 = "12_hours"
    HOURS_24 = "24_hours"
    HOURS_48 = "48_hours"


STANDBY_TO_MINUTES: dict[Standby, int] = {
    Standby.NEVER: 0,
    Standby.MINUTES_15: 15,
    Standby.MINUTES_30: 30,
    Standby.MINUTES_60: 60,
    Standby.HOURS_4: 240,
    Standby.HOURS_8: 480,
    Standby.HOURS_12: 720,
    Standby.HOURS_24: 1440,
    Standby.HOURS_48: 2880,
}
MINUTES_TO_STANDBY = {value: key for key, value in STANDBY_TO_MINUTES.items()}
