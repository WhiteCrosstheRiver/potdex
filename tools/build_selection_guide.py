#!/usr/bin/env python3
"""Build task-oriented manifests (coherent only) and selection_guide.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RAW, CATALOG, MANIFESTS, METADATA, ROOT, write_json
from families import pick_family_elements


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def manifest_from_family(
    scenario_id: str,
    family_id: str,
    display_name: str,
    choices: dict[str, dict],
    *,
    used_fallback: bool = False,
    fallback_sets: list[str] | None = None,
) -> dict:
    elements = {}
    for el in sorted(choices):
        row = choices[el]
        elements[el] = {
            "filename": row["filename"],
            "source_path": row["source_path"],
            "id": row["id"],
            "formalism": row.get("formalism"),
            "xc_functional": row.get("xc_functional"),
            "cutoff_wfc": row.get("cutoff_wfc"),
            "cutoff_rho": row.get("cutoff_rho"),
            "cutoff_source": row.get("cutoff_source"),
        }
    return {
        "scenario_id": scenario_id,
        "family_id": family_id,
        "primary_set": display_name,
        "coherent_family": True,
        "families_used": [display_name],
        "fallback_sets": fallback_sets or [],
        "silent_cross_library_mix": False,
        "mixed_set": used_fallback,
        "used_fallback_tar": used_fallback,
        "element_count": len(elements),
        "elements": elements,
        "view_path": f"catalog/views/by_family/{family_id}",
        "note": "场景视图已迁移至 by_family；请用 select_system_pp.py 做体系选势",
    }


def main() -> int:
    rows = load_jsonl(METADATA / "global_index.jsonl")

    relax = pick_family_elements(rows, "sssp_v2_pbe_efficiency")
    precision = pick_family_elements(rows, "sssp_v2_pbe_precision")
    blps = pick_family_elements(rows, "ofdft_blps_gga")

    precision_fallback = False
    prec_meta = RAW / "SSSP/v2.0/PBE_precision/metadata.json"
    if prec_meta.exists():
        precision_fallback = json.loads(prec_meta.read_text(encoding="utf-8")).get(
            "used_fallback_tar", False
        )

    manifests = {
        "relax_pbe": manifest_from_family(
            "relax_pbe",
            "sssp_v2_pbe_efficiency",
            "SSSP-2.0-PBE-efficiency",
            relax,
        ),
        "precision_pbe": manifest_from_family(
            "precision_pbe",
            "sssp_v2_pbe_precision",
            "SSSP-2.0-PBE-precision",
            precision,
            used_fallback=precision_fallback,
            fallback_sets=["SSSP-1.1.2-PBE-precision"] if precision_fallback else [],
        ),
        "ofdft_blps": manifest_from_family(
            "ofdft_blps",
            "ofdft_blps_gga",
            "BLPSLibrary-GGA-real",
            blps,
        ),
    }

    MANIFESTS.mkdir(parents=True, exist_ok=True)
    for name, data in manifests.items():
        write_json(MANIFESTS / f"{name}.json", data)

    # Deprecated mixed SOC shelf — documented, not used for system selection
    write_json(
        MANIFESTS / "soc_shelf_deprecated.json",
        {
            "warning": "此文件为历史混合货架，coherent_family=false，禁止用于多元素体系",
            "coherent_family": False,
            "use_instead": [
                "catalog/views/by_family/pseudodojo_nc_fr_pbe_standard",
                "catalog/views/by_family/sg15_oncv_pbe_fr",
                "catalog/views/by_family/pwmat_pd04_pbe_soc",
            ],
        },
    )

    guide = {
        "selection_model": {
            "element_shelf": "catalog/views/by_element/{Element}/",
            "coherent_family": "catalog/views/by_family/{family_id}/",
            "system_selection": "python tools/select_system_pp.py --elements ... --task ...",
        },
        "task_rules": {
            "relax": [
                "sssp_v2_pbe_efficiency",
                "sg15_oncv_pbe_sr",
                "pseudodojo_nc_sr_pbe_standard",
                "gbrv_v1.5_pbe_uspp",
            ],
            "precision": [
                "sssp_v2_pbe_precision",
                "pseudodojo_nc_sr_pbe_stringent",
                "sg15_oncv_pbe_sr",
            ],
            "soc": [
                "pseudodojo_nc_fr_pbe_standard",
                "pseudodojo_nc_fr_pbe_stringent",
                "sg15_oncv_pbe_fr",
                "pwmat_pd04_pbe_soc",
            ],
        },
        "legacy_scenarios": [
            {
                "scenario_id": "relax_pbe",
                "maps_to_family": "sssp_v2_pbe_efficiency",
                "description": "SSSP 效率集（仅 ABACUS-compatible 子集）",
            },
            {
                "scenario_id": "precision_pbe",
                "maps_to_family": "sssp_v2_pbe_precision",
                "description": "SSSP 精度集",
            },
        ],
        "specialist_heavy_elements": {
            "library_id": "pseudos_ac_she",
            "automatic_recommendation": False,
            "manual_review_required": True,
        },
        "single_point_policy": (
            "普通单点能继续使用结构弛豫时相同的 PP；"
            "若切换 precision PP，建议重新弛豫或检查原子受力"
        ),
    }
    write_json(METADATA / "selection_guide.json", guide)

    MAIN_ELEMENTS = [
        "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
        "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar", "K", "Ca",
        "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni", "Cu", "Zn",
        "Ga", "Ge", "As", "Se", "Br", "Kr", "Rb", "Sr", "Y", "Zr",
        "Nb", "Mo", "Tc", "Ru", "Rh", "Pd", "Ag", "Cd", "In", "Sn",
        "Sb", "Te", "I", "Xe", "Cs", "Ba", "La", "Hf", "Ta", "W",
        "Re", "Os", "Ir", "Pt", "Au", "Hg", "Tl", "Pb", "Bi",
    ]
    sg15 = pick_family_elements(rows, "sg15_oncv_pbe_sr")
    write_json(
        METADATA / "missing_elements.json",
        {
            "sssp_efficiency_missing": [el for el in MAIN_ELEMENTS if el not in relax],
            "sssp_precision_missing": [el for el in MAIN_ELEMENTS if el not in precision],
            "sg15_sr_covers_all_main": all(el in sg15 for el in MAIN_ELEMENTS),
            "note": "缺失元素请用 select_system_pp.py 自动切换到 SG15/PseudoDojo 等完整 family",
        },
    )

    print("=== build_selection_guide ===")
    for k, v in manifests.items():
        print(f"  {k}: {v['element_count']} elements (family={v['family_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
