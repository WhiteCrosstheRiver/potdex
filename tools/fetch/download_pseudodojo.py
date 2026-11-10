#!/usr/bin/env python3
"""Download Pseudo Dojo pseudopotentials from https://www.pseudo-dojo.org/"""

import io
import json
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://www.pseudo-dojo.org"
BASE_DIR = Path(__file__).resolve().parents[2] / "PseudoDOJO"
PP_FORMATS = {"upf", "psp8", "psml", "xml"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


def download(url: str, dest: Path, retries: int = 5) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[skip] {dest.name} (already exists)")
        return
    print(f"[download] {dest.name} ...")
    tmp = dest.with_suffix(dest.suffix + ".part")
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=600) as resp:
                total = resp.headers.get("Content-Length")
                total = int(total) if total else None
                done = 0
                chunk = 1024 * 1024
                with open(tmp, "wb") as f:
                    while True:
                        data = resp.read(chunk)
                        if not data:
                            break
                        f.write(data)
                        done += len(data)
                        if total:
                            pct = done * 100 // total
                            print(
                                f"\r  {done // (1024 * 1024)} / {total // (1024 * 1024)} MB ({pct}%)",
                                end="",
                                flush=True,
                            )
                        else:
                            print(f"\r  {done // (1024 * 1024)} MB", end="", flush=True)
            print()
            tmp.replace(dest)
            print(f"[done] {dest} ({dest.stat().st_size // 1024} KB)")
            return
        except Exception as exc:
            last_err = exc
            if tmp.exists():
                tmp.unlink()
            print(f"\n[retry {attempt}/{retries}] {dest.name}: {exc}")
    raise last_err


def extract_tgz(archive: Path, dest_root: Path) -> None:
    marker = dest_root / archive.stem / ".extracted"
    if marker.exists():
        print(f"[skip extract] {archive.name}")
        return
    print(f"[extract] {archive.name} -> {dest_root / archive.stem}")
    with tarfile.open(archive, mode="r:gz") as tf:
        tf.extractall(dest_root)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("ok\n", encoding="utf-8")


def is_pp_archive(path: str) -> bool:
    if not path.startswith("pseudos/") or not path.endswith(".tgz"):
        return False
    name = path.rsplit("/", 1)[-1]
    if name.endswith("_djrepo.tgz"):
        return False
    fmt = name.rsplit("_", 1)[-1].removesuffix(".tgz")
    return fmt in PP_FORMATS


def main() -> int:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    archives_dir = BASE_DIR / "archives"
    extracted_dir = BASE_DIR / "pseudos"
    meta_dir = BASE_DIR / "metadata"

    print("Fetching files.json ...")
    files = json.loads(fetch(f"{BASE_URL}/files.json"))
    (BASE_DIR / "files.json").write_text(json.dumps(files, indent=2), encoding="utf-8")

    pp_archives = sorted(f for f in files if is_pp_archive(f))
    meta_json = sorted(
        f for f in files
        if f.endswith(".json") and "/" not in f and f != "files.json"
    )

    print(f"PP archives: {len(pp_archives)}, metadata sets: {len(meta_json)}")

    failed = []

    for i, rel in enumerate(meta_json, 1):
        dest = meta_dir / rel
        print(f"\n(meta {i}/{len(meta_json)}) {rel}")
        try:
            download(f"{BASE_URL}/{rel}", dest)
        except Exception as exc:
            print(f"[error] {exc}")
            failed.append((rel, str(exc)))

    for i, rel in enumerate(pp_archives, 1):
        dest = archives_dir / rel.replace("pseudos/", "")
        print(f"\n({i}/{len(pp_archives)}) {rel}")
        try:
            download(f"{BASE_URL}/{rel}", dest)
            extract_tgz(dest, extracted_dir)
        except Exception as exc:
            print(f"[error] {exc}")
            failed.append((rel, str(exc)))

    print("\n=== Summary ===")
    print(f"Target: {BASE_DIR}")
    print(f"Archives: {len(pp_archives)}, Metadata: {len(meta_json)}, Failed: {len(failed)}")
    for rel, err in failed:
        print(f"  FAILED: {rel} -> {err}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
