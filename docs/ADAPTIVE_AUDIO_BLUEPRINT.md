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

Ordinary volume, source-mode, and EQ writes require the ULTIMEA media-player
entity to be `on`. Source routing has one deliberate exception: when a mapped
media player is already `playing` or a mapped Assist Satellite is active, the
blueprint may call `media_player.turn_on` for an `off` soundbar so the requested
route can be applied. Unavailable/unknown bars are never commanded directly.

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

### Assistant and media-player source routing

Source routing supports both Assist Satellites and media players.

For assistants, select entities under **Assistants → soundbar input** and choose
one **Assistant input**. While a selected `assist_satellite` is in any active
state (anything other than `idle`, `unknown`, or `unavailable`), that input
takes priority for its target soundbar. When all selected assistants return to
`idle`, the blueprint immediately recalculates the normal media-player/fallback
route.

Assistant source routing is independent from the existing **Voice assistants**
selection used for volume ducking. You can select the same Assist Satellite in
both places when you want both behaviors.

Media-player routing remains intentionally simple: assign media players to the
ULTIMEA input they use. The blueprint exposes six entity groups:

- **Media players → eARC**
- **Media players → HDMI**
- **Media players → Optical**
- **Media players → AUX**
- **Media players → Bluetooth**
- **Media players → USB**

Put each media player in only one source group.

If the blueprint controls **one ULTIMEA soundbar**, no Home Assistant area
assignment is required for source routing: every mapped assistant/media player
controls that selected bar directly.

If the blueprint controls **multiple ULTIMEA soundbars**, areas are used only to
disambiguate which bar a mapped assistant/media player controls. In that case,
the assistant/player and target soundbar must share an area.

An active mapped assistant always has priority over media-player routing. While
the assistant remains active, media-player state changes cannot take the source
away from the Assistant input.

When no mapped assistant is active, a mapped media player entering `playing`
switches its target soundbar to that player's mapped source. If more than one
mapped media player affecting the same bar is playing, the player that most
recently entered the `playing` state wins.

When the winning media player requires a **real input change**, the blueprint
protects the beginning of playback with a guarded handoff:

1. send pause to that winning media player;
2. wait up to two seconds for Home Assistant to **confirm the player is actually
   `paused`**; if pause is rejected/ignored, abort before changing the soundbar;
3. after confirmation, allow a 150 ms guard;
4. request the new ULTIMEA source;
5. wait up to three seconds for the bar's live `source` attribute to confirm the
   requested input; if it never confirms, stop and leave the media player paused
   rather than lose its content;
6. allow another 500 ms for the confirmed input to settle;
7. apply that input's one-shot default sound mode when appropriate;
8. resume the same media player, but only if it is still `paused`.

No pause is inserted when the bar is already on the player's mapped input.

The temporary pause/resume naturally emits media-player state events. Those events
are debounced for three seconds: if playback has resumed, the pause-triggered
parallel routing run is discarded. A real pause/stop that remains in place still
recalculates routing, so the next most-recent still-playing mapped player can take
over automatically.

If no mapped assistant is active and no mapped media player is playing,
**Fallback source when no mapped assistant or media player is active** is used.
This is one global source selector (`eARC`, `HDMI`, `Optical`, `AUX`,
`Bluetooth`, `USB`, or `No change`) and does not use Home Assistant areas.
`No change` leaves the current source untouched. For backward compatibility, the
older area-paired audio-input selector is consulted only when this new fallback is
set to `No change`.

The rule is event-driven: it re-evaluates when a mapped media player or mapped
assistant changes state, when Home Assistant starts, when the soundbar turns on,
and when a soundbar returns from `unavailable`/`unknown` to a known state.

If a real mapped route is active while the soundbar is `off` — a media player is
already `playing` or an assistant is active — the blueprint turns the soundbar
on. The subsequent `off → on` state change starts a fresh routing run, which
reads live source/capability state before selecting the winning input and applying
that input's one-shot default sound mode. This also covers the case where the bar
was physically unavailable, comes back as `off`, and the source player was
already playing.

The fallback source and legacy audio-input selector **never power the soundbar
on by themselves**; wake-up is reserved for an actual active mapped source.

Example:

```text
media_player.tv            → eARC
media_player.game_console  → HDMI
media_player.music_player  → Bluetooth
```

With the TV and console both playing, whichever entered `playing` most recently
controls the source. When it stops, the other active player takes over.

### Per-input sound mode

Each physical ULTIMEA input has an optional sound-mode mapping:

- **Sound mode → eARC / ARC**
- **Sound mode → HDMI**
- **Sound mode → Optical**
- **Sound mode → AUX**
- **Sound mode → Bluetooth**
- **Sound mode → USB**

Each mapping can be **Automatic / no input default, Movie, Music, Voice, Sport,
Night, or Game** and defaults to **Automatic / no input default**.

A configured value is only the **starting/default mode for that input**. When this
blueprint itself routes the bar to a source, it applies that input's default in
the **same source-routing run**, immediately after the source command succeeds.
It does not depend on a second source-change event. For source changes made by
Home Assistant, the physical remote, or the ULTIMEA app, the source-change listener
seeds the default immediately on the source event; the later 750 ms wait is used
only for source-specific volume recall/clamping.

For example, **AUX → Music** selects Music when the bar enters AUX. If the user,
EQ/content classification, Night policy, or another automation later changes Music
to another mode, that new mode is accepted and the AUX default is not re-applied
until the bar leaves AUX and later comes back.

**Automatic / no input default** means the source change itself does not seed a
mode. The normal Night/EQ/content policy may therefore choose a mode immediately
from the other configured rules.

Only sound modes reported by that soundbar in `sound_mode_list` are sent, so a
mapping unsupported by another ULTIMEA model is safely ignored. ARC and eARC use
the same mapping.

Quiet/night policy has priority: if Night mode is enabled and quiet hours or a
configured night-mode entity are active, a source change requests **Night**
instead of the per-input default.

## Minimum and maximum volume

### Optional per-zone normal volume

You can select multiple numeric entities as **Per-zone normal-volume entities**.
For each ULTIMEA soundbar, the blueprint looks for exactly one selected numeric
entity in the same Home Assistant area:

- one match: that value becomes the soundbar's per-zone normal target, but it is
  always capped by the global maximum below;
- no match: the global maximum below is used;
- more than one match: the area is treated as ambiguous and the global maximum is
  used rather than guessing;
- an `input_number` helper is ideal when you want a persistent dashboard slider;
- writable `input_number`/`number` zone entities can learn manual normal-volume
  changes when learning is enabled; sensors remain read-only.

The minimum/quiet endpoint remains global. Quiet-hour fades are calculated from
each soundbar's effective zone maximum down to that shared minimum, so different
zones can follow the same quiet-hours policy without sharing their normal volume.

The shared minimum and global maximum keep the existing fixed numeric value plus
optional numeric-entity override behavior. **Maximum volume is always a hard
ceiling**: a per-zone normal-volume entity may lower that zone's normal target but
can never raise it above the configured global maximum. Supported domains are
`input_number`, `number`, and `sensor`, with automatic normalization of 0–1 and
0–100 values.

Changing soundbar source can make some hardware recall a source-specific volume.
The blueprint watches source changes, lets that hardware update settle briefly,
then clamps only downward when the recalled volume exceeds the effective maximum.
It never raises volume as part of source-change handling.

**Learn min/max from manual volume changes** is an explicit option and is disabled
by default. When enabled:

- a manual volume change in a minimum-volume regime updates the selected minimum
  entity when it is an `input_number` or writable `number`;
- a manual volume change in normal operation updates the selected maximum entity
  under the same rule;
- manual learning is **debounced for three seconds**: intermediate volume steps do
  not write the helper. Only the final volume that remains unchanged for three
  seconds is learned;
- the helper update produced by that learning is treated as a **learning echo**.
  It updates the saved min/max value but is not allowed to command the soundbar
  back to the previous volume. Deliberate helper changes from outside the learning
  path remain valid policy inputs;
- numeric `sensor` sources and fixed numeric values are read-only and are never
  mutated;
- during the **before-quiet decreasing fade**, a settled manual increase learns
  the writable minimum endpoint; a manual decrease is temporary and is not
  learned;
- during the **after-quiet increasing fade**, a settled manual decrease learns
  the writable maximum/zone endpoint; a manual increase is temporary and is not
  learned;
- endpoint learning during a fade still requires **Learn min/max from manual
  volume changes** and a writable `input_number`/`number`. The directional
  hold behavior itself works even when no writable endpoint is available.

For fully separate quiet/minimum endpoints or different schedules, create separate
blueprint instances. Per-zone normal volume no longer requires separate instances.

## Quiet hours (ώρες κοινής ησυχίας)

Quiet hours may cross midnight, for example `22:00` to `07:00`.

- Normal operation targets the learned maximum.
- Quiet hours target the learned minimum.
- **Before** quiet hours, the configured transition duration linearly fades from
  maximum to minimum.
- **After** quiet hours, the configured transition duration linearly fades from
  minimum to maximum.
- The fade is stepped every five seconds **inside one active fade run**. There is no permanent five-second automation trigger. Manual changes are directional rather than simply aborting the run:
  - **Before quiet hours (volume moving down):** if the user raises the volume, the fade stops lowering that bar and the settled value becomes the new minimum when learning is available. If the user lowers the volume, that lower value is held until the scheduled fade itself falls below it, then automatic lowering resumes.
  - **After quiet hours (volume moving up):** if the user raises the volume, that higher value is held until the scheduled fade itself rises above it, then automatic raising resumes. If the user lowers the volume, the fade stops raising that bar and the settled value becomes the new maximum/zone target when learning is available.
  - The active fade re-reads current min/max helpers on every five-second step, so a newly learned endpoint takes effect immediately inside the already-running transition.
  - Direct minimum-volume conditions such as TTS still override while active.
- When automation later needs to return from ducking or retake a target after an interrupted boundary fade, the **Guarded handoff / restore duration** controls that restore. A value of **0 disables the handoff transition** and required automatic restores are applied immediately. Non-zero handoffs use fixed five-second steps and each step is allowed only while the observed volume still matches the previous expected step. A manual volume change never starts a handoff and is left at the user's chosen value; a manual/external change during an existing handoff aborts it. Queued intermediate volume events are checked against the current live volume, so stale self-generated steps cannot be learned later as manual changes.
- If an automation-originated duck ends while a quiet-boundary fade is active, the guarded handoff projects to the point the scheduled fade will reach when the handoff completes; the active fade run resumes its five-second steps from there.
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

EQ/content follow is **input-aware**. A media player selected under **Devices
connected to the soundbar** is eligible only while the ULTIMEA bar is currently on
the same input that player is assigned to under **Media players → eARC / HDMI /
Optical / AUX / Bluetooth / USB**.

For example, if `media_player.tv` is selected under Connected content and under
**Media players → eARC**, its TV-program metadata may drive Movie/Music/Voice/etc.
only while the bar is actually on eARC/ARC. If the bar switches to AUX, that TV is
ignored until eARC/ARC becomes active again. To drive EQ on AUX, a Connected
content media player must also be assigned under **Media players → AUX**.

With one selected ULTIMEA bar, the input mapping is sufficient. With multiple bars,
the existing Home Assistant area match is also required to determine which bar the
media player belongs to.

The blueprint combines eligible players' state with common metadata:

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

Classifier entities and the optional AI/snapshot hook are subject to the same
current-input gate: they participate only when the current input has at least one
eligible Connected content media player. A classifier therefore cannot change the
bar's EQ while all of its associated players belong to another input.

Like Night mode, EQ follow is event-driven. A manual sound-mode change is not
periodically overwritten; a new **eligible current-input** connected-content or
classifier event is needed before automatic EQ selection happens again.

A single media-player state transition can trigger both source routing and EQ
follow in parallel. To prevent an old-input EQ decision from landing after a new
input default, connected-content EQ runs wait up to three seconds for the
soundbar's **live source** to reach that media player's mapped input, then rebuild
the eligible player set from current state. If routing moved the bar from eARC to
AUX, a stale eARC/TV run is therefore discarded instead of changing AUX's mode
after its default was applied.

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
- a user-modified or otherwise different existing blueprint is never overwritten;
- when a managed blueprint is installed or updated after Home Assistant's
  Automation integration has already loaded, ULTIMEA resets the blueprint cache
  and reloads the live automation definition after startup. Existing automations
  using this blueprint are targeted individually when possible, so removed
  triggers cannot remain active just because Home Assistant expanded an older
  blueprint earlier in the same startup.

The public GitHub blueprint remains available as a manual fallback:

```text
https://github.com/Chreece/HA-Ultimea/blob/master/blueprints/automation/ultimea/adaptive_room_audio.yaml
```

After creating the automation, use **Run actions** once if you want the policy to
be applied immediately rather than waiting for the next relevant event.

## Execution model

Adaptive Room Audio is event-driven. Outside an active quiet-boundary fade it has
no `time_pattern` trigger and does not periodically execute. The dynamic start of
the pre-quiet fade is detected by a template trigger; Home Assistant re-evaluates
that clock template once per minute, but the automation itself runs only when the
template changes from false to true. Once a fade starts, the single active run uses
internal five-second delays until the transition ends.

The soundbar state trigger uses `to: null`, so ordinary attribute updates do not
start the automation. The volume-level attribute trigger is enabled only when
**Learn min/max from manual volume changes** is enabled.
