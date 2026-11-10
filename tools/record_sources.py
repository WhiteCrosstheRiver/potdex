#!/usr/bin/env python3
"""Record provenance and a SHA-256 manifest for every library under raw/.

Writes, per library:
  catalog/sources/<lib>.json    upstream URL, licence, fetch script, file/byte counts,
                                 manifest digest (tracked in git)
  catalog/sources/<lib>.sha256  "<sha256>  <path relative to raw/<lib>>" per file

Usage:
  python tools/record_sources.py            # (re)write records
  python tools/record_sources.py --verify   # compare raw/ against the tracked manifests
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import CATALOG, RAW, read_json, sha256_file, write_json

SOURCES = CATALOG / "sources"

# Licence values are what upstream states as far as we know; `license_verified`
# stays false until someone has checked the upstream page or LICENSE file.
LIBRARIES: dict[str, dict] = {
    "BLPSLibrary": {
        "url": "https://github.com/PrincetonUniversity/BLPSLibrary",
        "kind": "git",
        "license": "CC BY-ND 4.0",
        "license_verified": True,
        "license_file": "LICENSE.md",
        "fetch": None,
    },
    "pseudos_ac_she": {
        "url": "https://github.com/gmatteo/pseudos_ac_she",
        "kind": "git",
        "license": None,
        "license_verified": False,
        "fetch": None,
    },
    "PseudoDOJO": {
        "url": "https://www.pseudo-dojo.org",
        "kind": "http",
        "license": "CC BY 4.0",
        "license_verified": False,
        "fetch": "tools/fetch/download_pseudodojo.py",
    },
    "PSlibrary": {
        "url": "https://pseudopotentials.quantum-espresso.org/legacy_tables/ps-library",
        "kind": "http",
        "license": "GPL-2.0-or-later",
        "license_verified": False,
        "fetch": "tools/fetch/download_pslibrary.py",
    },
    "PWmat": {
        "url": "http://www.pwmat.com/pwmat-resource/pseduo-download/",
        "kind": "http",
        "license": None,
        "license_verified": False,
        "fetch": "tools/fetch/scrape_pwmat.py",
    },
    "Rappe-group": {
        "url": "https://www.sas.upenn.edu/rappegroup/research",
        "kind": "http",
        "license": None,
        "license_verified": False,
        "fetch": "tools/fetch/scrape_rappe_group.py",
    },
    "SG15-ONCV": {
        "url": "http://www.quantum-simulation.org/potentials/sg15_oncv/",
        "kind": "http",
        "license": "CC BY-SA 4.0",
        "license_verified": False,
        "fetch": None,
    },
    "SSSP": {
        "url": "https://www.materialscloud.org/discover/sssp",
        "kind": "http",
        "license": "per-pseudopotential (see SSSP metadata)",
        "license_verified": False,
        "fetch": "tools/download_sssp.py",
    },
    "Vanderbilt-USPP": {
        "url": "https://www.physics.rutgers.edu/gbrv/",
        "kind": "http",
        "license": None,
        "license_verified": False,
        "fetch": "tools/fetch/download_vanderbilt_uspp.py",
    },
}

SKIP_DIRS = {".git", "__pycache__"}


def iter_files(root: Path):
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if p.is_file() and not (SKIP_DIRS & set(p.relative_to(root).parts)):
            yield p


def git_head(path: Path) -> dict | None:
    if not (path / ".git").exists():
        return None
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%H %cs"],
            capture_output=True, text=True, check=True,
        ).stdout.split()
        return {"commit": out[0], "commit_date": out[1]}
    except (subprocess.CalledProcessError, IndexError, FileNotFoundError):
        return None


def build_manifest(root: Path) -> tuple[list[str], int, float]:
    lines, total, newest = [], 0, 0.0
    for p in iter_files(root):
        st = p.stat()
        total += st.st_size
        newest = max(newest, st.st_mtime)
        lines.append(f"{sha256_file(p)}  {p.relative_to(root).as_posix()}")
    return lines, total, newest


def record(lib: str, info: dict) -> None:
    root = RAW / lib
    lines, total, newest = build_manifest(root)
    body = "\n".join(lines) + "\n"
    (SOURCES / f"{lib}.sha256").write_text(body, encoding="utf-8", newline="\n")
    rec = {
        "library": lib,
        "path": f"raw/{lib}",
        **info,
        "git": git_head(root),
        "files": len(lines),
        "bytes": total,
        "newest_file_mtime": datetime.fromtimestamp(newest, timezone.utc).date().isoformat() if newest else None,
        "manifest": f"{lib}.sha256",
        "manifest_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    write_json(SOURCES / f"{lib}.json", rec)
    print(f"  {lib:16s} {len(lines):6d} files {total / 2**20:9.1f} MiB")


def verify(lib: str) -> bool:
    mf = SOURCES / f"{lib}.sha256"
    if not mf.exists():
        print(f"  {lib}: no manifest")
        return False
    expected = dict(
        (line.split("  ", 1)[1], line.split("  ", 1)[0])
        for line in mf.read_text(encoding="utf-8").splitlines() if line
    )
    actual, _, _ = build_manifest(RAW / lib)
    actual_map = dict((line.split("  ", 1)[1], line.split("  ", 1)[0]) for line in actual)
    missing = sorted(set(expected) - set(actual_map))
    added = sorted(set(actual_map) - set(expected))
    changed = sorted(k for k in expected.keys() & actual_map.keys() if expected[k] != actual_map[k])
    ok = not (missing or added or changed)
    print(f"  {lib:16s} {'ok' if ok else 'DIFFERS'}  missing={len(missing)} added={len(added)} changed={len(changed)}")
    for label, items in (("missing", missing), ("added", added), ("changed", changed)):
        for k in items[:5]:
            print(f"      {label}: {k}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true", help="check raw/ against tracked manifests")
    ap.add_argument("libs", nargs="*", help="limit to these libraries")
    args = ap.parse_args()

    libs = args.libs or sorted(LIBRARIES)
    unknown = [d.name for d in RAW.iterdir() if d.is_dir() and d.name not in LIBRARIES]
    if unknown:
        print(f"WARNING: raw/ has unregistered libraries: {unknown} (add them to LIBRARIES)")

    SOURCES.mkdir(parents=True, exist_ok=True)
    if args.verify:
        results = [verify(lib) for lib in libs]
        return 0 if all(results) else 1
    for lib in libs:
        record(lib, LIBRARIES[lib])
    index = {lib: read_json(SOURCES / f"{lib}.json") for lib in sorted(LIBRARIES) if (SOURCES / f"{lib}.json").exists()}
    write_json(SOURCES / "index.json", {
        lib: {k: rec[k] for k in ("url", "license", "license_verified", "files", "bytes", "manifest_sha256")}
        for lib, rec in index.items()
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
