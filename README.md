<!-- ko-fi-support -->
<p align="center">
  <a href="https://ko-fi.com/chreece">
    <img src="https://raw.githubusercontent.com/Chreece/pir2ha/main/.github/ko-fi-banner.svg" alt="Support Chreece on Ko-fi" width="600">
  </a>
</p>

<p align="center">
  <img src="custom_components/ultimea/brand/logo.png" alt="ULTIMEA for Home Assistant" width="640">
</p>

<h1 align="center">ULTIMEA for Home Assistant</h1>

<p align="center">
  Local Bluetooth control for <strong>app-capable ULTIMEA soundbars</strong>, with Poseidon D80 Boom (U2623) as the first hardware-verified model.<br>
  No ULTIMEA cloud account, phone app, or internet connection is required after installation.
</p>

<p align="center">
  <img alt="Release" src="https://img.shields.io/badge/release-2026.10.10.2-blue">
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
| ULTIMEA Poseidon D70 | 🧪 Reporter-confirmed: volume, ARC/Optical/Bluetooth/AUX/USB, mute and power-off; BLE power-on unavailable |
| ULTIMEA Aura A40 (V56) | 🧪 Confirmed BLE discovery and read-only state; no verified write controls |
| Other ULTIMEA devices that pass the APK common/custom protocol probe | 🧪 Experimental, capability-driven/read-only writes unless proven |

The integration is not a D80 model-name allow-list. It discovers likely ULTIMEA advertisements, selects the app protocol transport, asks the device for its model/protocol information, fetches the raw capability block when available, and probes safe read-only states. Writable controls are profile-gated and are exposed only when the exact model has a proven wire mapping. The D70 profile exposes only reporter-confirmed setters; Bluetooth power-on and uncaptured audio/EQ controls remain disabled.

## Aura A40 V56 read-only support

The [reporter's diagnostic](https://github.com/Chreece/HA-Ultimea/issues/5) confirms the Aura A40, common `8D11/8D22` Bluetooth transport, protocol v1, firmware V56, a working heartbeat and eight responsive state reads. The observed state is power on, volume 13, Optical (`INFO 01:06=01`) and Music (`INFO 01:08=02`).

ULTIMEA confirms the A40 has **Optical, Bluetooth, AUX and USB**, with **no HDMI/ARC**. The model-specific source decoder restricts INFO readback to these four sources. Optical (`01`) was seen in the diagnostic; the other INFO values are app-derived, supported by the capability bits and the physical input list. Unknown codes are never misrepresented as HDMI/ARC.

Home Assistant exposes three ordinary, visible **read-only sensors** for **Volume, Input and Sound mode**, plus the existing media-player state. Sensor values come from actual device read responses and notifications (reload/reconnect refreshes state).

**A40 write commands are not proven by this diagnostic.** No D80/D70 setters are inherited, so all A40 control buttons remain intentionally disabled. No further technical testing is required from the reporter for this safe, read-only implementation.

## Poseidon D70 partial support

Issue #4 now confirms the exact protocol model string `Poseidon D70` and
the following CONTROL writes from a working physical unit:

- Absolute volume: `02:03` (0–100 observed).
- Source: `02:02 00` ARC, `01` Optical, `02` Bluetooth,
  `03` AUX and `04` USB.
- Mute: `02:0A 00` on, `02:0A 01` off.
- Power **off**: `02:09 00`.

The D70 source enum is model-specific: ARC uses `00`, not the D80's
eARC setter value `10`. The input selector offers exactly ARC,
Optical, Bluetooth, AUX and USB; HDMI is not exposed.

**Power on is intentionally not offered.** The D70 stops accepting BLE
connections after shutdown. Power-off **does** acknowledge CONTROL
`02:09 00` before disconnecting: the PCAP contains both the `AA` request
and matching `BB` response approximately 150 ms later. The integration
therefore awaits the verified acknowledgement, after the standard
safe-code session. A failed GATT write, lost acknowledgement or early
disconnect cannot falsely mark the D70 as off. D80's separate,
hardware-verified power behavior is unchanged.

The anonymized PCAP was attached directly in the conversation as
`ultimad70_anon.zip` and independently parsed: 249 BLE packets and 139
valid ULTIMEA frames. It confirms **firmware V50**, all five D70 source
writes and replies, mute/unmute replies, volume 0/9/100 replies and
the shutdown acknowledgement. A sanitized, address/serial-free
`tests/fixtures/d70_pcap_evidence.json` records these findings.

The INFO source decoder is restricted to the D70's documented inputs
(no HDMI). EQ and sound-mode writes remain disabled because the capture
does not prove them. See [issue #4](https://github.com/Chreece/HA-Ultimea/issues/4).
The D80 and Aura A40 profiles remain independent.

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

## Adaptive Room Audio blueprint

The repository includes [`ULTIMEA Adaptive Room Audio`](blueprints/automation/ultimea/adaptive_room_audio.yaml), a room-aware automation blueprint that can:

- use fixed numeric min/max volume or optional numeric entity sources, with opt-in learning from manual volume changes;
- bind an optional `input_select`/`select` audio-input selector to each soundbar by Home Assistant area; the picker is searchable by friendly label and ambiguous/unassigned selectors are ignored;
- map Assist Satellites and room/output media players to source routing, with optional separate upstream pause/resume controllers per input (for example Snapclient → AUX while MPD is paused/resumed only for the handoff); a newly playing mapped route is paused on the fast path before the rest of the policy work, and playback resumes only after the target input plus input-default EQ have settled;
- optionally give each ULTIMEA input a one-shot default sound mode, for example **AUX → Music** or **HDMI → Game**; later manual/content/EQ changes are accepted, while **Automatic / no input default** leaves mode selection entirely to the other rules and Night retains priority;
- give each soundbar area an optional numeric normal-volume entity, such as an `input_number` dashboard slider, while keeping the global maximum as a hard ceiling; source changes are clamped downward if hardware recalls a louder per-source volume;
- apply quiet hours (ώρες κοινής ησυχίας), including event-driven before/after boundary fades and guarded five-second-step handoff/restores without permanent polling triggers;
- lower volume immediately for selected binary conditions, room-list state/attribute sources, TTS playback, active Assist satellites, or a night-mode boolean;
- select **Night** during quiet conditions;
- follow connected-player content into **Movie, Music, Voice, Sport, or Game** only when each player is mapped to the soundbar's currently active input; classifier/AI results use the same current-input gate;
- respect manual ULTIMEA volume and sound-mode changes instead of continuously fighting them, including directional holds during quiet-hour fades and learning a new minimum/maximum when the user's change opposes the fade direction.

The blueprint is bundled with the integration and is automatically installed when
ULTIMEA loads at:

```text
/config/blueprints/automation/ultimea/adaptive_room_audio.yaml
```

No separate import is required for normal use. Existing managed copies are updated
only while unchanged; a user-modified or otherwise different blueprint is never
overwritten. A byte-identical manually imported copy can be safely adopted for
future bundled updates. When a managed blueprint changes after Home Assistant has
already loaded its Automation integration, ULTIMEA also reloads the live automation
definition after startup so an older expanded trigger set cannot remain active.

HACS itself does not execute custom-integration code at download time. On a new
installation with no ULTIMEA config entry yet, the blueprint therefore appears as
soon as ULTIMEA is first loaded (for example after the soundbar is added/discovered).
Existing configured installations get it on the next Home Assistant start/reload
after updating the integration.

The public GitHub blueprint remains available as a manual fallback:

```text
https://github.com/Chreece/HA-Ultimea/blob/master/blueprints/automation/ultimea/adaptive_room_audio.yaml
```

Minimum/maximum volume can be fixed values or optional numeric entity sources; writable `input_number`/`number` sources can also learn manual changes when enabled. See [Adaptive Room Audio blueprint documentation](docs/ADAPTIVE_AUDIO_BLUEPRINT.md) for configuration and behavior.

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

## ❤️ Voluntary support

This is a private hobby project maintained in my free time and provided independently of contributions.

If you enjoy the project and would like to send me a voluntary personal thank-you, you can use **[Ko-fi](https://ko-fi.com/chreece)**.

Contributions are completely optional and do **not** buy or guarantee features, support, development work, early access, priority, or any other service. This is not a charitable donation and no donation receipt is issued.
