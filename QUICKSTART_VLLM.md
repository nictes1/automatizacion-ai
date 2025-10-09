# 🚀 Quick Start - Sistema Multi-Modelo vLLM

## Opción 1: Iniciar con Docker (Recomendado)

### Paso 1: Instalar NVIDIA Container Toolkit (una sola vez)

```bash
# Agregar repositorio
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Instalar
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configurar Docker
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### Paso 2: Descomentar servicios vLLM en docker-compose.yml

Edita `docker-compose.yml` y descomenta las secciones:
- `vllm-router` (líneas ~87-115)
- `vllm-agent` (líneas ~117-149)

### Paso 3: Iniciar servicios

```bash
docker-compose up vllm-router vllm-agent
```

**Nota**: La primera vez descargará los modelos (~10-15GB), toma 10-15 minutos.

## Opción 2: Iniciar en Host (Desarrollo)

### Paso 1: Instalar vLLM

```bash
pip install vllm
```

### Paso 2: Iniciar Router

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --quantization awq \
  --port 8001 \
  --gpu-memory-utilization 0.35 \
  --max-model-len 4096
```

### Paso 3: Iniciar Agent (en otra terminal)

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-14B-Instruct-AWQ \
  --quantization awq \
  --port 8002 \
  --gpu-memory-utilization 0.50 \
  --max-model-len 8192 \
  --enable-prefix-caching
```

## 🧪 Probar el Sistema

```bash
python scripts/test_multi_model.py
```

## 📊 Uso de VRAM Esperado

```
Router (8B AWQ):  ~7-8GB
Agent (14B AWQ):  ~10-12GB
Total:            ~18-20GB
Buffer libre:     ~4-6GB (en 3090 24GB)
```

## 🎯 ¿Cómo funciona?

1. **Router** (rápido ~100ms): Maneja saludos, consultas simples, precios
2. **Agent** (preciso ~300ms): Maneja reservas, tool calling, slot filling

## 🔄 Volver a Ollama

Si querés volver a usar solo Ollama:
1. Comenta los servicios vLLM en docker-compose.yml
2. `docker-compose restart orchestrator`

## 📝 Configuración

Edita `config/vllm_config.yaml` para ajustar:
- GPU memory utilization
- Max model length
- Routing strategy

