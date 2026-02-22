Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot/.."
try {
  docker compose up -d --build
}
finally {
  Pop-Location
}
