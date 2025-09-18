#!/usr/bin/env bash
set -euo pipefail
dc="docker compose"
SERVER_IP="${SERVER_IP:-192.168.100.4}"

echo "[verify] Servicios"
$dc ps

echo "[verify] Postgres"
$dc exec -T db psql -U pulpo -d pulpo -c "\dx"
$dc exec -T db psql -U pulpo -d pulpo -c "\dt pulpo.*"
$dc exec -T db psql -U pulpo -d pulpo -c "select count(*) as messages from pulpo.messages"

echo "[verify] n8n"
curl -s -o /dev/null -w "HTTP %{$(echo http_code)}\n" "http://${SERVER_IP}:5678" || true
curl -s -o /dev/null -w "%{http_code}\n" "http://${SERVER_IP}:5678"

echo "[verify] Ollama"
curl -s "http://${SERVER_IP}:11434/api/tags"
printf "ping" | $dc exec -T ollama ollama run llama3.1:8b >/dev/null && echo "ollama run OK" || echo "ollama run FAIL"
