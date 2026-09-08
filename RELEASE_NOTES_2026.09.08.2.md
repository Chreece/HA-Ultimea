# ULTIMEA 2026.09.08.2

Adaptive Room Audio is now a full room-aware policy engine rather than only a quiet-hours controller.

## Rich conditions everywhere

Minimum volume, zero/mute priority, ambient boost, Night mode, connected/activity gating, EQ follow and manual-learning gates all expose Home Assistant's native visual condition editor. Every one also has a Jinja template alternative for advanced policies. Templates can use per-bar variables such as `bar`, `bar_area`, `in_quiet_hours`, Min/Max and trigger context.

## Volume policy layers

The priority order is **zero/mute → minimum → scheduled/normal**. Quiet-hour boundary fades remain the only smooth transitions; TTS, Assist, binary/list/custom conditions and zero/mute changes are direct. Manual volume changes during a fade stop that fade instead of being learned.

Ambient-noise compensation can add a configurable number of percentage points in Min, normal operation or both, with an optional numeric entity source and selectable cap. Manual Min/Max learning subtracts an active boost before storing the base endpoint.

## Room and device selection

Each policy can use room-scoped room lists or global room lists. Room-list parsing accepts comma-separated state values plus list or comma-string attributes. Connected content/activity can be selected as media-player entities, devices, or labels; media players belonging to selected devices/labeled devices are included automatically.

A shared extra-trigger selector lets users list entities referenced by custom conditions/templates for immediate reevaluation.
