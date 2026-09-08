# ULTIMEA 2026.09.08.1

## Adaptive Room Audio refinements

- Minimum and maximum volume can now be entered directly as fixed percentages or supplied by optional numeric entities.
- Room-list entities now read both comma-separated state values and attributes containing lists or comma-separated strings of rooms.
- Manual min/max learning is now opt-in and only writes to selected writable `input_number`/`number` entities.
- A manual soundbar volume change during a quiet-hours fade stops that fade for the affected bar for the rest of the transition window; the one-minute reconciliation and unrelated policy events cannot restart it. Direct minimum-volume conditions can still apply immediately.

The public and integration-bundled blueprint copies remain byte-for-byte identical so automatic blueprint delivery continues to update untouched managed copies safely.
