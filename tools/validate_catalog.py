#!/usr/bin/env python3
"""Validate catalog integrity after build."""

from __future__ import annotations

import json
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


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    rows = load_jsonl(METADATA / "global_index.jsonl")

    paw_in_ready = [r["id"] for r in rows if r.get("abacus_ready") and r.get("formalism") == "PAW"]
    if paw_in_ready:
        errors.append(f"PAW in abacus_ready: {len(paw_in_ready)} entries")

    rrkjus_uspp = [
        r["id"]
        for r in rows
        if "rrkjus" in r.get("filename", "").lower() and r.get("formalism") != "USPP"
    ]
    if rrkjus_uspp[:5]:
        warnings.append(f"rrkjus not USPP: {len(rrkjus_uspp)} entries (sample check)")

    for manifest_path in sorted(MANIFESTS.glob("*.json")):
        if manifest_path.name in ("soc_shelf_deprecated.json",):
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("coherent_family", True):
            errors.append(f"incoherent manifest without deprecation: {manifest_path.name}")
            continue
        family_id = manifest.get("family_id")
        scenario_id = manifest.get("scenario_id")
        if family_id:
            family_view = CATALOG / "views" / "by_family" / family_id
            if not family_view.exists():
                errors.append(f"missing family view: {family_id}")
        if scenario_id and family_id:
            alias = CATALOG / "views" / "by_scenario" / scenario_id
            if not alias.exists():
                warnings.append(f"missing scenario alias: {scenario_id}")

    if (MANIFESTS / "soc_pbe.json").exists():
        errors.append("deprecated mixed soc_pbe.json still present — remove it")

    for row in rows:
        src = resolve_catalog_path(row["source_path"])
        if not src.exists():
            errors.append(f"missing source: {row['source_path']}")

    report = {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "checks": {
            "total_entries": len(rows),
            "abacus_ready": sum(1 for r in rows if r.get("abacus_ready")),
            "paw_rejected_from_ready": len(paw_in_ready) == 0,
        },
    }
    write_json(METADATA / "validation_report.json", report)

    print("=== validate_catalog ===")
    print(f"  ok: {report['ok']}")
    print(f"  errors: {len(errors)}")
    print(f"  warnings: {len(warnings)}")
    for err in errors[:20]:
        print(f"    ERROR: {err}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
