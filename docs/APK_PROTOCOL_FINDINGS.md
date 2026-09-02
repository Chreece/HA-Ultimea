# APK-derived multi-model protocol findings

This document records only what is supported by the reverse-engineered official
ULTIMEA Android APK and the hardware capture used for the first release.

## Shared Bluetooth architecture found in the APK

The Flutter AOT binary contains both `LegacyDelegate` and `FrontierDelegate`.
Both expose high-level operations including `getProtocolVersion`,
`fetchAbilities`, volume, power, mute, input source, EQ, tone control and
surround controls.

The APK contains these BLE characteristic UUIDs:

- `27758d11-...` — common write
- `27758d22-...` — common notify
- `27758d33-...` — OTA write
- `27758d44-...` — OTA notify
- `27758d55-...` — custom-common write candidate
- `27758d66-...` — custom-common notify candidate

The D80 Boom hardware capture verified `8D11 -> 8D22` for normal control and
`AA` command / `BB` response framing. The integration now also detects
`8D55/8D66` because the APK labels a separate custom-common transport path.
That second path is APK-derived and not yet hardware-verified by this project.

## Model strings embedded in the APK snapshot

- Apollo B60
- Apollo B70
- Nova S50
- Nova S70
- Nova S80
- Poseidon M70d
- Poseidon M80
- Poseidon M90V

The verified Poseidon D80 Boom model was obtained dynamically from the device;
it was not present as a literal model string in this APK snapshot. Therefore
an APK string list is not a complete product catalog and is not used as an
allow-list.

## Capability vocabulary found in the APK

The binary contains capability/property names including `hasToneControl`,
`hasXupMix`, `hasSurround`, `hasSurroundVolume`,
`hasMultipleSurroundVolume`, `hasThxEqMode`, `hasAuraCast`,
`hasAuraCastChannelSetting`, `hasDisplayScreen`, `hasUSB`, `hasHDMI`,
`hasARC`, `hasAux`, `hasBluetooth`, `hasSignalInputSourceGet`,
`supportPowerOn`, `sceneSupported` and `isMediaControlSupported`.

The D80 startup capture also contains a zero-payload capability request:

```
AA 00 00 00 00 AA
```

with a boolean-looking byte array response. The integration stores this raw
array in diagnostics, but **does not assign names to byte positions** because
that field ordering has not yet been proven across models.

## Safe support policy

A marketing model name is no longer sufficient to accept or reject a device.
Setup now:

1. discovers a likely ULTIMEA device;
2. finds either common or custom-common GATT transport;
3. issues the read-only model query and requires a valid AA/BB response;
4. reads protocol version, serial and firmware when available;
5. calls the APK capability request when available;
6. probes only the already-decoded zero-payload state GETs;
7. creates only entities whose read path answered with a valid shape.

Poseidon D80 Boom remains the only `verified` profile. Other devices that pass
this protocol/capability probe are `experimental` rather than falsely claimed
as hardware-verified.
