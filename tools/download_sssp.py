#!/usr/bin/env python3
"""Safely download and verify SSSP v2.0 tar archives."""

from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import METADATA, RAW, ROOT, write_json

ARCHIVES = [
    {
        "name": "SSSP-lib-pbe-eff-v2.tar.gz",
        "dest": RAW / "SSSP/v2.0/efficiency/SSSP-lib-pbe-eff-v2.tar.gz",
        "min_size": 50_000_000,
        "urls": [
            "https://archive.materialscloud.org/records/rcyfm-68h65/files/SSSP-lib-pbe-eff-v2.tar.gz",
            "https://www.materialscloud.org/discover/sssp/file/SSSP-lib-pbe-eff-v2.tar.gz",
        ],
    },
    {
        "name": "SSSP-lib-pbe-prec-v2.tar.gz",
        "dest": RAW / "SSSP/v2.0/precision/SSSP-lib-pbe-prec-v2.tar.gz",
        "min_size": 50_000_000,
        "urls": [
            "https://archive.materialscloud.org/records/rcyfm-68h65/files/SSSP-lib-pbe-prec-v2.tar.gz",
            "https://www.materialscloud.org/discover/sssp/file/SSSP-lib-pbe-prec-v2.tar.gz",
        ],
    },
]


def verify_tar(path: Path) -> tuple[bool, str, int]:
    try:
        with tarfile.open(path, "r:gz") as tf:
            upf = sum(1 for m in tf.getmembers() if m.name.endswith(".upf"))
            if upf < 50:
                return False, f"too few upf files: {upf}", upf
            # read first upf member to ensure archive not truncated
            for m in tf.getmembers():
                if m.isfile() and m.name.endswith(".upf"):
                    f = tf.extractfile(m)
                    if f is None:
                        return False, "cannot extract member", upf
                    data = f.read(1024)
                    if len(data) < 100:
                        return False, "empty upf member", upf
                    break
        return True, "ok", upf
    except (EOFError, tarfile.ReadError, OSError) as exc:
        return False, str(exc), 0


def download_url(url: str, part: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "potdex-sssp/1.0"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        if resp.status != 200:
            raise urllib.error.HTTPError(url, resp.status, resp.reason, resp.headers, None)
        total = 0
        with part.open("wb") as f:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                total += len(chunk)
    return total


def process_archive(spec: dict) -> dict:
    dest: Path = spec["dest"]
    part = dest.with_suffix(dest.suffix + ".part")
    result = {"name": spec["name"], "dest": str(dest), "status": "unknown"}

    if dest.exists():
        ok, msg, upf = verify_tar(dest)
        if ok:
            result.update({"status": "existing_ok", "upf_count": upf})
            return result
        result["existing_corrupt"] = msg

    last_err = None
    for url in spec["urls"]:
        try:
            print(f"  downloading {spec['name']} from {url}")
            if part.exists():
                part.unlink()
            size = download_url(url, part)
            if size < spec["min_size"]:
                raise RuntimeError(f"file too small: {size} bytes")
            ok, msg, upf = verify_tar(part)
            if not ok:
                raise RuntimeError(f"tar verify failed: {msg}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                backup = dest.with_suffix(dest.suffix + ".corrupt")
                dest.replace(backup)
            part.replace(dest)
            result.update(
                {
                    "status": "downloaded",
                    "bytes": size,
                    "upf_count": upf,
                    "url": url,
                    "md5": hashlib.md5(dest.read_bytes()).hexdigest(),
                }
            )
            return result
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, RuntimeError) as exc:
            last_err = str(exc)
            print(f"    failed: {exc}")
            if part.exists():
                part.unlink()

    if dest.exists():
        ok, msg, upf = verify_tar(dest)
        if ok:
            result.update({"status": "kept_existing", "upf_count": upf, "download_error": last_err})
        else:
            result.update({"status": "failed", "error": last_err, "corrupt": msg})
    else:
        result.update({"status": "failed", "error": last_err})
    return result


def main() -> int:
    results = [process_archive(spec) for spec in ARCHIVES]
    summary_path = METADATA / "sssp_download_summary.json"  # never write into raw/
    write_json(summary_path, {"archives": results})
    print("=== download_sssp ===")
    for item in results:
        print(item)

    failed = [r for r in results if r["status"] == "failed"]
    if failed:
        print("\n部分下载失败。可手动从 https://sssp.materialscloud.org/ 下载后放到对应目录。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
