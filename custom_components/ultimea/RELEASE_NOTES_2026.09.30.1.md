# ULTIMEA 2026.09.30.1

### Changed

- Quiet-hour fades now respect manual volume changes directionally instead of aborting the whole fade.
- Before quiet hours, manually raising volume holds that value and can learn it as the new minimum; manually lowering volume is held until the scheduled fade itself needs to go lower.
- After quiet hours, manually raising volume is held until the scheduled fade itself needs to go higher; manually lowering volume holds that value and can learn it as the new maximum/zone target.
- Active fades re-read the current min/max helpers on every five-second step so newly learned endpoints take effect immediately.

### Fixed

- Prevented active fades from continuing with stale min/max endpoints after manual endpoint learning.
- Preserved three-second settled manual learning and learning-echo suppression during directional fade control.
