from __future__ import annotations

import ast
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


def test_safe_code_known_hardware_pairs():
    pairs = (
        (0x13, 0xB7),
        (0xEC, 0x10),
        (0x80, 0x24),
        (0x7F, 0x9A),
        (0x6E, 0xA6),
        (0x91, 0x67),
        (0xC2, 0xFC),
        (0x3D, 0x26),
    )
    for first, second in pairs:
        assert protocol.safe_code_byte(first) == second
        assert protocol.build_safe_code_pair(first) == bytes([first, second])
        assert protocol.validate_safe_code_pair(bytes([first, second]))


def test_safe_code_full_captured_handshakes():
    captures = (
        (bytes.fromhex("13 b7"), bytes.fromhex("ec 10")),
        (bytes.fromhex("80 24"), bytes.fromhex("7f 9a")),
        (bytes.fromhex("6e a6"), bytes.fromhex("91 67")),
        (bytes.fromhex("c2 fc"), bytes.fromhex("3d 26")),
    )
    for request, response in captures:
        assert protocol.validate_safe_code_pair(request)
        assert protocol.validate_safe_code_pair(response)
        assert protocol.safe_code_response_complements(request[0], response)


def test_safe_code_command_frame_matches_capture():
    assert protocol.build_command(
        0x00, protocol.SAFE_CODE_COMMAND, protocol.build_safe_code_pair(0x6E)
    ) == bytes.fromhex("aa 02 00 00 01 6e a6 bf")


def test_safe_code_pair_validation_is_independent_of_complement_relation():
    response = protocol.build_safe_code_pair(0x80)
    assert protocol.validate_safe_code_pair(response)
    assert not protocol.safe_code_response_complements(0x6E, response)


def test_public_release_version():
    import json

    manifest = Path(__file__).parents[1] / "custom_components" / "ultimea" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["version"] == "2026.09.05"
    assert data["integration_type"] == "device"


def test_bluetooth_advertisement_callback_signature():
    runtime_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "runtime.py"
    )
    tree = ast.parse(runtime_py.read_text(encoding="utf-8"))
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "async_handle_advertisement"
    )
    assert [arg.arg for arg in method.args.args] == [
        "self",
        "service_info",
        "_change",
    ]


def test_unavailable_heartbeat_is_configurable():
    const_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "const.py"
    ).read_text(encoding="utf-8")
    config_flow_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "config_flow.py"
    ).read_text(encoding="utf-8")
    device_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "device.py"
    ).read_text(encoding="utf-8")

    assert 'CONF_HEARTBEAT_INTERVAL = "heartbeat_interval"' in const_py
    assert "DEFAULT_HEARTBEAT_INTERVAL = 30" in const_py
    assert "CONF_HEARTBEAT_INTERVAL" in config_flow_py
    assert "_async_heartbeat_loop" in device_py
    assert "INFO_POWER" in device_py


def test_apk_capability_query_command():
    assert protocol.build_command(0x00, 0x00) == bytes.fromhex("aa 00 00 00 00 aa")


def test_multimodel_transport_constants_present():
    const_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "const.py"
    ).read_text(encoding="utf-8")
    assert "27758d55-bf3a-4ac6-bee5-6259ccb7c9b7" in const_py
    assert "27758d66-bf3a-4ac6-bee5-6259ccb7c9b7" in const_py
    assert 'CAP_FETCH_ABILITIES = 0x00' in const_py


def test_no_d80_model_allowlist_in_identity_refresh():
    device_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "device.py"
    ).read_text(encoding="utf-8")
    assert 'model != SUPPORTED_MODEL' not in device_py
    assert "async_detect_capabilities" in device_py
    assert "_transport_candidates" in device_py


def test_apk_profile_contains_embedded_models_and_capabilities():
    profiles_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "profiles.py"
    ).read_text(encoding="utf-8")
    for model in ("Apollo B60", "Apollo B70", "Nova S80", "Poseidon M80", "Poseidon M90V"):
        assert model in profiles_py
    for capability in ("hasToneControl", "hasXupMix", "hasSurroundVolume", "hasAuraCast"):
        assert capability in profiles_py


def test_initial_full_refresh_is_deferred_until_ha_started():
    runtime_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "runtime.py"
    ).read_text(encoding="utf-8")
    init_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "__init__.py"
    ).read_text(encoding="utf-8")

    tree = ast.parse(runtime_py)
    start_method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "async_start"
    )
    start_source = ast.get_source_segment(runtime_py, start_method) or ""
    assert "async_ensure_connected" not in start_source
    assert "async_refresh_all" not in start_source
    assert "async_post_start" in runtime_py
    assert "async_refresh_all(reprobe_capabilities=reprobe_capabilities)" in runtime_py
    assert "EVENT_HOMEASSISTANT_STARTED" in init_py
    assert "CoreState.running" in init_py
    assert '"ULTIMEA post-start full status refresh"' in init_py


def test_reconnect_transition_schedules_full_state_refresh():
    runtime_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "runtime.py"
    ).read_text(encoding="utf-8")
    device_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "device.py"
    ).read_text(encoding="utf-8")

    assert "if self.keep_connected or not was_available:" in runtime_py
    assert "self._schedule_connect_and_refresh()" in runtime_py
    assert "_async_connect_and_refresh_background" in device_py
    assert "await self.async_refresh_all()" in device_py
    assert "await self.async_refresh_state()" in device_py


def test_safe_code_session_precedes_non_bootstrap_commands():
    runtime_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "runtime.py"
    ).read_text(encoding="utf-8")
    assert "await self._async_safe_code_handshake()" in runtime_py
    assert "validate_safe_code_pair(response)" in runtime_py
    assert "safe_code_response_complements" in runtime_py
    assert "INFO_PROTOCOL" in runtime_py
    assert "GROUP_CAPABILITIES" in runtime_py


def test_runtime_tasks_never_block_home_assistant_startup():
    device_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "device.py"
    ).read_text(encoding="utf-8")
    init_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "__init__.py"
    ).read_text(encoding="utf-8")

    assert "self.hass.async_create_task(" not in device_py
    assert "async_create_background_task(" in device_py
    assert "self._config_entry.async_create_background_task(" in device_py
    assert '"ULTIMEA unavailable heartbeat"' in device_py
    assert "eager_start=False" in device_py
    assert "config_entry=entry" in init_py
    assert "entry.async_create_background_task(" in init_py


def test_all_runtime_spawn_sites_use_background_task_helper():
    device_py = (
        Path(__file__).parents[1]
        / "custom_components"
        / "ultimea"
        / "device.py"
    ).read_text(encoding="utf-8")
    for task_name in (
        "ULTIMEA connect and refresh",
        "ULTIMEA unavailable heartbeat",
        "ULTIMEA delayed disconnect",
        "ULTIMEA post-power refresh",
    ):
        assert task_name in device_py
    assert device_py.count("_async_create_runtime_task(") >= 5
