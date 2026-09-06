# Changelog

All notable changes to this project are documented here.

The project uses calendar versioning for public releases: `YYYY.MM.DD` with patch suffixes when needed.

## 2026.09.06

### Changed

- Added profile-gated semantic wire mappings so a readable/capability-supported feature is no longer automatically treated as writable.
- D80 control paths now come only from the hardware-verified D80 profile; APK-common and generic devices remain read-only for controls until an exact setter mapping is proven for their wire family.
- Recorded the statically recovered Frontier single-LED command family as dormant profile evidence: `01:16/02:14` shutdown time, `01:11/02:0F` brightness and `01:12/02:10` power. These mappings are not assigned to any product model yet.
- Added semantic capability slots for incoming audio format and single-LED functions without creating guessed entities.
- Updated GitHub Actions checkout/setup-python dependencies to v7.

### Safety

- Media-player controls, configuration selects, Custom EQ numbers, X-Upmix and Style actions now require an explicit profile-specific writable mapping.
- Numeric command IDs are no longer allowed to define universal semantics. In particular, D80 `02:0F` remains outside all ordinary feature writes because it is the destructive restore-default command on that profile, while static Frontier evidence assigns the same numeric command to single-LED brightness.

### Evidence and limits

- D80 `01:10`, `01:11` and `01:12` remain intentionally unresolved and are not exposed as entities.
- D80 `01:62` remains unsupported/no-response, so incoming signal-format telemetry is not exposed on the D80.
- Frontier single-LED mappings remain dormant until a concrete product/profile ownership link is proven.

## 2026.09.05.4

### Added

- Added selectable D80 `Style` sound mode using the verified profile `0x08` selection/full-curve reply.
- Added five explicit Style actions: Bass, Rock, Pop, Classical and Reset (flat center), using the later labelled official-app capture and exact 41-byte device echoes.
- Added ten read-only Style gain sensors (31 Hz through 16 kHz), with signed 0.1 dB readback. No fake editable Style sliders or inferred XY interpolation.
- Added English, German and Greek entity labels and a Style badge on the dynamic media-player picture.

### Fixed

- Style/Custom EQ curves are validated for profile, frequencies and gain range; profile readback ignores short mode ACKs and waits for the full matching curve.
- Resubscribe the control notification characteristic on every new BLE connection instead of reusing a previous-session subscription marker.
- Clear custom-profile values when the mode changes, the bar powers off or the BLE session ends. Unknown/missing readback never becomes a flat curve or a remembered preset.
- Post-start/reconnect refresh reads all exposed statuses. A profile read is issued only after a fresh current-mode response confirms that same profile; background work never selects Style or resets it.
- Serialize sound-mode/profile operations and safe-code handshakes so concurrent commands cannot bypass session setup or mix Style and Custom EQ band writes.
- Keep Custom EQ writes gated to freshly confirmed profile `0x07`.
- Run the full protocol and mocked-device regression suite in a virtual environment. Manifest and both changelogs are updated atomically.

### Evidence and limits

- Corner names come from `d80-postaction-decoded-20260905-110322.json`, not the earlier unnamed A/B samples.
- Style buttons are actions, not a persistent preset selector. Reconnect does not infer an active Style from a saved curve. A missing/unrecognised current-mode report leaves Style readback unavailable.
- Continuous Style X/Y controls, physical-remote Bass/Mid/Treble/Surround and incoming audio codec telemetry remain unexposed without their missing protocol evidence.


## 2026.09.05.3

### Fixed

- Remove obsolete legacy `sensor.*` X-Upmix entity-registry entries on setup/reload. X-Upmix state and control now live only on the authoritative `switch` entity.

## 2026.09.05.2

### Added

- Added a dynamic media-player entity picture that shows the current input and EQ/sound mode together in one compact icon.
- Added source-aware MDI fallback icons for cards that do not render `entity_picture`.
- The dynamic icon also identifies decoded Custom Style profile `0x08` as `STY` without exposing it as a persistent selectable sound mode.

## 2026.09.05.1

### Added

- Added ten hardware-verified Poseidon D80 Boom Custom EQ `number` entities for 31/62/125/250/500 Hz and 1/2/4/8/16 kHz, with the app/device `-6…+6 dB` range.
- Added `Custom EQ` as a media-player sound mode backed by profile `0x07` and the D80's exact 41-byte EQ payload/readback path.
- Added a hardware-verified X-Upmix `switch`: SET uses `02:16 00/01` and state verification uses authoritative INFO `01:18`.
- Added a diagnostic Capabilities sensor that exposes the recovered semantic `fetchAbilities` field names while retaining the raw capability bytes.

### Fixed

- Restored the hardware-proven D80 INFO getter map: source `01:06`, volume `01:07`, sound mode `01:08`, prompt `01:0A`, screen timeout `01:0C`, power `01:0D`, mute `01:0E`, brightness `01:0F`, standby `01:17`, X-Upmix `01:18`.
- Corrected source GET decoding so eARC is `00` on INFO while eARC SET remains `10`.
- Corrected mute INFO decoding to the D80 wire convention `00=muted`, `01=unmuted`.
- After a post-start capability re-probe, a complete state refresh now runs so newly exposed entities are populated immediately.

### Evidence guardrails

- Custom Style profile `0x08` is decoded as a valid 41-byte curve format but is not exposed as a persistent sound mode because an authoritative restart/reconnect active-mode getter has not been proven.
- Bass, Mid, Treble and Surround are still not exposed because the D80 BLE GET+SET state path has not been proven for those physical-remote functions.

## 2026.09.05

### Added

- Added the official `00:01` safe-code session exchange recovered from the ULTIMEA app and validated against the Poseidon D80 Boom.
- Safe-code payload generation now uses the proven one-byte MD5 transform: final digest byte + 5, truncated to 8 bits.
- Firmware safe-code responses are pair-integrity validated before normal commands continue.
- The observed D80 `RX[0] == TX[0] ^ 0xFF` relation is recorded as a diagnostic only; it is not required because the app-side complement check was not statically proven.

### Changed

- Home Assistant startup no longer performs ULTIMEA BLE connections or status polling while HA is still booting.
- The first complete identity/capability/state refresh is scheduled only after `homeassistant_started` (or immediately on an integration reload when HA is already running).
- When a soundbar becomes available again after being unavailable, the integration reconnects once and refreshes all capability-proven statuses, including on-demand connection mode.
- Every new BLE protocol session establishes safe-code state before non-bootstrap commands; the state is reset on disconnect and when the active APK transport changes.

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

- Prevent the unavailable heartbeat, advertisement-replay reconnects, delayed disconnects and post-power refreshes from entering Home Assistant's startup task bucket; all runtime-spawned work now uses config-entry background tasks and cannot block bootstrap.
- Populate runtime states on setup/reconnect instead of leaving entities unknown.
- Avoid false service failures when a control command succeeds but its immediate notification ACK is missed.
- Prevent already-configured soundbars from being rediscovered as a separate MAC-address entry.
- Never use a test-device MAC as a supported-device identifier.
- Match Home Assistant's current Bluetooth advertisement callback signature (`service_info`, `change`) to prevent callback replay errors.

### Not yet implemented

- Bass, mid, treble and surround level.
- Firmware OTA.
