"""Download Vanderbilt GBRV pseudopotentials into Vanderbilt-USPP/."""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
import os
from pathlib import Path

RAW_DIR = Path(os.environ["POTDEX_RAW"]) if os.environ.get("POTDEX_RAW") else Path(__file__).resolve().parents[2] / "raw"

BASE_URL = "https://www.physics.rutgers.edu/gbrv/"
ROOT = RAW_DIR / "Vanderbilt-USPP" / "GBRV-v1.5"
PRODUCTION_FMT = "upf"
ARCHIVE_FORMATS = {"uspp", "paw", "paw-xml"}

ELEMENT_PREFIXES = sorted(
    [
        "li", "be", "na", "mg", "al", "si", "cl", "ca", "sc", "ti", "cr", "mn",
        "fe", "co", "ni", "cu", "zn", "ga", "ge", "as", "se", "br", "kr", "rb",
        "sr", "zr", "nb", "mo", "tc", "ru", "rh", "pd", "ag", "cd", "in", "sn",
        "sb", "te", "cs", "ba", "la", "hf", "ta", "re", "os", "ir", "pt", "au",
        "hg", "tl", "pb", "bi",
        "h", "b", "c", "n", "o", "f", "k", "v", "w", "y", "i", "s", "p",
    ],
    key=len,
    reverse=True,
)


def classify(filename: str) -> tuple[str, str] | None:
    low = filename.lower()
    if low.endswith(".tar.gz"):
        return None

    prefix = None
    for candidate in ELEMENT_PREFIXES:
        if low.startswith(candidate + "_"):
            prefix = candidate
            break
    if prefix is None:
        return None

    element = prefix.capitalize() if len(prefix) == 1 else prefix[:1].upper() + prefix[1:]

    if low.endswith(".uspp.f.upf"):
        return "upf", element
    if low.endswith("_abinit.paw.xml"):
        return "paw-xml", element
    if low.endswith("_abinit.paw"):
        return "paw", element
    if low.endswith(".uspp"):
        return "uspp", element
    return None


def dest_path(fmt: str, element: str, filename: str) -> Path:
    if fmt == PRODUCTION_FMT:
        return ROOT / PRODUCTION_FMT / element / filename
    if fmt in ARCHIVE_FORMATS:
        return ROOT / "archive" / fmt / element / filename
    raise ValueError(f"unsupported format: {fmt}")


def fetch_links() -> list[str]:
    html = urllib.request.urlopen(BASE_URL, timeout=30).read().decode("utf-8", "replace")
    links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    seen: set[str] = set()
    out: list[str] = []
    for link in links:
        low = link.lower()
        if any(low.endswith(ext) for ext in (".upf", ".paw", ".uspp", ".xml")):
            if link not in seen:
                seen.add(link)
                out.append(link)
    return out


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "potdex-vanderbilt-uspp/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    dest.write_bytes(data)


def main() -> int:
    links = fetch_links()
    stats = {"ok": 0, "skip": 0, "fail": 0}
    failures: list[str] = []

    print(f"Found {len(links)} pseudopotential links")
    print(f"Target: {ROOT}")

    for link in links:
        filename = link.split("/")[-1]
        info = classify(filename)
        if info is None:
            stats["skip"] += 1
            continue

        fmt, element = info
        dest = dest_path(fmt, element, filename)
        url = BASE_URL + link if not link.startswith("http") else link
        try:
            download(url, dest)
            stats["ok"] += 1
            print(f"OK  {fmt}/{element}/{filename}")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            stats["fail"] += 1
            failures.append(f"{filename}: {exc}")
            print(f"ERR {filename}: {exc}", file=sys.stderr)

    print("\n--- summary ---")
    print(f"downloaded/exists: {stats['ok']}")
    print(f"skipped: {stats['skip']}")
    print(f"failed: {stats['fail']}")
    if failures:
        print("failures:")
        for item in failures:
            print(f"  - {item}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
