#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="docker/docker-compose.yml"
MAX_ATTEMPTS=90
RETRY_DELAY_SECONDS=2

cd "$ROOT_DIR"

fail() {
  printf 'Error: %s\n' "$1" >&2
  exit 1
}

show_diagnostics() {
  printf '\nContainer state:\n'
  docker compose -f "$COMPOSE_FILE" ps || true
  printf '\nRecent backend/frontend logs:\n'
  docker compose -f "$COMPOSE_FILE" logs --tail=100 backend frontend || true
}

wait_for_stack() {
  local attempt
  for ((attempt = 1; attempt <= MAX_ATTEMPTS; attempt++)); do
    if docker compose -f "$COMPOSE_FILE" exec -T backend \
      curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && \
      docker compose -f "$COMPOSE_FILE" exec -T backend \
      curl -fsS http://frontend:3000 >/dev/null 2>&1; then
      return 0
    fi

    if ((attempt % 10 == 0)); then
      printf 'Still waiting for the stack (%d/%d)...\n' "$attempt" "$MAX_ATTEMPTS"
    fi
    if ((attempt < MAX_ATTEMPTS)); then
      sleep "$RETRY_DELAY_SECONDS"
    fi
  done
  return 1
}

command -v docker >/dev/null 2>&1 || fail "Docker is not installed. Install Docker Desktop for macOS first."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is unavailable. Update Docker Desktop first."
docker info >/dev/null 2>&1 || fail "Docker daemon is not running. Start Docker Desktop and try again."

[ -f .env.example ] || fail ".env.example is missing. Re-download or restore the complete repository."

if [ ! -f .env ]; then
  cp .env.example .env
  printf 'Created .env from .env.example.\n'
fi

mkdir -p local_config backend/local_storage

printf 'Validating Docker Compose configuration...\n'
docker compose -f "$COMPOSE_FILE" config --quiet

printf 'Building and starting Story Asset Studio in the background...\n'
docker compose -f "$COMPOSE_FILE" up -d --build

printf 'Waiting for backend migrations and frontend startup...\n'
if ! wait_for_stack; then
  printf 'Error: services did not become ready within %d seconds.\n' "$((MAX_ATTEMPTS * RETRY_DELAY_SECONDS))" >&2
  show_diagnostics
  exit 1
fi

docker compose -f "$COMPOSE_FILE" ps
printf '\nStory Asset Studio is ready.\n'
printf 'Frontend: http://localhost:3000\n'
printf 'API docs: http://localhost:8000/docs\n'
printf 'Logs: docker compose -f %s logs -f backend frontend\n' "$COMPOSE_FILE"
printf 'Stop: docker compose -f %s down\n' "$COMPOSE_FILE"
