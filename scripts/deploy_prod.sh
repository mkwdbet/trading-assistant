#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  echo ".env is missing. Copy .env.production.example to .env and fill it first."
  exit 1
fi

mkdir -p data
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps

