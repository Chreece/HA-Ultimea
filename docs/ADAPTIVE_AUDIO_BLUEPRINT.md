# ULTIMEA Adaptive Room Audio blueprint

`adaptive_room_audio.yaml` is a room-aware Home Assistant automation blueprint for
ULTIMEA soundbars. It is designed to cooperate with manual control instead of
continuously forcing one fixed configuration.

## What it controls

The blueprint has three independent feature switches:

- **Volume follow** — normal/quiet learned volume, direct ducking for room events,
  and smooth quiet-hours boundary fades.
- **Night mode** — selects ULTIMEA **Night** during quiet hours or while a selected
  night-mode boolean/binary sensor is on.
- **EQ follow** — selects **Movie, Music, Voice, Sport, or Game** from the content
  of media players associated with the soundbar's room.

A soundbar is only written while its Home Assistant media-player entity is `on`.
Unavailable, unknown and powered-off bars are skipped.

## Audio-input selectors

You can optionally select one `input_select` or `select` entity for each soundbar
area. Home Assistant's entity picker can be searched by the entity's friendly
name/label; the stored blueprint value remains the stable entity ID. This removes
the need to hard-code a particular `input_select.*` ID.

Source selectors are intentionally **zone-local**:

- assign the selector and ULTIMEA media player to the same Home Assistant area;
- exactly one selector in that area is required before the blueprint writes a
  source;
- selectors without an area are not treated as global;
- multiple matching selectors are treated as ambiguous and are ignored;
- supported values are the soundbar's reported sources (`eARC`, `HDMI`, `Optical`,
  `AUX`, `Bluetooth`, `USB`) plus common aliases such as `ARC`, `SPDIF`, and `BT`.

Source follow is event-driven. A manual source choice is not continuously fought;
the blueprint acts again only when the configured selector changes, Home Assistant
starts, or that soundbar turns on.

## Minimum and maximum volume

Each endpoint can be configured as a fixed **0–100%** number and can optionally
be overridden by a numeric Home Assistant entity. Supported entity domains are
`input_number`, `number`, and `sensor`. Entity values may be expressed as either
`0..1` or `0..100`; the blueprint normalizes them automatically.

**Learn min/max from manual volume changes** is an explicit option and is disabled
by default. When enabled:

- a manual volume change in a minimum-volume regime updates the selected minimum
  entity when it is an `input_number` or writable `number`;
- a manual volume change in normal operation updates the selected maximum entity
  under the same rule;
- numeric `sensor` sources and fixed numeric values are read-only and are never
  mutated;
- manual changes during a quiet-hours fade do not learn either endpoint. They
  interrupt that fade instead.

For different rooms with independent dynamic endpoints, create separate blueprint
instances and use separate numeric entities.

## Quiet hours (ώρες κοινής ησυχίας)

Quiet hours may cross midnight, for example `22:00` to `07:00`.

- Normal operation targets the learned maximum.
- Quiet hours target the learned minimum.
- **Before** quiet hours, the configured transition duration linearly fades from
  maximum to minimum.
- **After** quiet hours, the configured transition duration linearly fades from
  minimum to maximum.
- The fade is stepped every five seconds. If the user changes the soundbar volume during the fade, the fade stays stopped for that soundbar for the rest of the transition window. A direct minimum-volume condition such as TTS can still override while it is active.
- When automation later needs to return from ducking or retake a target after an interrupted boundary fade, the **Guarded handoff / restore duration** is used instead of one abrupt volume jump. The handoff also uses fixed five-second steps and each step is allowed only while the observed volume still matches the previous expected step. A manual/external change therefore aborts the handoff. Queued intermediate volume events are checked against the current live volume, so stale self-generated steps cannot be learned later as manual changes.
- If an automation-originated duck ends while a quiet-boundary fade is already active, recovery is limited to one normal boundary-fade step at a time rather than jumping directly to the current scheduled point.
- TTS, active binary conditions, Assist activity, list-state conditions, and a
  night-mode boolean switch to minimum volume immediately. Those non-time
  transitions are deliberately not faded.

If quiet start and quiet end are identical, quiet hours and their boundary fades
are disabled.

## Room matching

Area assignment is important. The blueprint compares each ULTIMEA media player
with the selected condition/content entities using Home Assistant areas.

For binary sensors, input booleans, TTS media players, Assist satellites and
connected content media players:

- an entity in the **same area** affects that soundbar;
- an entity with **no area** is treated as global;
- an entity in a different area does not affect that soundbar.

## Room-list entities: state and attributes

Some installations already maintain entities that describe which rooms are active.
The blueprint can consume a selected entity from both its **state** and its
**attributes**:

- the state may be a comma-separated string;
- an attribute may be a list/tuple-like value;
- an attribute may be a comma-separated string.

Each token may be an area ID, area name, or entity ID whose assigned Home Assistant
area identifies the room. `all` and `*` apply to every selected soundbar. Other
attributes are ignored unless they are list-like or contain commas.

Example state:

```text
master_bedroom,kids_room
```

Example attribute:

```yaml
rooms:
  - master_bedroom
  - kids_room
```

When the selected source updates, matching soundbars recalculate their room policy.

## TTS and Assist ducking

Selected TTS/announcement media players request minimum volume while they are
`playing` or `buffering`.

Selected `assist_satellite` entities request minimum volume whenever their state
is not `idle` (for example listening, processing, or responding).

## Night mode behavior

Night mode is requested when either:

- the current time is inside quiet hours; or
- a selected night-mode `input_boolean`/`binary_sensor` is on for the room.

Night mode is event-driven rather than continuously forced. If the user manually
changes the ULTIMEA sound mode after the automation has applied Night, the
blueprint does not immediately change it back. It waits until the room/night
context changes again.

When Night ends:

- with EQ follow enabled, the current connected content is classified and the
  matching mode is selected;
- otherwise the configured normal sound mode is restored (or left unchanged if
  **No change** is selected).

## EQ/content follow

Select the media players physically/logically connected to the soundbar, such as a
TV, Android TV box, game console bridge, Kodi/Plex/Jellyfin player, or Music
Assistant player. The blueprint combines their state with common metadata:

- `app_name`
- `media_title`
- `media_series_title`
- `media_album_name`
- `media_artist`
- `media_content_type`
- `media_channel`
- `media_playlist`
- `source`

The text is compared with editable keyword lists for **Game, Sport, Voice, Music,
and Movie** (in that priority order). Only modes reported in the ULTIMEA entity's
`sound_mode_list` are sent.

Like Night mode, EQ follow is event-driven. A manual sound-mode change is not
periodically overwritten; a new connected-content/classifier event is needed
before automatic EQ selection happens again.

## Optional AI / snapshot classification

There is no universal Home Assistant action for "take a screenshot and classify
what is playing" across every camera/TV/LLM integration. The blueprint therefore
provides a provider-neutral hook instead of hard-coding one vendor.

1. Select one or more **content classifier entities**. Their state (or common
   `classification`, `content_type`, `label`, or `result` attribute) should contain
   a label/description that the EQ keyword rules can understand.
2. Optionally configure the **snapshot / AI classification actions** input. Those
   actions run when a connected media player changes.
3. The custom action sequence may take a snapshot, call the user's preferred AI or
   vision integration, and update a selected classifier entity.
4. The blueprint then consumes that classifier together with ordinary media-player
   metadata.

This keeps the core blueprint local and integration-agnostic while still allowing
AI-assisted recognition where the user's Home Assistant installation supports it.

## Automatic installation

The blueprint is bundled inside the ULTIMEA custom integration. When the ULTIMEA
integration loads, it automatically installs the blueprint at:

```text
/config/blueprints/automation/ultimea/adaptive_room_audio.yaml
```

No separate blueprint import is required for normal HACS/manual integration
installations once ULTIMEA has loaded. HACS itself does not execute integration
code at download time, so on a brand-new installation with no ULTIMEA config entry
the blueprint appears when the integration is first loaded (for example when a
soundbar is added/discovered). Existing configured installations get it on the
next Home Assistant start/reload after updating ULTIMEA.

Updates are deliberately safe:

- a blueprint created by ULTIMEA is automatically updated while it remains
  unchanged by the user;
- an existing byte-identical manual copy is safely adopted and can receive future
  bundled updates;
- a user-modified or otherwise different existing blueprint is never overwritten.

The public GitHub blueprint remains available as a manual fallback:

```text
https://github.com/Chreece/HA-Ultimea/blob/master/blueprints/automation/ultimea/adaptive_room_audio.yaml
```

After creating the automation, use **Run actions** once if you want the policy to
be applied immediately rather than waiting for the next relevant event. Volume
follow also performs a one-minute reconciliation for recovery and initialization.
