# Contributing

Thanks for helping improve ULTIMEA for Home Assistant.

## Before opening an issue

1. Update to the latest release.
2. Restart Home Assistant after updating the custom integration.
3. Confirm the soundbar is a Poseidon D80 Boom (U2623).
4. Download integration diagnostics from Home Assistant.
5. Check Home Assistant logs for `custom_components.ultimea` messages.

## Bug reports

Please use the bug-report issue form. Include the Home Assistant version, integration version, D80 firmware, Bluetooth connection type, diagnostics, and reproducible steps.

Do not post unredacted Bluetooth addresses, serial numbers, tokens, or unrelated Home Assistant diagnostics publicly.

## Adding protocol support

Protocol additions must be based on observed traffic and then confirmed by a direct write/read test against hardware. Do not submit guessed command IDs or values.

When adding a command:

1. Document the observed official-app write in `docs/PROTOCOL.md`.
2. Add protocol constants/mappings without embedding a device address.
3. Add or update parser/command tests.
4. Verify state synchronization from the corresponding D80 notification/query.
5. Update translations and the README if a new entity is exposed.

## Code style

- Keep blocking work out of the Home Assistant event loop.
- Use Home Assistant's Bluetooth manager; do not create an independent global scanner.
- Do not stop/restart system Bluetooth as part of normal integration behavior.
- Keep device-specific protocol code separate from Home Assistant entity code.
- Prefer push updates; do not add polling when a safe protocol query or notification exists.

## Pull requests

Pull requests should be focused and include tests where practical. HACS validation, hassfest, and repository tests must pass.
