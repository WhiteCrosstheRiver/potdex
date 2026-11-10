#!/usr/bin/env python3
"""Probe PSlibrary website structure."""
import re
import urllib.request

BASE = "https://pseudopotentials.quantum-espresso.org"
UPF_BASE = f"{BASE}/upf_files"

def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "replace")

# Main page elements
main = fetch(f"{BASE}/legacy_tables/ps-library")
elements = re.findall(r'/legacy_tables/ps-library/([a-z]+)"', main)
print(f"Elements on main page: {len(elements)}")
print(elements[:10], "...", elements[-5:])

# Sample element page
for slug in ("h", "fe", "si", "u"):
    html = fetch(f"{BASE}/legacy_tables/ps-library/{slug}")
    # filenames in table
    names = re.findall(r'([A-Z][a-z]?\.[^<\s]+\.UPF)', html)
    hrefs = re.findall(r'href="([^"]+)"', html)
    upf_hrefs = [h for h in hrefs if "UPF" in h or "upf" in h]
    print(f"\n=== {slug} ===")
    print(f"  UPF names in page: {len(names)}")
    if names:
        print(f"  sample: {names[0]}")
    print(f"  upf hrefs: {upf_hrefs[:3]}")

# Test direct download
test = "H.pbe-kjpaw_psl.1.0.0.UPF"
for url in (
    f"{UPF_BASE}/{test}",
    f"{BASE}/upf_files/{test}",
):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(200)
            print(f"\nOK {url} -> {len(data)} bytes preview: {data[:80]!r}")
    except Exception as e:
        print(f"\nFAIL {url} -> {e}")
