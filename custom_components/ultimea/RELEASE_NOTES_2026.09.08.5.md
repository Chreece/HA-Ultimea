# ULTIMEA 2026.09.08.5

### Fixed

- Managed Adaptive Room Audio blueprint updates now reload the live Home Assistant automation definition after startup when Automation had already expanded an older blueprint copy.
- Existing ULTIMEA blueprint automations are reloaded individually by automation ID when possible, preventing removed triggers such as the old permanent five-second `transition_tick` from surviving an integration update.
- A brand-new blueprint installation uses one full automation reload only when necessary because automations that previously failed on a missing blueprint cannot be discovered by blueprint reference.
- User-modified/unmanaged blueprint files remain preserved and are not overwritten or auto-reloaded.
