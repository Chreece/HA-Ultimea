# ULTIMEA Adaptive Room Audio blueprint

`adaptive_room_audio.yaml` is a room-aware Home Assistant automation blueprint for ULTIMEA soundbars. It combines quiet-hour fading with priority policies, rich conditions, room lists, connected-device activity, manual-control protection, Night mode and EQ/content follow.

## Policy priority

Volume policy is evaluated per soundbar in this order:

1. **Zero / mute priority** — direct, highest priority.
2. **Minimum-volume policy** — quiet hours, TTS, Assist, binary/list/custom conditions and optionally Night conditions.
3. **Scheduled / normal volume** — Max in ordinary operation, with the configured linear fade only immediately before/after quiet hours.
4. **Ambient-noise boost** can modify steady Min and/or steady Max. It deliberately does not modify the time fade.

Unavailable/off soundbars are skipped. A connected/activity gate can additionally leave a bar untouched when its connected source is inactive.

## Rich conditions + templates

Every major condition family provides both:

- Home Assistant's native **Condition** selector, which supports nested AND/OR, entity/device state, numeric state, time, zone and template conditions; and
- a dedicated **Template** selector for direct Jinja expressions.

The condition list is optional. When it is non-empty, all conditions inside that list must pass for that custom source to activate. A group's template is an additional alternative (for activation groups) or AND-gate (for gating groups), as described in the blueprint UI.

Per-bar templates can use `bar`, `bar_area`, `in_quiet_hours`, `min_volume`, `max_volume`, `trigger_id` and group-specific variables documented in each input. Select **Extra condition/template trigger entities** for any arbitrary entities referenced by templates/conditions when immediate reevaluation is needed; otherwise volume policy has a one-minute recovery tick.

## Minimum / maximum endpoints

Min and Max may be fixed 0–100% values or overridden by optional `input_number`, `number`, or numeric `sensor` entities. Entity values may use 0..1 or 0..100 and are normalized.

Manual learning is opt-in. With a writable `input_number`/`number` endpoint, a manual change in steady Min learns Min and a manual change in normal operation learns Max. Read-only sensors and fixed blueprint numbers are never mutated. A separate rich condition + template can restrict when learning is allowed.

When an ambient boost is active, learning subtracts the boost first so a 15% manually selected boosted volume with a +5% modifier learns a 10% base, not 15%.

## Quiet hours and manual fade interruption

Quiet hours may cross midnight. Before quiet start the volume moves linearly Max→Min; after quiet end it moves Min→Max in five-second steps. Other policy changes are direct.

A manual volume change during either time fade is not learned. Transition ticks compare the current soundbar volume with the previous automation target; once the user moves away from the fade trajectory the automation leaves that value alone for the remainder of that uninterrupted fade window.

## Room-list sources

Minimum, zero/mute, boost and Night policies each have both **room-scoped** and **global** room-list selectors.

A selected entity may provide tokens through:

- its state (`living_room,kids_room`);
- a list/tuple-like attribute; or
- a comma-separated string attribute.

Tokens may be area IDs, area names, entity IDs, `all`, or `*`. Room-scoped sources affect only matching soundbars. A global source affects every selected soundbar as soon as it contains any valid room token. This supports policies such as "any sleeping room lowers every bar" without hardcoded entities.

## Zero / mute priority

Zero/mute conditions can be selected from binary entities, room lists, rich HA conditions, or templates. The effect selector supports **Volume 0**, **Mute**, or **Volume 0 and mute**. Optional custom actions can run with `bar` and `bar_area` available.

Automatic unmute is disabled by default because blindly unmuting could override a user's manual mute. Enable it only when the automation is intended to own mute state.

## Ambient-noise compensation

Noise conditions can come from binary entities, room lists, the rich condition editor, or a template. The boost is a fixed percentage-point value or an optional numeric entity. It can apply to Min, Max, or both steady regimes and can be capped at Max or 100%.

This can model dehumidifiers, fans, 3D printers or any other noisy device without embedding model-specific logic in the blueprint.

## Connected activity: entities, devices and labels

Connected content can be selected three ways:

- direct `media_player` entities;
- Home Assistant **device** selector; or
- Home Assistant **label** selector.

For selected devices, their media-player entities are included automatically. For labels, directly labeled media-player entities and media players belonging to labeled devices are included. This allows a generic "TV" label policy without hardcoding entity IDs.

The activity gate can be disabled, require any matching connected player to be active, or require one to be playing/buffering/on. A rich condition and template can further gate volume management. When the gate fails, the user can choose **Leave unchanged** or **Set volume 0**.

## TTS and Assist

Selected TTS media players request Min while playing/buffering. Selected Assist Satellites request Min whenever they are not idle/unknown/unavailable. Same-area matching is used; entities without an area are global.

## Night mode

Night is requested by scheduled quiet hours plus optional Night binary entities, room/global room lists, rich conditions and templates. A toggle decides whether non-time Night conditions should also request Min.

Night/EQ changes remain event-driven rather than being enforced every minute, preserving manual sound-mode choices until relevant context changes.

## EQ/content follow

Connected media state plus metadata (`app_name`, title, artist, content type, channel, playlist, source, etc.) and optional classifier entities are matched against editable Game/Sport/Voice/Music/Movie keywords. A rich condition and template can gate EQ follow. Only sound modes present in the ULTIMEA entity's `sound_mode_list` are sent.

The optional AI action hook is provider-neutral and may take screenshots/snapshots, invoke a vision/LLM integration, and update classifier entities.

## Automatic installation

ULTIMEA installs the bundled blueprint to `/config/blueprints/automation/ultimea/adaptive_room_audio.yaml` when the integration loads. Managed copies update automatically only while unchanged by the user; modified copies are preserved.
