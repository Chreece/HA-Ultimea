from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

MODULE = Path(__file__).parents[1] / "custom_components" / "ultimea" / "protocol.py"
spec = importlib.util.spec_from_file_location("ultimea_protocol", MODULE)
protocol = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


def test_volume_9_command():
    assert protocol.build_command(0x02, 0x03, b"\x09") == bytes.fromhex(
        "aa 01 00 02 03 09 b8"
    )


def test_earc_command():
    assert protocol.build_command(0x02, 0x02, b"\x10") == bytes.fromhex(
        "aa 01 00 02 02 10 be"
    )


def test_identity_model_query():
    assert protocol.build_command(0x01, 0x02) == bytes.fromhex("aa 00 00 01 02 ad")


def test_parse_padded_notification():
    payload = bytes.fromhex(
        "bb 01 00 02 03 09 b8 "
        "31 33 34 00 31 35 00 30 30 11 00 e0 01 d0 02 a0 05 40 0b d6 "
        "03 00 00 d0 07 00 00 a0 0f 00 00 40 1f 00 00 80 3e 00 00 0f 00 00 00"
    )
    frames = list(protocol.iter_frames(payload))
    assert len(frames) == 1
    assert frames[0].group == 0x02
    assert frames[0].command == 0x03
    assert frames[0].data == b"\x09"


def test_parse_two_embedded_frames():
    payload = bytes.fromhex(
        "bb 01 00 02 0c 00 b8 bb 01 00 01 07 0f c1 32 38 07 00"
    )
    frames = list(protocol.iter_frames(payload))
    assert [(frame.group, frame.command, frame.data) for frame in frames] == [
        (0x02, 0x0C, b"\x00"),
        (0x01, 0x07, b"\x0f"),
    ]


def test_state_query_commands():
    assert protocol.build_command(0x01, 0x06) == bytes.fromhex("aa 00 00 01 06 b1")
    assert protocol.build_command(0x01, 0x08) == bytes.fromhex("aa 00 00 01 08 b3")
    assert protocol.build_command(0x01, 0x0E) == bytes.fromhex("aa 00 00 01 0e b9")
    assert protocol.build_command(0x01, 0x17) == bytes.fromhex("aa 00 00 01 17 c2")
