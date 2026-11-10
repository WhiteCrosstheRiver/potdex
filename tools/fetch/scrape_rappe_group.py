"""
Download Rappe Group OPIUM pseudopotentials from UPenn website.

Source: https://www.sas.upenn.edu/rappegroup/research/pseudo-potential-gga.html
        https://www.sas.upenn.edu/rappegroup/research/pseudo-potential-lda.html
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import os
from pathlib import Path

RAW_DIR = Path(os.environ["POTDEX_RAW"]) if os.environ.get("POTDEX_RAW") else Path(__file__).resolve().parents[2] / "raw"

BASE_URL = "https://www.sas.upenn.edu/rappegroup/research"
ROOT_DIR = RAW_DIR / "Rappe-group"

PP_EXTENSIONS = {".fhi", ".param", ".rpt"}

DATABASES = [
    ("PBE-GGA", "pseudo-potential-gga.html"),
    ("PZ-LDA", "pseudo-potential-lda.html"),
]

# Do not retry known upstream gaps.
SKIP_DOWNLOADS = {
    "y.optgga3.fhi",
    "p.optgga1.fhi",
    "p.optgga2.fhi",
    "mo.optgga3.fhi",
    "mo.optgga3.rpt",
    "ga.optlda1.fhi",
}

ELEMENT_SYMBOLS = {
    "h": "H",
    "he": "He",
    "li": "Li",
    "be": "Be",
    "b": "B",
    "c": "C",
    "n": "N",
    "o": "O",
    "f": "F",
    "ne": "Ne",
    "na": "Na",
    "mg": "Mg",
    "al": "Al",
    "si": "Si",
    "p": "P",
    "s": "S",
    "cl": "Cl",
    "ar": "Ar",
    "k": "K",
    "ca": "Ca",
    "sc": "Sc",
    "ti": "Ti",
    "v": "V",
    "cr": "Cr",
    "mn": "Mn",
    "fe": "Fe",
    "co": "Co",
    "ni": "Ni",
    "cu": "Cu",
    "zn": "Zn",
    "ga": "Ga",
    "ge": "Ge",
    "as": "As",
    "se": "Se",
    "br": "Br",
    "kr": "Kr",
    "rb": "Rb",
    "sr": "Sr",
    "y": "Y",
    "zr": "Zr",
    "nb": "Nb",
    "mo": "Mo",
    "tc": "Tc",
    "ru": "Ru",
    "rh": "Rh",
    "pd": "Pd",
    "ag": "Ag",
    "cd": "Cd",
    "in": "In",
    "sn": "Sn",
    "sb": "Sb",
    "te": "Te",
    "i": "I",
    "xe": "Xe",
    "cs": "Cs",
    "ba": "Ba",
    "la": "La",
    "hf": "Hf",
    "ta": "Ta",
    "w": "W",
    "re": "Re",
    "os": "Os",
    "ir": "Ir",
    "pt": "Pt",
    "au": "Au",
    "hg": "Hg",
    "tl": "Tl",
    "pb": "Pb",
    "bi": "Bi",
    "po": "Po",
    "at": "At",
    "rn": "Rn",
}


def fetch(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8", "replace")


def extract_links(html: str) -> list[str]:
    return re.findall(r'href=["\']([^"\']+)["\']', html, re.I)


def element_symbol(slug: str) -> str:
    return ELEMENT_SYMBOLS.get(slug.lower(), slug.capitalize())


def is_pp_file(name: str) -> bool:
    return Path(name).suffix.lower() in PP_EXTENSIONS


def dest_path(db_name: str, ext: str, symbol: str, filename: str) -> Path:
    if ext == "fhi":
        return ROOT_DIR / db_name / "upstream" / "fhi" / symbol / filename
    return ROOT_DIR / db_name / "source-only" / ext / symbol / filename


def get_element_pages(index_path: str) -> list[str]:
    html = fetch_text(f"{BASE_URL}/{index_path}")
    return sorted(
        link
        for link in extract_links(html)
        if link.endswith(".html") and "PSP/" in link.replace("\\", "/")
    )


def resolve_file_url(page_path: str, filename: str) -> str:
    page_dir = "/".join(page_path.split("/")[:-1])
    return f"{BASE_URL}/{page_dir}/{filename}"


def download_file(url: str, dest: Path, retries: int = 3) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True

    for attempt in range(1, retries + 1):
        try:
            data = fetch(url)
            dest.write_bytes(data)
            return True
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if attempt == retries:
                print(f"  FAIL {dest.name}: {exc}")
                return False
            time.sleep(attempt)
    return False


def scrape_database(db_name: str, index_path: str) -> dict[str, int]:
    stats = {"elements": 0, "files": 0, "failed": 0, "skipped": 0}
    pages = get_element_pages(index_path)
    print(f"\n[{db_name}] {len(pages)} element pages")

    for page_path in pages:
        slug = page_path.split("/")[-1].replace(".html", "")
        symbol = element_symbol(slug)
        html = fetch_text(f"{BASE_URL}/{page_path}")
        pp_files = [f for f in extract_links(html) if is_pp_file(f)]

        if not pp_files:
            continue

        stats["elements"] += 1
        print(f"  {symbol}: {len(pp_files)} files")

        for filename in pp_files:
            if filename in SKIP_DOWNLOADS:
                stats["skipped"] += 1
                continue

            ext = Path(filename).suffix.lower().lstrip(".")
            dest = dest_path(db_name, ext, symbol, filename)
            url = resolve_file_url(page_path, filename)
            ok = download_file(url, dest)
            if ok:
                stats["files"] += 1
            else:
                stats["failed"] += 1

    return stats


def rebuild_metadata() -> None:
    script = Path(__file__).resolve().parents[2] / "reorganize_rappe_group.py"
    subprocess.run([sys.executable, str(script)], check=True)


def main() -> None:
    ROOT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output: {ROOT_DIR}")

    total = {"elements": 0, "files": 0, "failed": 0, "skipped": 0}
    for db_name, index_path in DATABASES:
        stats = scrape_database(db_name, index_path)
        for key in total:
            total[key] += stats[key]

    rebuild_metadata()

    print("\n" + "=" * 50)
    print(
        f"Done. elements={total['elements']}, files={total['files']}, "
        f"failed={total['failed']}, skipped_upstream_missing={total['skipped']}"
    )
    print(f"Saved to: {ROOT_DIR}")


if __name__ == "__main__":
    main()
