"""Execute the release workflow shell with a local GitHub CLI stand-in."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).parents[1]


def run_release(tmp_path, version, *, exists=False):
    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    step = next(
        item for item in workflow["jobs"]["release"]["steps"]
        if item.get("name") == "Create tag and GitHub release if missing"
    )
    gh = tmp_path / "gh"
    gh.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['RELEASE_TEST_TRACE'], 'a') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:3] == ['release', 'view']:\n"
        "    sys.exit(0 if os.environ['RELEASE_TEST_EXISTS'] == '1' else 1)\n"
    )
    gh.chmod(0o755)
    trace = tmp_path / "calls.jsonl"
    subprocess.run(
        ["bash", "-eo", "pipefail", "-c", step["run"]],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "VERSION": version,
            "TARGET_SHA": "verified-test-commit",
            "RELEASE_TEST_TRACE": str(trace),
            "RELEASE_TEST_EXISTS": "1" if exists else "0",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    return [json.loads(line) for line in trace.read_text().splitlines()]


@pytest.mark.parametrize("version", ["2026.11.17b1", "2026.11.17.1b2"])
def test_beta_does_not_replace_latest_stable(tmp_path, version):
    calls = run_release(tmp_path, version)
    assert calls == [
        ["release", "view", version],
        ["release", "create", version, "--target", "verified-test-commit",
         "--title", version, "--notes-file", "release-notes.md",
         "--prerelease", "--latest=false"],
    ]


def test_stable_release_flags_are_unchanged(tmp_path):
    calls = run_release(tmp_path, "2026.11.17")
    assert calls[-1] == [
        "release", "create", "2026.11.17", "--target", "verified-test-commit",
        "--title", "2026.11.17", "--notes-file", "release-notes.md",
    ]


def test_existing_beta_is_not_republished(tmp_path):
    assert run_release(tmp_path, "2026.11.17b1", exists=True) == [
        ["release", "view", "2026.11.17b1"]
    ]
