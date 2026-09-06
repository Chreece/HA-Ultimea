# ULTIMEA 2026.09.06

## Universal wire-profile safety

This release separates semantic capabilities from numeric protocol command IDs so support discovered through safe reads can no longer accidentally enable a setter from the wrong ULTIMEA wire family.

### Changed

- D80 writes now require the hardware-verified D80 profile mapping.
- APK-common and generic devices remain read-only for controls until their exact setter mappings are proven.
- Media-player controls, configuration selects, Custom EQ numbers, X-Upmix and Style actions are gated by explicit profile-specific writable mappings.
- Added semantic capability slots for incoming audio format and single-LED features without exposing guessed entities.
- Recorded the recovered Frontier single-LED family as dormant static evidence only: `01:16/02:14` shutdown time, `01:11/02:0F` brightness, `01:12/02:10` power.

### Safety

The same numeric command can mean different things on different ULTIMEA profiles. D80 `02:0F` remains excluded from ordinary feature writes because it is the destructive restore-default command on the D80, while static Frontier evidence maps `02:0F` to single-LED brightness.

### Evidence boundaries

- D80 `01:10`, `01:11` and `01:12` remain unresolved and are not exposed as entities.
- D80 `01:62` remains unsupported/no-response, so incoming signal-format telemetry is not exposed on the D80.
- Frontier single-LED mappings are not assigned to any product model until profile ownership is proven.
