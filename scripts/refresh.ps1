# One-command refresh: lint, type check, test, then run the pipeline.
# Usage: .\scripts\refresh.ps1   (or)   powershell -File scripts\refresh.ps1

$ErrorActionPreference = "Stop"

Write-Host "==> Format check"
python -m ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Lint"
python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Type check"
python -m mypy config src main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Tests"
python -m pytest
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "==> Run pipeline"
python main.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Data refreshed. Hit Refresh in Power BI."