# ULTIMEA 2026.10.01

### Added

- Optional default sound mode for each ULTIMEA input: eARC/ARC, HDMI, Optical, AUX, Bluetooth and USB.
- Each input can use **Automatic / no input default**, Movie, Music, Voice, Sport, Night or Game.

### Changed

- Per-input modes are one-shot defaults, not enforced modes. A configured default is applied only when the bar enters that input.
- Later manual, EQ/content, Night or external automation changes are accepted while the bar remains on that input.
- **Automatic / no input default** leaves mode selection entirely to the existing Night/EQ/content rules.
- Night policy keeps priority during quiet/night conditions.
- Unsupported mapped modes are ignored when they are not present in the bar's reported `sound_mode_list`.
