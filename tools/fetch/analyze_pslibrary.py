#!/usr/bin/env python3
"""Analyze PSlibrary file inventory across all elements."""
import json
import re
import urllib.request
from collections import Counter

BASE = "https://pseudopotentials.quantum-espresso.org"

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")

main = fetch(f"{BASE}/legacy_tables/ps-library")
elements = sorted(set(re.findall(r'/legacy_tables/ps-library/([a-z]+)"', main)))

all_files = []
pp_types = Counter()
versions = Counter()
functionals = Counter()
relativistic = Counter()

for slug in elements:
    html = fetch(f"{BASE}/legacy_tables/ps-library/{slug}")
    names = re.findall(r'([A-Z][a-z]?\.[^<\s]+\.UPF)', html)
    for name in names:
        all_files.append({"element": slug, "filename": name})
        desc = name.split(".", 1)[1].rsplit(".UPF", 1)[0]
        parts = desc.split("-")
        if parts[0] == "rel":
            relativistic["full"] += 1
            parts = parts[1:]
        else:
            relativistic["scalar"] += 1
        if parts:
            functionals[parts[0]] += 1
        if "kjpaw" in desc:
            pp_types["PAW (kjpaw)"] += 1
        elif "rrkjus" in desc:
            pp_types["USPP (rrkjus)"] += 1
        m = re.search(r"_psl\.([\d.]+)", desc)
        if m:
            versions[f"psl.{m.group(1)}"] += 1

print(f"Elements: {len(elements)}")
print(f"Total UPF files: {len(all_files)}")
print(f"Unique filenames: {len(set(f['filename'] for f in all_files))}")
print("\nPP types:", dict(pp_types))
print("\nTop versions:", versions.most_common(10))
print("\nFunctionals:", dict(functionals))
print("\nRelativistic:", dict(relativistic))

out = {
    "elements": elements,
    "files": all_files,
    "stats": {
        "total": len(all_files),
        "pp_types": dict(pp_types),
        "versions": dict(versions),
    },
}
import os
from pathlib import Path

RAW_DIR = Path(os.environ["POTDEX_RAW"]) if os.environ.get("POTDEX_RAW") else Path(__file__).resolve().parents[2] / "raw"
inv = RAW_DIR / "PSlibrary" / "metadata" / "pslibrary_inventory.json"
with open(inv, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2)
print(f"\nWrote {inv}")
