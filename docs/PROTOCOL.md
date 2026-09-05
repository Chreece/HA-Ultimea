# Poseidon D80 Boom BLE protocol notes

Protocol documentation for ULTIMEA integration release `2026.09.05.1`.

The mappings below were recovered from the official ULTIMEA Android application and validated against a physical Poseidon D80 Boom. The integration remains capability-driven for other app-capable ULTIMEA models; D80-specific advanced controls are enabled only by the verified D80 profile.

## GATT

- Discovery service: `0000260a-0000-1000-8000-00805f9b34fb`
- Common service: `27758daa-bf3a-4ac6-bee5-6259ccb7c9b7`
- Common write: `27758d11-bf3a-4ac6-bee5-6259ccb7c9b7`
- Common notify: `27758d22-bf3a-4ac6-bee5-6259ccb7c9b7`
- Alternate app write: `27758d55-bf3a-4ac6-bee5-6259ccb7c9b7`
- Alternate app notify: `27758d66-bf3a-4ac6-bee5-6259ccb7c9b7`
- OTA service: `27758dff-bf3a-4ac6-bee5-6259ccb7c9b7`

OTA is intentionally not implemented.

## Frame

```text
AA LEN 00 GROUP CMD DATA... CHECKSUM   host -> soundbar
BB LEN 00 GROUP CMD DATA... CHECKSUM   soundbar -> host
```

Checksum for both directions:

```text
(0xAA + reserved + group + command + sum(data)) & 0xff
```

`LEN` is not included in the checksum. Notifications may contain stale padding after the declared frame length; parsers must honor `6 + LEN` rather than consuming the complete BLE notification buffer.

## Safe-code session `00:01`

The official app establishes a safe-code exchange before normal commands.

For one byte `b`:

```text
safe(b) = (MD5(bytes([b])).digest()[-1] + 5) & 0xff
```

APP request payload:

```text
[b, safe(b)]
```

Observed D80 firmware response:

```text
[b ^ 0xff, safe(b ^ 0xff)]
```

The integration validates the returned pair integrity. The first-byte complement relation is recorded diagnostically but is not required because static app analysis did not prove that the official app itself enforces that relation.

## Hardware-verified INFO group `0x01`

All are zero-payload queries.

| Function | Cmd | Response |
|---|---:|---|
| Protocol version | `01` | little-endian integer, captured `01 00` = 1.0 |
| Model | `02` | ASCII/NUL string |
| BLE MAC | `03` | 6 bytes |
| Serial | `04` | ASCII/NUL string |
| Firmware | `05` | little-endian integer |
| Source | `06` | eARC `00`, Optical `01`, Bluetooth `02`, AUX `03`, USB `04`, HDMI `05` |
| Volume | `07` | one-byte absolute volume |
| Sound mode | `08` | Movie `01`, Music `02`, Voice `03`, Sport `04`, Night `05`, Game `06`, Custom EQ `07` when active |
| Prompt sound | `0A` | None `00`, Low `01`, Medium `02`, High `03` |
| Screen timeout | `0C` | Never `00`, 5 s `01`, 30 s `02`, 60 s `03` |
| Power | `0D` | Off `00`, On `01` |
| Mute | `0E` | Muted `00`, unmuted `01` |
| Brightness | `0F` | configured brightness enum |
| Auto standby | `17` | current `uint16 LE` minutes + supported option list |
| X-Upmix | `18` | Off `00`, On `01` |

Responsive INFO commands `0B`, `10`, `11` and `12` remain unnamed and are not exposed as guessed entities.

## Hardware-verified CONTROL group `0x02`

| Function | Cmd | Data |
|---|---:|---|
| Device name | `01` | app-defined string payload |
| Source | `02` | Optical `01`, Bluetooth `02`, AUX `03`, USB `04`, HDMI `05`, eARC `10` |
| Volume | `03` | one-byte absolute volume |
| Sound mode / Custom curves | `04` | standard one-byte mode or 41-byte custom profile |
| Prompt sound | `06` | None `00`, Low `01`, Medium `02`, High `03` |
| Screen timeout | `08` | Never `00`, 5 s `01`, 30 s `02`, 60 s `03` |
| Power | `09` | Off `00`, On `01` |
| Mute | `0A` | Mute on `00`, mute off `01` |
| Display brightness | `0C` | Dim `01`, Low `02`, Medium `03`, Normal `04`, High `05` |
| Auto standby | `15` | two-byte little-endian minute count |
| X-Upmix | `16` | Off `00`, On `01` |

### X-Upmix ACK behavior

`02:16` changes the D80 state but does not provide a dependable same-command `02:16` echo. The verified implementation writes `02:16` and then reads authoritative `01:18` until the requested state is confirmed. Unrelated `02:0C` pushes may occur during this sequence and must not be treated as the X-Upmix ACK.

## Custom EQ and Custom Style

`02:04` is overloaded for standard sound modes and the D80 custom sound profiles.

A full custom profile is exactly 41 bytes:

```text
profile:u8 + 10 * (frequency_hz:uint16_le + gain_tenths_db:int16_le)
```

Frequencies:

```text
31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000 Hz
```

Gain range captured from the app is `-60..+60` tenths dB = `-6..+6 dB`.

- Profile `0x07` = **Custom Equalizer**. A one-byte `02:04 07` request returns the stored 41-byte profile, and full writes are echoed exactly by the D80. This is exposed by the integration.
- Profile `0x08` = **Custom Style** (the app's XY Style pad). The 41-byte format is proven, but an authoritative restart/reconnect getter for the active Style state has not been proven, so it is decoded but not exposed as a persistent HA sound mode.

## Capability block `00:00`

`fetchAbilities` returns a prefix of the app's `DHa` capability structure. The D80 capture contains 18 fields:

```text
0  hasLed
1  hasBass
2  hasSurround
3  haseARC
4  hasARC
5  hasHDMI
6  hasBluetooth
7  hasAux
8  hasUSB
9  hasDolbyAtmos
10 hasDolbyVision
11 hasBurnSN
12 hasOTA
13 chipCode
14 hasSingleLed
15 hasDisplayScreen
16 offStateBoot
17 hasCustomStandbyTime
```

The integration keeps the raw bytes and also exposes the recovered semantic names in the diagnostic Capabilities sensor. Missing later fields are omitted rather than interpreted as false.

## Intentionally not exposed

- Bass / Mid / Treble
- Surround level
- Incoming HDMI/eARC codec/format
- Firmware OTA
- Unknown INFO `0B/10/11/12`

These remain unimplemented because the D80 BLE state/control path has not been proven sufficiently to create reliable Home Assistant entities.
