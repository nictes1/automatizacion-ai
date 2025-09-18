#!/usr/bin/env bash
set -euo pipefail

SERVICE=${1:-db}
VOL=pulpo_dbdata

read -p "Esto borrará SOLO el volumen de Postgres ($VOL). Continuar? (yes/no) " ans
[ "$ans" != "yes" ] && { echo "Abortado"; exit 1; }

docker compose stop "$SERVICE" || true
docker compose rm -f "$SERVICE" || true
docker volume rm "$VOL"
docker compose up -d "$SERVICE"
docker compose logs -f "$SERVICE"