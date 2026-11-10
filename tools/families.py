"""Coherent PP family definitions — one dataset per family, no cross-library mixing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    display_name: str
    description: str
    task_tags: tuple[str, ...]  # relax, precision, soc, uspp, ofdft
    xc: str  # PBE, PBEsol, LDA
    soc: bool
    formalisms: tuple[str, ...]  # NC, USPP, ...

    def match(self, row: dict) -> bool:
        if not row.get("abacus_ready") and self.family_id != "ofdft_blps_gga":
            if self.family_id.startswith("ofdft"):
                pass
            else:
                return False
        fn = row.get("filename", "")
        dataset = row.get("dataset") or ""
        lib = row.get("library_id", "")
        formalism = row.get("formalism", "")

        if formalism not in self.formalisms and self.family_id != "ofdft_blps_gga":
            return False

        if self.soc:
            if self.family_id == "pwmat_pd04_pbe_soc":
                if row.get("relativistic") != "full":
                    return False
            elif not (row.get("has_soc") and row.get("relativistic") == "full"):
                return False
        else:
            if row.get("has_soc") and row.get("relativistic") == "full":
                return False

        xc = (row.get("xc_functional") or "").upper()
        if self.family_id == "ofdft_blps_gga":
            pass  # BLPS uses GGA/LDA label, skip XC gate
        elif self.xc == "PBE" and xc not in ("PBE", ""):
            return False
        elif self.xc == "PBEsol" and "PBESOL" not in xc:
            return False

        matchers: dict[str, Callable[[dict], bool]] = {
            "sssp_v2_pbe_efficiency": lambda r: (
                r["library_id"] == "sssp" and r.get("dataset") == "PBE_efficiency"
            ),
            "sssp_v2_pbe_precision": lambda r: (
                r["library_id"] == "sssp" and r.get("dataset") == "PBE_precision"
            ),
            "sg15_oncv_pbe_sr": lambda r: (
                r["library_id"] == "sg15_oncv"
                and "_FR-" not in fn
                and fn.endswith("-1.0.upf")
            ),
            "sg15_oncv_pbe_fr": lambda r: (
                r["library_id"] == "sg15_oncv"
                and "_FR-" in fn
                and fn.endswith("-1.0.upf")
            ),
            "pseudodojo_nc_sr_pbe_standard": lambda r: (
                r["library_id"] == "pseudodojo"
                and r.get("dataset") == "nc-sr-05_pbe_standard_upf"
            ),
            "pseudodojo_nc_sr_pbe_stringent": lambda r: (
                r["library_id"] == "pseudodojo"
                and r.get("dataset") == "nc-sr-05_pbe_stringent_upf"
            ),
            "pseudodojo_nc_fr_pbe_standard": lambda r: (
                r["library_id"] == "pseudodojo"
                and r.get("dataset") == "nc-fr-04_pbe_standard"
            ),
            "pseudodojo_nc_fr_pbe_stringent": lambda r: (
                r["library_id"] == "pseudodojo"
                and r.get("dataset") == "nc-fr-04_pbe_stringent"
            ),
            "gbrv_v1.5_pbe_uspp": lambda r: (
                r["library_id"] == "gbrv" and r.get("role") == "production"
            ),
            "pwmat_pd04_pbe_soc": lambda r: (
                r["library_id"] == "pwmat"
                and r.get("dataset") == "NCPP-PD04-PBE-SOC"
            ),
            "ofdft_blps_gga": lambda r: (
                r["library_id"] == "blps" and fn.endswith(".psp")
            ),
        }
        matcher = matchers.get(self.family_id)
        return matcher(row) if matcher else False


FAMILIES: list[FamilySpec] = [
    FamilySpec(
        "sssp_v2_pbe_efficiency",
        "SSSP v2.0 PBE Efficiency",
        "官方 SSSP v2.0 PBE 效率集（仅 NC/USPP）",
        ("relax",),
        "PBE",
        False,
        ("NC", "USPP"),
    ),
    FamilySpec(
        "sssp_v2_pbe_precision",
        "SSSP v2.0 PBE Precision",
        "官方 SSSP v2.0 PBE 精度集（仅 NC/USPP）",
        ("precision",),
        "PBE",
        False,
        ("NC", "USPP"),
    ),
    FamilySpec(
        "sg15_oncv_pbe_sr",
        "SG15 ONCV PBE Scalar-Relativistic",
        "SG15 v1.0 标量相对论 PBE",
        ("relax", "precision"),
        "PBE",
        False,
        ("NC",),
    ),
    FamilySpec(
        "sg15_oncv_pbe_fr",
        "SG15 ONCV PBE Full-Relativistic",
        "SG15 v1.0 全相对论 SOC",
        ("soc",),
        "PBE",
        True,
        ("NC",),
    ),
    FamilySpec(
        "pseudodojo_nc_sr_pbe_standard",
        "PseudoDojo NC-SR-05 PBE Standard",
        "PseudoDojo 标量相对论 NC standard",
        ("relax",),
        "PBE",
        False,
        ("NC",),
    ),
    FamilySpec(
        "pseudodojo_nc_sr_pbe_stringent",
        "PseudoDojo NC-SR-05 PBE Stringent",
        "PseudoDojo 标量相对论 NC stringent",
        ("precision",),
        "PBE",
        False,
        ("NC",),
    ),
    FamilySpec(
        "pseudodojo_nc_fr_pbe_standard",
        "PseudoDojo NC-FR-04 PBE Standard",
        "PseudoDojo 全相对论 SOC standard",
        ("soc",),
        "PBE",
        True,
        ("NC",),
    ),
    FamilySpec(
        "pseudodojo_nc_fr_pbe_stringent",
        "PseudoDojo NC-FR-04 PBE Stringent",
        "PseudoDojo 全相对论 SOC stringent",
        ("soc", "precision"),
        "PBE",
        True,
        ("NC",),
    ),
    FamilySpec(
        "gbrv_v1.5_pbe_uspp",
        "GBRV v1.5 PBE USPP",
        "Vanderbilt GBRV 超软赝势",
        ("relax", "uspp"),
        "PBE",
        False,
        ("USPP",),
    ),
    FamilySpec(
        "pwmat_pd04_pbe_soc",
        "PWmat PD04 PBE SOC",
        "PWmat NCPP-PD04-PBE-SOC 全相对论集",
        ("soc",),
        "PBE",
        True,
        ("NC",),
    ),
    FamilySpec(
        "ofdft_blps_gga",
        "BLPS GGA Real-space",
        "ABACUS OFDFT 局域赝势",
        ("ofdft",),
        "PBE",
        False,
        ("LOCAL",),
    ),
]

FAMILY_BY_ID = {f.family_id: f for f in FAMILIES}


def pick_family_elements(rows: list[dict], family_id: str) -> dict[str, dict]:
    spec = FAMILY_BY_ID[family_id]
    chosen: dict[str, dict] = {}
    for row in rows:
        if not spec.match(row):
            continue
        el = row.get("element")
        if not el:
            continue
        if el not in chosen:
            chosen[el] = row
    return chosen


def family_covers(elements: list[str], family_choices: dict[str, dict]) -> tuple[bool, list[str]]:
    missing = [el for el in elements if el not in family_choices]
    return len(missing) == 0, missing
