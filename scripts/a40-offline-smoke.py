#!/usr/bin/env python3
"""Dependency-free smoke tests for HA-Ultimea core protocol and Aura A40.

Run from the checked-out repository:
    python3 scripts/a40-offline-smoke.py

This deliberately does not substitute for the complete pytest/yaml/jinja2
suite, which includes blueprint and Style tests.
"""

from __future__ import annotations

import compileall
import importlib.util
import inspect
import json
from pathlib import Path
import runpy
import sys
import traceback
import types

ROOT = Path(__file__).resolve().parents[1]


def _install_pytest_raises_shim() -> None:
    """Provide only the pytest.raises API used by an isolated A40 test."""
    if importlib.util.find_spec("pytest") is not None:
        return

    class _Raises:
        def __init__(self, expected: type[BaseException], match: str | None) -> None:
            self.expected = expected
            self.match = match

        def __enter__(self):
            return self

        def __exit__(self, kind, error, tb) -> bool:
            if kind is None:
                raise AssertionError(f"Expected {self.expected.__name__} to be raised")
            if not issubclass(kind, self.expected):
                return False
            if self.match is not None and self.match not in str(error):
                raise AssertionError(
                    f"Expected exception containing {self.match!r}, got {error!r}"
                )
            return True

    shim = types.ModuleType("pytest")
    shim.raises = lambda expected, match=None: _Raises(expected, match)
    sys.modules["pytest"] = shim


def main() -> int:
    print("[1/3] Compiling integration (stdlib only)", flush=True)
    if not compileall.compile_dir(str(ROOT / "custom_components" / "ultimea"), quiet=1):
        print("COMPILE_RESULT=FAIL", flush=True)
        return 1

    print("[2/3] Validating integration JSON", flush=True)
    for file in sorted((ROOT / "custom_components" / "ultimea").rglob("*.json")):
        json.loads(file.read_text(encoding="utf-8"))
    print("JSON_RESULT=PASS", flush=True)

    _install_pytest_raises_shim()
    print("[3/3] Executing A40 and protocol tests without pip", flush=True)
    passed = failed = skipped = 0
    for name in ("test_aura_a40.py", "test_protocol.py", "test_wire_profiles.py"):
        path = ROOT / "tests" / name
        try:
            functions = runpy.run_path(str(path), run_name=f"_local_{name.replace('.', '_')}")
        except Exception:
            failed += 1
            print(f"FAIL import {name}", flush=True)
            traceback.print_exc()
            continue
        for test_name, test in sorted(functions.items()):
            if not (test_name.startswith("test_") and inspect.isfunction(test)):
                continue
            if inspect.signature(test).parameters:
                print(f"SKIP {name}::{test_name} (fixture required)", flush=True)
                skipped += 1
                continue
            try:
                test()
            except Exception:
                print(f"FAIL {name}::{test_name}", flush=True)
                traceback.print_exc()
                failed += 1
            else:
                passed += 1
                print(f"PASS {name}::{test_name}", flush=True)
    print(f"TEST_RESULT={'PASS' if failed == 0 and passed > 0 else 'FAIL'}")
    print(f"TESTS_PASSED={passed} TESTS_FAILED={failed} TESTS_SKIPPED={skipped}")
    print("FULL_PYTEST_SUITE=NOT_RUN (Style and blueprint tests need dependencies)")
    return 0 if failed == 0 and passed > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
