"""Merge duplicate GBRV libraries and split ABACUS production UPF from archive formats."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass, asdict
import os
from pathlib import Path

RAW_DIR = Path(os.environ["POTDEX_RAW"]) if os.environ.get("POTDEX_RAW") else Path(__file__).resolve().parents[2] / "raw"

ROOT = Path(__file__).resolve().parents[2]
OLD_LIB = RAW_DIR / "GBRV" / "v1.5"
CANONICAL = RAW_DIR / "Vanderbilt-USPP" / "GBRV-v1.5"
PRODUCTION_FMT = "upf"
ARCHIVE_FORMATS = {"uspp", "paw", "paw-xml"}
FORMAT_ALIASES = {"xml": "paw-xml"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_format(fmt: str) -> str:
    return FORMAT_ALIASES.get(fmt, fmt)


@dataclass
class FileRecord:
    filename: str
    element: str
    format: str
    source: str
    path: str
    sha256: str
    size: int


def scan_library(base: Path, source_name: str) -> dict[tuple[str, str, str], FileRecord]:
    records: dict[tuple[str, str, str], FileRecord] = {}
    if not base.exists():
        return records

    for path in base.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if len(rel.parts) < 3:
            continue
        fmt, element, filename = rel.parts[0], rel.parts[1], rel.parts[-1]
        fmt = normalize_format(fmt)
        key = (filename.lower(), element, fmt)
        records[key] = FileRecord(
            filename=filename,
            element=element,
            format=fmt,
            source=source_name,
            path=str(path),
            sha256=sha256(path),
            size=path.stat().st_size,
        )
    return records


def compare(
    old: dict[tuple[str, str, str], FileRecord],
    new: dict[tuple[str, str, str], FileRecord],
) -> dict[str, list]:
    all_keys = sorted(set(old) | set(new))
    identical: list[dict] = []
    only_old: list[dict] = []
    only_new: list[dict] = []
    conflicts: list[dict] = []

    for key in all_keys:
        o, n = old.get(key), new.get(key)
        if o and n:
            if o.sha256 == n.sha256:
                identical.append(asdict(o))
            else:
                conflicts.append(
                    {
                        "filename": key[0],
                        "element": key[1],
                        "format": key[2],
                        "old": asdict(o),
                        "new": asdict(n),
                    }
                )
        elif o:
            only_old.append(asdict(o))
        else:
            only_new.append(asdict(n))

    return {
        "identical": identical,
        "only_old": only_old,
        "only_new": only_new,
        "conflicts": conflicts,
    }


def canonical_path(record: FileRecord) -> Path:
    if record.format == PRODUCTION_FMT:
        return CANONICAL / PRODUCTION_FMT / record.element / record.filename
    if record.format in ARCHIVE_FORMATS:
        return CANONICAL / "archive" / record.format / record.element / record.filename
    raise ValueError(f"unknown format: {record.format}")


def install_record(record: FileRecord, *, copy_from: Path) -> Path:
    dest = canonical_path(record)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if sha256(dest) == record.sha256:
            return dest
        raise RuntimeError(f"destination exists with different content: {dest}")
    shutil.copy2(copy_from, dest)
    return dest


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def main() -> int:
    old = scan_library(OLD_LIB, "GBRV/v1.5")
    new = scan_library(CANONICAL, "Vanderbilt-USPP/GBRV-v1.5")
    report = compare(old, new)

    meta_dir = CANONICAL / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    report_path = meta_dir / "merge_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("--- compare ---")
    print(f"identical: {len(report['identical'])}")
    print(f"only_old:  {len(report['only_old'])}")
    print(f"only_new:  {len(report['only_new'])}")
    print(f"conflicts: {len(report['conflicts'])}")

    if report["conflicts"]:
        print("conflicts detected; aborting merge", file=sys.stderr)
        for item in report["conflicts"][:10]:
            print(f"  {item['format']}/{item['element']}/{item['filename']}", file=sys.stderr)
        return 1

    chosen: dict[tuple[str, str, str], FileRecord] = {}
    for key, record in new.items():
        chosen[key] = record
    for key, record in old.items():
        chosen.setdefault(key, record)

    staging = CANONICAL.parent / "_merge_staging"
    remove_tree(staging)
    staging.mkdir(parents=True)

    installed = 0
    for record in chosen.values():
        src = Path(record.path)
        if record.format == PRODUCTION_FMT:
            dest = staging / PRODUCTION_FMT / record.element / record.filename
        else:
            dest = staging / "archive" / record.format / record.element / record.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        installed += 1

    # Replace flat format dirs with canonical layout.
    for name in ("upf", "uspp", "paw", "paw-xml", "xml", "archive"):
        remove_tree(CANONICAL / name)

    for item in staging.iterdir():
        shutil.move(str(item), str(CANONICAL / item.name))
    remove_tree(staging)

    remove_tree(OLD_LIB.parent)

    summary = {
        "canonical_root": str(CANONICAL),
        "production_format": PRODUCTION_FMT,
        "archive_formats": sorted(ARCHIVE_FORMATS),
        "installed_files": installed,
        "production_files": sum(
            1 for p in (CANONICAL / PRODUCTION_FMT).rglob("*") if p.is_file()
        ),
        "archive_files": sum(
            sum(1 for p in (CANONICAL / "archive" / fmt).rglob("*") if p.is_file())
            for fmt in ARCHIVE_FORMATS
            if (CANONICAL / "archive" / fmt).exists()
        ),
        "removed_old_root": str(OLD_LIB.parent),
        "legacy_inputs": "not_downloaded",
    }
    summary_path = meta_dir / "library_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n--- merge complete ---")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
