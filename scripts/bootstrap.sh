#!/usr/bin/env bash
set -euo pipefail
dc="docker compose"

$dc up -d
$dc exec -T db sh -lc 'until pg_isready -U pulpo -d pulpo; do sleep 1; done'
$dc exec -T db psql -U pulpo -d pulpo -f /docker-entrypoint-initdb.d/01_core_up.sql || true
cat sql/02_seed_dev.sql | $dc exec -T db psql -U pulpo -d pulpo || true
$dc exec -T db psql -U pulpo -d pulpo -c "select count(*) messages from pulpo.messages"

# modelos ollama (con retry simple)
for m in llama3.1:8b qwen2.5:7b-instruct nomic-embed-text; do
  for i in {1..3}; do $dc exec -T ollama ollama pull "$m" && break || sleep 5; done
done

# smoke tests
printf "hola" | $dc exec -T ollama ollama run llama3.1:8b >/dev/null || true
curl -sf http://192.168.100.4:5678 >/dev/null && echo "n8n OK" || echo "n8n FAIL"
curl -sf http://192.168.100.4:11434/api/tags >/dev/null && echo "ollama OK" || echo "ollama FAIL"
