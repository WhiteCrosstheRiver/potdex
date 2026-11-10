# potdex agent guide

## Layout

- Original libraries (gitignored): `PSlibrary/`, `PseudoDOJO/`, `SSSP/`, `SG15-ONCV/`,
  `Vanderbilt-USPP/`, `PWmat/`, `Rappe-group/`, `BLPSLibrary/`, `pseudos_ac_she/`
- **Catalog**: `catalog/metadata/`, `catalog/manifests/` (tracked); `catalog/views/` (gitignored, rebuilt)
- **Tools**: `tools/run_pipeline.py` (catalog build); `tools/fetch/` (one-off download/scrape scripts)
- Folder and file names must stay ASCII.

## Three-layer model

1. `by_element/` — per-element shelf (all abacus_ready options)
2. `by_family/` — **coherent datasets** (one family = one flat pseudo_dir)
3. `select_system_pp.py` — pick a family that **fully covers** the system

Do NOT use mixed cross-library scenario views for multi-element systems.

## Pipeline

```
parse_upf_header → download_sssp → extract_sssp → scan_libraries
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

`SSSP/v2.0/precision/SSSP-lib-pbe-prec-v2.tar.gz` is corrupt locally.
Run `python tools/download_sssp.py` or download manually from https://sssp.materialscloud.org/
