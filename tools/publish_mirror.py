#!/usr/bin/env python3
"""Maintainer tool: upload the packed mirror assets to a GitHub Release.

Reads catalog/sources/mirror.json (written by pack_mirror.py), creates the
release for its tag if needed, and uploads every part that is not already
there with the same size. Safe to re-run after an interrupted upload.

Needs a token in GITHUB_TOKEN (fine-grained: Contents read/write on the repo).

Usage:
  set GITHUB_TOKEN=...            (PowerShell: $env:GITHUB_TOKEN = "...")
  python tools/publish_mirror.py [--dir dist/mirror] [--draft]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT
from sources import mirror

API = "https://api.github.com"


def call(method: str, url: str, token: str, data: bytes | None = None, ctype: str = "application/json"):
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "potdex-publish",
        "Content-Type": ctype,
    })
    with urllib.request.urlopen(req, timeout=3600) as resp:
        body = resp.read()
        return json.loads(body) if body else None


class FileBody:
    """Stream a file to urllib without loading it into memory."""

    def __init__(self, path: Path):
        self.f = path.open("rb")
        self.size = path.stat().st_size
        self.sent = 0

    def read(self, n: int = -1) -> bytes:
        chunk = self.f.read(1 << 20 if n < 0 else n)
        self.sent += len(chunk)
        print(f"\r      {self.sent / 2**20:8.1f} / {self.size / 2**20:8.1f} MiB", end="", flush=True)
        return chunk

    def __len__(self) -> int:
        return self.size


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(ROOT / "dist" / "mirror"))
    ap.add_argument("--draft", action="store_true", help="create the release as a draft")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("GITHUB_TOKEN is not set")
        return 2
    mir = mirror()
    if not mir:
        print("catalog/sources/mirror.json missing; run tools/pack_mirror.py first")
        return 2
    repo, tag = mir["repo"], mir["tag"]

    try:
        rel = call("GET", f"{API}/repos/{repo}/releases/tags/{tag}", token)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        body = json.dumps({
            "tag_name": tag,
            "name": f"Raw pseudopotential data {tag}",
            "body": "Mirror of raw/ for tools/fetch_all.py. Each library keeps its upstream licence; "
                    "see catalog/sources/registry.json.",
            "draft": args.draft,
        }).encode()
        rel = call("POST", f"{API}/repos/{repo}/releases", token, body)
        print(f"created release {tag}")

    existing = {a["name"]: a for a in rel.get("assets", [])}
    upload_base = rel["upload_url"].split("{", 1)[0]
    for lib, spec in mir["libraries"].items():
        for part in spec["parts"]:
            name = part["name"]
            path = Path(args.dir) / name
            have = existing.get(name)
            if have and have["size"] == part["size"]:
                print(f"  {name}: already uploaded")
                continue
            if have:
                call("DELETE", f"{API}/repos/{repo}/releases/assets/{have['id']}", token)
            if not path.exists():
                print(f"  {name}: MISSING locally ({path})")
                return 1
            print(f"  {name}: uploading")
            url = f"{upload_base}?{urllib.parse.urlencode({'name': name})}"
            call("POST", url, token, FileBody(path), "application/octet-stream")  # type: ignore[arg-type]
            print()
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
