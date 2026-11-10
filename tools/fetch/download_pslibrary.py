#!/usr/bin/env python3
"""Download PSlibrary pseudopotentials from Quantum ESPRESSO.

Source: https://pseudopotentials.quantum-espresso.org/legacy_tables/ps-library

Layout (plan B):
  PSlibrary/
    metadata/inventory.json
    psl-1.0.0/{Element}/*.UPF
    legacy/{Element}/*.UPF
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://pseudopotentials.quantum-espresso.org"
UPF_URL = f"{BASE_URL}/upf_files"
TABLE_URL = f"{BASE_URL}/legacy_tables/ps-library"
BASE_DIR = Path(__file__).resolve().parents[2] / "raw" / "PSlibrary"
META_DIR = BASE_DIR / "metadata"
PSL_100_DIR = BASE_DIR / "psl-1.0.0"
LEGACY_DIR = BASE_DIR / "legacy"

ELEMENT_SLUG_RE = re.compile(r'/legacy_tables/ps-library/([a-z]+)"')
UPF_HREF_RE = re.compile(r'/upf_files/([A-Z][a-z]?\.[^"\'?\s]+\.UPF)')
UPF_NAME_RE = re.compile(r"([A-Z][a-z]?\.[A-Za-z0-9._-]+\.UPF)")


def fetch(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def discover_elements() -> list[str]:
    html = fetch(TABLE_URL)
    return sorted(set(ELEMENT_SLUG_RE.findall(html)))


def discover_upf_for_element(slug: str) -> list[str]:
    html = fetch(f"{TABLE_URL}/{slug}")
    names = UPF_HREF_RE.findall(html)
    if not names:
        names = UPF_NAME_RE.findall(html)
    return sorted(set(names))


def version_bucket(filename: str) -> str:
    return "psl-1.0.0" if "_psl.1.0.0." in filename else "legacy"


def element_symbol(filename: str) -> str:
    return filename.split(".", 1)[0]


def dest_for(filename: str) -> Path:
    symbol = element_symbol(filename)
    bucket = PSL_100_DIR if version_bucket(filename) == "psl-1.0.0" else LEGACY_DIR
    return bucket / symbol / filename


def download_upf(filename: str) -> tuple[Path, int]:
    dest = dest_for(filename)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest, dest.stat().st_size

    url = f"{UPF_URL}/{filename}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    data = fetch_bytes(url)
    if len(data) == 0:
        raise RuntimeError("empty response")
    if not data.lstrip().startswith(b"<UPF"):
        raise RuntimeError("not a valid UPF file")

    tmp.write_bytes(data)
    tmp.replace(dest)
    return dest, len(data)


def build_inventory(elements: list[str]) -> list[dict]:
    inventory: list[dict] = []
    for i, slug in enumerate(elements, 1):
        print(f"[scan {i}/{len(elements)}] {slug}")
        for filename in discover_upf_for_element(slug):
            inventory.append(
                {
                    "element_slug": slug,
                    "element": element_symbol(filename),
                    "filename": filename,
                    "version_bucket": version_bucket(filename),
                    "url": f"{UPF_URL}/{filename}",
                    "local_path": str(dest_for(filename).relative_to(BASE_DIR)),
                }
            )
        time.sleep(0.15)
    return inventory


def main() -> int:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    META_DIR.mkdir(parents=True, exist_ok=True)

    inventory_path = META_DIR / "inventory.json"
    if inventory_path.exists():
        print(f"Loading existing inventory: {inventory_path}")
        inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    else:
        print("Discovering elements and UPF files ...")
        elements = discover_elements()
        print(f"Elements: {len(elements)}")
        inventory = build_inventory(elements)
        inventory_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
        print(f"Wrote {inventory_path} ({len(inventory)} entries)")

    unique_files = sorted({item["filename"] for item in inventory})
    v100 = sum(1 for f in unique_files if version_bucket(f) == "psl-1.0.0")
    print(f"Unique UPF files: {len(unique_files)} (psl-1.0.0: {v100}, legacy: {len(unique_files) - v100})")

    failed: list[tuple[str, str]] = []
    skipped = 0
    downloaded = 0
    total_bytes = 0

    for i, filename in enumerate(unique_files, 1):
        dest = dest_for(filename)
        if dest.exists() and dest.stat().st_size > 0:
            skipped += 1
            if i % 100 == 0 or i == len(unique_files):
                print(f"[{i}/{len(unique_files)}] skipped so far: {skipped}")
            continue

        print(f"[{i}/{len(unique_files)}] {filename}")
        try:
            path, size = download_upf(filename)
            downloaded += 1
            total_bytes += size
            print(f"  -> {path} ({size // 1024} KB)")
        except Exception as exc:
            print(f"  [error] {exc}")
            failed.append((filename, str(exc)))
        time.sleep(0.1)

    summary = {
        "source": TABLE_URL,
        "total_unique": len(unique_files),
        "psl_1_0_0": v100,
        "legacy": len(unique_files) - v100,
        "downloaded_this_run": downloaded,
        "skipped_existing": skipped,
        "failed": len(failed),
        "bytes_downloaded": total_bytes,
        "failed_files": [{"filename": f, "error": e} for f, e in failed],
    }
    summary_path = META_DIR / "download_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    print(f"Target: {BASE_DIR}")
    print(f"Unique files: {len(unique_files)}")
    print(f"Downloaded this run: {downloaded} ({total_bytes // (1024 * 1024)} MB)")
    print(f"Skipped (existing): {skipped}")
    print(f"Failed: {len(failed)}")
    print(f"Summary: {summary_path}")
    for filename, err in failed[:20]:
        print(f"  FAILED: {filename} -> {err}")
    if len(failed) > 20:
        print(f"  ... and {len(failed) - 20} more")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
