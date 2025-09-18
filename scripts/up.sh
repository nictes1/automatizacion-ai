#!/usr/bin/env bash
set -euo pipefail
dc="docker compose"
SERVER_IP="${SERVER_IP:-192.168.100.4}"
USE_GPU="${USE_GPU:-1}"   # 1=gpu, 0=cpu

# (Opcional) forzar CPU sin tocar el compose
if [ "$USE_GPU" = "0" ]; then
  echo "[up] Forzando CPU para Ollama (sin GPU)"
  sed -E -i.bak '/gpus: all|NVIDIA_VISIBLE_DEVICES|NVIDIA_DRIVER_CAPABILITIES/d' docker-compose.yml
fi

echo "[up] Levantando servicios…"
$dc up -d
echo "[up] Esperando DB…"
$dc exec -T db sh -lc 'until pg_isready -U pulpo -d pulpo; do sleep 1; done'

echo "[up] Aplicando schema…"
$dc exec -T db psql -U pulpo -d pulpo -f /docker-entrypoint-initdb.d/01_core_up.sql || true

if [ -f sql/02_seed_dev.sql ]; then
  echo "[up] Aplicando seed…"
  cat sql/02_seed_dev.sql | $dc exec -T db psql -U pulpo -d pulpo || true
fi

echo "[up] Cargando modelos Ollama (con retries)…"
for m in llama3.1:8b qwen2.5:7b-instruct nomic-embed-text; do
  for i in {1..3}; do $dc exec -T ollama ollama pull "$m" && break || sleep 5; done
done

echo "[up] Smoke tests…"
$dc exec -T db psql -U pulpo -d pulpo -c "select count(*) as messages from pulpo.messages"
curl -sf "http://${SERVER_IP}:5678" >/dev/null && echo "n8n OK" || echo "n8n FAIL"
curl -sf "http://${SERVER_IP}:11434/api/tags" >/dev/null && echo "ollama OK" || echo "ollama FAIL"
printf "hola" | $dc exec -T ollama ollama run llama3.1:8b >/dev/null && echo "ollama run OK" || echo "ollama run FAIL"
echo "[up] Listo."
