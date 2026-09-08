from __future__ import annotations

from pathlib import Path
import json

root = Path('.')
bp_path = root / 'blueprints/automation/ultimea/adaptive_room_audio.yaml'
text = bp_path.read_text(encoding='utf-8')


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Expected exactly one match, found {count} for:\n{old[:240]}')
    text = text.replace(old, new, 1)


replace_once(
'''    Create two input_number helpers for the learned minimum and maximum volume.
    Helpers may use either a 0–1 range or a 0–100 percentage range. Manual volume
    changes are learned into the active endpoint instead of being immediately
    overwritten. For different rooms with different learned levels, create one
    automation instance per room/group.

    "Comma-list" entities are optional sensors/text entities whose state contains
    comma-separated area IDs, area names, or entity IDs. If an item resolves to
    the same area as a soundbar, that room is treated as a quiet/low-volume room.
    The special values `all` and `*` apply globally.
''',
'''    Minimum and maximum volume can be fixed percentages or read from optional
    numeric entities. When manual-volume learning is enabled and the selected
    source is a writable input_number/number entity, a manual volume change in a
    normal or minimum-volume regime updates that endpoint. Manual changes during
    a quiet-hours fade stop the fade for that soundbar instead of being learned.

    "Room-list" entities may expose rooms in their state as comma-separated area
    IDs/names/entity IDs, or in attributes as lists or comma-separated strings.
    Any token that resolves to the same area as a soundbar requests minimum volume.
    The special values `all` and `*` apply globally.
''')

replace_once(
'''        min_volume_helper:
          name: Learned minimum volume helper
          description: >-
            input_number used for quiet/TTS/Assist volume. Use either a 0–1 range
            or a 0–100 percentage range. Manual changes while in a low-volume
            regime update this helper.
          selector:
            entity:
              filter:
                - domain: input_number
        max_volume_helper:
          name: Learned maximum volume helper
          description: >-
            input_number used for normal volume. Use either a 0–1 range or a
            0–100 percentage range. Manual changes in normal operation update
            this helper.
          selector:
            entity:
              filter:
                - domain: input_number
''',
'''        min_volume_value:
          name: Minimum volume
          description: >-
            Fixed quiet/TTS/Assist volume in percent. Used when no minimum-volume
            entity is selected below.
          default: 20
          selector:
            number:
              min: 0
              max: 100
              step: 1
              unit_of_measurement: "%"
              mode: slider
        min_volume_helper:
          name: Minimum volume entity (optional)
          description: >-
            Optional numeric entity whose state overrides the fixed minimum above.
            input_number and number entities can also be updated by manual-volume
            learning; sensor entities are read-only. Values may use 0–1 or 0–100.
            Select at most one entity.
          default: []
          selector:
            entity:
              multiple: true
              filter:
                - domain:
                    - input_number
                    - number
                    - sensor
        max_volume_value:
          name: Maximum volume
          description: >-
            Fixed normal-operation volume in percent. Used when no maximum-volume
            entity is selected below.
          default: 50
          selector:
            number:
              min: 0
              max: 100
              step: 1
              unit_of_measurement: "%"
              mode: slider
        max_volume_helper:
          name: Maximum volume entity (optional)
          description: >-
            Optional numeric entity whose state overrides the fixed maximum above.
            input_number and number entities can also be updated by manual-volume
            learning; sensor entities are read-only. Values may use 0–1 or 0–100.
            Select at most one entity.
          default: []
          selector:
            entity:
              multiple: true
              filter:
                - domain:
                    - input_number
                    - number
                    - sensor
''')

replace_once(
'''        list_state_entities:
          name: Comma-list entities
          description: >-
            Entities whose state is a comma-separated list of active area IDs,
            area names, or entity IDs. Matching a soundbar's area requests the
            learned minimum volume. `all` or `*` applies to every selected bar.
          default: []
          selector:
            entity:
              multiple: true
''',
'''        list_state_entities:
          name: Room-list entities (state or attributes)
          description: >-
            Entities may provide active rooms in their state as comma-separated
            area IDs/names/entity IDs, or in attributes as a list or a comma-
            separated string. Matching a soundbar's area requests minimum volume.
            `all` or `*` applies to every selected bar.
          default: []
          selector:
            entity:
              multiple: true
''')

replace_once(
'''        apply_volume_follow:
          name: Volume follow
          description: Apply learned min/max volume and quiet-hour fades.
          default: true
          selector:
            boolean: {}
''',
'''        apply_volume_follow:
          name: Volume follow
          description: Apply min/max volume and quiet-hour fades.
          default: true
          selector:
            boolean: {}
        learn_manual_volume_changes:
          name: Learn min/max from manual volume changes
          description: >-
            When enabled, manual soundbar volume changes update the active minimum
            or maximum only when that endpoint uses a writable input_number/number
            entity. Manual changes during a quiet-hours fade never change an
            endpoint; they stop that fade for the affected soundbar.
          default: false
          selector:
            boolean: {}
''')

replace_once(
'''variables:
  ultimea_players: !input ultimea_players
  min_volume_helper: !input min_volume_helper
  max_volume_helper: !input max_volume_helper
''',
'''variables:
  ultimea_players: !input ultimea_players
  min_volume_value: !input min_volume_value
  min_volume_source_input: !input min_volume_helper
  max_volume_value: !input max_volume_value
  max_volume_source_input: !input max_volume_helper
''')

replace_once(
'''  apply_volume_follow: !input apply_volume_follow
  apply_night_mode: !input apply_night_mode
  apply_eq_follow: !input apply_eq_follow
''',
'''  apply_volume_follow: !input apply_volume_follow
  learn_manual_volume_changes: !input learn_manual_volume_changes
  apply_night_mode: !input apply_night_mode
  apply_eq_follow: !input apply_eq_follow
''')

replace_once(
'''  - trigger: state
    entity_id: !input min_volume_helper
    id: volume_helper
  - trigger: state
    entity_id: !input max_volume_helper
    id: volume_helper
''',
'''  - trigger: state
    entity_id: !input min_volume_helper
    id: volume_source
  - trigger: state
    entity_id: !input max_volume_helper
    id: volume_source
''')

replace_once(
'''      min_volume_candidate: >-
        {% set v = states(min_volume_helper) | float(0.20) %}
        {% set scale = state_attr(min_volume_helper, 'max') | float(1) %}
        {% set normalized = v / 100 if scale > 1.5 else v %}
        {{ [[normalized, 0.0] | max, 1.0] | min }}
      max_volume_candidate: >-
        {% set v = states(max_volume_helper) | float(0.50) %}
        {% set scale = state_attr(max_volume_helper, 'max') | float(1) %}
        {% set normalized = v / 100 if scale > 1.5 else v %}
        {{ [[normalized, 0.0] | max, 1.0] | min }}
''',
'''      min_volume_entity: >-
        {% if min_volume_source_input is string %}
          {{ min_volume_source_input }}
        {% elif min_volume_source_input | length > 0 %}
          {{ min_volume_source_input[0] }}
        {% else %}
          {{ '' }}
        {% endif %}
      max_volume_entity: >-
        {% if max_volume_source_input is string %}
          {{ max_volume_source_input }}
        {% elif max_volume_source_input | length > 0 %}
          {{ max_volume_source_input[0] }}
        {% else %}
          {{ '' }}
        {% endif %}
      min_volume_candidate: >-
        {% if min_volume_entity %}
          {% set raw = states(min_volume_entity) | float(min_volume_value | float(20)) %}
          {% set scale = state_attr(min_volume_entity, 'max') | float(0) %}
          {% set normalized = raw / 100 if scale > 1.5 or raw > 1.5 else raw %}
        {% else %}
          {% set normalized = (min_volume_value | float(20)) / 100 %}
        {% endif %}
        {{ [[normalized, 0.0] | max, 1.0] | min }}
      max_volume_candidate: >-
        {% if max_volume_entity %}
          {% set raw = states(max_volume_entity) | float(max_volume_value | float(50)) %}
          {% set scale = state_attr(max_volume_entity, 'max') | float(0) %}
          {% set normalized = raw / 100 if scale > 1.5 or raw > 1.5 else raw %}
        {% else %}
          {% set normalized = (max_volume_value | float(50)) / 100 %}
        {% endif %}
        {{ [[normalized, 0.0] | max, 1.0] | min }}
      room_list_area_ids: >-
        {% set ns = namespace(area_ids=[]) %}
        {% for holder in list_state_entities %}
          {% set obj = expand(holder) | first %}
          {% if obj is not none %}
            {% for raw in (obj.state | string).split(',') %}
              {% set token = raw | trim %}
              {% if token %}
                {% if token | lower in ['all', '*'] %}
                  {% set ns.area_ids = ns.area_ids + ['*'] %}
                {% else %}
                  {% set resolved = token if token in areas() else area_id(token) %}
                  {% if resolved %}
                    {% set ns.area_ids = ns.area_ids + [resolved] %}
                  {% endif %}
                {% endif %}
              {% endif %}
            {% endfor %}
            {% for value in obj.attributes.values() %}
              {% if value is string and ',' in value %}
                {% for raw in value.split(',') %}
                  {% set token = raw | trim %}
                  {% if token %}
                    {% if token | lower in ['all', '*'] %}
                      {% set ns.area_ids = ns.area_ids + ['*'] %}
                    {% else %}
                      {% set resolved = token if token in areas() else area_id(token) %}
                      {% if resolved %}
                        {% set ns.area_ids = ns.area_ids + [resolved] %}
                      {% endif %}
                    {% endif %}
                  {% endif %}
                {% endfor %}
              {% elif value is iterable and value is not string and value is not mapping %}
                {% for raw in value %}
                  {% set token = raw | string | trim %}
                  {% if token %}
                    {% if token | lower in ['all', '*'] %}
                      {% set ns.area_ids = ns.area_ids + ['*'] %}
                    {% else %}
                      {% set resolved = token if token in areas() else area_id(token) %}
                      {% if resolved %}
                        {% set ns.area_ids = ns.area_ids + [resolved] %}
                      {% endif %}
                    {% endif %}
                  {% endif %}
                {% endfor %}
              {% endif %}
            {% endfor %}
          {% endif %}
        {% endfor %}
        {{ ns.area_ids | unique | list }}
''')

replace_once(
'''      scheduled_volume: >-
        {% if in_quiet_hours %}
          {{ min_volume }}
        {% elif quiet_hours_enabled
                and transition_before_seconds > 0
                and 0 < seconds_until_quiet_start <= transition_before_seconds %}
          {% set progress = 1 - (seconds_until_quiet_start / transition_before_seconds) %}
          {{ max_volume - ((max_volume - min_volume) * progress) }}
        {% elif quiet_hours_enabled
                and transition_after_seconds > 0
                and seconds_since_quiet_end < transition_after_seconds %}
          {% set progress = seconds_since_quiet_end / transition_after_seconds %}
          {{ min_volume + ((max_volume - min_volume) * progress) }}
        {% else %}
          {{ max_volume }}
        {% endif %}
''',
'''      scheduled_volume: >-
        {% if in_quiet_hours %}
          {{ min_volume }}
        {% elif quiet_hours_enabled
                and transition_before_seconds > 0
                and 0 < seconds_until_quiet_start <= transition_before_seconds %}
          {% set progress = 1 - (seconds_until_quiet_start / transition_before_seconds) %}
          {{ max_volume - ((max_volume - min_volume) * progress) }}
        {% elif quiet_hours_enabled
                and transition_after_seconds > 0
                and seconds_since_quiet_end < transition_after_seconds %}
          {% set progress = seconds_since_quiet_end / transition_after_seconds %}
          {{ min_volume + ((max_volume - min_volume) * progress) }}
        {% else %}
          {{ max_volume }}
        {% endif %}
      previous_scheduled_volume: >-
        {% if before_transition_active and transition_before_seconds > 0 %}
          {% set step = ((max_volume - min_volume) * 5 / transition_before_seconds) %}
          {{ [max_volume, scheduled_volume + step] | min }}
        {% elif after_transition_active and transition_after_seconds > 0 %}
          {% set step = ((max_volume - min_volume) * 5 / transition_after_seconds) %}
          {{ [min_volume, scheduled_volume - step] | max }}
        {% else %}
          {{ scheduled_volume }}
        {% endif %}
''')

# Replace legacy repeated comma-state parsing with pre-resolved area list (manual block).
start = '''              manual_list_low: >-
                {% set ns = namespace(active=false) %}
                {% for holder in list_state_entities %}
'''
end = '''                {{ ns.active }}
          - variables:
              manual_extra_low: >-
'''
i = text.find(start)
if i < 0:
    raise SystemExit('manual_list_low block start not found')
j = text.find(end, i)
if j < 0:
    raise SystemExit('manual_list_low block end not found')
replacement = '''              manual_list_low: >-
                {{ '*' in room_list_area_ids
                   or (manual_bar_area != '' and manual_bar_area in room_list_area_ids) }}
          - variables:
              manual_extra_low: >-
'''
text = text[:i] + replacement + text[j + len(end):]

replace_once(
'''              manual_expected_volume: >-
                {{ min_volume if manual_extra_low else scheduled_volume }}
              manual_volume: >-
                {{ trigger.to_state.attributes.get('volume_level') | float(0) }}
              manual_is_low_regime: >-
                {{ in_quiet_hours or manual_extra_low }}
              manual_differs_from_expected: >-
                {{ (manual_volume - manual_expected_volume) | abs > 0.004 }}
          - choose:
              - conditions:
                  - condition: template
                    value_template: "{{ manual_differs_from_expected and manual_is_low_regime }}"
                sequence:
                  - action: input_number.set_value
                    target:
                      entity_id: "{{ min_volume_helper }}"
                    data:
                      value: >-
                        {% set scale = state_attr(min_volume_helper, 'max') | float(1) %}
                        {{ (manual_volume * 100 if scale > 1.5 else manual_volume) | round(2) }}
              - conditions:
                  - condition: template
                    value_template: "{{ manual_differs_from_expected and not manual_is_low_regime }}"
                sequence:
                  - action: input_number.set_value
                    target:
                      entity_id: "{{ max_volume_helper }}"
                    data:
                      value: >-
                        {% set scale = state_attr(max_volume_helper, 'max') | float(1) %}
                        {{ (manual_volume * 100 if scale > 1.5 else manual_volume) | round(2) }}
          - stop: Manual ULTIMEA volume change handled without fighting the user.
''',
'''              manual_expected_volume: >-
                {{ min_volume if manual_extra_low else scheduled_volume }}
              manual_volume: >-
                {{ trigger.to_state.attributes.get('volume_level') | float(0) }}
              manual_is_low_regime: >-
                {{ in_quiet_hours or manual_extra_low }}
              manual_in_time_transition: >-
                {{ (before_transition_active or after_transition_active) and not manual_extra_low }}
              manual_differs_from_expected: >-
                {{ (manual_volume - manual_expected_volume) | abs > 0.004
                   and (not manual_in_time_transition
                        or (manual_volume - previous_scheduled_volume) | abs > 0.004) }}
              manual_learning_entity: >-
                {{ min_volume_entity if manual_is_low_regime else max_volume_entity }}
              manual_learning_domain: >-
                {{ manual_learning_entity.split('.', 1)[0] if manual_learning_entity else '' }}
              manual_learning_value: >-
                {% if manual_learning_entity %}
                  {% set scale = state_attr(manual_learning_entity, 'max') | float(0) %}
                  {% set current = states(manual_learning_entity) | float(0) %}
                  {{ (manual_volume * 100 if scale > 1.5 or current > 1.5 else manual_volume) | round(2) }}
                {% else %}
                  {{ manual_volume | round(2) }}
                {% endif %}
          - choose:
              - conditions:
                  - condition: template
                    value_template: >-
                      {{ manual_differs_from_expected
                         and not manual_in_time_transition
                         and learn_manual_volume_changes
                         and manual_learning_domain == 'input_number' }}
                sequence:
                  - action: input_number.set_value
                    continue_on_error: true
                    target:
                      entity_id: "{{ manual_learning_entity }}"
                    data:
                      value: "{{ manual_learning_value }}"
              - conditions:
                  - condition: template
                    value_template: >-
                      {{ manual_differs_from_expected
                         and not manual_in_time_transition
                         and learn_manual_volume_changes
                         and manual_learning_domain == 'number' }}
                sequence:
                  - action: number.set_value
                    continue_on_error: true
                    target:
                      entity_id: "{{ manual_learning_entity }}"
                    data:
                      value: "{{ manual_learning_value }}"
          - stop: Manual ULTIMEA volume change handled without fighting the user.
''')

# Replace legacy repeated comma-state parsing with pre-resolved area list (per-bar block).
start = '''                    list_low: >-
                      {% set ns = namespace(active=false) %}
                      {% for holder in list_state_entities %}
'''
end = '''                      {{ ns.active }}
                - variables:
                    extra_low: >-
'''
i = text.find(start)
if i < 0:
    raise SystemExit('list_low block start not found')
j = text.find(end, i)
if j < 0:
    raise SystemExit('list_low block end not found')
replacement = '''                    list_low: >-
                      {{ '*' in room_list_area_ids
                         or (bar_area != '' and bar_area in room_list_area_ids) }}
                - variables:
                    extra_low: >-
'''
text = text[:i] + replacement + text[j + len(end):]

replace_once(
'''                    current_volume: >-
                      {{ state_attr(bar, 'volume_level') | float(-1) }}
                    tick_can_adjust: >-
                      {{ trigger_id != 'transition_tick' or not extra_low }}
                - choose:
                    - conditions:
                        - condition: template
                          value_template: >-
                            {{ is_state(bar, 'on')
                               and tick_can_adjust
                               and (current_volume < 0 or (current_volume - desired_volume) | abs > 0.009) }}
''',
'''                    current_volume: >-
                      {{ state_attr(bar, 'volume_level') | float(-1) }}
                    previous_transition_target: >-
                      {{ previous_scheduled_volume | float(desired_volume) | round(2) }}
                    fade_interrupted_by_manual_volume: >-
                      {{ trigger_id == 'transition_tick'
                         and not extra_low
                         and (before_transition_active or after_transition_active)
                         and current_volume >= 0
                         and (current_volume - previous_transition_target) | abs > 0.004 }}
                    tick_can_adjust: >-
                      {{ trigger_id != 'transition_tick'
                         or (not extra_low and not fade_interrupted_by_manual_volume) }}
                - choose:
                    - conditions:
                        - condition: template
                          value_template: >-
                            {{ is_state(bar, 'on')
                               and tick_can_adjust
                               and (current_volume < 0 or (current_volume - desired_volume) | abs > 0.009) }}
''')

replace_once(
'''              {{ apply_volume_follow
                 and (trigger_id != 'transition_tick'
                      or before_transition_active
                      or after_transition_active) }}
''',
'''              {{ apply_volume_follow
                 and (
                   (trigger_id == 'transition_tick'
                    and (before_transition_active or after_transition_active))
                   or (trigger_id == 'policy_tick'
                       and not before_transition_active
                       and not after_transition_active)
                   or trigger_id not in ['transition_tick', 'policy_tick']
                 ) }}
''')

bp_path.write_text(text, encoding='utf-8')
bundled = root / 'custom_components/ultimea/blueprints/adaptive_room_audio.yaml'
bundled.write_bytes(bp_path.read_bytes())

# Update blueprint tests.
test_path = root / 'tests/test_blueprint.py'
t = test_path.read_text(encoding='utf-8')
t = t.replace('''        "min_volume_helper",
        "max_volume_helper",
''', '''        "min_volume_value",
        "min_volume_helper",
        "max_volume_value",
        "max_volume_helper",
''')
t = t.replace('''        "apply_volume_follow",
        "apply_night_mode",
''', '''        "apply_volume_follow",
        "learn_manual_volume_changes",
        "apply_night_mode",
''')
old_asserts = '''    assert inputs["min_volume_helper"]["selector"]["entity"]["filter"] == [
        {"domain": "input_number"}
    ]
    assert inputs["max_volume_helper"]["selector"]["entity"]["filter"] == [
        {"domain": "input_number"}
    ]
'''
new_asserts = '''    assert inputs["min_volume_value"]["selector"]["number"]["min"] == 0
    assert inputs["min_volume_value"]["selector"]["number"]["max"] == 100
    assert inputs["max_volume_value"]["selector"]["number"]["min"] == 0
    assert inputs["max_volume_value"]["selector"]["number"]["max"] == 100

    for key in ("min_volume_helper", "max_volume_helper"):
        selector = inputs[key]["selector"]["entity"]
        assert selector["multiple"] is True
        assert inputs[key]["default"] == []
        domains = selector["filter"][0]["domain"]
        assert domains == ["input_number", "number", "sensor"]
'''
if old_asserts not in t:
    raise SystemExit('old min/max test assertions not found')
t = t.replace(old_asserts, new_asserts)
old_markers = '''    assert "seconds: \\\"/5\\\"" in text
    assert "manual_differs_from_expected" in text
    assert "area_id(" in text
    assert "states(holder).split(',')" in text
    assert "sound_mode_list" in text
    assert "quiet_hours_enabled" in text
'''
new_markers = '''    assert "seconds: \\\"/5\\\"" in text
    assert "manual_differs_from_expected" in text
    assert "learn_manual_volume_changes" in text
    assert "number.set_value" in text
    assert "min_volume_value" in text
    assert "max_volume_value" in text
    assert "obj.attributes.values()" in text
    assert "value is iterable" in text
    assert "value is string and ',' in value" in text
    assert "room_list_area_ids" in text
    assert "previous_scheduled_volume" in text
    assert "fade_interrupted_by_manual_volume" in text
    assert "manual_in_time_transition" in text
    assert "area_id(" in text
    assert "sound_mode_list" in text
    assert "quiet_hours_enabled" in text
'''
if old_markers not in t:
    raise SystemExit('old marker assertions not found')
t = t.replace(old_markers, new_markers)
test_path.write_text(t, encoding='utf-8')

# Version and changelogs.
version = '2026.09.08.1'
manifest_path = root / 'custom_components/ultimea/manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
manifest['version'] = version
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

changelog_path = root / 'CHANGELOG.md'
changelog = changelog_path.read_text(encoding='utf-8')
heading = f'''## {version}

### Changed

- Minimum and maximum volume no longer require `input_number` helpers: each endpoint now has a fixed percentage plus an optional numeric entity override (`input_number`, `number`, or numeric `sensor`).
- Room-list sources now consume comma-separated room tokens from entity state and also inspect attributes that are lists or comma-separated strings.
- Added an explicit **Learn min/max from manual volume changes** option. Learning is opt-in and writes only to writable `input_number`/`number` endpoint entities; read-only sensors and fixed numeric values are never mutated.
- Manual volume changes during the configured before/after quiet-hours fade now stop the fade for that soundbar. Transition ticks detect that the current volume no longer matches the previous automation target and leave the user's value alone until the transition window ends or another room condition changes.
- The one-minute reconciliation no longer writes volume while a quiet-hours fade is active, so it cannot restart a fade that the user interrupted.

'''
marker = '## 2026.09.08\n'
if marker not in changelog:
    raise SystemExit('2026.09.08 changelog marker missing')
changelog = changelog.replace(marker, heading + marker, 1)
changelog_path.write_text(changelog, encoding='utf-8')
(root / 'custom_components/ultimea/CHANGELOG.md').write_text(changelog, encoding='utf-8')

# README: bump badge and refine blueprint bullets.
readme_path = root / 'README.md'
readme = readme_path.read_text(encoding='utf-8')
readme = readme.replace('release-2026.09.08-blue', 'release-2026.09.08.1-blue')
readme = readme.replace('''- learn persistent normal and quiet volume endpoints from the user's own volume changes;
''', '''- use fixed numeric min/max volume or optional numeric entity sources, with opt-in learning from manual volume changes;
''')
readme = readme.replace('''- lower volume immediately for selected binary conditions, comma-list room sensors, TTS playback, active Assist satellites, or a night-mode boolean;
''', '''- lower volume immediately for selected binary conditions, room-list state/attribute sources, TTS playback, active Assist satellites, or a night-mode boolean;
''')
readme = readme.replace('''- respect manual ULTIMEA volume and sound-mode changes instead of continuously fighting them.
''', '''- respect manual ULTIMEA volume and sound-mode changes instead of continuously fighting them, including stopping an in-progress quiet-hours fade when the user changes volume.
''')
readme_path.write_text(readme, encoding='utf-8')

# Blueprint docs: update volume/list/fade behavior.
docs_path = root / 'docs/ADAPTIVE_AUDIO_BLUEPRINT.md'
docs = docs_path.read_text(encoding='utf-8')
start = docs.index('## Learned minimum and maximum volume')
end = docs.index('## Quiet hours (ώρες κοινής ησυχίας)')
volume_section = '''## Minimum and maximum volume

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

'''
docs = docs[:start] + volume_section + docs[end:]
docs = docs.replace('''- The fade is stepped every five seconds.
''', '''- The fade is stepped every five seconds. If the user changes the soundbar volume during the fade, subsequent fade ticks for that soundbar stop until the transition window ends or another room condition changes.
''')
cstart = docs.index('## Comma-list entities')
cend = docs.index('## TTS and Assist ducking')
list_section = '''## Room-list entities: state and attributes

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

'''
docs = docs[:cstart] + list_section + docs[cend:]
docs_path.write_text(docs, encoding='utf-8')

notes = f'''# ULTIMEA {version}

## Adaptive Room Audio refinements

- Minimum and maximum volume can now be entered directly as fixed percentages or supplied by optional numeric entities.
- Room-list entities now read both comma-separated state values and attributes containing lists or comma-separated strings of rooms.
- Manual min/max learning is now opt-in and only writes to selected writable `input_number`/`number` entities.
- A manual soundbar volume change during a quiet-hours fade stops that fade for the affected bar; the one-minute reconciliation cannot restart it while the fade window remains active.

The public and integration-bundled blueprint copies remain byte-for-byte identical so automatic blueprint delivery continues to update untouched managed copies safely.
'''
(root / f'RELEASE_NOTES_{version}.md').write_text(notes, encoding='utf-8')
(root / 'custom_components/ultimea' / f'RELEASE_NOTES_{version}.md').write_text(notes, encoding='utf-8')

# Remove temporary transformer files in the same commit as the real changes.
Path('scripts/_tmp_adaptive_audio_v2.py').unlink()
Path('.github/workflows/_tmp_blueprint_v2.yml').unlink()
