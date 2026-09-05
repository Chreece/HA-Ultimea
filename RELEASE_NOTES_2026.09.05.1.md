# ULTIMEA 2026.09.05.1

## Added

- Ten hardware-verified Poseidon D80 Boom Custom EQ number entities covering 31 Hz through 16 kHz with the app/device -6…+6 dB range.
- Custom EQ as a media-player sound mode using profile `0x07` and the D80's exact 41-byte curve read/write path.
- Hardware-verified X-Upmix switch using `02:16` with authoritative `01:18` state verification.
- Diagnostic Capabilities sensor exposing the recovered semantic `fetchAbilities` fields alongside the raw bytes.

## Fixed

- Restored the hardware-proven D80 INFO getter map and separate eARC GET/SET encodings.
- Corrected mute GET decoding (`00=muted`, `01=unmuted`).
- Complete post-start state refresh after capability re-probing.
- Custom Style profile `0x08` no longer leaves a stale previous HA sound-mode value; it remains decoded but intentionally not exposed as a persistent selectable mode.

## Still intentionally not exposed

Bass, Mid/Midrange, Treble, Surround level, incoming HDMI/eARC codec/format, firmware OTA, and unnamed INFO commands remain excluded until their D80 BLE state/control semantics are proven.
