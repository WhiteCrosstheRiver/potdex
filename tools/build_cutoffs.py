#!/usr/bin/env python3
"""Bind cutoffs to PP entries: SSSP exact-md5 / v2 official set; PseudoDojo Ha->Ry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RAW, METADATA, ROOT, write_json, write_jsonl


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def apply_sssp_v13(rows: list[dict]) -> tuple[int, list[dict]]:
    matched = 0
    unresolved: list[dict] = []
    md5_index = {row["md5"]: row for row in rows if row.get("md5")}

    for json_path in sorted((RAW / "SSSP").glob("v*/SSSP_*_*.json")):
        if "v2.0" in str(json_path):
            continue
        meta = json.loads(json_path.read_text(encoding="utf-8"))
        set_id = json_path.stem
        for element, info in meta.items():
            if not isinstance(info, dict) or "md5" not in info:
                continue
            md5 = info["md5"].lower()
            row = md5_index.get(md5)
            if row is None:
                unresolved.append(
                    {
                        "set_id": set_id,
                        "element": element,
                        "filename": info.get("filename"),
                        "md5": md5,
                        "reason": "md5_not_in_global_index",
                    }
                )
                continue
            row["cutoff_wfc"] = info.get("cutoff_wfc")
            row["cutoff_rho"] = info.get("cutoff_rho")
            row["cutoff_unit"] = "Ry"
            row["cutoff_source"] = set_id
            row["cutoff_match"] = "exact_md5"
            matched += 1
    return matched, unresolved


def _raw_key(path: str | None) -> str | None:
    """Path relative to raw/, whether or not the stored path carries the raw/ prefix."""
    if path is None:
        return None
    return path[4:] if path.startswith("raw/") else path


def apply_sssp_v2(rows: list[dict]) -> int:
    matched = 0
    for meta_path in sorted((RAW / "SSSP/v2.0").glob("*/metadata.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        set_id = meta.get("set_id", meta_path.parent.name)
        path_index = {_raw_key(item["source_path"]): item for item in meta.get("files", [])}
        for row in rows:
            if row.get("library_id") != "sssp":
                continue
            info = path_index.get(_raw_key(row.get("source_path")))
            if not info:
                continue
            row["cutoff_wfc"] = info.get("cutoff_wfc")
            row["cutoff_rho"] = info.get("cutoff_rho")
            row["cutoff_unit"] = "Ry"
            row["cutoff_source"] = set_id
            row["cutoff_match"] = "sssp_v2_official_set"
            matched += 1
    return matched


def apply_pseudodojo_hints(rows: list[dict]) -> int:
    matched = 0
    meta_dir = RAW / "PseudoDOJO/metadata"
    if not meta_dir.exists():
        return 0

    for meta_path in sorted(meta_dir.glob("*.json")):
        dataset = meta_path.stem
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for row in rows:
            if row.get("library_id") != "pseudodojo":
                continue
            row_dataset = row.get("dataset") or ""
            if row_dataset not in {dataset, f"{dataset}_upf"}:
                continue
            el = row.get("element")
            if not el or el not in meta:
                continue
            hints = meta[el]
            hn = hints.get("hn")
            hh = hints.get("hh")
            if hn is None and hh is None:
                continue
            level = "stringent" if "stringent" in dataset else "standard"
            original = hh if level == "stringent" and hh is not None else hn
            if original is None:
                continue
            row["original_cutoff"] = original
            row["original_unit"] = "Ha"
            row["ecutwfc_ry"] = float(original) * 2
            row["cutoff_level"] = "high" if level == "stringent" else "normal"
            row["cutoff_source"] = "PseudoDojo hint"
            row["cutoff_match"] = "dojo_hint"
            matched += 1
    return matched


def main() -> int:
    src = METADATA / "global_index.jsonl"
    if not src.exists():
        print("global_index.jsonl not found; run build_global_index.py first", file=sys.stderr)
        return 1

    rows = load_jsonl(src)
    v13_matched, unresolved = apply_sssp_v13(rows)
    v2_matched = apply_sssp_v2(rows)
    dojo_matched = apply_pseudodojo_hints(rows)

    write_jsonl(src, rows)

    cutoffs_summary = {
        "sssp_v13_exact_md5": v13_matched,
        "sssp_v2_official_set": v2_matched,
        "pseudodojo_hints": dojo_matched,
        "unresolved_count": len(unresolved),
    }
    write_json(METADATA / "cutoffs_merged.json", cutoffs_summary)
    write_json(METADATA / "cutoffs_unresolved.json", unresolved)

    print("=== build_cutoffs ===")
    print(cutoffs_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
