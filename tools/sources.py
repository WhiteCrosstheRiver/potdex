"""Registry, manifests and verification for the raw/ libraries.

catalog/sources/registry.json   where each library comes from (tracked)
catalog/sources/<lib>.sha256    "<sha256>  <path inside raw/<lib>>" per file (tracked)
catalog/sources/mirror.json     GitHub Release assets that mirror raw/ (tracked, written by pack_mirror.py)
"""

from __future__ import annotations

import fnmatch
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from common import CATALOG, RAW, read_json, sha256_file

SOURCES = CATALOG / "sources"
REGISTRY = SOURCES / "registry.json"
MIRROR = SOURCES / "mirror.json"
SKIP_DIRS = {".git", "__pycache__"}

# Files written by fetch scripts or our own tools (timestamps, inventories, markers).
# A mismatch here is reported but does not make a library incomplete.
GENERATED = [
    "metadata/*",
    "*/metadata/*",
    "*/*/metadata/*",
    "*summary*.json",
    "*/.extracted",
    "*/*/.extracted",
    "*/metadata.json",
    "*/*/metadata.json",
    "files.json",
]


def registry() -> dict[str, dict]:
    return read_json(REGISTRY)["libraries"]


def mirror() -> dict:
    return read_json(MIRROR) if MIRROR.exists() else {}


def is_generated(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, pat) for pat in GENERATED)


def iter_files(root: Path):
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if p.is_file() and not (SKIP_DIRS & set(p.relative_to(root).parts)) and not p.name.endswith(".part"):
            yield p


def load_manifest(lib: str) -> dict[str, str]:
    mf = SOURCES / f"{lib}.sha256"
    if not mf.exists():
        return {}
    out = {}
    for line in mf.read_text(encoding="utf-8").splitlines():
        if line:
            digest, rel = line.split("  ", 1)
            out[rel] = digest
    return out


def scan(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256_file(p) for p in iter_files(root)} if root.exists() else {}


def manifest_text(files: dict[str, str]) -> str:
    return "".join(f"{files[k]}  {k}\n" for k in sorted(files))


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Check:
    lib: str
    expected: int = 0
    missing: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    generated_diffs: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.expected > 0 and not self.missing and not self.changed

    @property
    def exact(self) -> bool:
        return self.complete and not self.added and not self.generated_diffs

    def summary(self) -> str:
        if self.expected == 0:
            return "no manifest"
        if self.exact:
            return "ok"
        if self.complete:
            return f"ok (generated files differ: {len(self.generated_diffs)}, extra: {len(self.added)})"
        return f"INCOMPLETE missing={len(self.missing)} changed={len(self.changed)} extra={len(self.added)}"


def check(lib: str, raw: Path = RAW, actual: dict[str, str] | None = None) -> Check:
    expected = load_manifest(lib)
    actual = scan(raw / lib) if actual is None else actual
    c = Check(lib, expected=len(expected))
    for rel, digest in expected.items():
        if rel not in actual:
            (c.generated_diffs if is_generated(rel) else c.missing).append(rel)
        elif actual[rel] != digest:
            (c.generated_diffs if is_generated(rel) else c.changed).append(rel)
    for rel in actual:
        if rel not in expected:
            (c.generated_diffs if is_generated(rel) else c.added).append(rel)
    return c
