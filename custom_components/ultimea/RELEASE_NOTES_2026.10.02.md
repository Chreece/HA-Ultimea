# ULTIMEA 2026.10.02

### Changed

- Active mapped media-player or Assist Satellite routes can wake an `off` ULTIMEA soundbar.
- When the bar returns from `unavailable` or `unknown` to a known `off` state while a mapped route is already active, the blueprint powers it on.
- The subsequent `off → on` event performs a fresh source-routing pass and applies the winning input's one-shot default sound mode.
- Fallback source and legacy audio-input selector settings never wake the bar by themselves.
