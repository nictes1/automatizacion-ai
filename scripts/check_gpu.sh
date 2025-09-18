#!/usr/bin/env bash
set -euo pipefail
dc="docker compose"
echo "[check] GPU en contenedor:"
$dc exec -T ollama nvidia-smi || { echo "GPU NO visible"; exit 1; }
echo "[check] Disparando carga… (mirá otro terminal con: watch -n1 nvidia-smi)"
printf "resume en 10 palabras" | $dc exec -T ollama ollama run llama3.1:8b >/dev/null
echo "[check] Hecho. Si no viste uso en nvidia-smi, revisemos drivers/runtime."

