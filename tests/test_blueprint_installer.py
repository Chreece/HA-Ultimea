from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "custom_components" / "ultimea" / "blueprint_installer.py"
spec = importlib.util.spec_from_file_location("ultimea_blueprint_installer", MODULE)
installer = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = installer
spec.loader.exec_module(installer)


def _source_dir(tmp_path: Path, content: str) -> Path:
    source = tmp_path / "bundled"
    source.mkdir()
    (source / installer.BLUEPRINT_FILENAME).write_text(content, encoding="utf-8")
    return source


def _target(config: Path) -> Path:
    return (
        config
        / "blueprints"
        / "automation"
        / "ultimea"
        / installer.BLUEPRINT_FILENAME
    )


def _state(config: Path) -> dict:
    path = config / "blueprints" / "automation" / "ultimea" / ".ultimea-managed.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_repository_and_bundled_blueprint_are_identical() -> None:
    public = ROOT / "blueprints" / "automation" / "ultimea" / "adaptive_room_audio.yaml"
    bundled = ROOT / "custom_components" / "ultimea" / "blueprints" / "adaptive_room_audio.yaml"
    assert public.read_bytes() == bundled.read_bytes()


def test_missing_blueprint_is_installed_and_then_left_unchanged(tmp_path: Path) -> None:
    config = tmp_path / "config"
    source = _source_dir(tmp_path, "blueprint: v1\n")

    first = installer.install_bundled_blueprints(config, bundled_dir=source)
    assert first.installed == (installer.BLUEPRINT_RELATIVE_PATH,)
    assert first.changed
    assert _target(config).read_text(encoding="utf-8") == "blueprint: v1\n"
    assert installer.BLUEPRINT_FILENAME in _state(config)["managed"]

    second = installer.install_bundled_blueprints(config, bundled_dir=source)
    assert second.unchanged == (installer.BLUEPRINT_RELATIVE_PATH,)
    assert not second.changed


def test_untouched_managed_blueprint_updates_but_user_edit_is_preserved(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config"
    source = _source_dir(tmp_path, "blueprint: v1\n")
    installer.install_bundled_blueprints(config, bundled_dir=source)

    (source / installer.BLUEPRINT_FILENAME).write_text("blueprint: v2\n", encoding="utf-8")
    upgraded = installer.install_bundled_blueprints(config, bundled_dir=source)
    assert upgraded.updated == (installer.BLUEPRINT_RELATIVE_PATH,)
    assert _target(config).read_text(encoding="utf-8") == "blueprint: v2\n"

    _target(config).write_text("blueprint: user-custom\n", encoding="utf-8")
    (source / installer.BLUEPRINT_FILENAME).write_text("blueprint: v3\n", encoding="utf-8")
    preserved = installer.install_bundled_blueprints(config, bundled_dir=source)
    assert preserved.preserved == (installer.BLUEPRINT_RELATIVE_PATH,)
    assert not preserved.changed
    assert _target(config).read_text(encoding="utf-8") == "blueprint: user-custom\n"


def test_preexisting_unmanaged_blueprint_is_never_overwritten(tmp_path: Path) -> None:
    config = tmp_path / "config"
    source = _source_dir(tmp_path, "blueprint: bundled\n")
    target = _target(config)
    target.parent.mkdir(parents=True)
    target.write_text("blueprint: mine\n", encoding="utf-8")

    result = installer.install_bundled_blueprints(config, bundled_dir=source)
    assert result.preserved == (installer.BLUEPRINT_RELATIVE_PATH,)
    assert target.read_text(encoding="utf-8") == "blueprint: mine\n"


def test_identical_manual_copy_is_safely_adopted_for_future_updates(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config"
    source = _source_dir(tmp_path, "blueprint: same\n")
    target = _target(config)
    target.parent.mkdir(parents=True)
    target.write_text("blueprint: same\n", encoding="utf-8")

    adopted = installer.install_bundled_blueprints(config, bundled_dir=source)
    assert adopted.unchanged == (installer.BLUEPRINT_RELATIVE_PATH,)
    assert installer.BLUEPRINT_FILENAME in _state(config)["managed"]

    (source / installer.BLUEPRINT_FILENAME).write_text("blueprint: newer\n", encoding="utf-8")
    upgraded = installer.install_bundled_blueprints(config, bundled_dir=source)
    assert upgraded.updated == (installer.BLUEPRINT_RELATIVE_PATH,)
    assert target.read_text(encoding="utf-8") == "blueprint: newer\n"


def test_integration_reloads_live_automations_after_blueprint_update() -> None:
    init_text = (ROOT / "custom_components" / "ultimea" / "__init__.py").read_text(
        encoding="utf-8"
    )

    assert "_async_reload_blueprint_automations" in init_text
    assert "automations_with_blueprint" in init_text
    assert 'hass.services.async_call("automation", "reload"' in init_text
    assert '"id": automation_id' in init_text
    assert "EVENT_HOMEASSISTANT_STARTED" in init_text
    assert "full_reload=bool(result.installed)" in init_text
