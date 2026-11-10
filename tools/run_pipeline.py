#!/usr/bin/env python3
"""Rebuild the whole catalog from raw/ (offline).

Downloading is tools/fetch_all.py's job; this script only reads raw/ and writes
catalog/. Pass --with-download to also run the legacy SSSP v2 downloader first.

Usage:
  python tools/run_pipeline.py
  python tools/run_pipeline.py --from build_cutoffs.py   # resume from a step
  python tools/run_pipeline.py --list
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

STEPS = [
    "parse_upf_header.py",
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
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--with-download", action="store_true", help="run download_sssp.py first (network)")
    ap.add_argument("--from", dest="start", metavar="STEP", help="start at this step")
    ap.add_argument("--list", action="store_true", help="print the steps and exit")
    args = ap.parse_args()

    steps = (["download_sssp.py"] if args.with_download else []) + STEPS
    if args.start:
        if args.start not in steps:
            print(f"unknown step {args.start!r}; steps: {', '.join(steps)}")
            return 2
        steps = steps[steps.index(args.start):]
    if args.list:
        print("\n".join(steps))
        return 0

    for step in steps:
        print(f"\n>>> {step}", flush=True)
        result = subprocess.run([sys.executable, str(TOOLS / step)], cwd=str(TOOLS))
        if result.returncode != 0:
            print(f"FAILED: {step}  (resume with --from {step})", file=sys.stderr)
            return result.returncode
    print("\n=== pipeline complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
