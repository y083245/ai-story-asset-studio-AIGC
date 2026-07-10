$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

Write-Host "Story Asset Studio doctor"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Error "missing: docker"
}

docker compose version | Out-Null

if (Test-Path ".env") {
  Write-Host "ok: .env exists"
} else {
  Write-Host "warn: .env is missing; setup scripts will create it"
}

if (-not (Test-Path "backend/pyproject.toml")) { Write-Error "missing: backend" }
if (-not (Test-Path "frontend/package.json")) { Write-Error "missing: frontend" }

try {
  Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
  Write-Host "ok: backend health endpoint is reachable"
} catch {
  Write-Host "info: backend is not running yet"
}

Write-Host "doctor completed"
