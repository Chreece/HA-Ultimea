# ULTIMEA 2026.10.01.1

### Fixed

- Automation-driven source changes now apply that input's default sound mode in the same source-routing run.
- The blueprint no longer depends on a separate `bar_source_change` event when it switches the source itself.
- Remote/app/manual source changes seed the per-input default immediately; the later 750 ms wait is only for source-specific volume recall/clamping.
- One-shot semantics are preserved: later manual, EQ/content, Night, or external automation mode changes remain accepted while the bar stays on that input.
