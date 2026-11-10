# potdex agent guide

## Layout

- **Raw data** (gitignored): `raw/<lib>/` for PSlibrary, PseudoDOJO, SSSP, SG15-ONCV,
  Vanderbilt-USPP, PWmat, Rappe-group, BLPSLibrary, pseudos_ac_she. Override location with `POTDEX_RAW`.
- **Provenance** (tracked): `catalog/sources/registry.json` (where each library comes from),
  `<lib>.sha256` manifests, `mirror.json` (GitHub Release mirror). Protocol: `docs/DATA.md`.
- **Catalog**: `catalog/metadata/`, `catalog/manifests/` (tracked); `catalog/views/` (gitignored, rebuilt)
- **Tools**: `tools/fetch_all.py` (download + verify raw/), `tools/run_pipeline.py` (catalog build, offline),
  `tools/record_sources.py` (manifests / `--verify`), `tools/pack_mirror.py` + `publish_mirror.py` (maintainer),
  `tools/fetch/` (per-site scrapers used by fetch_all)
- Folder and file names must stay ASCII. Pipeline never writes into raw/; refer to raw files via
  `common.RAW` / `resolve_catalog_path()`, never `ROOT / "raw"`.

## Three-layer model

1. `by_element/` — per-element shelf (all abacus_ready options)
2. `by_family/` — **coherent datasets** (one family = one flat pseudo_dir)
3. `select_system_pp.py` — pick a family that **fully covers** the system

Do NOT use mixed cross-library scenario views for multi-element systems.

## Pipeline

```
fetch_all (network, separate)  →  run_pipeline:
parse_upf_header → extract_sssp → scan_libraries
→ build_global_index → build_cutoffs → build_selection_guide
→ build_catalog_views (includes build_families) → validate_catalog → smoke_test_abacus
```

## System selection

```powershell
python tools/select_system_pp.py --elements Fe O --task relax --output ./calc/Fe2O3
```

Task → family priority is in `tools/select_system_pp.py` (`task_family_order`).

## Hard rules

- `coherent_family: true` on all family manifests
- PAW never in abacus_ready views
- SSSP rejected when element only has PAW (e.g. Fe in efficiency set)
- `soc_shelf_deprecated.json` documents the old mixed 117-element view — do not use

## Known data issue

`raw/SSSP/v2.0/precision/SSSP-lib-pbe-prec-v2.tar.gz` is truncated locally and its upstream URL
returns 404; extract_sssp falls back to v1.1.2 PBE precision. No public source for SSSP v2.0,
v0.7 or `SSSP_1.0_plots.tar.gz` has been found: they reach other machines only via the mirror.
