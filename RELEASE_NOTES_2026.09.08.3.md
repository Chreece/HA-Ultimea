# ULTIMEA 2026.09.08.3

This release adds the next zone-first Adaptive Room Audio capability: optional
per-zone normal volume.

## Per-zone normal volume

- Select any number of `input_number`, `number`, or numeric sensor entities.
- Put each selected entity in the same Home Assistant area as its ULTIMEA soundbar.
- Exactly one same-area match overrides the global maximum for that soundbar.
- No match or multiple matches fall back to the global maximum; nothing is guessed.
- `input_number` helpers provide persistent dashboard sliders and can learn manual
  normal-volume changes when learning is enabled.
- The shared minimum/quiet volume remains global.
- Quiet-boundary fades and guarded restores calculate against each zone's effective
  maximum and retain fixed five-second stepping.
