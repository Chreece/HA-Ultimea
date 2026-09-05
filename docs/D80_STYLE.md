# D80 Custom Style: labelled capture, protocol and exposure

Source: `d80-postaction-decoded-20260905-110322.json` (2026-09-05, ACTION_THEN_ENTER capture).
Source SHA-256: `95bce0fc53c038d896490bad85707d4d992b72189c8d5f9a766721be66fe43ad`.
The earlier `D80-profile08-recovered-analysis-20260905.md` had unnamed A/B
samples. The later source above explicitly labels all four corners. Do not
retroactively assign names to the earlier samples; use the later labelled frames.
The public regression fixture contains only relevant labels and protocol frames,
not the phone bugreport or unrelated device/account information.

## Observed wire behavior

`GROUP_CONTROL=0x02`, `CMD_SOUND_MODE=0x04`.
`08` selects Style and returns a full 41-byte curve. A full curve is
`profile:u8 + 10 * (frequency_hz:u16le + gain_tenths_db:i16le)`.
Every listed full write has an identical device echo, and both frame checksums
validate. Gains below are dB, not whole-byte or integer-dB approximations.

| Captured action | 31 | 62 | 125 | 250 | 500 | 1000 | 2000 | 4000 | 8000 | 16000 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| STYLE_BASS_CORNER | 5.5 | 5.0 | 2.5 | 0.0 | 0.0 | -3.5 | -5.0 | -5.0 | 0.0 | 0.0 |
| STYLE_ROCK_CORNER | 5.0 | 3.5 | -3.0 | 5.0 | -2.0 | 1.5 | 3.5 | 4.0 | 4.5 | 4.5 |
| STYLE_POP_CORNER | 4.0 | 3.5 | 2.0 | 0.0 | -2.0 | 0.0 | 2.5 | 3.5 | 3.5 | 4.0 |
| STYLE_CLASSICAL_CORNER | 0.0 | 0.0 | 0.0 | 3.5 | 3.5 | 3.5 | 0.0 | -2.0 | -2.5 | -2.5 |
| STYLE_RESET_CENTER_2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Home Assistant behavior

Style is a media-player sound-mode choice. Four named buttons apply the captured
corner curves. Style Reset applies the recorded all-zero center curve and selects
Style; it never sends a device/factory reset command. These are stateless actions,
not a persistent preset selector. Ten diagnostic sensors expose the confirmed
Style gains; Custom EQ number entities remain for profile 07 only.

Only complete, valid profile-08 replies/notifications supply Style gains. The
media-player `style_preset` attribute matches the entire captured gain tuple;
a non-matching confirmed curve is `custom`, never the nearest named preset.
Unknown/absent values are not zeros. Mode changes, power-off and disconnect clear
custom-profile values. No restored HA state is treated as device evidence.

After HA has fully started, and after reconnect/recovery, a complete state refresh
runs. Background profile readback is conditional on a fresh current-mode response
for the same profile, rechecked immediately before the profile request. No fresh
confirmation means no profile activation and unavailable curve values. This
conditional implementation is not a claim that every D80 firmware reports
active Style through INFO 01:08; that hardware readback coverage remains limited.

Sound-mode/curve operations are serialized, and reads wait for a matching full
profile rather than accepting the one-byte mode acknowledgment. Writes require
exact full-payload echoes. The Bluetooth safe-code handshake is still performed
before dependent commands, once per session, including concurrent callers.

## Still not claimed

The four corner curves do not determine the app's continuous XY interpolation.
There are no synthetic Style X/Y sliders, and Style Bass is not the physical
remote's separate bass-level control. No extra tone/surround/codec commands are
introduced by this change.

## Captured frames

`STYLE_BASS_CORNER` TX:

```text
aa 29 00 02 04 08 1f 00 37 00 3e 00 32 00 7d 00 19 00 fa 00 00 00 f4 01 00 00 e8 03 dd ff d0 07 ce ff a0 0f ce ff 40 1f 00 00 80 3e 00 00 07
```

`STYLE_BASS_CORNER` RX:

```text
bb 29 00 02 04 08 1f 00 37 00 3e 00 32 00 7d 00 19 00 fa 00 00 00 f4 01 00 00 e8 03 dd ff d0 07 ce ff a0 0f ce ff 40 1f 00 00 80 3e 00 00 07
```

`STYLE_ROCK_CORNER` TX:

```text
aa 29 00 02 04 08 1f 00 32 00 3e 00 23 00 7d 00 e2 ff fa 00 32 00 f4 01 ec ff e8 03 0f 00 d0 07 23 00 a0 0f 28 00 40 1f 2d 00 80 3e 2d 00 16
```

`STYLE_ROCK_CORNER` RX:

```text
bb 29 00 02 04 08 1f 00 32 00 3e 00 23 00 7d 00 e2 ff fa 00 32 00 f4 01 ec ff e8 03 0f 00 d0 07 23 00 a0 0f 28 00 40 1f 2d 00 80 3e 2d 00 16
```

`STYLE_POP_CORNER` TX:

```text
aa 29 00 02 04 08 1f 00 28 00 3e 00 23 00 7d 00 14 00 fa 00 00 00 f4 01 ec ff e8 03 00 00 d0 07 19 00 a0 0f 23 00 40 1f 23 00 80 3e 28 00 e0
```

`STYLE_POP_CORNER` RX:

```text
bb 29 00 02 04 08 1f 00 28 00 3e 00 23 00 7d 00 14 00 fa 00 00 00 f4 01 ec ff e8 03 00 00 d0 07 19 00 a0 0f 23 00 40 1f 23 00 80 3e 28 00 e0
```

`STYLE_CLASSICAL_CORNER` TX:

```text
aa 29 00 02 04 08 1f 00 00 00 3e 00 00 00 7d 00 00 00 fa 00 23 00 f4 01 23 00 e8 03 23 00 d0 07 00 00 a0 0f ec ff 40 1f e7 ff 80 3e e7 ff 2f
```

`STYLE_CLASSICAL_CORNER` RX:

```text
bb 29 00 02 04 08 1f 00 00 00 3e 00 00 00 7d 00 00 00 fa 00 23 00 f4 01 23 00 e8 03 23 00 d0 07 00 00 a0 0f ec ff 40 1f e7 ff 80 3e e7 ff 2f
```

`STYLE_RESET_CENTER_2` TX:

```text
aa 29 00 02 04 08 1f 00 00 00 3e 00 00 00 7d 00 00 00 fa 00 00 00 f4 01 00 00 e8 03 00 00 d0 07 00 00 a0 0f 00 00 40 1f 00 00 80 3e 00 00 0f
```

`STYLE_RESET_CENTER_2` RX:

```text
bb 29 00 02 04 08 1f 00 00 00 3e 00 00 00 7d 00 00 00 fa 00 00 00 f4 01 00 00 e8 03 00 00 d0 07 00 00 a0 0f 00 00 40 1f 00 00 80 3e 00 00 0f
```

`CUSTOM_STYLE_TAB` TX:

```text
aa 01 00 02 04 08 b8
```

`CUSTOM_STYLE_TAB` RX:

```text
bb 29 00 02 04 08 1f 00 00 00 3e 00 00 00 7d 00 00 00 fa 00 00 00 f4 01 00 00 e8 03 00 00 d0 07 00 00 a0 0f 00 00 40 1f 00 00 80 3e 00 00 0f
```
