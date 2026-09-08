from __future__ import annotations

import ast
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TRANSFORMER = ROOT / "scripts" / "_tmp_adaptive_policy_engine_transform.py"
PUBLIC_BP = ROOT / "blueprints" / "automation" / "ultimea" / "adaptive_room_audio.yaml"
BUNDLED_BP = ROOT / "custom_components" / "ultimea" / "blueprints" / "adaptive_room_audio.yaml"


def extract_constant(name: str) -> str:
    tree = ast.parse(TRANSFORMER.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and target.id == name:
            value = ast.literal_eval(node.value)
            if not isinstance(value, str):
                raise TypeError(f"{name} is not a string")
            return value
    raise KeyError(name)


condition_sections = extract_constant("condition_sections")
content_section = extract_constant("content_section")
options_section = extract_constant("options_section")

bp = PUBLIC_BP.read_text(encoding="utf-8")
start_marker = "\n    minimum_conditions:\n"
end_marker = "\nvariables:\n"
start = bp.index(start_marker) + 1
end = bp.index(end_marker, start) + 1
replacement = condition_sections + content_section + options_section
fixed = bp[:start] + replacement + bp[end:]

# The previous transform could only corrupt the input section. Assert that the
# rebuilt section contains every intended top-level input group before writing.
for marker in (
    "    minimum_conditions:\n",
    "    zero_conditions:\n",
    "    ambient_boost:\n",
    "    night_conditions:\n",
    "    policy_gate:\n",
    "    content_follow:\n",
    "    options:\n",
    "variables:\n",
):
    if marker not in fixed:
        raise RuntimeError(f"Missing rebuilt marker: {marker.strip()}")

# Parse with a loader that accepts Home Assistant's !input tag.
class Loader(yaml.SafeLoader):
    pass

Loader.add_constructor("!input", lambda loader, node: loader.construct_scalar(node))
yaml.load(fixed, Loader=Loader)

PUBLIC_BP.write_text(fixed, encoding="utf-8")
BUNDLED_BP.write_text(fixed, encoding="utf-8")
print("Adaptive policy input section repaired and YAML parsed successfully")
