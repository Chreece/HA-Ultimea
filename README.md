<p align="center">
  <img src="custom_components/ultimea/brand/logo.png" alt="ULTIMEA for Home Assistant" width="640">
</p>

<h1 align="center">ULTIMEA for Home Assistant</h1>

<p align="center">
  Local Bluetooth control for <strong>app-capable ULTIMEA soundbars</strong>, with Poseidon D80 Boom (U2623) as the first hardware-verified model.<br>
  No ULTIMEA cloud account, phone app, or internet connection is required after installation.
</p>

<p align="center">
  <img alt="Release" src="https://img.shields.io/badge/release-2026.09.02-blue">
  <img alt="Home Assistant 2026.7+" src="https://img.shields.io/badge/Home%20Assistant-2026.7%2B-41BDF5">
  <img alt="HACS" src="https://img.shields.io/badge/HACS-Custom-41BDF5">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
</p>

> [!IMPORTANT]
> This is an **unofficial community integration**. It is not affiliated with, endorsed by, or supported by ULTIMEA. ULTIMEA and Poseidon are trademarks of their respective owners.

## Supported devices

| Device/protocol | Status |
| --- | --- |
| ULTIMEA Poseidon D80 Boom (U2623) | ✅ Hardware verified |
| Other ULTIMEA devices that pass the APK common/custom protocol probe | 🧪 Experimental, capability-driven |

The integration is no longer a D80 model-name allow-list. It discovers likely ULTIMEA advertisements, selects either the APK `8D11/8D22` common transport or the `8D55/8D66` custom-common transport, asks the device for its own model/protocol information, fetches the raw app capability block when available, and probes safe read-only state commands. Only capability-proven entities are created.

The APK snapshot contains explicit code paths/model strings for **Apollo B60/B70, Nova S50/S70/S80, Poseidon M70d/M80/M90V**, but those names are **not** claimed as hardware-verified. New models are allowed to prove protocol compatibility even when their name does not exist in this APK version. See [`docs/APK_PROTOCOL_FINDINGS.md`](docs/APK_PROTOCOL_FINDINGS.md).

## Features

The lists below are the **verified D80 Boom feature set**. On other models, Home Assistant only creates a control after its corresponding safe GET command succeeds with a known response shape.

### Media player

- Power on/off
- Absolute volume
- Volume up/down in native device steps (when capability-proven)
- Mute/unmute
- Sources: **eARC, HDMI, Optical, AUX, Bluetooth, USB**
- Sound modes: **Movie, Music, Voice, Sport, Night, Game**

### Configuration entities

- Display brightness: **Dim, Low, Medium, Normal, High**
- Screen timeout: **Never, 5 s, 30 s, 60 s**
- Prompt sound: **None, Low, Medium, High**
- Automatic standby: **Never, 15/30/60 min, 4/8/12/24/48 h**

### Integration behavior

- Automatic Bluetooth discovery
- Home Assistant host Bluetooth and connectable Bluetooth proxies
- Device-side model/protocol identification (no hard-coded model allow-list)
- Device serial and firmware detection
- Full state query during setup and reconnect
- Push updates from the soundbar while connected
- Command acknowledgement validation
- State-query verification if an immediate ACK is missed
- Persistent and on-demand Bluetooth connection modes
- Automatic unavailable-device heartbeat/recovery through Home Assistant's Bluetooth manager
- Diagnostics with identifying data redacted
- English, German, and Greek translations

## Installation

### HACS

Until the repository is accepted into the default HACS catalog, add it as a custom repository:

1. Open **HACS → Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/Chreece/HA-ULTIMEA`.
4. Select category **Integration**.
5. Install **ULTIMEA**.
6. Restart Home Assistant.

Then open **Settings → Devices & services**. A powered/advertising compatible ULTIMEA soundbar should be discovered automatically. You can also select **Add Integration → ULTIMEA**.

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

## Configuration

The setup flow verifies the ULTIMEA app protocol over BLE and capability-probes the soundbar before creating the entry. The device title is based on the reported model and serial suffix, while the Bluetooth address is retained as the discovery key so Home Assistant can suppress duplicate discoveries immediately.

The integration options contain:

| Option | Default | Purpose |
|---|---:|---|
| Keep Bluetooth connection open | On | Enables immediate push updates from the physical remote/device |
| On-demand disconnect delay | 15 s | Releases the BLE connection for the official app after a command |
| Maximum protocol volume | 100 | Maps the device integer volume to Home Assistant's `0.0–1.0` volume scale |
| Unavailable heartbeat interval | 30 s | Retries only this configured soundbar while unavailable and refreshes state when it returns |

If your soundbar firmware uses a different maximum volume, change **Maximum protocol volume** in the integration options.

## State synchronization

When Home Assistant connects, the integration actively reads each capability-proven current state instead of waiting for the next change. It queries:

- power
- mute
- volume
- source
- sound mode
- display brightness
- screen timeout
- prompt sound
- automatic standby
- model
- serial
- firmware

While the BLE connection remains open, valid ULTIMEA notifications update the entities without polling. If Home Assistant marks the soundbar unavailable (or a persistent BLE link drops), an unavailable-only heartbeat retries that configured device at the configured interval and performs a full refresh as soon as communication returns.

## Bluetooth routing

The integration uses Home Assistant's shared Bluetooth manager. It does **not** start or stop global Bluetooth scanning and does not hard-code a local adapter. The unavailable heartbeat uses the same manager and targets only the configured soundbar address.

Home Assistant can therefore select a suitable connectable route from supported local adapters or Bluetooth proxies. For the most responsive state updates, keep the connection open. If the ULTIMEA phone app needs frequent access to the soundbar, on-demand mode may be preferable.

## Diagnostics

Open:

**Settings → Devices & services → ULTIMEA → device → ⋮ → Download diagnostics**

The diagnostic payload includes runtime state, availability, RSSI, and identity information useful for bug reports. Bluetooth address and serial are redacted.

When opening an issue, include:

- Home Assistant version
- ULTIMEA integration version
- model and firmware shown by Home Assistant
- whether the connection is local Bluetooth or a Bluetooth proxy
- diagnostics
- relevant Home Assistant logs

## Troubleshooting

### Device is discovered but cannot be added

Make sure the soundbar is powered and not exclusively connected to the ULTIMEA app. The setup flow must connect once to verify the ULTIMEA app protocol and read the device-reported model.

### Entities are unavailable or unknown after restart

The integration performs a complete read after connecting. If the soundbar is out of range, powered down, or another client owns the BLE connection, state remains unavailable until Home Assistant can reconnect.

### The ULTIMEA phone app cannot connect

Disable **Keep Bluetooth connection open** in the integration options. Home Assistant will connect when needed and release the soundbar after the configured delay.

### A previously configured D80 is discovered again

Release `2026.09.02` keeps the Bluetooth address as the config-entry discovery identity and the device serial as registry metadata, preventing the duplicate-discovery behavior seen in early development builds.

## Currently not implemented

The following controls are intentionally **not guessed** and will be added only after their app commands are captured and verified on hardware:

- Bass
- Mid
- Treble
- Surround level
- X-Upmix
- Custom/advanced EQ
- Firmware OTA

## Protocol documentation

The reverse-engineered and hardware-verified BLE frame format and command table are documented in [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

## Privacy

Control is local over Bluetooth. The integration does not require ULTIMEA credentials, does not call ULTIMEA cloud APIs, and does not intentionally transmit device state outside Home Assistant.

## Contributing

Bug reports, additional ULTIMEA model/firmware observations, protocol captures, translations, and tested support for additional ULTIMEA models are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Release history

See [`CHANGELOG.md`](CHANGELOG.md).

## License

MIT. See [`LICENSE`](LICENSE).
