# potdex one-step setup (Windows PowerShell):
#   .\setup.ps1                 download all libraries into raw\, verify, build the catalog
#   .\setup.ps1 SG15-ONCV SSSP  only some libraries
# Needs Python 3.9+ on PATH (and git for BLPSLibrary / pseudos_ac_she).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if (Get-Command python -ErrorAction SilentlyContinue) { "python" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { throw "Python 3.9+ not found on PATH" }
& $py tools/fetch_all.py @args
$fetch = $LASTEXITCODE
& $py tools/run_pipeline.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if ($fetch -ne 0) { Write-Warning "Some libraries are incomplete (see summary above); the catalog was built from what is present." }
exit $fetch
