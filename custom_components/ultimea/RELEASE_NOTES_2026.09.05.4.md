# ULTIMEA 2026.09.05.4

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
