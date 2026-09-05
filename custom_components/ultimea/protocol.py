"""ULTIMEA AA/BB BLE protocol helpers."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
import hashlib

COMMAND_HEADER = 0xAA
RESPONSE_HEADER = 0xBB
SAFE_CODE_COMMAND = 0x01

EQ_CUSTOM_PROFILE = 0x07
EQ_STYLE_PROFILE = 0x08
EQ_FREQUENCIES_HZ = (31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
EQ_GAIN_MIN_TENTHS_DB = -60
EQ_GAIN_MAX_TENTHS_DB = 60
EQ_GAIN_STEP_TENTHS_DB = 10
EQ_PAYLOAD_LENGTH = 1 + len(EQ_FREQUENCIES_HZ) * 4


@dataclass(frozen=True, slots=True)
class UltimeaFrame:
    header: int
    group: int
    command: int
    data: bytes
    raw: bytes


@dataclass(frozen=True, slots=True)
class UltimeaEqualizerPayload:
    profile: int
    frequencies_hz: tuple[int, ...]
    gains_tenths_db: tuple[int, ...]


def checksum(group: int, command: int, data: bytes = b"", reserved: int = 0) -> int:
    return (COMMAND_HEADER + reserved + group + command + sum(data)) & 0xFF


def build_command(group: int, command: int, data: bytes = b"") -> bytes:
    if len(data) > 0xFF:
        raise ValueError("ULTIMEA payload is limited to 255 bytes")
    return bytes([COMMAND_HEADER, len(data), 0x00, group, command, *data, checksum(group, command, data)])


def safe_code_byte(value: int) -> int:
    if not 0 <= value <= 0xFF:
        raise ValueError("safe-code data byte must be between 0 and 255")
    digest = hashlib.md5(bytes([value]), usedforsecurity=False).digest()
    return (digest[-1] + 5) & 0xFF


def build_safe_code_pair(value: int) -> bytes:
    return bytes([value, safe_code_byte(value)])


def validate_safe_code_pair(data: bytes) -> bool:
    return len(data) == 2 and data[1] == safe_code_byte(data[0])


def safe_code_response_complements(request_value: int, response: bytes) -> bool:
    if not 0 <= request_value <= 0xFF:
        raise ValueError("safe-code request byte must be between 0 and 255")
    return len(response) == 2 and response[0] == (request_value ^ 0xFF)


def parse_frame(payload: bytes, offset: int = 0) -> UltimeaFrame | None:
    if offset < 0 or offset + 6 > len(payload) or payload[offset] != RESPONSE_HEADER:
        return None
    data_len = payload[offset + 1]
    frame_len = 6 + data_len
    end = offset + frame_len
    if end > len(payload):
        return None
    reserved = payload[offset + 2]
    group = payload[offset + 3]
    command = payload[offset + 4]
    data = bytes(payload[offset + 5 : offset + 5 + data_len])
    frame_checksum = payload[offset + 5 + data_len]
    if frame_checksum != checksum(group, command, data, reserved):
        return None
    return UltimeaFrame(RESPONSE_HEADER, group, command, data, bytes(payload[offset:end]))


def iter_frames(payload: bytes) -> Iterator[UltimeaFrame]:
    index = 0
    while index < len(payload):
        try:
            start = payload.index(RESPONSE_HEADER, index)
        except ValueError:
            return
        frame = parse_frame(payload, start)
        if frame is None:
            index = start + 1
            continue
        yield frame
        index = start + len(frame.raw)


def parse_equalizer_payload(data: bytes) -> UltimeaEqualizerPayload | None:
    """Decode the D80 41-byte custom-EQ/style curve payload."""
    if len(data) != EQ_PAYLOAD_LENGTH:
        return None
    frequencies: list[int] = []
    gains: list[int] = []
    offset = 1
    for _ in EQ_FREQUENCIES_HZ:
        frequencies.append(int.from_bytes(data[offset : offset + 2], "little"))
        gains.append(int.from_bytes(data[offset + 2 : offset + 4], "little", signed=True))
        offset += 4
    return UltimeaEqualizerPayload(data[0], tuple(frequencies), tuple(gains))


def build_equalizer_payload(
    gains_tenths_db: tuple[int, ...] | list[int],
    *,
    profile: int = EQ_CUSTOM_PROFILE,
    frequencies_hz: tuple[int, ...] = EQ_FREQUENCIES_HZ,
) -> bytes:
    if len(gains_tenths_db) != len(EQ_FREQUENCIES_HZ):
        raise ValueError("ULTIMEA EQ requires exactly 10 gain values")
    if len(frequencies_hz) != len(EQ_FREQUENCIES_HZ):
        raise ValueError("ULTIMEA EQ requires exactly 10 frequencies")
    payload = bytearray([profile & 0xFF])
    for frequency, gain in zip(frequencies_hz, gains_tenths_db, strict=True):
        if not 0 <= int(frequency) <= 0xFFFF:
            raise ValueError(f"Invalid EQ frequency: {frequency}")
        if not -0x8000 <= int(gain) <= 0x7FFF:
            raise ValueError(f"Invalid EQ gain: {gain}")
        payload.extend(int(frequency).to_bytes(2, "little"))
        payload.extend(int(gain).to_bytes(2, "little", signed=True))
    return bytes(payload)


def decode_ascii(data: bytes) -> str:
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
