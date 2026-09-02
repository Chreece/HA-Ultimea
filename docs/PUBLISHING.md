# Publishing checklist

This repository is structured for HACS as a Home Assistant integration.

## GitHub repository settings

HACS requires the repository to be public, have Issues enabled, have a concise description, and have repository topics.

Recommended description:

> Local Bluetooth control for ULTIMEA Poseidon D80 Boom soundbars in Home Assistant.

Recommended topics:

- `home-assistant`
- `hacs`
- `custom-component`
- `ultimea`
- `poseidon-d80`
- `bluetooth`
- `soundbar`
- `local-control`

## Before releasing 2026.09.02

1. Push the repository to `https://github.com/Chreece/HA-ULTIMEA`.
2. Ensure the **Validate** and **Tests** workflows pass.
3. Confirm Issues are enabled and the repository has a description/topics.
4. Create a **GitHub Release**, not only a tag, named/tagged `2026.09.02`.
5. Use `RELEASE_NOTES_2026.09.02.md` as the release body.
6. Add the repository to HACS as a custom integration and perform a clean install test.
7. If submitting to the default HACS catalog, follow the current HACS inclusion process after HACS and hassfest pass.

## HACS structure

```text
custom_components/
└── ultimea/
    ├── __init__.py
    ├── manifest.json
    ├── brand/
    └── ...
hacs.json
README.md
```

Only one integration exists below `custom_components/`.
