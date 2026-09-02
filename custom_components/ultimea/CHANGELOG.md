# Changelog

All notable changes to this project are documented here.

The project uses calendar versioning for public releases: `YYYY.MM.DD`.

## 2026.09.02

First public HACS-ready release.

### Added

- Added APK-derived multi-model capability probing with common `8D11/8D22` and custom-common `8D55/8D66` transport detection; D80 Boom remains the verified profile.
- Generic support for ULTIMEA Poseidon D80 Boom (U2623); no device MAC is hard-coded.
- Bluetooth discovery using ULTIMEA manufacturer/service data followed by device-side model verification.
- Native Home Assistant `media_player` with power, volume, mute, source and sound-mode controls.
- Configuration `select` entities for display brightness, screen timeout, prompt sound and automatic standby.
- Full initial/reconnect state refresh for power, mute, volume, source, sound mode and all exposed settings.
- Device model, serial and firmware detection.
- Push state updates through the D80 notification characteristic.
- Command ACK matching with state-query verification fallback.
- Persistent and on-demand BLE connection modes.
- Unavailable-device heartbeat with automatic targeted reconnect and full state refresh on recovery.
- Support for Home Assistant's shared Bluetooth manager and connectable Bluetooth proxies.
- Diagnostics with Bluetooth address and serial redaction.
- English, German and Greek translations.
- Local Home Assistant brand assets for light and dark themes.
- HACS and hassfest GitHub validation workflows.
- Repository documentation, issue templates, contributing guide and security policy.

### Fixed since development builds

- Populate runtime states on setup/reconnect instead of leaving entities unknown.
- Avoid false service failures when a control command succeeds but its immediate notification ACK is missed.
- Prevent already-configured soundbars from being rediscovered as a separate MAC-address entry.
- Never use a test-device MAC as a supported-device identifier.
- Match Home Assistant's current Bluetooth advertisement callback signature (`service_info`, `change`) to prevent callback replay errors.

### Not yet implemented

- Bass, mid, treble, surround, X-Upmix and advanced EQ controls.
- Firmware OTA.
