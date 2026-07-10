$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

docker compose -f docker/docker-compose.yml down -v

if (Test-Path "backend/local_storage") {
  Remove-Item "backend/local_storage" -Recurse -Force
}
New-Item -ItemType Directory -Force "backend/local_storage" | Out-Null

Write-Host "Local containers, database volume, and generated local assets were removed."
