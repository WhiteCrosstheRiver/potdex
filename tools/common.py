"""Shared utilities for potdex catalog pipeline."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Downloaded upstream libraries, never edited by the pipeline.
# Set POTDEX_RAW to keep them elsewhere (e.g. a shared disk on a cluster).
RAW = Path(os.environ["POTDEX_RAW"]).resolve() if os.environ.get("POTDEX_RAW") else ROOT / "raw"
CATALOG = ROOT / "catalog"
METADATA = CATALOG / "metadata"
LIBRARIES_META = METADATA / "libraries"
VIEWS = CATALOG / "views"
MANIFESTS = CATALOG / "manifests"

ELEMENT_SYMBOLS = {
    "h", "he", "li", "be", "b", "c", "n", "o", "f", "ne",
    "na", "mg", "al", "si", "p", "s", "cl", "ar", "k", "ca",
    "sc", "ti", "v", "cr", "mn", "fe", "co", "ni", "cu", "zn",
    "ga", "ge", "as", "se", "br", "kr", "rb", "sr", "y", "zr",
    "nb", "mo", "tc", "ru", "rh", "pd", "ag", "cd", "in", "sn",
    "sb", "te", "i", "xe", "cs", "ba", "la", "ce", "pr", "nd",
    "pm", "sm", "eu", "gd", "tb", "dy", "ho", "er", "tm", "yb",
    "lu", "hf", "ta", "w", "re", "os", "ir", "pt", "au", "hg",
    "tl", "pb", "bi", "po", "at", "rn", "fr", "ra", "ac", "th",
    "pa", "u", "np", "pu", "am", "cm", "bk", "cf", "es", "fm",
    "md", "no", "lr", "rf", "db", "sg", "bh", "hs", "mt", "ds",
    "rg", "cn", "nh", "fl", "mc", "lv", "ts", "og", "uue", "ubn",
}

ELEMENT_RE = re.compile(r"^([A-Z][a-z]?)")


def rel_path(path: Path) -> str:
    """Catalog path for a file: 'raw/<lib>/...' for raw data (wherever RAW lives), else repo-relative."""
    path = path.resolve()
    try:
        return "raw/" + path.relative_to(RAW).as_posix()
    except ValueError:
        return path.relative_to(ROOT).as_posix()


def resolve_catalog_path(path: str) -> Path:
    """Inverse of rel_path: map a stored 'raw/...' path onto RAW."""
    if path.startswith("raw/"):
        return RAW / path[4:]
    return ROOT / path


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_element(token: str) -> str | None:
    if not token:
        return None
    token = token.strip()
    if len(token) == 1:
        sym = token.upper()
    elif len(token) == 2:
        sym = token[0].upper() + token[1].lower()
    else:
        sym = token[0].upper() + token[1:].lower()
    return sym if sym.lower() in ELEMENT_SYMBOLS else None


def element_from_filename(filename: str) -> str | None:
    stem = Path(filename).stem
    m = ELEMENT_RE.match(stem)
    if m:
        return normalize_element(m.group(1))
    parts = stem.replace("_", ".").split(".")
    for part in parts:
        el = normalize_element(part)
        if el:
            return el
    return None


def element_from_sssp_filename(filename: str) -> str | None:
    token = Path(filename).name.split(".", 1)[0]
    return normalize_element(token)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # newline="\n": identical bytes whether the catalog is built on Windows or Linux
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def hint_formalism_from_filename(filename: str) -> str | None:
    low = filename.lower()
    if "kjpaw" in low or ".paw." in low:
        return "PAW"
    if "rrkjus" in low or ".us." in low or "uspp" in low:
        return "USPP"
    if "rrkj" in low or ".nc." in low or "oncv" in low:
        return "NC"
    return None


def hint_xc_from_filename(filename: str) -> str | None:
    low = filename.lower()
    if "pbesol" in low:
        return "PBEsol"
    if "pbe" in low or "gga" in low:
        return "PBE"
    if "lda" in low or "pz" in low:
        return "LDA"
    return None
