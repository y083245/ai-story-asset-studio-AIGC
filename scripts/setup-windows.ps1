$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ComposeFile = "docker/docker-compose.yml"
$MaxAttempts = 90
$RetryDelaySeconds = 2

Set-Location $RootDir

function Fail {
  param([string]$Message)
  [Console]::Error.WriteLine("Error: $Message")
  exit 1
}

function Show-Diagnostics {
  Write-Host "`nContainer state:"
  docker compose -f $ComposeFile ps
  Write-Host "`nRecent backend/frontend logs:"
  docker compose -f $ComposeFile logs --tail=100 backend frontend
}

function Test-ServiceUrl {
  param([string]$Url)
  docker compose -f $ComposeFile exec -T backend curl -fsS $Url *> $null
  return $LASTEXITCODE -eq 0
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Fail "Docker is not installed. Install Docker Desktop for Windows first."
}

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
  Fail "Docker Compose v2 is unavailable. Update Docker Desktop first."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  Fail "Docker daemon is not running. Start Docker Desktop and try again."
}

if (-not (Test-Path ".env.example")) {
  Fail ".env.example is missing. Re-download or restore the complete repository."
}
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host "Created .env from .env.example."
}

New-Item -ItemType Directory -Force "local_config" | Out-Null
New-Item -ItemType Directory -Force "backend/local_storage" | Out-Null

Write-Host "Validating Docker Compose configuration..."
docker compose -f $ComposeFile config --quiet
if ($LASTEXITCODE -ne 0) {
  Fail "Docker Compose configuration is invalid."
}

Write-Host "Building and starting Story Asset Studio in the background..."
docker compose -f $ComposeFile up -d --build
if ($LASTEXITCODE -ne 0) {
  Fail "Docker Compose build or startup failed."
}

Write-Host "Waiting for backend migrations and frontend startup..."
$Ready = $false
for ($Attempt = 1; $Attempt -le $MaxAttempts; $Attempt++) {
  $BackendReady = Test-ServiceUrl "http://127.0.0.1:8000/health"
  $FrontendReady = $false
  if ($BackendReady) {
    $FrontendReady = Test-ServiceUrl "http://frontend:3000"
  }
  if ($BackendReady -and $FrontendReady) {
    $Ready = $true
    break
  }
  if ($Attempt % 10 -eq 0) {
    Write-Host "Still waiting for the stack ($Attempt/$MaxAttempts)..."
  }
  if ($Attempt -lt $MaxAttempts) {
    Start-Sleep -Seconds $RetryDelaySeconds
  }
}

if (-not $Ready) {
  [Console]::Error.WriteLine("Error: services did not become ready within $($MaxAttempts * $RetryDelaySeconds) seconds.")
  Show-Diagnostics
  exit 1
}

docker compose -f $ComposeFile ps
Write-Host "`nStory Asset Studio is ready."
Write-Host "Frontend: http://localhost:3000"
Write-Host "API docs: http://localhost:8000/docs"
Write-Host "Logs: docker compose -f $ComposeFile logs -f backend frontend"
Write-Host "Stop: docker compose -f $ComposeFile down"
