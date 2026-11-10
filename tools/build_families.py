#!/usr/bin/env python3
"""Build coherent family manifests and by_family flat views."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import resolve_catalog_path, CATALOG, METADATA, ROOT, write_json
from families import FAMILIES, pick_family_elements


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def link_file(src: Path, dest: Path) -> str:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    try:
        os.link(src, dest)
        return "hardlink"
    except OSError:
        pass
    try:
        dest.symlink_to(src)
        return "symlink"
    except OSError:
        pass
    shutil.copy2(src, dest)
    return "copy"


def build_family_manifest(spec, choices: dict[str, dict]) -> dict:
    elements = {}
    for el in sorted(choices):
        row = choices[el]
        elements[el] = {
            "filename": row["filename"],
            "source_path": row["source_path"],
            "id": row["id"],
            "formalism": row.get("formalism"),
            "xc_functional": row.get("xc_functional"),
            "has_soc": row.get("has_soc"),
            "relativistic": row.get("relativistic"),
            "cutoff_wfc": row.get("cutoff_wfc"),
            "cutoff_rho": row.get("cutoff_rho"),
            "cutoff_source": row.get("cutoff_source"),
        }
    return {
        "family_id": spec.family_id,
        "display_name": spec.display_name,
        "description": spec.description,
        "task_tags": list(spec.task_tags),
        "xc_functional": spec.xc,
        "soc": spec.soc,
        "coherent_family": True,
        "families_used": [spec.display_name],
        "silent_cross_library_mix": False,
        "element_count": len(elements),
        "elements": elements,
        "view_path": f"catalog/views/by_family/{spec.family_id}",
    }


def main() -> int:
    rows = load_jsonl(METADATA / "global_index.jsonl")
    families_dir = CATALOG / "manifests" / "families"
    families_dir.mkdir(parents=True, exist_ok=True)
    view_root = CATALOG / "views" / "by_family"
    if view_root.exists():
        shutil.rmtree(view_root)
    view_root.mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    stats: dict[str, dict] = {}

    for spec in FAMILIES:
        choices = pick_family_elements(rows, spec.family_id)
        manifest = build_family_manifest(spec, choices)
        write_json(families_dir / f"{spec.family_id}.json", manifest)

        view_dir = view_root / spec.family_id
        view_dir.mkdir(parents=True, exist_ok=True)
        methods: dict[str, int] = {}
        linked = 0
        for el, info in manifest["elements"].items():
            src = resolve_catalog_path(info["source_path"])
            if not src.exists():
                continue
            if spec.family_id == "ofdft_blps_gga":
                dest_name = info["filename"]
            else:
                dest_name = f"{el}.upf"
            dest = view_dir / dest_name
            method = link_file(src, dest)
            methods[method] = methods.get(method, 0) + 1
            linked += 1

        stats[spec.family_id] = {
            "elements": manifest["element_count"],
            "linked": linked,
            "methods": methods,
        }
        index.append(
            {
                "family_id": spec.family_id,
                "display_name": spec.display_name,
                "element_count": manifest["element_count"],
                "task_tags": list(spec.task_tags),
                "soc": spec.soc,
                "view_path": manifest["view_path"],
            }
        )

    write_json(CATALOG / "manifests" / "families_index.json", {"families": index})
    write_json(CATALOG / "views" / "families_build_summary.json", stats)

    print("=== build_families ===")
    for spec in FAMILIES:
        print(f"  {spec.family_id}: {stats[spec.family_id]['elements']} elements, linked={stats[spec.family_id]['linked']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
