# Poseidon D80 Boom BLE protocol notes

These commands were obtained from the official ULTIMEA Android application and then validated by direct BLE writes to a Poseidon D80 Boom. The integration performs its own model query before accepting a device, so the implementation is model-generic and contains no test-device address.

## GATT

- Discovery service: `0000260a-0000-1000-8000-00805f9b34fb`
- Common service: `27758daa-bf3a-4ac6-bee5-6259ccb7c9b7`
- Common write: `27758d11-bf3a-4ac6-bee5-6259ccb7c9b7` (`write-without-response`)
- Common notify: `27758d22-bf3a-4ac6-bee5-6259ccb7c9b7` (`notify`)
- Second/OTA service: `27758dff-bf3a-4ac6-bee5-6259ccb7c9b7`

## Frame

```text
AA LEN 00 GROUP CMD DATA... CHECKSUM   host -> D80
BB LEN 00 GROUP CMD DATA... CHECKSUM   D80 -> host
```

Checksum for both directions:

```text
(0xAA + reserved + group + command + sum(data)) & 0xff
```

`LEN` is not included in the checksum.

## Verified control group `0x02`

| Function | Cmd | Data |
|---|---:|---|
| Source | `02` | Optical `01`, Bluetooth `02`, AUX `03`, USB `04`, HDMI `05`, eARC `10` |
| Volume | `03` | one-byte absolute volume |
| Sound mode | `04` | Movie `01`, Music `02`, Voice `03`, Sport `04`, Night `05`, Game `06` |
| Prompt sound | `06` | None `00`, Low `01`, Medium `02`, High `03` |
| Screen timeout | `08` | Never `00`, 5 s `01`, 30 s `02`, 60 s `03` |
| Power | `09` | Off `00`, On `01` |
| Mute | `0A` | Mute on `00`, mute off `01` |
| Display brightness | `0C` | Dim `01`, Low `02`, Medium `03`, Normal `04`, High `05`; notification `00` means runtime screen-off |
| Auto standby | `15` | two-byte little-endian minute count; `0` = never |

## Safe identity/read group `0x01`

Zero-data queries used by the official app:

| Query | Cmd | Response |
|---|---:|---|
| Model | `02` | NUL-terminated ASCII, verified `Poseidon D80 Boom` |
| Serial | `04` | NUL-terminated ASCII device serial |
| Firmware | `05` | little-endian integer (`10` => `V10` on captured unit) |
| Mute state | `06` | current boolean mute state |
| Volume | `07` | current one-byte absolute volume |
| Source | `08` | current source enum |
| Prompt sound | `0A` | current prompt level enum |
| Display brightness | `0C` | current configured brightness enum |
| Power | `0D` | current power state |
| Sound mode | `0E` | current sound-mode enum |
| Screen timeout | `0F` | current timeout enum |
| Auto standby | `17` | current minutes (`uint16 LE`) followed by supported option list |

The official app emits these zero-payload queries during its normal device and settings initialization. The integration uses the same read path to build an initial state snapshot and to verify a write if its immediate control ACK is missed.
