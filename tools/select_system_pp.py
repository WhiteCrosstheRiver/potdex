#!/usr/bin/env python3
"""Select a coherent PP family for a multi-element system."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import resolve_catalog_path, CATALOG, METADATA, ROOT, write_json
from families import FAMILIES, FAMILY_BY_ID, family_covers, pick_family_elements


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_family_manifest(family_id: str) -> dict | None:
    path = CATALOG / "manifests" / "families" / f"{family_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def task_family_order(task: str, xc: str, soc: bool) -> list[str]:
    if soc:
        return [
            "pseudodojo_nc_fr_pbe_standard",
            "pseudodojo_nc_fr_pbe_stringent",
            "sg15_oncv_pbe_fr",
            "pwmat_pd04_pbe_soc",
        ]
    if task == "precision":
        return [
            "sssp_v2_pbe_precision",
            "pseudodojo_nc_sr_pbe_stringent",
            "sg15_oncv_pbe_sr",
            "gbrv_v1.5_pbe_uspp",
        ]
    if task == "uspp":
        return ["gbrv_v1.5_pbe_uspp"]
    if task == "ofdft":
        return ["ofdft_blps_gga"]
    # relax (default)
    return [
        "sssp_v2_pbe_efficiency",
        "sg15_oncv_pbe_sr",
        "pseudodojo_nc_sr_pbe_standard",
        "gbrv_v1.5_pbe_uspp",
    ]


def reject_reason(family_id: str, elements: list[str], choices: dict[str, dict], rows: list[dict]) -> str:
    missing = [el for el in elements if el not in choices]
    if not missing:
        return ""
    if family_id.startswith("sssp"):
        details = []
        for el in missing[:5]:
            sssp_rows = [
                r
                for r in rows
                if r.get("library_id") == "sssp"
                and r.get("element") == el
                and r.get("dataset") == family_id.replace("sssp_v2_", "").replace("_", "_").replace("pbe", "PBE")
            ]
            # simpler: check if element exists but PAW only
            ds = "PBE_efficiency" if "efficiency" in family_id else "PBE_precision"
            el_rows = [
                r for r in rows if r.get("library_id") == "sssp" and r.get("element") == el and r.get("dataset") == ds
            ]
            if el_rows and all(r.get("formalism") == "PAW" for r in el_rows):
                details.append(f"{el}: SSSP 仅有 PAW，ABACUS 不支持")
            else:
                details.append(f"{el}: 不在 SSSP 官方集")
        return "; ".join(details) if details else f"缺少元素: {', '.join(missing)}"
    return f"缺少元素: {', '.join(missing)}"


def evaluate_family(
    family_id: str,
    elements: list[str],
    rows: list[dict],
) -> dict:
    spec = FAMILY_BY_ID[family_id]
    choices = pick_family_elements(rows, family_id)
    ok, missing = family_covers(elements, choices)
    result = {
        "family_id": family_id,
        "display_name": spec.display_name,
        "full_coverage": ok,
        "coherent_family": True,
        "missing_elements": missing,
        "elements": {},
        "reject_reason": "",
        "pseudo_dir": f"catalog/views/by_family/{family_id}",
    }
    if ok:
        for el in elements:
            row = choices[el]
            result["elements"][el] = {
                "filename": f"{el}.upf",
                "source_path": row["source_path"],
                "original_filename": row["filename"],
                "formalism": row.get("formalism"),
                "cutoff_wfc": row.get("cutoff_wfc"),
                "cutoff_rho": row.get("cutoff_rho"),
            }
    else:
        result["reject_reason"] = reject_reason(family_id, elements, choices, rows)
    return result


def materialize_output(plan: dict, output: Path) -> None:
    pp_dir = output / "pp"
    if pp_dir.exists():
        shutil.rmtree(pp_dir)
    pp_dir.mkdir(parents=True, exist_ok=True)

    for el, info in plan["elements"].items():
        src = resolve_catalog_path(info["source_path"])
        dest = pp_dir / f"{el}.upf"
        if src.exists():
            try:
                os.link(src, dest)
            except OSError:
                shutil.copy2(src, dest)

    species_lines = []
    for el in sorted(plan["elements"]):
        species_lines.append(f"{el}  0.0  {el}.upf")

    (output / "pp_selection.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (output / "STRU.species.inc").write_text(
        "ATOMIC_SPECIES\n" + "\n".join(species_lines) + "\n",
        encoding="utf-8",
    )


def print_report(elements: list[str], task: str, xc: str, soc: bool, results: list[dict]) -> None:
    print(f"体系：{' '.join(elements)}")
    print(f"任务：{task}")
    print(f"泛函：{xc}  SOC：{'是' if soc else '否'}")
    print()

    rank = 1
    for res in results:
        if res["full_coverage"]:
            print(f"方案 {rank}：{res['display_name']}")
            for el in elements:
                info = res["elements"][el]
                print(f"  {el}: {info['source_path']}")
            print("  完整覆盖：是")
            print("  同一数据集：是")
            print(f"  pseudo_dir: {res['pseudo_dir']}")
            print()
            rank += 1
        else:
            print(f"拒绝：{res['display_name']}")
            print(f"  原因：{res['reject_reason']}")
            print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Select coherent PP family for a system")
    parser.add_argument("--elements", nargs="+", required=True, help="Element symbols, e.g. Fe O")
    parser.add_argument("--task", choices=["relax", "precision", "soc", "uspp", "ofdft"], default="relax")
    parser.add_argument("--xc", default="PBE")
    parser.add_argument("--soc", action="store_true", help="Require full-relativistic SOC PP")
    parser.add_argument("--allow-mixed", action="store_true", help="Allow mixed-family shelf (not recommended)")
    parser.add_argument("--output", type=Path, help="Write pp/ + pp_selection.json to this directory")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    elements = [el[0].upper() + el[1:].lower() if len(el) > 1 else el.upper() for el in args.elements]
    soc = args.soc or args.task == "soc"

    index_path = METADATA / "global_index.jsonl"
    if not index_path.exists():
        print("global_index.jsonl not found. Run: python tools/run_pipeline.py", file=sys.stderr)
        return 1

    rows = load_jsonl(index_path)
    order = task_family_order(args.task, args.xc, soc)
    results = [evaluate_family(fid, elements, rows) for fid in order]

    if args.json:
        print(json.dumps({"elements": elements, "task": args.task, "results": results}, indent=2, ensure_ascii=False))
    else:
        print_report(elements, args.task, args.xc, soc, results)

    best = next((r for r in results if r["full_coverage"]), None)
    if best and args.output:
        materialize_output(best, args.output)
        if not args.json:
            print(f"已写入：{args.output / 'pp'}")
            print(f"  pseudo_dir → {args.output / 'pp'}")

    return 0 if best else 1


if __name__ == "__main__":
    raise SystemExit(main())
