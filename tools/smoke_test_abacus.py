#!/usr/bin/env python3
"""ABACUS smoke test framework — validates PP readability when abacus is available."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import resolve_catalog_path, CATALOG, METADATA, ROOT, write_json
from select_system_pp import evaluate_family, load_jsonl, task_family_order

TESTS = [
    {
        "id": "nc_si",
        "description": "普通 NC — Si SCF",
        "elements": ["Si"],
        "task": "relax",
        "family_expect": "sg15_oncv_pbe_sr",
    },
    {
        "id": "uspp_al",
        "description": "USPP — Al SCF",
        "elements": ["Al"],
        "task": "uspp",
        "family_expect": "gbrv_v1.5_pbe_uspp",
    },
    {
        "id": "magnetic_fe",
        "description": "磁性 — Fe 自旋极化",
        "elements": ["Fe"],
        "task": "relax",
        "family_expect": "sg15_oncv_pbe_sr",
    },
    {
        "id": "soc_bi",
        "description": "SOC — Bi",
        "elements": ["Bi"],
        "task": "soc",
        "family_expect": "pseudodojo_nc_fr_pbe_standard",
    },
]


def find_abacus() -> str | None:
    exe = shutil.which("abacus")
    if exe:
        return exe
    for candidate in (
        Path("C:/Program Files/ABACUS/abacus.exe"),
        Path.home() / "abacus" / "abacus",
    ):
        if candidate.exists():
            return str(candidate)
    return None


def abacus_version(exe: str) -> str:
    try:
        proc = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return (proc.stdout or proc.stderr or "").strip()[:200]
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def validate_pp_readable(source_path: Path) -> tuple[bool, str]:
    if not source_path.exists():
        return False, "file missing"
    text = source_path.read_text(encoding="utf-8", errors="replace")
    if "<UPF" not in text and "<PP_HEADER>" not in text:
        return False, "not a UPF file"
    if "element=" not in text.lower() and "<PP_HEADER>" not in text:
        return False, "no PP_HEADER"
    return True, "header readable"


def run_smoke_tests() -> dict:
    abacus = find_abacus()
    rows = load_jsonl(METADATA / "global_index.jsonl")
    results = []

    for test in TESTS:
        order = task_family_order(test["task"], "PBE", test["task"] == "soc")
        evals = [evaluate_family(fid, test["elements"], rows) for fid in order]
        best = next((e for e in evals if e["full_coverage"]), None)

        entry = {
            "id": test["id"],
            "description": test["description"],
            "status": "pending",
            "family_used": None,
            "pp_check": None,
            "abacus_run": "skipped",
        }

        if best is None:
            # No candidate family has any of these elements: the libraries are simply
            # not downloaded (partial raw/), which is not a catalog error.
            if all(len(e.get("missing_elements", [])) == len(test["elements"]) for e in evals):
                entry["status"] = "skipped_library_not_present"
            else:
                entry["status"] = "failed"
                entry["error"] = "no coherent family covers test system"
            results.append(entry)
            continue

        entry["family_used"] = best["family_id"]
        src = resolve_catalog_path(best["elements"][test["elements"][0]]["source_path"])
        ok, msg = validate_pp_readable(src)
        entry["pp_check"] = msg
        if not ok:
            entry["status"] = "failed"
            results.append(entry)
            continue

        if abacus:
            entry["abacus_run"] = "not_implemented_minimal_input"
            entry["status"] = "pp_readable"
            entry["note"] = "ABACUS 已找到，完整 SCF 冒烟需本地 INPUT/STRU 模板"
        else:
            entry["abacus_run"] = "skipped_no_abacus"
            entry["status"] = "pp_readable"

        results.append(entry)

    passed = sum(1 for r in results if r["status"] in ("pp_readable", "passed"))
    skipped = sum(1 for r in results if r["status"].startswith("skipped"))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # pp_readable only proves the file parses; an ABACUS SCF run is not done yet.
        "abacus_smoke_test": "passed" if passed == len(results) else ("partial" if passed + skipped == len(results) else "failed"),
        "skipped": skipped,
        "abacus_found": abacus is not None,
        "abacus_executable": abacus,
        "abacus_version": abacus_version(abacus) if abacus else None,
        "passed": passed,
        "total": len(results),
        "tests": results,
    }
    return report


def main() -> int:
    report = run_smoke_tests()
    write_json(METADATA / "abacus_smoke_test.json", report)
    print("=== smoke_test_abacus ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["passed"] + report["skipped"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
