# ULTIMEA 2026.10.02.1

### Changed

- Winning mapped media players are paused during real ULTIMEA source changes so announcements/playback do not begin while the bar is still switching inputs.
- Handoff flow: pause → 250 ms guard → request source → wait up to 2 s for live source confirmation → 500 ms settle → apply input default mode → resume.
- Playback resumes only on the same winning media player and only if it is still paused.
- No pause occurs when the bar is already on the correct input.
- The automation's own temporary pause/resume events are debounced so they cannot cause a competing source route; genuine pauses/stops still work normally.
