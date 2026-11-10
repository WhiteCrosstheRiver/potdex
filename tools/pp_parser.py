"""UPF / BLPS header parser for ABACUS catalog classification."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path

from common import hint_formalism_from_filename, hint_xc_from_filename, normalize_element

UPF2_HEADER_RE = re.compile(r"<PP_HEADER\b([^>]*)/?>", re.I | re.S)
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
PP_INFO_TYPE_RE = re.compile(r"Pseudopotential type:\s*(\w+)", re.I)
XC_TOKEN_RE = re.compile(r"\b(PBE|PBEsol|LDA|PZ)\b", re.I)


@dataclass
class PPInfo:
    parse_success: bool
    file_format: str
    formalism: str
    abacus_ready: bool
    element: str | None
    relativistic: str
    has_soc: bool
    xc_functional: str | None
    pseudo_type_raw: str | None
    is_paw: bool
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"t", "true", "1", "yes"}


def _parse_upf_v2_header(text: str) -> dict[str, str]:
    m = UPF2_HEADER_RE.search(text)
    if not m:
        return {}
    return {k.lower(): v for k, v in ATTR_RE.findall(m.group(1))}


def _parse_upf_v1_header(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if "<PP_HEADER>" not in text:
        return out
    block = text.split("<PP_HEADER>", 1)[1].split("</PP_HEADER>", 1)[0]
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    if len(lines) >= 2:
        out["element"] = lines[1]
    if len(lines) >= 3:
        line3 = lines[2].upper()
        if "ULTRASOFT" in line3 or line3.strip() == "US":
            out["pseudo_type"] = "US"
        elif "NORM" in line3 or line3.strip() == "NC":
            out["pseudo_type"] = "NC"
        elif "PAW" in line3:
            out["pseudo_type"] = "PAW"
    for ln in lines:
        up = ln.upper()
        if "PBE" in up:
            out["xc"] = "PBE"
        elif "PBESOL" in up:
            out["xc"] = "PBEsol"
        elif "LDA" in up or "PZ" in up:
            out["xc"] = "LDA"
    return out


def _formalism_from_fields(
    pseudo_type: str | None,
    is_paw: bool,
    filename: str,
    pp_info_type: str | None,
) -> str:
    pt = (pseudo_type or "").upper()
    info = (pp_info_type or "").upper()
    if is_paw or pt == "PAW" or info == "PAW":
        return "PAW"
    if pt in {"US", "USPP"} or info in {"US", "USPP"}:
        return "USPP"
    if pt == "NC" or info == "NC":
        return "NC"
    hint = hint_formalism_from_filename(filename)
    return hint or "UNKNOWN"


def parse_upf(path: Path) -> PPInfo:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return PPInfo(
            parse_success=False,
            file_format="UNKNOWN",
            formalism="UNKNOWN",
            abacus_ready=False,
            element=None,
            relativistic="unknown",
            has_soc=False,
            xc_functional=None,
            pseudo_type_raw=None,
            is_paw=False,
            error=str(exc),
        )

    if "<UPF" in text[:200]:
        file_format = "UPF2"
        attrs = _parse_upf_v2_header(text)
    elif "<PP_HEADER>" in text:
        file_format = "UPF1"
        attrs = _parse_upf_v1_header(text)
    else:
        return PPInfo(
            parse_success=False,
            file_format="UNKNOWN",
            formalism="UNKNOWN",
            abacus_ready=False,
            element=None,
            relativistic="unknown",
            has_soc=False,
            xc_functional=None,
            pseudo_type_raw=None,
            is_paw=False,
            error="not a recognized UPF file",
        )

    pp_info_m = PP_INFO_TYPE_RE.search(text)
    pp_info_type = pp_info_m.group(1) if pp_info_m else None

    pseudo_type = attrs.get("pseudo_type")
    is_paw = _truthy(attrs.get("is_paw"))
    relativistic = (attrs.get("relativistic") or "unknown").lower()
    has_soc = _truthy(attrs.get("has_so"))
    element = normalize_element(attrs.get("element", "")) if attrs.get("element") else None

    formalism = _formalism_from_fields(pseudo_type, is_paw, path.name, pp_info_type)

    xc = attrs.get("xc") or attrs.get("functional")
    if xc:
        xc = xc.upper().replace("PBX", "PBE").replace("PBC", "")
        if "PBESOL" in xc:
            xc_functional = "PBEsol"
        elif "PBE" in xc:
            xc_functional = "PBE"
        elif "LDA" in xc or "PZ" in xc:
            xc_functional = "LDA"
        else:
            xc_functional = hint_xc_from_filename(path.name)
    else:
        xc_functional = hint_xc_from_filename(path.name)

    abacus_ready = formalism in {"NC", "USPP"}

    return PPInfo(
        parse_success=True,
        file_format=file_format,
        formalism=formalism,
        abacus_ready=abacus_ready,
        element=element,
        relativistic=relativistic,
        has_soc=has_soc,
        xc_functional=xc_functional,
        pseudo_type_raw=pseudo_type or pp_info_type,
        is_paw=is_paw,
    )


def parse_blps(path: Path) -> PPInfo:
    element = None
    token = path.stem.split(".", 1)[0]
    element = normalize_element(token)
    return PPInfo(
        parse_success=True,
        file_format="BLPS",
        formalism="LOCAL",
        abacus_ready=False,
        element=element,
        relativistic="none",
        has_soc=False,
        xc_functional="GGA" if "gga" in path.name.lower() else "LDA",
        pseudo_type_raw="BLPS",
        is_paw=False,
    )
