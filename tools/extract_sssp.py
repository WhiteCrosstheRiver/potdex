#!/usr/bin/env python3
"""Extract SSSP v2.0 official tar archives into canonical upf directories."""

from __future__ import annotations

import json
import shutil
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT, element_from_filename, element_from_sssp_filename, md5_file, rel_path, write_json

SETS = [
    {
        "tar": ROOT / "SSSP/v2.0/efficiency/SSSP-lib-pbe-eff-v2.tar.gz",
        "fallback_tar": None,
        "dest": ROOT / "SSSP/v2.0/PBE_efficiency/upf",
        "metadata_src": ROOT / "SSSP/v2.0/efficiency/cutoffs.json",
        "fallback_metadata": None,
        "set_id": "SSSP-2.0-PBE-efficiency",
        "xc": "PBE",
        "tier": "efficiency",
    },
    {
        "tar": ROOT / "SSSP/v2.0/precision/SSSP-lib-pbe-prec-v2.tar.gz",
        "fallback_tar": ROOT / "SSSP/v1.1.2/SSSP_1.1.2_PBE_precision.tar.gz",
        "dest": ROOT / "SSSP/v2.0/PBE_precision/upf",
        "metadata_src": ROOT / "SSSP/v2.0/precision/cutoffs.json",
        "fallback_metadata": ROOT / "SSSP/v1.1.2/SSSP_1.1.2_PBE_precision.json",
        "set_id": "SSSP-2.0-PBE-precision",
        "xc": "PBE",
        "tier": "precision",
    },
    {
        "tar": ROOT / "SSSP/v2.0/efficiency/SSSP-lib-pbesol-eff-v2.tar.gz",
        "fallback_tar": None,
        "dest": ROOT / "SSSP/v2.0/PBEsol_efficiency/upf",
        "metadata_src": ROOT / "SSSP/v2.0/efficiency/cutoffs.json",
        "fallback_metadata": None,
        "set_id": "SSSP-2.0-PBEsol-efficiency",
        "xc": "PBEsol",
        "tier": "efficiency",
    },
    {
        "tar": ROOT / "SSSP/v2.0/precision/SSSP-lib-pbesol-prec-v2.tar.gz",
        "fallback_tar": None,
        "dest": ROOT / "SSSP/v2.0/PBEsol_precision/upf",
        "metadata_src": ROOT / "SSSP/v2.0/precision/cutoffs.json",
        "fallback_metadata": None,
        "set_id": "SSSP-2.0-PBEsol-precision",
        "xc": "PBEsol",
        "tier": "precision",
    },
]


def _extract_tar(tar_path: Path, dest: Path) -> int:
    extracted = 0
    with tarfile.open(tar_path, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile() or not member.name.lower().endswith(".upf"):
                continue
            src = tf.extractfile(member)
            if src is None:
                continue
            out_name = Path(member.name).name
            out_path = dest / out_name
            with out_path.open("wb") as f:
                shutil.copyfileobj(src, f)
            extracted += 1
    return extracted


def extract_set(spec: dict) -> dict:
    tar_path: Path = spec["tar"]
    dest: Path = spec["dest"]
    marker = dest.parent / ".extracted"
    used_tar = tar_path
    used_fallback = False

    if marker.exists() and any(dest.glob("*.upf")):
        files = sorted(dest.glob("*.upf"))
        return {
            "set_id": spec["set_id"],
            "status": "skipped_existing",
            "files": len(files),
            "dest": rel_path(dest),
        }

    if not tar_path.exists() and spec.get("fallback_tar"):
        used_tar = spec["fallback_tar"]
        used_fallback = True

    if not used_tar.exists():
        return {
            "set_id": spec["set_id"],
            "status": "missing_tar",
            "tar": rel_path(used_tar),
        }

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    try:
        extracted = _extract_tar(used_tar, dest)
    except (EOFError, tarfile.ReadError, OSError) as exc:
        fallback = spec.get("fallback_tar")
        if fallback and fallback.exists() and fallback != used_tar:
            used_tar = fallback
            used_fallback = True
            if dest.exists():
                shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            try:
                extracted = _extract_tar(used_tar, dest)
            except (EOFError, tarfile.ReadError, OSError) as exc2:
                return {
                    "set_id": spec["set_id"],
                    "status": "extract_failed",
                    "tar": rel_path(used_tar),
                    "error": str(exc2),
                }
        else:
            return {
                "set_id": spec["set_id"],
                "status": "extract_failed",
                "tar": rel_path(used_tar),
                "error": str(exc),
            }

    metadata_src = spec["metadata_src"]
    if used_fallback and spec.get("fallback_metadata"):
        metadata_src = spec["fallback_metadata"]

    metadata = {
        "set_id": spec["set_id"],
        "xc_functional": spec["xc"],
        "tier": spec["tier"],
        "source_tar": rel_path(used_tar),
        "used_fallback_tar": used_fallback,
        "cutoffs_source": rel_path(metadata_src) if metadata_src.exists() else None,
        "files": [],
    }

    cutoffs = {}
    if metadata_src.exists():
        cutoffs = json.loads(metadata_src.read_text(encoding="utf-8"))

    for upf in sorted(dest.glob("*.upf")):
        element = element_from_sssp_filename(upf.name) or element_from_filename(upf.name)
        entry = {
            "filename": upf.name,
            "element": element,
            "source_path": rel_path(upf),
            "md5": md5_file(upf),
            "size": upf.stat().st_size,
        }
        if element and element in cutoffs and isinstance(cutoffs[element], dict):
            info = cutoffs[element]
            entry["cutoff_wfc"] = info.get("cutoff_wfc")
            entry["cutoff_rho"] = info.get("cutoff_rho")
            entry["cutoff_unit"] = "Ry"
            entry["cutoff_source"] = spec["set_id"]
            entry["cutoff_match"] = (
                "exact_md5" if "md5" in info else "sssp_v2_official_set"
            )
            if "md5" in info:
                entry["expected_md5"] = info["md5"]
        metadata["files"].append(entry)

    meta_path = dest.parent / "metadata.json"
    write_json(meta_path, metadata)
    marker.write_text("ok\n", encoding="utf-8")

    return {
        "set_id": spec["set_id"],
        "status": "extracted",
        "files": extracted,
        "dest": rel_path(dest),
        "metadata": rel_path(meta_path),
        "used_fallback_tar": used_fallback,
    }


def main() -> int:
    results = [extract_set(spec) for spec in SETS]
    summary_path = ROOT / "SSSP/v2.0/extract_summary.json"
    write_json(summary_path, {"sets": results})
    print("=== extract_sssp summary ===")
    for item in results:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
