"""Install bundled ULTIMEA blueprints into Home Assistant safely."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Final

BLUEPRINT_FILENAME: Final = "adaptive_room_audio.yaml"
BLUEPRINT_RELATIVE_PATH: Final = f"ultimea/{BLUEPRINT_FILENAME}"
_TARGET_DIRECTORY: Final = Path("blueprints") / "automation" / "ultimea"
_STATE_FILENAME: Final = ".ultimea-managed.json"
_STATE_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class BlueprintInstallResult:
    """Result of synchronizing bundled blueprints into the HA config directory."""

    installed: tuple[str, ...] = ()
    updated: tuple[str, ...] = ()
    unchanged: tuple[str, ...] = ()
    preserved: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        """Return whether at least one Home Assistant blueprint file changed."""
        return bool(self.installed or self.updated)


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def _read_managed_state(path: Path) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}

    if payload.get("version") != _STATE_VERSION:
        return {}
    managed = payload.get("managed")
    if not isinstance(managed, dict):
        return {}
    return {
        str(name): str(digest)
        for name, digest in managed.items()
        if isinstance(name, str) and isinstance(digest, str)
    }


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(data)
    temporary.replace(path)


def _write_managed_state(path: Path, managed: dict[str, str]) -> None:
    payload = {
        "version": _STATE_VERSION,
        "managed": dict(sorted(managed.items())),
    }
    _atomic_write(
        path,
        (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )


def install_bundled_blueprints(
    config_dir: str | Path,
    *,
    bundled_dir: str | Path | None = None,
) -> BlueprintInstallResult:
    """Install/update bundled blueprints without overwriting user modifications.

    A blueprint becomes managed only when ULTIMEA creates it or when an existing
    file is byte-for-byte identical to the bundled copy. On later integration
    updates, a managed blueprint is replaced only when its current digest still
    matches the digest ULTIMEA last installed. Any user-edited or otherwise
    unmanaged file at the destination is preserved.
    """

    source_dir = (
        Path(bundled_dir)
        if bundled_dir is not None
        else Path(__file__).resolve().parent / "blueprints"
    )
    target_dir = Path(config_dir) / _TARGET_DIRECTORY
    state_path = target_dir / _STATE_FILENAME
    managed = _read_managed_state(state_path)

    installed: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []
    preserved: list[str] = []
    state_changed = False

    for filename in (BLUEPRINT_FILENAME,):
        source = source_dir / filename
        target = target_dir / filename
        source_data = source.read_bytes()
        source_digest = _digest(source_data)

        if not target.exists():
            _atomic_write(target, source_data)
            managed[filename] = source_digest
            installed.append(BLUEPRINT_RELATIVE_PATH)
            state_changed = True
            continue

        target_data = target.read_bytes()
        target_digest = _digest(target_data)
        previous_managed_digest = managed.get(filename)

        if target_digest == source_digest:
            unchanged.append(BLUEPRINT_RELATIVE_PATH)
            if previous_managed_digest != source_digest:
                # Safe adoption: an existing byte-identical copy has no user
                # differences to preserve, so future bundled updates can track it.
                managed[filename] = source_digest
                state_changed = True
            continue

        if previous_managed_digest is not None and target_digest == previous_managed_digest:
            _atomic_write(target, source_data)
            managed[filename] = source_digest
            updated.append(BLUEPRINT_RELATIVE_PATH)
            state_changed = True
            continue

        preserved.append(BLUEPRINT_RELATIVE_PATH)

    if state_changed:
        _write_managed_state(state_path, managed)

    return BlueprintInstallResult(
        installed=tuple(installed),
        updated=tuple(updated),
        unchanged=tuple(unchanged),
        preserved=tuple(preserved),
    )
