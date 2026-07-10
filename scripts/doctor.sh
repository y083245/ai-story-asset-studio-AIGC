#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Story Asset Studio doctor"

command -v docker >/dev/null 2>&1 || { echo "missing: docker"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "missing: docker compose"; exit 1; }

[ -f .env ] && echo "ok: .env exists" || echo "warn: .env is missing; setup scripts will create it"
[ -f backend/pyproject.toml ] && echo "ok: backend present" || { echo "missing: backend"; exit 1; }
[ -f frontend/package.json ] && echo "ok: frontend present" || { echo "missing: frontend"; exit 1; }

if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "ok: backend health endpoint is reachable"
else
  echo "info: backend is not running yet"
fi

echo "doctor completed"
