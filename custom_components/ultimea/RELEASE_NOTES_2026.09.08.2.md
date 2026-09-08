# ULTIMEA 2026.09.08.2

This narrow Adaptive Room Audio refinement adds two requested behaviors without
folding in the deferred room-policy or per-zone-volume work.

## Audio-input selector

- Optional `input_select`/`select` entities can drive a soundbar source.
- The Home Assistant picker is searchable by friendly name/label while storing the entity ID.
- Selectors are paired strictly by Home Assistant area; no-area and ambiguous matches are ignored.

## Guarded volume handoff

- Non-urgent restore/retake changes use the configured handoff duration with fixed five-second stepping.
- Every next step verifies the previous expected volume; a user/external change aborts the handoff.
- Quiet-boundary catch-up is limited to one normal five-second fade step.
- Direct minimum-volume requests such as TTS/Assist remain immediate.
- Queued stale intermediate volume events are ignored using the current live volume, so the handoff does not depend on `context.parent_id` surviving timer-triggered actions.

Per-zone volume is intentionally the next separate item.
