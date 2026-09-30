# ULTIMEA 2026.09.30

### Added

- Event-driven media-player source routing with per-source mappings, latest-playing-wins behavior, and a global fallback source.
- Capture-backed partial Poseidon D70 support for absolute volume and ARC/Optical/AUX source writes.
- Model-specific source wire values and labels.

### Changed

- Single-soundbar source routing no longer requires Home Assistant area assignment; multiple bars still use areas for disambiguation.
- Guarded handoff duration `0` now disables the transition completely.
- Manual min/max learning settles for three seconds before saving and suppresses the resulting helper write as a learning echo.
- Maximum volume is a hard ceiling even when per-zone normal-volume entities are configured.
- Source changes clamp only downward after hardware source-specific volume recall settles.

### Fixed

- INFO source replies now use the INFO source enum, including `01:06 00`.
- eARC blueprint routing automatically maps to ARC when the target bar exposes ARC.
- Fixed stale/intermediate learned-volume and per-zone-max interactions that could raise volume unexpectedly.
