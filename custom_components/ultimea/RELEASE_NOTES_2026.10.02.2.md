# ULTIMEA 2026.10.02.2

### Fixed

- Source handoff now requires the winning mapped media player to actually report `paused` before the ULTIMEA source may change.
- If pause is rejected/ignored or does not confirm within two seconds, the handoff aborts before touching the soundbar source.
- After confirmed pause, the blueprint requests the source and requires live source confirmation within three seconds.
- If the bar does not confirm the requested input, the media player remains paused rather than losing content into the wrong source.
- Only after confirmed source plus the 500 ms settle window are the input default mode and playback resume allowed.
- Added order-sensitive regression coverage for pause-confirm-before-source and source-confirm-before-resume.
