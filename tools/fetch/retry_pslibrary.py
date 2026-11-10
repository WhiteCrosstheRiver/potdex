#!/usr/bin/env python3
"""Retry failed PSlibrary downloads."""
import json
import urllib.request
from pathlib import Path

from download_pslibrary import download_upf

BASE = Path(__file__).resolve().parents[2] / "raw" / "PSlibrary"
summary = json.loads((BASE / "metadata/download_summary.json").read_text(encoding="utf-8"))

retry = [
    "B.rel-pbe-n-kjpaw_psl.1.0.0.UPF",
    "Ir.pbe-n-kjpaw_psl.0.2.3.UPF",
    "Ir.pbe-n-rrkjus_psl.0.2.3.UPF",
    "Ir.pbesol-n-kjpaw_psl.0.2.3.UPF",
    "Ir.pbesol-n-rrkjus_psl.0.2.3.UPF",
    "Ir.pz-n-kjpaw_psl.0.2.3.UPF",
    "Ir.pz-n-rrkjus_psl.0.2.3.UPF",
    "Ir.rel-pbe-n-kjpaw_psl.0.2.3.UPF",
    "Ir.rel-pbe-n-rrkjus_psl.0.2.3.UPF",
    "Ir.rel-pbesol-n-kjpaw_psl.0.2.3.UPF",
    "Ir.rel-pbesol-n-rrkjus_psl.0.2.3.UPF",
    "Ir.rel-pz-n-kjpaw_psl.0.2.3.UPF",
    "Ir.rel-pz-n-rrkjus_psl.0.2.3.UPF",
]

failed = []
for name in retry:
    print(f"retry {name}")
    try:
        path, size = download_upf(name)
        print(f"  OK {path} ({size//1024} KB)")
    except Exception as e:
        print(f"  FAIL {e}")
        failed.append((name, str(e)))

print(f"\nDone. failed={len(failed)}")
