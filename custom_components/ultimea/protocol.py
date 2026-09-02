"""ULTIMEA AA/BB BLE protocol helpers.

The frame format was derived from the official ULTIMEA Android application and
validated against a physical Poseidon D80 Boom. The APK exposes both Legacy and
Frontier delegates plus common/custom BLE transports; model support is therefore
capability-probed above this framing layer. Commands begin with 0xAA and
notifications begin with 0xBB. The checksum is calculated using 0xAA for both
command and notification frames.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterator

COMMAND_HEADER = 0xAA
RESPONSE_HEADER = 0xBB


@dataclass(frozen=True, slots=True)
class UltimeaFrame:
    """A decoded ULTIMEA BLE frame."""

    header: int
    group: int
    command: int
    data: bytes
    raw: bytes


def checksum(group: int, command: int, data: bytes = b"", reserved: int = 0) -> int:
    """Calculate the ULTIMEA frame checksum."""
    return (COMMAND_HEADER + reserved + group + command + sum(data)) & 0xFF


def build_command(group: int, command: int, data: bytes = b"") -> bytes:
    """Build a command frame for the soundbar."""
    if len(data) > 0xFF:
        raise ValueError("ULTIMEA payload is limited to 255 bytes")

    return bytes(
        [
            COMMAND_HEADER,
            len(data),
            0x00,
            group,
            command,
            *data,
            checksum(group, command, data),
        ]
    )


def parse_frame(payload: bytes, offset: int = 0) -> UltimeaFrame | None:
    """Parse a single valid notification frame starting at offset."""
    if offset < 0 or offset + 6 > len(payload):
        return None
    if payload[offset] != RESPONSE_HEADER:
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

    raw = bytes(payload[offset:end])
    return UltimeaFrame(RESPONSE_HEADER, group, command, data, raw)


def iter_frames(payload: bytes) -> Iterator[UltimeaFrame]:
    """Yield all valid frames embedded in a BLE notification.

    ULTIMEA notifications can be padded to 50 bytes and can occasionally
    contain another complete frame after the first one. Invalid padding is
    skipped byte-by-byte and only checksum-valid 0xBB frames are emitted.
    """
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


def decode_ascii(data: bytes) -> str:
    """Decode a NUL-terminated ASCII field."""
    return data.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
