#!/usr/bin/env sh
# potdex one-step setup (Linux / macOS):
#   ./setup.sh                  download all libraries into raw/, verify, build the catalog
#   ./setup.sh SG15-ONCV SSSP   only some libraries
# Needs Python 3.9+ (and git for BLPSLibrary / pseudos_ac_she).
set -u
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python) || { echo "Python 3.9+ not found" >&2; exit 1; }
"$PY" tools/fetch_all.py "$@"
fetch=$?
"$PY" tools/run_pipeline.py || exit $?
[ "$fetch" -ne 0 ] && echo "WARNING: some libraries are incomplete (see summary above); the catalog was built from what is present." >&2
exit "$fetch"
