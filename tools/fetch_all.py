#!/usr/bin/env python3
"""Download every raw/ library and verify it against the tracked SHA-256 manifests.

For each library in catalog/sources/registry.json:
  1. already present and matching its manifest  -> skip
  2. potdex mirror (GitHub Release assets listed in catalog/sources/mirror.json)
     -> exact copy of the maintainer's raw/, verified by SHA-256
  3. otherwise / if the mirror fails -> upstream recipe (git clone at a pinned
     commit, direct files with checksums, or the scraper in tools/fetch/)
  4. verify again and report

Usage:
  python tools/fetch_all.py                    # everything
  python tools/fetch_all.py SG15-ONCV SSSP     # some libraries
  python tools/fetch_all.py --plan             # show what would be done, download nothing
  python tools/fetch_all.py --upstream         # ignore the mirror
  python tools/fetch_all.py --mirror-only      # never scrape upstream

Environment:
  POTDEX_RAW      where raw/ lives (default: <repo>/raw)
  POTDEX_MIRROR   override the mirror base URL (e.g. file:///D:/potdex-mirror/)

Only the Python standard library is needed (plus git for the two git libraries).
If `certifi` is installed it is used for TLS; verification is never disabled.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import ssl
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import RAW, ROOT, sha256_file
from sources import check, load_manifest, md5_file, mirror, registry

UA = {"User-Agent": "Mozilla/5.0 (potdex fetch_all)"}
DOWNLOADS = RAW / ".downloads"


# ---------------------------------------------------------------- helpers

def ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


CTX = ssl_context()


def human(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TiB"


def download(url: str, dest: Path, retries: int = 4) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120, context=CTX) as resp, tmp.open("wb") as out:
                total = int(resp.headers.get("Content-Length") or 0)
                done, t0 = 0, time.time()
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if total > (8 << 20) and time.time() - t0 > 5:  # progress only for big files
                        t0 = time.time()
                        print(f"      {dest.name}: {human(done)} / {human(total)}", flush=True)
            tmp.replace(dest)
            return
        except (urllib.error.URLError, OSError) as exc:
            last = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403, 404):
                break
            time.sleep(2 * attempt)
    if tmp.exists():
        tmp.unlink()
    raise RuntimeError(f"download failed: {url}: {last}")


def safe_members(tf: tarfile.TarFile, flatten: bool = False, strip_prefix: str | None = None):
    for m in tf.getmembers():
        if not (m.isfile() or m.isdir()):
            continue  # no links/devices from archives
        p = PurePosixPath(m.name)
        parts = [x for x in p.parts if x not in ("", ".")]
        if strip_prefix:
            if not parts or parts[0] != strip_prefix:
                continue
            parts = parts[1:]
        if not parts or p.is_absolute() or ".." in parts:
            continue
        if flatten:
            if m.isdir():
                continue
            parts = parts[-1:]
        yield m, Path(*parts)


def extract(archive: Path, dest: Path, flatten: bool = False, strip_prefix: str | None = None) -> int:
    n = 0
    with tarfile.open(archive, "r:*") as tf:
        for m, rel in safe_members(tf, flatten, strip_prefix):
            target = dest / rel
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            src = tf.extractfile(m)
            if src is None:
                continue
            with src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
            os.utime(target, (m.mtime, m.mtime))
            n += 1
    return n


# ---------------------------------------------------------------- upstream steps

def step_git(lib: str, step: dict, plan: bool) -> None:
    dest = RAW / lib
    if plan:
        print(f"    git clone {step['url']} @ {step['commit'][:10]}")
        return
    if not shutil.which("git"):
        raise RuntimeError("git is not installed")
    # Byte-exact checkout: never let a user's core.autocrlf rewrite line endings,
    # or the files would not match the manifest.
    exact = ["-c", "core.autocrlf=false", "-c", "core.eol=lf"]
    if not (dest / ".git").exists():
        if dest.exists() and any(dest.iterdir()):
            raise RuntimeError(f"{dest} exists but is not a git checkout; move it away and retry")
        subprocess.run(["git", *exact, "clone", "--quiet", "--no-checkout", step["url"], str(dest)], check=True)
        subprocess.run(["git", "-C", str(dest), "config", "core.autocrlf", "false"], check=True)
    else:
        subprocess.run(["git", "-C", str(dest), "fetch", "--quiet", "origin"], check=True)
    subprocess.run(["git", "-C", str(dest), *exact, "-c", "advice.detachedHead=false",
                    "checkout", "--quiet", "--force", step["commit"]], check=True)


def step_files(lib: str, step: dict, plan: bool) -> None:
    manifest = load_manifest(lib)
    root = RAW / lib
    for entry in step["files"]:
        entry = {"path": entry} if isinstance(entry, str) else entry
        rel = entry["path"]
        dest = root / rel
        name = PurePosixPath(rel).name
        base = step["base"]
        url = base.format(name=name) if "{name}" in base else base + rel

        def good() -> bool:
            if not dest.exists():
                return False
            if "md5" in entry:
                return md5_file(dest) == entry["md5"]
            want = entry.get("sha256") or manifest.get(rel)
            return want is None or sha256_file(dest) == want

        if good():
            continue
        if plan:
            print(f"    download {url}")
            continue
        print(f"    {rel}")
        download(url, dest)
        if not good():
            bad = dest.with_name(dest.name + ".bad")
            dest.replace(bad)
            raise RuntimeError(f"checksum mismatch for {rel} (kept as {bad.name})")


def step_extract(lib: str, step: dict, plan: bool) -> None:
    root = RAW / lib
    if plan:
        print(f"    extract {step['archive']} -> {step['dest']}/")
        return
    n = extract(root / step["archive"], root / step["dest"], flatten=step.get("flatten", False))
    print(f"    extracted {n} files from {step['archive']}")


def step_script(lib: str, step: dict, plan: bool) -> None:
    if plan:
        print(f"    run {step['script']}")
        return
    env = dict(os.environ, POTDEX_RAW=str(RAW))
    script = ROOT / step["script"]
    subprocess.run([sys.executable, str(script)], cwd=str(script.parent), env=env, check=True)


STEPS = {"git": step_git, "files": step_files, "extract": step_extract, "script": step_script}


def fetch_upstream(lib: str, info: dict, plan: bool) -> None:
    for step in info.get("upstream", []):
        if step["type"] == "note":
            print(f"    note: {step['text']}")
            continue
        STEPS[step["type"]](lib, step, plan)


# ---------------------------------------------------------------- mirror

class Concat:
    """Read several part files as one stream (for split mirror archives)."""

    def __init__(self, paths: list[Path]):
        self.paths, self.i, self.f = paths, 0, None

    def read(self, n: int = -1) -> bytes:
        out = b""
        while self.i < len(self.paths) and (n < 0 or len(out) < n):
            if self.f is None:
                self.f = self.paths[self.i].open("rb")
            chunk = self.f.read(-1 if n < 0 else n - len(out))
            if not chunk:
                self.f.close()
                self.f, self.i = None, self.i + 1
                continue
            out += chunk
        return out

    def close(self) -> None:
        if self.f:
            self.f.close()


def fetch_mirror(lib: str, spec: dict, base_url: str, plan: bool, keep: bool) -> None:
    parts = spec["parts"]
    if plan:
        size = sum(p["size"] for p in parts)
        print(f"    mirror: {len(parts)} part(s), {human(size)} from {base_url}")
        return
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    local = []
    for p in parts:
        dest = DOWNLOADS / p["name"]
        if not (dest.exists() and dest.stat().st_size == p["size"] and sha256_file(dest) == p["sha256"]):
            download(base_url.rstrip("/") + "/" + p["name"], dest)
            if sha256_file(dest) != p["sha256"]:
                dest.unlink()
                raise RuntimeError(f"mirror part {p['name']} failed its SHA-256 check")
        local.append(dest)
    staging = RAW / f".staging-{lib}"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    stream = Concat(local)
    try:
        with tarfile.open(fileobj=stream, mode="r|gz") as tf:  # type: ignore[arg-type]
            n = 0
            for m in tf:
                parts_ = [x for x in PurePosixPath(m.name).parts if x not in ("", ".")]
                if not m.isfile() or not parts_ or parts_[0] != lib or ".." in parts_:
                    continue
                target = staging.joinpath(*parts_[1:])
                target.parent.mkdir(parents=True, exist_ok=True)
                src = tf.extractfile(m)
                if src is None:
                    continue
                with src, target.open("wb") as out:
                    shutil.copyfileobj(src, out)
                os.utime(target, (m.mtime, m.mtime))
                n += 1
    finally:
        stream.close()
    # merge into raw/<lib> (keeps anything already there, e.g. a .git dir)
    dest_root = RAW / lib
    for f in sorted(staging.rglob("*")):
        if f.is_file():
            target = dest_root / f.relative_to(staging)
            target.parent.mkdir(parents=True, exist_ok=True)
            f.replace(target)
    shutil.rmtree(staging)
    print(f"    unpacked {n} files from mirror")
    if not keep:
        for p in local:
            p.unlink()


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("libs", nargs="*", help="libraries to fetch (default: all)")
    ap.add_argument("--plan", action="store_true", help="show what would be done; download nothing")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--upstream", action="store_true", help="skip the mirror, use upstream recipes")
    g.add_argument("--mirror-only", action="store_true", help="never fall back to upstream")
    ap.add_argument("--force", action="store_true", help="re-fetch even if the library already verifies")
    ap.add_argument("--keep-downloads", action="store_true", help="keep mirror archives in raw/.downloads/")
    args = ap.parse_args()

    reg = registry()
    libs = args.libs or sorted(reg)
    unknown = [lib for lib in libs if lib not in reg]
    if unknown:
        print(f"unknown libraries: {unknown}. Known: {', '.join(sorted(reg))}")
        return 2

    mir = mirror()
    base_url = os.environ.get("POTDEX_MIRROR") or mir.get("base_url")
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"raw/ = {RAW}")
    print(f"mirror = {base_url or '(none published yet)'}\n")

    results: dict[str, str] = {}
    for lib in libs:
        info = reg[lib]
        print(f"[{lib}]")
        if not args.force:
            c = check(lib)
            if c.complete:
                print("    already complete")
                results[lib] = c.summary()
                continue
        spec = (mir.get("libraries") or {}).get(lib)
        errors = []
        done = False
        if spec and base_url and not args.upstream:
            try:
                fetch_mirror(lib, spec, base_url, args.plan, args.keep_downloads)
                done = True
            except Exception as exc:  # noqa: BLE001
                errors.append(f"mirror: {exc}")
                print(f"    mirror failed: {exc}")
        if not done and not args.mirror_only:
            try:
                fetch_upstream(lib, info, args.plan)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"upstream: {exc}")
                print(f"    upstream failed: {exc}")
        if args.plan:
            results[lib] = "planned"
            continue
        c = check(lib)
        results[lib] = c.summary() + (f"  [{'; '.join(errors)}]" if errors and not c.complete else "")
        if not c.complete:
            for rel in (c.missing + c.changed)[:5]:
                print(f"    still missing/different: {rel}")

    print("\n=== fetch_all summary ===")
    for lib, status in results.items():
        print(f"  {lib:16s} {status}")
    if args.plan:
        return 0
    incomplete = [lib for lib in libs if not check(lib).complete]
    if incomplete:
        print(f"\nIncomplete: {', '.join(incomplete)}")
        if not base_url:
            print("No mirror is published yet; see docs/DATA.md for how the maintainer publishes one.")
        return 1
    print("\nAll libraries complete. Next: python tools/run_pipeline.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
