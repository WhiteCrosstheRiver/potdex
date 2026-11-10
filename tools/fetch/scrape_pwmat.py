"""
Download PWmat pseudopotentials from official website.

Source: http://www.pwmat.com/potential-download
        http://www.pwmat.com/pwmat-resource/pseduo-download/
"""
from __future__ import annotations

import io
import re
import time
import zipfile
import urllib.error
import urllib.request
import os
from pathlib import Path

RAW_DIR = Path(os.environ["POTDEX_RAW"]) if os.environ.get("POTDEX_RAW") else Path(__file__).resolve().parents[2] / "raw"

BASE_URL = "http://www.pwmat.com/pwmat-resource/pseduo-download/"
ROOT_DIR = RAW_DIR / "PWmat"

PACKAGES = [
    "NCPP-PD04-PBE.zip",
    "NCPP-PD04-PBE-SOC.zip",
    "NCPP-FHI-LDA.zip",
    "NCPP-PD03-PBE.zip",
    "NCPP-SG15-LDA.zip",
    "NCPP-SG15-PBE.zip",
    "NCPP-SG15-PBE-SOC.zip",
    "ONCV-PWM-PBE.zip",
    "H.zip",
    "GTH_POTENTIALS.zip",
    "GTH_BASIS_SETS.zip",
    "BASIS_MOLOPT.zip",
]

PP_EXTENSIONS = {".upf", ".UPF"}
MISC_NAMES = {"GTH_POTENTIALS", "GTH_BASIS_SETS", "BASIS_MOLOPT"}


def fetch(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def download_zip(name: str, retries: int = 3) -> bytes | None:
    url = BASE_URL + name
    for attempt in range(1, retries + 1):
        try:
            data = fetch(url)
            if len(data) < 1024 or not data.startswith(b"PK"):
                raise ValueError(f"unexpected payload size={len(data)}")
            return data
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            if attempt == retries:
                print(f"  FAIL zip {name}: {exc}")
                return None
            time.sleep(attempt)
    return None


def element_symbol(path: Path, parent_name: str | None) -> str:
    if parent_name and re.fullmatch(r"[A-Z][a-z]?", parent_name):
        return parent_name

    stem = path.stem
    token = stem.split(".")[0]
    token = re.split(r"[-_]", token)[0]
    if len(token) == 1:
        return token.upper()
    return token[0].upper() + token[1:].lower()


def save_member(zf: zipfile.ZipFile, member: str, lib_name: str) -> bool:
    info = zf.getinfo(member)
    if info.is_dir():
        return False

    filename = Path(member).name
    parts = Path(member).parts

    if filename in MISC_NAMES or Path(filename).suffix == "":
        dest = ROOT_DIR / lib_name / "misc" / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            return True
        dest.write_bytes(zf.read(member))
        return True

    if Path(filename).suffix not in PP_EXTENSIONS:
        return False

    parent = parts[-2] if len(parts) >= 2 else None
    symbol = element_symbol(Path(filename), parent)
    dest = ROOT_DIR / lib_name / "upf" / symbol / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.write_bytes(zf.read(member))
    return True


def process_zip(name: str) -> dict[str, int]:
    stats = {"pp": 0, "misc": 0, "skipped": 0, "failed": 0}
    lib_name = name.removesuffix(".zip")
    print(f"\n[{lib_name}] downloading...")

    data = download_zip(name)
    if data is None:
        stats["failed"] += 1
        return stats

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            filename = Path(member).name
            if filename in MISC_NAMES or (
                Path(filename).suffix == "" and not member.endswith("/")
            ):
                if save_member(zf, member, lib_name):
                    stats["misc"] += 1
                continue

            if Path(filename).suffix in PP_EXTENSIONS:
                if save_member(zf, member, lib_name):
                    stats["pp"] += 1
                else:
                    stats["failed"] += 1
            else:
                stats["skipped"] += 1

    print(f"  pp={stats['pp']}, misc={stats['misc']}, skipped={stats['skipped']}")
    return stats


def main() -> None:
    ROOT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output: {ROOT_DIR}")

    total = {"pp": 0, "misc": 0, "skipped": 0, "failed": 0}
    for name in PACKAGES:
        stats = process_zip(name)
        for key in total:
            total[key] += stats[key]

    print("\n" + "=" * 50)
    print(
        f"Done. pp={total['pp']}, misc={total['misc']}, "
        f"skipped={total['skipped']}, failed={total['failed']}"
    )
    print(f"Saved to: {ROOT_DIR}")


if __name__ == "__main__":
    main()
