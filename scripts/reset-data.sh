#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

docker compose -f docker/docker-compose.yml down -v
rm -rf backend/local_storage
mkdir -p backend/local_storage

echo "Local containers, database volume, and generated local assets were removed."
