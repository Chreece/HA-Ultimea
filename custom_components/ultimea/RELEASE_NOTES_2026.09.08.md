# ULTIMEA 2026.09.08

## Adaptive Room Audio blueprint

This release adds the **ULTIMEA Adaptive Room Audio** Home Assistant automation blueprint. It supports room-aware quiet hours (ώρες κοινής ησυχίας), smooth before/after quiet-hour volume transitions, immediate TTS/Assist/binary/list-state ducking, Night mode, connected-content EQ follow, optional AI/snapshot classification actions, and persistent user-learned minimum/maximum volume through `input_number` helpers.

## Automatic installation

The blueprint is now bundled inside the integration and is installed automatically to:

```text
/config/blueprints/automation/ultimea/adaptive_room_audio.yaml
```

when the ULTIMEA integration loads. Existing ULTIMEA-managed copies update automatically only while they remain unchanged. A byte-identical pre-existing manual copy can be safely adopted. Any user-modified or otherwise different blueprint is preserved and never overwritten.

HACS itself does not execute integration code at download time, so a brand-new installation with no ULTIMEA config entry receives the blueprint when ULTIMEA is first loaded. Existing configured installations receive it on the next Home Assistant start/reload after updating.

## Safety and tests

- Blueprint file I/O runs in Home Assistant's executor and cannot block the event loop.
- Blueprint-install errors do not prevent the soundbar integration from loading.
- The Automation blueprint cache is reset after a successful install/update when Automation is already loaded.
- Regression tests cover first install, unchanged reload, safe managed update, preservation of user edits, adoption of identical manual copies, and byte-for-byte synchronization between the public and bundled blueprint copies.
