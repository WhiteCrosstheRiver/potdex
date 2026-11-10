#!/usr/bin/env python3
"""Record provenance and a SHA-256 manifest for every library under raw/.

Writes, per library (all tracked in git):
  catalog/sources/<lib>.json    upstream URL, licence, file/byte counts, manifest digest
  catalog/sources/<lib>.sha256  "<sha256>  <path inside raw/<lib>>" per file
  catalog/sources/index.json    one-line summary per library

Usage:
  python tools/record_sources.py              # (re)write records from what is in raw/ now
  python tools/record_sources.py --verify     # check raw/ against the tracked manifests
  python tools/record_sources.py SSSP PWmat   # limit to some libraries

Re-record only after you have deliberately changed raw/ (new download, repaired file);
the manifests are the reference that tools/fetch_all.py checks downloads against.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RAW, read_json, write_json
from sources import SOURCES, check, iter_files, manifest_text, registry, scan


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


def record(lib: str, info: dict) -> None:
    root = RAW / lib
    files = scan(root)
    body = manifest_text(files)
    (SOURCES / f"{lib}.sha256").write_text(body, encoding="utf-8", newline="\n")
    total = sum(p.stat().st_size for p in iter_files(root))
    rec = {
        "library": lib,
        "path": f"raw/{lib}",
        "url": info.get("url"),
        "license": info.get("license"),
        "license_verified": info.get("license_verified", False),
        "git": git_head(root),
        "files": len(files),
        "bytes": total,
        "manifest": f"{lib}.sha256",
        "manifest_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    write_json(SOURCES / f"{lib}.json", rec)
    print(f"  {lib:16s} {len(files):6d} files {total / 2**20:9.1f} MiB")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verify", action="store_true", help="check raw/ against tracked manifests")
    ap.add_argument("libs", nargs="*", help="limit to these libraries")
    args = ap.parse_args()

    reg = registry()
    libs = args.libs or sorted(reg)
    bad = [lib for lib in libs if lib not in reg]
    if bad:
        print(f"unknown libraries: {bad}; add them to catalog/sources/registry.json first")
        return 2
    if RAW.exists():
        unknown = [d.name for d in RAW.iterdir() if d.is_dir() and d.name not in reg]
        if unknown:
            print(f"WARNING: raw/ has unregistered libraries: {unknown}")

    SOURCES.mkdir(parents=True, exist_ok=True)
    if args.verify:
        ok = True
        for lib in libs:
            c = check(lib)
            print(f"  {lib:16s} {c.summary()}")
            for label, items in (("missing", c.missing), ("changed", c.changed), ("extra", c.added)):
                for rel in items[:5]:
                    print(f"      {label}: {rel}")
            ok &= c.complete
        return 0 if ok else 1

    for lib in libs:
        record(lib, reg[lib])
    index = {}
    for lib in sorted(reg):
        p = SOURCES / f"{lib}.json"
        if p.exists():
            rec = read_json(p)
            index[lib] = {k: rec.get(k) for k in ("url", "license", "license_verified", "files", "bytes", "manifest_sha256")}
    write_json(SOURCES / "index.json", index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
