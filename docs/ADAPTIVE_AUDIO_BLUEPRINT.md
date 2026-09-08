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

## Learned minimum and maximum volume

Home Assistant blueprints cannot rewrite their own numeric inputs. To make manual
volume choices persistent, the blueprint therefore uses two `input_number`
helpers:

- one for the learned **minimum** volume;
- one for the learned **maximum** volume.

The helpers can use either `0..1` or `0..100`; the blueprint detects the helper's
scale from its configured maximum.

When the soundbar volume changes away from the value calculated by the automation:

- during quiet hours or another low-volume condition, the new value becomes the
  learned minimum;
- during normal operation, the new value becomes the learned maximum.

The automation then uses the newly learned value instead of fighting the user's
choice. Run separate blueprint instances (with separate helpers) when rooms need
independent learned limits.

## Quiet hours (ώρες κοινής ησυχίας)

Quiet hours may cross midnight, for example `22:00` to `07:00`.

- Normal operation targets the learned maximum.
- Quiet hours target the learned minimum.
- **Before** quiet hours, the configured transition duration linearly fades from
  maximum to minimum.
- **After** quiet hours, the configured transition duration linearly fades from
  minimum to maximum.
- The fade is stepped every five seconds.
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

## Comma-list entities

Some installations already maintain sensors whose state is a dynamic comma-separated
list. The blueprint can consume those directly.

Each token may be:

- an area ID, such as `living_room`;
- an area name, such as `Living Room`;
- an entity ID whose Home Assistant area identifies the room;
- `all` or `*` to affect every selected soundbar.

Example state:

```text
master_bedroom,kids_room
```

When the list changes, matching soundbars immediately recalculate their volume.

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

## Import

Use Home Assistant's blueprint import UI with:

```text
https://github.com/Chreece/HA-Ultimea/blob/master/blueprints/automation/ultimea/adaptive_room_audio.yaml
```

After creating the automation, use **Run actions** once if you want the policy to
be applied immediately rather than waiting for the next relevant event. Volume
follow also performs a one-minute reconciliation for recovery and initialization.
