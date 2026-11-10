"""
Reorganize Rappe-group and build metadata.

Layout policy:
- upstream/fhi/     : upstream computable artifacts (not ABACUS production)
- source-only/      : param + rpt, excluded from auto selection
- abacus/upf/       : reserved for future converted UPF (currently empty)
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "Rappe-group"
METADATA = ROOT / "metadata"

LEGACY_BUCKETS = {
    "fhi": ("upstream", "fhi"),
    "param": ("source-only", "param"),
    "rpt": ("source-only", "rpt"),
}

FUNCTIONALS = ("PBE-GGA", "PZ-LDA")

# Curated upstream gaps; do not retry source downloads for these.
UPSTREAM_MISSING = [
    {
        "functional": "PBE-GGA",
        "element": "Y",
        "missing_files": ["y.optgga3.fhi"],
        "missing_kinds": ["fhi"],
        "notes": "Page links y.optgga3.fhi (404). Only optgga1 param/rpt present.",
    },
    {
        "functional": "PBE-GGA",
        "element": "P",
        "missing_files": ["p.optgga1.fhi", "p.optgga2.fhi"],
        "missing_kinds": ["fhi"],
        "notes": "Source page has param/rpt only; no .fhi links.",
    },
    {
        "functional": "PBE-GGA",
        "element": "Mo",
        "missing_files": ["mo.optgga3.fhi", "mo.optgga3.rpt"],
        "missing_kinds": ["fhi", "rpt"],
        "notes": "Source page has mo.optgga3.param only.",
    },
    {
        "functional": "PZ-LDA",
        "element": "Ga",
        "missing_files": ["ga.optlda1.fhi"],
        "missing_kinds": ["fhi"],
        "notes": "Source page has param/rpt only; no .fhi link.",
    },
]

VERSION_RE = re.compile(r"(?:optgga|optlda|ggaopt)(\d+)", re.I)


def version_index(basename: str) -> int | None:
    match = VERSION_RE.search(basename)
    return int(match.group(1)) if match else None


def basename_from_filename(filename: str) -> str:
    return Path(filename).stem


def dest_for(functional: str, ext: str, element: str, filename: str) -> Path:
    bucket, sub = LEGACY_BUCKETS[ext]
    return ROOT / functional / bucket / sub / element / filename


def migrate_legacy_layout() -> int:
    moved = 0
    for functional in FUNCTIONALS:
        for ext, (bucket, sub) in LEGACY_BUCKETS.items():
            legacy_root = ROOT / functional / ext
            if not legacy_root.exists():
                continue
            for src in legacy_root.rglob("*"):
                if not src.is_file():
                    continue
                element = src.parent.name
                dest = ROOT / functional / bucket / sub / element / src.name
                if dest.resolve() == src.resolve():
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    src.unlink()
                else:
                    shutil.move(str(src), str(dest))
                moved += 1
            _prune_empty_dirs(legacy_root)
    return moved


def _prune_empty_dirs(path: Path) -> None:
    if not path.exists():
        return
    for child in sorted(path.rglob("*"), reverse=True):
        if child.is_dir():
            try:
                child.rmdir()
            except OSError:
                pass
    try:
        path.rmdir()
    except OSError:
        pass


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def collect_bundles(functional: str) -> list[dict]:
    bundles: dict[tuple[str, str], dict] = {}

    def add_file(ext: str, bucket: str, sub: str) -> None:
        root = ROOT / functional / bucket / sub
        if not root.exists():
            return
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            element = file_path.parent.name
            base = basename_from_filename(file_path.name)
            key = (element, base)
            entry = bundles.setdefault(
                key,
                {
                    "functional": functional,
                    "element": element,
                    "basename": base,
                    "version_index": version_index(base),
                    "files": {},
                },
            )
            entry["files"][ext] = rel(file_path)

    add_file("fhi", "upstream", "fhi")
    add_file("param", "source-only", "param")
    add_file("rpt", "source-only", "rpt")

    missing_lookup = {
        (item["functional"], item["element"]): item for item in UPSTREAM_MISSING
    }

    # Mark upstream_preferred within each element (highest version_index only).
    by_element: dict[tuple[str, str], list[dict]] = {}
    for bundle in bundles.values():
        by_element.setdefault((bundle["functional"], bundle["element"]), []).append(
            bundle
        )

    for group in by_element.values():
        versioned = [b for b in group if b["version_index"] is not None]
        if not versioned:
            continue
        preferred_version = max(b["version_index"] for b in versioned)
        for bundle in group:
            bundle["upstream_preferred"] = bundle["version_index"] == preferred_version

    inventory = []
    for bundle in sorted(
        bundles.values(),
        key=lambda b: (b["functional"], b["element"], b["basename"]),
    ):
        has_fhi = "fhi" in bundle["files"]
        has_param = "param" in bundle["files"]
        has_rpt = "rpt" in bundle["files"]
        missing = missing_lookup.get((bundle["functional"], bundle["element"]))

        if has_fhi and has_param and has_rpt:
            status = "complete"
        elif missing:
            status = "upstream_missing"
        else:
            status = "partial"

        bundle.update(
            {
                "status": status,
                "abacus_eligible": False,
                "auto_select_allowed": False,
                "selection_scope": "metadata_only",
            }
        )
        if "upstream_preferred" not in bundle:
            bundle["upstream_preferred"] = False
        inventory.append(bundle)

    return inventory


def build_summary(inventory: list[dict]) -> dict:
    files = list(ROOT.rglob("*"))
    file_count = sum(1 for p in files if p.is_file() and "metadata" not in p.parts)
    return {
        "canonical_root": "Rappe-group",
        "source": "https://www.sas.upenn.edu/rappegroup/research/pseudo-potential-gga.html",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_format": None,
        "production_path": "Rappe-group/abacus/upf/{Element}/",
        "upstream_format": "fhi",
        "upstream_path": "Rappe-group/{functional}/upstream/fhi/{Element}/",
        "source_only_formats": ["param", "rpt"],
        "source_only_path": "Rappe-group/{functional}/source-only/{format}/{Element}/",
        "abacus_active_files": 0,
        "upstream_files": sum(1 for e in inventory if "fhi" in e["files"]),
        "source_only_files": sum(
            1 for e in inventory for k in e["files"] if k in {"param", "rpt"}
        ),
        "inventory_bundles": len(inventory),
        "on_disk_files": file_count,
        "selection_policy": {
            "keep_all_versions": True,
            "auto_delete_by_version": False,
            "auto_select_by_version": False,
            "upstream_preferred_is_hint_only": True,
            "source_only_in_auto_selection": False,
            "fhi_in_abacus_active": False,
        },
    }


def write_metadata(inventory: list[dict]) -> None:
    METADATA.mkdir(parents=True, exist_ok=True)
    (ROOT / "abacus" / "upf").mkdir(parents=True, exist_ok=True)

    summary = build_summary(inventory)
    (METADATA / "library_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (METADATA / "inventory.json").write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (METADATA / "upstream_missing.json").write_text(
        json.dumps(UPSTREAM_MISSING, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    moved = migrate_legacy_layout()
    inventory = []
    for functional in FUNCTIONALS:
        inventory.extend(collect_bundles(functional))
    write_metadata(inventory)
    print(f"Migrated files: {moved}")
    print(f"Inventory bundles: {len(inventory)}")
    print(f"Metadata: {METADATA}")


if __name__ == "__main__":
    main()
