#!/usr/bin/env python3
"""Parse UPF/BLPS headers and write soc_index.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import CATALOG, METADATA, ROOT, rel_path, write_json
from pp_parser import parse_blps, parse_upf


def collect_pp_files() -> list[Path]:
    patterns = [
        "PSlibrary/**/*.UPF",
        "PSlibrary/**/*.upf",
        "PseudoDOJO/**/*.upf",
        "Vanderbilt-USPP/**/*.UPF",
        "Vanderbilt-USPP/**/*.upf",
        "PWmat/**/*.UPF",
        "PWmat/**/*.upf",
        "SG15-ONCV/**/*.upf",
        "SSSP/**/*.upf",
        "pseudos_ac_she/**/*.upf",
        "BLPSLibrary/**/*.psp",
        "BLPSLibrary/**/*.lps",
    ]
    files: list[Path] = []
    for pat in patterns:
        files.extend(ROOT.glob(pat))
    return sorted({p.resolve() for p in files if p.is_file()})


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse PP headers for catalog")
    parser.add_argument("--limit", type=int, default=0, help="Limit files for testing")
    args = parser.parse_args()

    files = collect_pp_files()
    if args.limit:
        files = files[: args.limit]

    soc_entries: list[dict] = []
    stats = {"parsed": 0, "abacus_ready": 0, "paw": 0, "soc": 0, "failed": 0}

    cache_dir = METADATA / "parsed_headers"
    cache_dir.mkdir(parents=True, exist_ok=True)

    for path in files:
        suffix = path.suffix.lower()
        if suffix in {".psp", ".lps"}:
            info = parse_blps(path)
        else:
            info = parse_upf(path)

        if not info.parse_success:
            stats["failed"] += 1
            continue

        stats["parsed"] += 1
        if info.abacus_ready:
            stats["abacus_ready"] += 1
        if info.formalism == "PAW":
            stats["paw"] += 1
        if info.has_soc and info.relativistic == "full":
            stats["soc"] += 1
            soc_entries.append(
                {
                    "source_path": rel_path(path),
                    "element": info.element,
                    "filename": path.name,
                    "relativistic": info.relativistic,
                    "has_soc": info.has_soc,
                    "formalism": info.formalism,
                    "xc_functional": info.xc_functional,
                }
            )

        cache_name = rel_path(path).replace("/", "__") + ".json"
        write_json(cache_dir / cache_name, info.to_dict())

    write_json(
        METADATA / "soc_index.json",
        {
            "generated_from": "parse_upf_header.py",
            "count": len(soc_entries),
            "entries": soc_entries,
        },
    )

    print("=== parse_upf_header summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  soc_index: {METADATA / 'soc_index.json'}")
    print(f"  header cache: {cache_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
