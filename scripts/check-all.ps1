Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "== Backend tests =="
Push-Location "$PSScriptRoot/../backend"
try {
  .\.venv\Scripts\python -m pytest -q
}
finally {
  Pop-Location
}

Write-Host "== Frontend lint =="
Push-Location "$PSScriptRoot/../frontend"
try {
  npm run lint
  npm run typecheck
  npm run test
  npm run build
}
finally {
  Pop-Location
}

Write-Host "All checks passed."
