# ULTIMEA 2026.10.01.3

### Fixed

- Fixed the parallel-trigger race between source routing and Connected content / EQ follow.
- Connected-content EQ waits up to three seconds for the bar's live source to reach the triggering player's mapped input.
- EQ eligibility is then rebuilt from current live state, so stale old-input runs cannot overwrite the new input's default sound mode.
- Prevents eARC/TV content from switching the bar back to Movie after routing to AUX and applying AUX's Music default.
