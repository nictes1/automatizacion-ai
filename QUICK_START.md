# 🚀 Quick Start - SLM Pipeline

Guía rápida para levantar el SLM Pipeline en 5 minutos.

---

## ⚡ Setup Rápido

### 1. Instalar Dependencias

```bash
# Python dependencies
pip install -r requirements.txt

# Ollama (para SLMs locales)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
ollama pull phi3:mini
```

### 2. Configurar Environment

```bash
# Copiar ejemplo
cp .env.example .env

# Editar .env
nano .env
```

**Mínimo requerido:**
```bash
ENABLE_SLM_PIPELINE=true
SLM_CANARY_PERCENT=0  # 100% SLM para testing
SLM_EXTRACTOR_MODEL=qwen2.5:7b
SLM_PLANNER_MODEL=qwen2.5:7b
```

### 3. Ejecutar Tests

```bash
# Unit tests
pytest tests/unit/test_planner_slm.py -v

# E2E tests
pytest tests/e2e/test_slm_pipeline_e2e.py -v

# Smoke tests
./tests/smoke/smoke_test.sh
```

### 4. Ejecutar Ejemplo

```bash
python examples/integration_example.py
```

**Output esperado:**
```
🚀 PulpoAI - Ejemplos de Integración SLM Pipeline
=========================================

✅ Orchestrator initialized:
   - SLM Pipeline: True
   - Canary: 0%

[greeting] ✓ intent=greeting actions=0 latency=120ms
[info_hours] ✓ intent=info_hours actions=1 latency=650ms
...
✅ Todos los ejemplos ejecutados correctamente
```

---

## 🧪 Testing Rápido

### Opción 1: Ejemplo Python

```python
import asyncio
from services.orchestrator_integration import OrchestratorServiceIntegrated
from examples.integration_example import create_snapshot, MockLLMClient

async def test():
    llm = MockLLMClient()
    orchestrator = OrchestratorServiceIntegrated(llm)
    
    snapshot = create_snapshot("Quiero turno mañana 15hs")
    response = await orchestrator.decide(snapshot)
    
    print(f"Respuesta: {response.assistant}")
    print(f"Debug: {response.debug}")

asyncio.run(test())
```

### Opción 2: cURL (si tenés API corriendo)

```bash
curl -X POST http://localhost:8000/orchestrator/decide \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "ws-test-123",
    "conversation_id": "conv-test-456",
    "user_input": "Quiero turno mañana 15hs",
    "vertical": "servicios",
    "slots": {}
  }' | jq .
```

### Opción 3: Smoke Tests

```bash
cd tests/smoke
./smoke_test.sh
```

---

## 📊 Verificar Métricas

### Logs

```bash
# Ver telemetría en tiempo real
tail -f logs/orchestrator.log | grep TELEMETRY

# Filtrar por latencia alta
grep "t_total_ms" logs/orchestrator.log | awk -F'=' '{if ($NF > 1500) print}'

# Filtrar por confidence baja
grep "confidence=" logs/orchestrator.log | awk -F'=' '{if ($NF < 0.7) print}'
```

### Métricas del Orchestrator

```python
from services.orchestrator_integration import OrchestratorServiceIntegrated

orchestrator = OrchestratorServiceIntegrated(llm_client)

# Después de varios requests
metrics = orchestrator.get_metrics()
print(metrics)
# {
#   "slm_requests": 85,
#   "legacy_requests": 15,
#   "total_requests": 100,
#   "slm_percentage": 85.0,
#   "slm_error_rate": 0.5
# }
```

---

## 🔧 Troubleshooting

### Problema: "Model not found"

```bash
# Verificar modelos instalados
ollama list

# Instalar modelo faltante
ollama pull qwen2.5:7b
```

### Problema: "Schema validation failed"

```bash
# Verificar schemas presentes
ls -la config/schemas/

# Debería mostrar:
# extractor_v1.json
# planner_v1.json
# response_v1.json
```

### Problema: Tests fallan

```bash
# Reinstalar dependencias
pip install -r requirements.txt --force-reinstall

# Limpiar cache
find . -type d -name __pycache__ -exec rm -rf {} +
pytest --cache-clear
```

---

## 📚 Documentación Completa

- **[RESUMEN_FINAL.md](RESUMEN_FINAL.md)** - Resumen ejecutivo
- **[INTEGRACION_SLM.md](INTEGRACION_SLM.md)** - Guía de integración
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Checklist de deploy
- **[ARQUITECTURA_SLM.md](ARQUITECTURA_SLM.md)** - Arquitectura técnica
- **[ESTADO_FINAL_INTEGRACION.md](ESTADO_FINAL_INTEGRACION.md)** - Estado final

---

## 🚀 Deploy a Staging

```bash
# 1. Build
docker-compose -f docker-compose.staging.yml build

# 2. Deploy
docker-compose -f docker-compose.staging.yml up -d

# 3. Verificar
curl http://staging.pulpoai.com/webhook/pulpo/twilio/health

# 4. Smoke tests
API_URL=http://staging.pulpoai.com ./tests/smoke/smoke_test.sh
```

---

## 📞 Ayuda

- **Slack**: #pulpo-slm-pipeline
- **Docs**: `/docs` folder
- **Issues**: GitHub Issues

---

**Última actualización:** 15 Enero 2025  
**Estado:** ✅ READY
