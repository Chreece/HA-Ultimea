# ULTIMEA 2026.09.08.4

Adaptive Room Audio no longer runs on permanent polling ticks.

- Removed the every-5-seconds transition trigger.
- Removed the every-minute policy trigger.
- A pre-quiet template trigger fires once when the configured transition window begins.
- The active fade itself uses internal five-second delays in one automation run.
- Outside a fade, the automation sleeps until a real state/time event occurs.
- Soundbar attribute-only changes no longer trigger the general state watcher.
- Manual volume attribute watching is enabled only when manual learning is enabled.
- Parallel mode keeps TTS/Assist/condition events responsive during an active fade.
