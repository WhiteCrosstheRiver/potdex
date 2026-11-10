#!/usr/bin/env python3
"""Build catalog views: by_family, by_element; legacy by_scenario aliases."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import resolve_catalog_path, CATALOG, MANIFESTS, METADATA, ROOT, write_json


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


def build_legacy_scenario_aliases() -> dict:
    """by_scenario 仅作为 by_family 的符号链接别名，不再混合跨库。"""
    stats: dict[str, dict] = {}
    scenario_root = CATALOG / "views" / "by_scenario"
    if scenario_root.exists():
        shutil.rmtree(scenario_root)
    scenario_root.mkdir(parents=True, exist_ok=True)

    for manifest_path in sorted(MANIFESTS.glob("*.json")):
        if manifest_path.name == "soc_shelf_deprecated.json":
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        family_id = manifest.get("family_id")
        scenario_id = manifest.get("scenario_id")
        if not family_id or not scenario_id:
            continue

        family_view = CATALOG / "views" / "by_family" / family_id
        alias = scenario_root / scenario_id
        if not family_view.exists():
            stats[scenario_id] = {"status": "missing_family_view"}
            continue
        try:
            alias.symlink_to(family_view, target_is_directory=True)
            stats[scenario_id] = {
                "status": "symlink_to_family",
                "target": str(family_view.relative_to(ROOT)),
            }
        except OSError:
            # fallback: copy links manually
            alias.mkdir(parents=True, exist_ok=True)
            linked = 0
            for src_file in family_view.glob("*.upf"):
                dest = alias / src_file.name
                link_file(src_file, dest)
                linked += 1
            stats[scenario_id] = {"status": "copied_from_family", "linked": linked}
    return stats


def build_element_views(rows: list[dict]) -> dict:
    view_root = CATALOG / "views" / "by_element"
    if view_root.exists():
        shutil.rmtree(view_root)
    view_root.mkdir(parents=True, exist_ok=True)

    methods: dict[str, int] = {}
    linked = 0
    for row in rows:
        if not row.get("abacus_ready"):
            continue
        el = row.get("element")
        if not el:
            continue
        src = resolve_catalog_path(row["source_path"])
        if not src.exists():
            continue
        lib = row["library_id"]
        dataset = (row.get("dataset") or "default").replace("/", "_")
        dest_name = f"{lib}__{dataset}__{row['filename']}"
        dest = view_root / el / dest_name
        method = link_file(src, dest)
        methods[method] = methods.get(method, 0) + 1
        linked += 1

    return {"linked": linked, "methods": methods}


def main() -> int:
    # build_families must run first
    from build_families import main as build_families_main

    build_families_main()

    rows = load_jsonl(METADATA / "global_index.jsonl")
    scenario_stats = build_legacy_scenario_aliases()
    element_stats = build_element_views(rows)

    families_summary = json.loads(
        (CATALOG / "views" / "families_build_summary.json").read_text(encoding="utf-8")
    )
    summary = {
        "by_family": families_summary,
        "by_scenario_aliases": scenario_stats,
        "by_element": element_stats,
    }
    write_json(CATALOG / "views" / "build_summary.json", summary)

    print("=== build_catalog_views ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
