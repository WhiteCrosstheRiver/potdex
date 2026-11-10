# potdex

A local, versioned index of pseudopotential libraries (SSSP, PseudoDojo, SG15,
PSlibrary, GBRV, PWmat, …) that picks a **coherent** set of potentials for a
given system and code, and can be rebuilt on any machine from one command.

The git repository holds the code, the catalog metadata and a SHA-256 manifest
of every data file. The potential files themselves (~9 GB) are **not** in git;
`setup` downloads them and checks each one against the manifests.

## Quick start

```bash
git clone https://github.com/WhiteCrosstheRiver/potdex.git
cd potdex
./setup.sh            # Linux / macOS
.\setup.ps1           # Windows PowerShell
```

`setup` = `python tools/fetch_all.py` (download + verify every library into `raw/`)
followed by `python tools/run_pipeline.py` (build the catalog, offline).
It is safe to re-run: libraries that already verify are skipped, interrupted
downloads resume.

Requirements: Python ≥ 3.9 (standard library only) and git. Optional:
`pip install certifi` if your Python cannot verify TLS certificates.

Fetch only what you need:

```bash
python tools/fetch_all.py SSSP SG15-ONCV     # just these libraries
python tools/fetch_all.py --plan             # show what would be downloaded
POTDEX_RAW=/shared/potdex-raw ./setup.sh     # keep raw/ on another disk
```

## Pick potentials for a system

```bash
python tools/select_system_pp.py --elements Fe O --task relax --output calculations/Fe2O3
```

This writes `calculations/Fe2O3/pp/` (hard links), `pp_selection.json` and an
ABACUS `STRU` species block. It only returns families that cover **all**
elements from **one** dataset; see [catalog/README.md](catalog/README.md).

## What gets downloaded

| Library | Files | Size | Source | How setup gets it |
|---|---:|---:|---|---|
| SSSP | 414 | 1.7 GiB | Materials Cloud | mirror; v1.x also from Materials Cloud (md5-checked) |
| PSlibrary | 1425 | 3.5 GiB | quantum-espresso.org | mirror, else scraper |
| PseudoDOJO | 2312 | 2.3 GiB | pseudo-dojo.org | mirror, else scraper |
| pseudos_ac_she | 965 | 482 MiB | GitHub `gmatteo/pseudos_ac_she` | git clone at pinned commit |
| Vanderbilt-USPP (GBRV) | 578 | 243 MiB | rutgers.edu/gbrv | mirror, else scraper |
| PWmat | 681 | 208 MiB | pwmat.com | mirror, else scraper |
| SG15-ONCV | 380 | 66 MiB | quantum-simulation.org | tarballs + files, checksum-exact |
| Rappe-group | 240 | 26 MiB | upenn.edu | mirror, else scraper |
| BLPSLibrary | 40 | 6 MiB | GitHub `PrincetonUniversity/BLPSLibrary` | git clone at pinned commit |

Exact counts, licences and upstream URLs: [catalog/sources/](catalog/sources/).
Every library keeps its upstream licence; check it before redistributing.

## Layout

```text
raw/                 downloaded libraries (gitignored; see catalog/sources/)
catalog/sources/     registry.json (where each library comes from), <lib>.sha256 manifests, mirror.json
catalog/metadata/    global index, cutoffs, coverage and validation reports
catalog/manifests/   coherent family definitions
catalog/views/       per-element and per-family folders of hard links (rebuilt, gitignored)
tools/               pipeline, fetch_all, selection; tools/fetch/ holds the per-site scrapers
docs/DATA.md         how data is published, verified and updated (maintainers)
```

## Status

Built for ABACUS / Quantum ESPRESSO style UPF today. Planned: per-code
compatibility (CP2K GTH, VASP POTCAR metadata, Gaussian ECPs), and identifying
the potentials used by an existing calculation. See [AGENTS.md](AGENTS.md).
