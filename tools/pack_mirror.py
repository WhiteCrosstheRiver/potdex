#!/usr/bin/env python3
"""Maintainer tool: pack raw/ libraries into GitHub-Release-sized mirror assets.

Each library becomes <lib>.tar.gz (members prefixed "<lib>/", .git excluded),
split into parts of at most --part-size bytes (GitHub's per-asset limit is 2 GiB).
Writes catalog/sources/mirror.json, which tools/fetch_all.py reads.

Usage:
  python tools/pack_mirror.py --tag raw-2026.11 [--out dist/mirror] [LIB ...]
then upload with tools/publish_mirror.py (see docs/DATA.md).

Only pack libraries whose licence allows redistribution; check the
`license` / `license_verified` fields in catalog/sources/registry.json first.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import sys
import tarfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RAW, ROOT, write_json
from sources import MIRROR, check, iter_files, mirror, registry

DEFAULT_PART = 1_900_000_000


class SplitWriter:
    """File-like object that writes consecutive part files and hashes them."""

    def __init__(self, out_dir: Path, stem: str, part_size: int):
        self.out_dir, self.stem, self.part_size = out_dir, stem, part_size
        self.parts: list[dict] = []
        self.f = None
        self.h = None
        self.written = 0

    def _open(self) -> None:
        name = f"{self.stem}.part{len(self.parts):03d}"
        self.f = (self.out_dir / name).open("wb")
        self.h = hashlib.sha256()
        self.written = 0
        self.parts.append({"name": name, "size": 0, "sha256": ""})

    def _close(self) -> None:
        if self.f:
            self.f.close()
            self.parts[-1]["size"] = self.written
            self.parts[-1]["sha256"] = self.h.hexdigest()
            self.f = None

    def write(self, data: bytes) -> int:
        view = memoryview(data)
        while view:
            if self.f is None or self.written >= self.part_size:
                self._close()
                self._open()
            n = min(len(view), self.part_size - self.written)
            self.f.write(view[:n])
            self.h.update(view[:n])
            self.written += n
            view = view[n:]
        return len(data)

    def flush(self) -> None:
        pass

    def close(self) -> list[dict]:
        self._close()
        # a single part gets the plain name
        if len(self.parts) == 1:
            old = self.out_dir / self.parts[0]["name"]
            new_name = self.stem
            old.replace(self.out_dir / new_name)
            self.parts[0]["name"] = new_name
        return self.parts


def pack(lib: str, out_dir: Path, part_size: int) -> dict:
    root = RAW / lib
    files = list(iter_files(root))
    w = SplitWriter(out_dir, f"{lib}.tar.gz", part_size)
    with gzip.GzipFile(fileobj=w, mode="wb", compresslevel=6, mtime=0) as gz:  # type: ignore[arg-type]
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tf:
            for p in files:
                info = tf.gettarinfo(str(p), arcname=f"{lib}/{p.relative_to(root).as_posix()}")
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with p.open("rb") as f:
                    tf.addfile(info, f)
    parts = w.close()
    size = sum(p["size"] for p in parts)
    print(f"  {lib:16s} {len(files):6d} files -> {len(parts)} part(s), {size / 2**20:9.1f} MiB")
    return {"files": len(files), "parts": parts}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("libs", nargs="*", help="libraries to pack (default: all registered)")
    ap.add_argument("--tag", required=True, help="GitHub release tag, e.g. raw-2026.11")
    ap.add_argument("--repo", default="WhiteCrosstheRiver/potdex", help="owner/name of the GitHub repo")
    ap.add_argument("--out", default=str(ROOT / "dist" / "mirror"), help="output directory")
    ap.add_argument("--part-size", type=int, default=DEFAULT_PART)
    ap.add_argument("--allow-incomplete", action="store_true", help="pack even if raw/<lib> fails --verify")
    args = ap.parse_args()

    reg = registry()
    libs = args.libs or sorted(reg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for lib in libs:
        c = check(lib)
        if not c.complete and not args.allow_incomplete:
            print(f"refusing to pack {lib}: {c.summary()} (run record_sources.py after fixing raw/)")
            return 1

    current = mirror()
    if current.get("tag") not in (None, args.tag):
        current = {}  # a new tag starts a fresh asset list
    libraries = current.get("libraries", {})
    for lib in libs:
        libraries[lib] = pack(lib, out, args.part_size)

    write_json(MIRROR, {
        "_doc": "GitHub Release assets that mirror raw/. Written by tools/pack_mirror.py; read by tools/fetch_all.py.",
        "repo": args.repo,
        "tag": args.tag,
        "base_url": f"https://github.com/{args.repo}/releases/download/{args.tag}/",
        "libraries": dict(sorted(libraries.items())),
    })
    print(f"\nwrote {MIRROR.relative_to(ROOT)}; assets in {out}")
    print("next: python tools/publish_mirror.py   (needs GITHUB_TOKEN with contents:write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
