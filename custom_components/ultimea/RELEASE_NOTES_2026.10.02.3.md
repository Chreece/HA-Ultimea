# ULTIMEA 2026.10.02.3

### Added

- Per-input Pause/resume controllers for eARC, HDMI, Optical, AUX, Bluetooth, and USB.
- These controllers never trigger source routing; they only protect playback during a real source handoff.
- Supports room-specific Snapcast output triggers with a separate upstream producer such as MPD.

### Changed

- If controllers are configured for an input, the mapped route/output entity is never used as the pause target.
- If no controller is configured, the blueprint falls back to pausing the winning mapped player.
- All active controllers must confirm paused before source switching, and only paused controllers are resumed after source confirmation/settle.
