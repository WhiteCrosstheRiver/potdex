#!/usr/bin/env python3
"""Run full catalog build pipeline."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

STEPS = [
    "parse_upf_header.py",
    "download_sssp.py",
    "extract_sssp.py",
    "scan_libraries.py",
    "build_global_index.py",
    "build_cutoffs.py",
    "build_selection_guide.py",
    "build_catalog_views.py",
    "validate_catalog.py",
    "smoke_test_abacus.py",
]


def main() -> int:
    for step in STEPS:
        script = TOOLS / step
        print(f"\n>>> {step}")
        result = subprocess.run([sys.executable, str(script)], cwd=str(TOOLS))
        if result.returncode != 0:
            print(f"FAILED: {step}", file=sys.stderr)
            return result.returncode
    print("\n=== pipeline complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
