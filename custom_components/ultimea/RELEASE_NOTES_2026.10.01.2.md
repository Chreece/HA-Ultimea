# ULTIMEA 2026.10.01.2

### Fixed

- Connected content / EQ follow now follows the soundbar's **currently active input**.
- A media player can drive EQ only when it is selected under **Devices connected to the soundbar** and also assigned to **Media players →** the active input.
- Players mapped to another input are ignored, even when they are in the same room.
- Classifier entities and the optional AI/snapshot hook are gated by the same active-input rule.
- Multi-soundbar setups keep Home Assistant area matching in addition to the input mapping.
