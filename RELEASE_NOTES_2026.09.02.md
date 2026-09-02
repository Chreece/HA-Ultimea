# ULTIMEA 2026.09.02

First public HACS-ready release of local Home Assistant control for **app-capable ULTIMEA soundbars**, with the **Poseidon D80 Boom (U2623)** as the first hardware-verified model.

## Highlights

- Added APK-derived multi-model capability probing with common `8D11/8D22` and custom-common `8D55/8D66` transport detection; D80 Boom remains the verified profile.
- Fully local Bluetooth control; no ULTIMEA cloud account required.
- Generic ULTIMEA discovery with read-only protocol/capability probing — no hard-coded device address or D80-only model allow-list.
- Power, volume, mute, source and six sound modes through a native media-player entity.
- Display brightness, screen timeout, prompt sound and automatic standby entities.
- Complete state refresh after setup/reconnect plus push updates while connected.
- Support for Home Assistant Bluetooth adapters and connectable Bluetooth proxies.
- Compatible with Home Assistant's current two-argument Bluetooth advertisement callback API.
- Runtime heartbeat/reconnect tasks are tied to the config-entry background lifecycle, so unavailable-device recovery cannot hold Home Assistant startup open.
- Device serial/firmware metadata and redacted diagnostics.
- English, German and Greek translations.
- Local brand assets and HACS/hassfest repository validation.

## Upgrade note

Early `0.1.x` development builds can be upgraded in place. Existing configured D80 entries are retained; duplicate MAC-address discovery behavior from the development builds has been corrected.

## Known gaps

Bass, mid, treble, surround level, X-Upmix, advanced EQ and firmware OTA are not yet exposed because those protocol commands have not yet been hardware-verified.

### Availability recovery

- Adds an unavailable-only Bluetooth heartbeat. When the D80 disappears or a persistent link drops, Home Assistant retries only that configured soundbar at the configured interval and refreshes all states immediately after recovery.
- The heartbeat uses Home Assistant's Bluetooth manager and never starts/stops global scanning or resets adapters.
