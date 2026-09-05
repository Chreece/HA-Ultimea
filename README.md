<p align="center">
  <img src="custom_components/ultimea/brand/logo.png" alt="ULTIMEA for Home Assistant" width="640">
</p>

<h1 align="center">ULTIMEA for Home Assistant</h1>

<p align="center">
  Local Bluetooth control for <strong>app-capable ULTIMEA soundbars</strong>, with Poseidon D80 Boom (U2623) as the first hardware-verified model.<br>
  No ULTIMEA cloud account, phone app, or internet connection is required after installation.
</p>

<p align="center">
  <img alt="Release" src="https://img.shields.io/badge/release-2026.09.05.4-blue">
  <img alt="Home Assistant 2026.7+" src="https://img.shields.io/badge/Home%20Assistant-2026.7%2B-41BDF5">
  <img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-41BDF5">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>

> [!IMPORTANT]
> This is an **unofficial community integration**. It is not affiliated with, endorsed by, or supported by ULTIMEA.

## Supported devices

| Device/protocol | Status |
| --- | --- |
| ULTIMEA Poseidon D80 Boom (U2623) | ✅ Hardware verified |
| Other ULTIMEA devices that pass the APK common/custom protocol probe | 🧪 Experimental, capability-driven |

The integration is not a D80 model-name allow-list. It discovers likely ULTIMEA advertisements, selects the app protocol transport, asks the device for its model/protocol information, fetches the raw capability block when available, and probes safe read-only states. D80-only advanced functions are enabled by the hardware-verified D80 profile.

## Poseidon D80 Boom entities

### Media player

- Power on/off
- Absolute volume and volume step
- Mute/unmute
- Sources: **eARC, HDMI, Optical, AUX, Bluetooth, USB**
- Sound modes: **Movie, Music, Voice, Sport, Night, Game, Custom EQ, Style**

### Advanced audio

- **X-Upmix switch** — hardware-verified SET `02:16 00/01`, verified against INFO `01:18`
- **10-band Custom EQ** — ten `number` entities:
  - 31 Hz
  - 62 Hz
  - 125 Hz
  - 250 Hz
  - 500 Hz
  - 1 kHz
  - 2 kHz
  - 4 kHz
  - 8 kHz
  - 16 kHz
- EQ range: **-6 dB … +6 dB**
- The integration preserves the other nine EQ bands when changing one band.
- EQ controls are available while the hardware-verified Custom EQ profile `0x07` is active.

### Custom Style

Select **Style** in the media-player sound-mode selector to load the bar's stored
profile `0x08`. Five buttons apply the captured **Style Bass**, **Style Rock**,
**Style Pop**, **Style Classical**, and **Style Reset** curves. Each action selects
Style and requires the complete 41-byte device echo; Reset is the flat center of
Style, **not** a factory reset. The corner curves come from the later labelled
capture, not the earlier unnamed A/B samples.

Ten **Style gain sensors** in Diagnostics show the actual confirmed curve in dB,
including half-decibel values. They are read-only. The existing Custom EQ sliders
remain writable only in Custom EQ (profile `0x07`). `style_preset` on the media
player identifies an exact captured curve, or `custom` for another confirmed curve.

Style values are cleared on disconnect/mode change and are not restored from a
remembered button press. After HA has started or the bar reconnects, the
integration reads current state first; it reads profile `0x08` only when a fresh
mode response identifies it as active. If the device does not provide that
confirmation, Style values remain unavailable until an explicit Style action or
a complete profile notification confirms them. Background refresh never selects
Style or resets its curve. There are no guessed continuous X/Y controls.

See [Style capture evidence](docs/D80_STYLE.md) for the exact curves and limits.

### Settings

- Display brightness: **Dim, Low, Medium, Normal, High**
- Screen timeout: **Never, 5 s, 30 s, 60 s**
- Prompt sound: **None, Low, Medium, High**
- Automatic standby: **Never, 15/30/60 min, 4/8/12/24/48 h**

### Diagnostics

A **Capabilities** diagnostic sensor exposes:

- the raw `fetchAbilities` bytes
- the recovered semantic capability names for every returned field
- the integration's currently safe/proven feature set
- protocol version and selected BLE transport

For the captured D80 firmware the capability payload contains the first 18 recovered fields, including LED, bass, surround, eARC/ARC/HDMI/Bluetooth/AUX/USB, Dolby Atmos/Vision, OTA, chip code, display-screen and custom-standby flags. Missing later fields are omitted, not silently treated as false.

## Safe-code session

Release `2026.09.05` added the official `00:01` session exchange required by the app protocol. The integrity byte is:

```text
(MD5(single_byte).last_digest_byte + 5) & 0xff
```

Every new BLE protocol session establishes safe-code state before normal non-bootstrap commands. Firmware replies are pair-integrity validated. The D80's observed first-byte complement relationship is retained as a diagnostic rather than imposed as an app requirement because static analysis did not prove that the official app enforces it.

## State synchronization

Home Assistant does **not** connect to the soundbar while HA is still booting. The first complete identity/capability/state refresh is scheduled after `homeassistant_started`; integration reloads run it immediately when HA is already running.

After a reconnect/recovery the integration refreshes every exposed state, including X-Upmix. Custom EQ/Style readback requires fresh current-mode confirmation for profile `0x07`/`0x08`, so background refresh never selects a different profile merely to obtain EQ values.

While a persistent BLE connection is open, valid ULTIMEA notifications update entities without polling. In on-demand mode the connection is released after the configured delay.

## Bluetooth routing

The integration uses Home Assistant's shared Bluetooth manager and can use supported local adapters or connectable Bluetooth proxies. It does not start/stop global Bluetooth scanning and does not hard-code a local adapter or test-device MAC address.

## Installation

### HACS

Until the repository is accepted into the default HACS catalog:

1. Open **HACS → Integrations**.
2. Open **Custom repositories**.
3. Add `https://github.com/Chreece/HA-ULTIMEA` as an **Integration**.
4. Install **ULTIMEA**.
5. Restart Home Assistant.
6. Open **Settings → Devices & services** and add/discover the soundbar.

### Manual

Copy:

```text
custom_components/ultimea/
```

into:

```text
/config/custom_components/ultimea/
```

and restart Home Assistant.

## Options

| Option | Default | Purpose |
|---|---:|---|
| Keep Bluetooth connection open | On | Enables immediate push updates from the physical remote/device |
| On-demand disconnect delay | 15 s | Releases BLE for the official app after a command |
| Maximum protocol volume | 100 | Maps device volume to Home Assistant's `0.0–1.0` scale |
| Unavailable heartbeat interval | 30 s | Retries only this configured soundbar while unavailable |

## Evidence boundaries

The integration deliberately does **not** turn every APK method or capability flag into a Home Assistant control.

Not currently exposed:

- Bass
- Mid/Midrange
- Treble
- Surround level
- Continuous Custom Style XY interpolation
- Current incoming HDMI/eARC codec/format
- Firmware OTA
- Responsive but still unnamed INFO commands `01:0B`, `01:10`, `01:11`, `01:12`

Style mode, captured corner actions and confirmed curve readback are exposed. Its continuous XY interpolation is not reconstructed. The separate physical-remote Bass/Mid/Treble/Surround controls remain outside the proven ordinary D80 BLE GET+SET surface and are not guessed.

## Protocol documentation

See [`docs/PROTOCOL.md`](docs/PROTOCOL.md) for the hardware-verified INFO/CONTROL command maps, safe-code algorithm, Custom EQ payload, X-Upmix verification behavior and capability-field order.

## Diagnostics and troubleshooting

Download diagnostics from:

**Settings → Devices & services → ULTIMEA → device → ⋮ → Download diagnostics**

If the phone app cannot connect, disable **Keep Bluetooth connection open** so Home Assistant releases BLE after the configured delay. If the soundbar is powered down/out of range, entities stay unavailable until the configured targeted recovery path reaches it again.

## Privacy

Control is local over Bluetooth. The integration requires no ULTIMEA credentials and intentionally sends no soundbar state to an ULTIMEA cloud service.

## Contributing

Bug reports, additional model/firmware observations, protocol captures, translations and hardware-tested support are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Release history

See [`CHANGELOG.md`](CHANGELOG.md).

## License

MIT. See [`LICENSE`](LICENSE).
