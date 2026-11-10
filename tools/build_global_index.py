#!/usr/bin/env python3
"""Merge per-library scans into global_index.jsonl and coverage_report.json."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import LIBRARIES_META, METADATA, write_json, write_jsonl


def main() -> int:
    rows: list[dict] = []
    md5_map: dict[str, str] = {}
    duplicates = 0

    for lib_file in sorted(LIBRARIES_META.glob("*.json")):
        data = json.loads(lib_file.read_text(encoding="utf-8"))
        for entry in data.get("entries", []):
            md5 = entry.get("md5")
            if md5 in md5_map:
                entry["duplicate_of"] = md5_map[md5]
                duplicates += 1
            else:
                md5_map[md5] = entry["id"]
                entry["duplicate_of"] = None
            rows.append(entry)

    write_jsonl(METADATA / "global_index.jsonl", rows)

    by_element: dict[str, list[str]] = defaultdict(list)
    abacus_by_element: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        el = row.get("element")
        if not el:
            continue
        by_element[el].append(row["id"])
        if row.get("abacus_ready"):
            abacus_by_element[el].append(row["id"])

    coverage = {
        "total_entries": len(rows),
        "duplicate_entries": duplicates,
        "elements_any": len(by_element),
        "elements_abacus_ready": len(abacus_by_element),
        "by_library": {},
        "by_element_abacus_count": {k: len(v) for k, v in sorted(abacus_by_element.items())},
    }

    for row in rows:
        lib = row["library_id"]
        coverage["by_library"].setdefault(lib, {"total": 0, "abacus_ready": 0})
        coverage["by_library"][lib]["total"] += 1
        if row.get("abacus_ready"):
            coverage["by_library"][lib]["abacus_ready"] += 1

    write_json(METADATA / "coverage_report.json", coverage)
    print(f"=== build_global_index: {len(rows)} rows, {duplicates} duplicates ===")
    print(f"  elements (abacus_ready): {coverage['elements_abacus_ready']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
