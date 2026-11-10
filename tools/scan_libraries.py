#!/usr/bin/env python3
"""Scan all PP libraries and emit catalog/metadata/libraries/*.json entries."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (
    LIBRARIES_META,
    RAW,
    ROOT,
    element_from_filename,
    element_from_sssp_filename,
    md5_file,
    rel_path,
    sha256_file,
    write_json,
)
from pp_parser import parse_blps, parse_upf


def make_entry(
    *,
    library_id: str,
    path: Path,
    role: str,
    dataset: str | None = None,
    conversion_required: bool = False,
) -> dict:
    suffix = path.suffix.lower()
    if suffix in {".psp", ".lps"}:
        info = parse_blps(path)
    else:
        info = parse_upf(path)

    element = info.element or element_from_filename(path.name)
    if library_id.startswith("sssp") and not element:
        element = element_from_sssp_filename(path.name)

    entry = {
        "id": f"{library_id}:{element or 'unknown'}:{path.name}",
        "library_id": library_id,
        "element": element,
        "filename": path.name,
        "source_path": rel_path(path),
        "file_format": info.file_format,
        "formalism": info.formalism,
        "abacus_ready": info.abacus_ready,
        "xc_functional": info.xc_functional,
        "relativistic": info.relativistic,
        "has_soc": info.has_soc,
        "role": role,
        "dataset": dataset,
        "conversion_required": conversion_required,
        "md5": md5_file(path),
        "sha256": sha256_file(path),
        "parse_success": info.parse_success,
    }
    return entry


def scan_pslibrary() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    for bucket in ("psl-1.0.0", "legacy"):
        root = RAW / "PSlibrary" / bucket
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.UPF")):
            entries.append(
                make_entry(library_id="pslibrary", path=path, role="production", dataset=bucket)
            )
    summary = {
        "library_id": "pslibrary",
        "canonical_root": "raw/PSlibrary",
        "source_url": "https://pseudopotentials.quantum-espresso.org/legacy_tables/ps-library",
        "pp_family": "mixed",
        "abacus_formats": ["UPF"],
        "counts": {"entries": len(entries), "abacus_ready": sum(1 for e in entries if e["abacus_ready"])},
    }
    return summary, entries


def scan_pseudodojo() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    root = RAW / "PseudoDOJO/pseudos"
    for path in sorted(root.rglob("*.upf")):
        dataset = path.parent.name
        entries.append(
            make_entry(library_id="pseudodojo", path=path, role="production", dataset=dataset)
        )
    summary = {
        "library_id": "pseudodojo",
        "canonical_root": "raw/PseudoDOJO/pseudos",
        "source_url": "https://www.pseudo-dojo.org/",
        "pp_family": "NC",
        "abacus_formats": ["UPF"],
        "counts": {"entries": len(entries), "abacus_ready": sum(1 for e in entries if e["abacus_ready"])},
    }
    return summary, entries


def scan_gbrv() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    for sub, role in (("upf", "production"), ("archive", "archive")):
        root = RAW / "Vanderbilt-USPP/GBRV-v1.5" / sub
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            entries.append(
                make_entry(
                    library_id="gbrv",
                    path=path,
                    role=role,
                    dataset=f"GBRV-v1.5/{sub}",
                )
            )
    summary = {
        "library_id": "gbrv",
        "canonical_root": "raw/Vanderbilt-USPP/GBRV-v1.5",
        "source_url": "https://www.physics.rutgers.edu/gbrv/",
        "pp_family": "USPP",
        "abacus_formats": ["UPF"],
        "counts": {"entries": len(entries), "abacus_ready": sum(1 for e in entries if e["abacus_ready"])},
    }
    return summary, entries


def scan_pwmat() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    root = RAW / "PWmat"
    for path in sorted(root.rglob("*.UPF")) + sorted(root.rglob("*.upf")):
        rel = path.relative_to(root)
        dataset = rel.parts[0] if rel.parts else None
        entries.append(
            make_entry(library_id="pwmat", path=path, role="production", dataset=dataset)
        )
    summary = {
        "library_id": "pwmat",
        "canonical_root": "raw/PWmat",
        "source_url": "http://www.pwmat.com/potential-download",
        "pp_family": "NC",
        "abacus_formats": ["UPF"],
        "counts": {"entries": len(entries), "abacus_ready": sum(1 for e in entries if e["abacus_ready"])},
    }
    return summary, entries


def scan_sg15() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    root = RAW / "SG15-ONCV/upf"
    for path in sorted(root.glob("*.upf")):
        entries.append(make_entry(library_id="sg15_oncv", path=path, role="production"))
    summary = {
        "library_id": "sg15_oncv",
        "canonical_root": "raw/SG15-ONCV/upf",
        "source_url": "http://www.quantum-simulation.org/potentials/sg15_oncv/",
        "pp_family": "NC",
        "abacus_formats": ["UPF"],
        "counts": {"entries": len(entries), "abacus_ready": sum(1 for e in entries if e["abacus_ready"])},
    }
    return summary, entries


def scan_sssp() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    for set_dir in sorted((RAW / "SSSP/v2.0").glob("*_*/upf")):
        dataset = set_dir.parent.name
        for path in sorted(set_dir.glob("*.upf")):
            entries.append(
                make_entry(library_id="sssp", path=path, role="production", dataset=dataset)
            )
    summary = {
        "library_id": "sssp",
        "canonical_root": "raw/SSSP/v2.0",
        "source_url": "https://sssp.materialscloud.org/",
        "pp_family": "mixed",
        "abacus_formats": ["UPF"],
        "counts": {"entries": len(entries), "abacus_ready": sum(1 for e in entries if e["abacus_ready"])},
    }
    return summary, entries


def scan_pseudos_ac_she() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    root = RAW / "pseudos_ac_she"
    for path in sorted(root.rglob("*.upf")):
        parts = path.relative_to(root).parts
        dataset = parts[0] if parts else None
        entries.append(
            make_entry(
                library_id="pseudos_ac_she",
                path=path,
                role="production",
                dataset=dataset,
            )
        )
    summary = {
        "library_id": "pseudos_ac_she",
        "canonical_root": "raw/pseudos_ac_she",
        "source_url": "https://github.com/gmatteo/pseudos_ac_she",
        "pp_family": "NC",
        "automatic_recommendation": False,
        "manual_review_required": True,
        "counts": {"entries": len(entries), "abacus_ready": sum(1 for e in entries if e["abacus_ready"])},
    }
    return summary, entries


def scan_rappe() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    inv_path = RAW / "Rappe-group/metadata/inventory.json"
    if inv_path.exists():
        inventory = json.loads(inv_path.read_text(encoding="utf-8"))
        for bundle in inventory:
            for ext, rel in bundle.get("files", {}).items():
                path = RAW / "Rappe-group" / rel
                if not path.exists():
                    continue
                role = "upstream" if ext == "fhi" else "source_only"
                entries.append(
                    make_entry(
                        library_id="rappe",
                        path=path,
                        role=role,
                        dataset=bundle.get("functional"),
                        conversion_required=ext == "fhi",
                    )
                )
    summary = {
        "library_id": "rappe",
        "canonical_root": "raw/Rappe-group",
        "source_url": "https://www.sas.upenn.edu/rappegroup/research/pseudo-potential-gga.html",
        "pp_family": "FHI",
        "abacus_formats": [],
        "counts": {"entries": len(entries), "abacus_ready": 0},
    }
    return summary, entries


def scan_blps() -> tuple[dict, list[dict]]:
    entries: list[dict] = []
    root = RAW / "BLPSLibrary"
    for path in sorted(root.rglob("*.psp")) + sorted(root.rglob("*.lps")):
        parts = path.relative_to(root).parts
        dataset = "/".join(parts[:-1]) if len(parts) > 1 else None
        entries.append(
            make_entry(library_id="blps", path=path, role="production", dataset=dataset)
        )
    summary = {
        "library_id": "blps",
        "canonical_root": "raw/BLPSLibrary",
        "source_url": "https://github.com/PrincetonUniversity/BLPSLibrary",
        "pp_family": "BLPS",
        "abacus_formats": ["BLPS"],
        "counts": {"entries": len(entries), "abacus_ready": 0},
    }
    return summary, entries


SCANNERS = [
    scan_pslibrary,
    scan_pseudodojo,
    scan_gbrv,
    scan_pwmat,
    scan_sg15,
    scan_sssp,
    scan_pseudos_ac_she,
    scan_rappe,
    scan_blps,
]


def main() -> int:
    LIBRARIES_META.mkdir(parents=True, exist_ok=True)
    total = 0
    for scanner in SCANNERS:
        summary, entries = scanner()
        lib_id = summary["library_id"]
        out = {"summary": summary, "entries": entries}
        write_json(LIBRARIES_META / f"{lib_id}.json", out)
        total += len(entries)
        print(f"  {lib_id}: {len(entries)} entries, abacus_ready={summary['counts'].get('abacus_ready', 0)}")
    print(f"=== scan_libraries total entries: {total} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
