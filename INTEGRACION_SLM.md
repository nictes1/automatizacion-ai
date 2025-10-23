# 🔌 Guía de Integración - SLM Pipeline

Guía completa para integrar el SLM Pipeline con el orchestrator existente y desplegar a producción con canary deployment.

---

## 📋 Tabla de Contenidos

1. [Feature Flags](#feature-flags)
2. [Integración con Orchestrator](#integración-con-orchestrator)
3. [Webhook Twilio → Snapshot](#webhook-twilio--snapshot)
4. [Canary Deployment](#canary-deployment)
5. [Telemetría y Métricas](#telemetría-y-métricas)
6. [Smoke Tests](#smoke-tests)
7. [Rollout Plan](#rollout-plan)
8. [Troubleshooting](#troubleshooting)

---

## 🚩 Feature Flags

### Variables de Entorno

Agregar a `.env`:

```bash
# SLM Pipeline - Feature Flags
ENABLE_SLM_PIPELINE=true        # Habilitar pipeline SLM
SLM_CANARY_PERCENT=10           # 0-100% (0 = 100% SLM)

# Modelos
SLM_EXTRACTOR_MODEL=qwen2.5:7b
SLM_PLANNER_MODEL=qwen2.5:7b
SLM_RESPONSE_MODEL=phi3:mini

# Thresholds
SLM_CONFIDENCE_THRESHOLD=0.7
SLM_FALLBACK_TO_LLM=true

# Timeouts (ms)
SLM_EXTRACTOR_TIMEOUT_MS=300
SLM_PLANNER_TIMEOUT_MS=300
SLM_BROKER_TIMEOUT_MS=5000
SLM_TOTAL_TIMEOUT_MS=10000
```

### Comportamiento

| `ENABLE_SLM_PIPELINE` | `SLM_CANARY_PERCENT` | Resultado |
|-----------------------|----------------------|-----------|
| `false` | cualquiera | 100% Legacy |
| `true` | `0` | 100% SLM |
| `true` | `10` | 10% SLM, 90% Legacy |
| `true` | `50` | 50% SLM, 50% Legacy |
| `true` | `100` | 100% Legacy |

---

## 🔄 Integración con Orchestrator

### Arquitectura con n8n

El flujo real es:

```
Twilio → n8n webhook → Normaliza → Call Orchestrator (HTTP) → Response → n8n → Twilio
```

**n8n maneja:**
- Webhook de Twilio
- Normalización de datos
- Carga de estado desde DB
- Ejecución de tool_calls
- Envío via Twilio
- Persistencia en DB

**Orchestrator maneja:**
- Clasificación de intent
- Extracción de entidades
- Decisión de tools
- Generación de respuesta

### Paso 1: Actualizar api/orchestrator.py

**Antes (Legacy only):**
```python
@router.post("/decide")
async def decide(request: DecideRequest):
    response = await orchestrator_service.decide(snapshot)
    return DecideResponse(...)
```

**Después (SLM Pipeline + Canary):**
```python
from services.orchestrator_integration import OrchestratorServiceIntegrated

# Feature flags
ENABLE_SLM_PIPELINE = os.getenv("ENABLE_SLM_PIPELINE", "false").lower() == "true"
SLM_CANARY_PERCENT = int(os.getenv("SLM_CANARY_PERCENT", "0"))

@router.post("/decide")
async def decide(request: DecideRequest, x_workspace_id: str = Header(None)):
    # Routing: SLM vs Legacy
    if ENABLE_SLM_PIPELINE:
        response = await orchestrator_slm.decide(snapshot)
    else:
        response = await orchestrator_service.decide(snapshot)
    
    return DecideResponse(...)
```

### Paso 2: Inicializar en FastAPI

```python
# main.py o app.py
from fastapi import FastAPI
from services.orchestrator_integration import OrchestratorServiceIntegrated
from services.llm_client import get_llm_client

app = FastAPI()

@app.on_event("startup")
async def startup():
    llm_client = get_llm_client()
    orchestrator = OrchestratorServiceIntegrated(llm_client)
    
    app.state.orchestrator = orchestrator
    
    print(f"[STARTUP] Orchestrator initialized: SLM={orchestrator.enable_slm_pipeline}")

@app.on_event("shutdown")
async def shutdown():
    # Cleanup si es necesario
    pass
```

### Paso 3: Usar en Routes

```python
from fastapi import APIRouter, Depends, Request

router = APIRouter()

def get_orchestrator(request: Request):
    return request.app.state.orchestrator

@router.post("/chat")
async def chat(
    payload: dict,
    orchestrator = Depends(get_orchestrator)
):
    snapshot = build_snapshot(payload)  # Tu helper
    response = await orchestrator.decide(snapshot)
    
    return {
        "message": response.assistant,
        "debug": response.debug
    }
```

---

## 📨 Webhook Twilio → Snapshot

### Arquitectura

```
Twilio → FastAPI Route → Adapter → Snapshot → Orchestrator → Response → TwiML
```

### Implementación

**1. Registrar routes:**

```python
# main.py
from api.routes import webhook_twilio

app.include_router(webhook_twilio.router)
```

**2. Configurar webhook en Twilio:**

```
URL: https://tu-dominio.com/webhook/pulpo/twilio/wa/inbound
Method: POST
```

**3. Implementar resolvers:**

Editar `api/webhook_adapter.py`:

```python
async def resolve_workspace_by_phone(from_phone: str, to_phone: str) -> Optional[str]:
    """
    Lookup en DB:
    1. Buscar workspace por to_phone (número del negocio)
    2. Fallback a workspace default
    """
    # Normalizar número
    phone = to_phone.replace("whatsapp:", "").replace("+", "")
    
    # Query DB
    workspace = await db.query(
        "SELECT workspace_id FROM workspaces WHERE phone_number = $1",
        phone
    )
    
    if workspace:
        return workspace["workspace_id"]
    
    # Fallback
    return os.getenv("DEFAULT_WORKSPACE_ID")
```

---

## 🎯 Canary Deployment

### Estrategia de Rollout

**Fase 1: Canary 10% (Día 1-2)**
```bash
ENABLE_SLM_PIPELINE=true
SLM_CANARY_PERCENT=10
```

**Métricas a observar:**
- `t_total_ms` p50/p90/p99
- `slm_error_rate` < 1%
- `confidence` promedio > 0.8
- Feedback de usuarios (quejas/elogios)

**Criterios de éxito:**
- ✅ p90 < 1500ms
- ✅ Error rate < 1%
- ✅ No quejas de usuarios
- ✅ Intent accuracy > 90%

---

**Fase 2: Canary 50% (Día 3-4)**
```bash
SLM_CANARY_PERCENT=50
```

**Métricas adicionales:**
- Comparar SLM vs Legacy (latencia, accuracy)
- Identificar edge cases donde SLM falla
- Ajustar prompts si es necesario

---

**Fase 3: Full SLM (Día 5+)**
```bash
SLM_CANARY_PERCENT=0  # 0 = 100% SLM
```

**Post-deployment:**
- Monitorear 48hs continuas
- Mantener Legacy como fallback automático
- Preparar rollback instantáneo si es necesario

---

### Rollback Instantáneo

**Opción 1: Deshabilitar SLM**
```bash
ENABLE_SLM_PIPELINE=false
# Restart no necesario si leés env en cada request
```

**Opción 2: Canary 0%**
```bash
SLM_CANARY_PERCENT=100  # 100% = todo a legacy
```

**Opción 3: Restart con env anterior**
```bash
# Revertir .env y restart
systemctl restart pulpo-api
```

---

## 📊 Telemetría y Métricas

### Log Estructurado

Cada request loguea:

```
TELEMETRY route=slm_pipeline workspace=ws-123 intent=book confidence=0.92 
actions=2 t_extract_ms=180 t_plan_ms=150 t_policy_ms=5 t_broker_ms=450 
t_reduce_ms=10 t_nlg_ms=80 t_total_ms=875
```

### Métricas Clave

| Métrica | Objetivo | Alerta si |
|---------|----------|-----------|
| `t_total_ms` p90 | < 1500ms | > 2000ms |
| `t_total_ms` p50 | < 800ms | > 1200ms |
| `slm_error_rate` | < 1% | > 2% |
| `confidence` avg | > 0.8 | < 0.7 |
| `actions` max | ≤ 3 | > 3 |
| `policy_denied_rate` | < 10% | > 15% |
| `tool_success_rate` | > 95% | < 90% |

### Dashboard Grafana (Queries)

**Latencia p90:**
```promql
histogram_quantile(0.90, 
  rate(orchestrator_latency_ms_bucket[5m])
)
```

**Error rate:**
```promql
rate(orchestrator_errors_total[5m]) 
/ 
rate(orchestrator_requests_total[5m])
```

**SLM vs Legacy:**
```promql
sum by (route) (
  rate(orchestrator_requests_total[5m])
)
```

---

## 🧪 Smoke Tests

### Ejecutar Tests

```bash
cd tests/smoke
./smoke_test.sh
```

**Output esperado:**
```
🧪 PulpoAI SLM Pipeline - Smoke Test
=========================================
API: http://localhost:8000/orchestrator/decide
Workspace: 550e8400-e29b-41d4-a716-446655440003

Ejecutando 6 tests...

[greeting] ✓ intent=greeting actions=0 latency=120ms
  → "Hola! Te ayudo con turnos, precios y horarios. ¿Qué nece..."

[info_hours] ✓ intent=info_hours actions=1 latency=650ms
  → "Nuestros horarios: • Lunes: 09:00-13:00, 14:00-19:00 • M..."

[info_price_generic] ✓ intent=info_price actions=1 latency=680ms
  → "Algunos precios: • Corte de Cabello: $3500–$6000 • Color..."

[info_price_specific] ✓ intent=info_price actions=1 latency=720ms
  → "Precio para Coloración: • Coloración: $8000–$12000..."

[book_incomplete] ✓ intent=book actions=1 latency=800ms
  → "¿Te viene bien un horario entre las 10:00 y 18:00? Decim..."

[book_complete] ✓ intent=book actions=2 latency=1200ms
  → "¡Listo! Tu turno de Corte de Cabello quedó reservado par..."

=========================================
📊 Resultados
=========================================
Passed: 6
Failed: 0
Total: 6

Latencia promedio: 695ms
Latencia total: 4170ms

✓ All tests passed!
```

### Configurar para CI/CD

```yaml
# .github/workflows/smoke-tests.yml
name: Smoke Tests

on: [push, pull_request]

jobs:
  smoke:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Start API
        run: |
          docker-compose up -d api
          sleep 10
      
      - name: Run Smoke Tests
        run: |
          cd tests/smoke
          ./smoke_test.sh
      
      - name: Stop API
        run: docker-compose down
```

---

## 📅 Rollout Plan (2 Semanas)

### Semana 1: Canary + Observación

**Día 1-2: Canary 10%**
- ✅ Deploy con `SLM_CANARY_PERCENT=10`
- ✅ Monitorear métricas cada 2hs
- ✅ Smoke tests cada 6hs
- ✅ Revisar logs de errores

**Día 3-4: Canary 50%**
- ✅ Elevar a `SLM_CANARY_PERCENT=50`
- ✅ Comparar SLM vs Legacy (latencia, accuracy)
- ✅ Identificar edge cases
- ✅ Ajustar prompts si es necesario

**Día 5: Canary 100%**
- ✅ `SLM_CANARY_PERCENT=0` (100% SLM)
- ✅ Monitoreo intensivo 48hs
- ✅ Preparar rollback si es necesario

### Semana 2: Optimización

**Día 6-7: Fine-tuning**
- Ajustar prompts de Extractor/Planner
- Optimizar timeouts
- Reducir latencia de tools lentos

**Día 8-9: Golden Dataset**
- Crear 10 conversaciones golden por intent
- Automatizar tests en CI/CD
- Baseline de métricas

**Día 10: Documentación**
- Actualizar README
- Documentar decisiones arquitectónicas
- Crear runbook de troubleshooting

---

## 🔧 Troubleshooting

### Problema: Alta Latencia (p90 > 2000ms)

**Diagnóstico:**
```bash
# Revisar logs
grep "TELEMETRY" logs/orchestrator.log | grep "t_total_ms" | sort -t= -k11 -n | tail -20
```

**Causas comunes:**
1. **Extractor lento**: `t_extract_ms > 500ms`
   - Solución: Reducir few-shot examples, usar modelo más pequeño
2. **Broker lento**: `t_broker_ms > 1000ms`
   - Solución: Optimizar tools, aumentar timeout, paralelizar
3. **LLM lento**: Modelo muy grande
   - Solución: Cambiar a modelo 3B-7B

---

### Problema: Baja Confidence (<0.7)

**Diagnóstico:**
```bash
grep "confidence=" logs/orchestrator.log | awk -F'confidence=' '{print $2}' | awk '{print $1}' | sort -n
```

**Causas comunes:**
1. **Prompt ambiguo**: Mejorar few-shot examples
2. **Input ruidoso**: Normalizar texto (lowercase, typos)
3. **Modelo pequeño**: Probar modelo más grande

**Solución:**
```python
# Habilitar fallback a LLM grande
SLM_FALLBACK_TO_LLM=true
SLM_CONFIDENCE_THRESHOLD=0.7
```

---

### Problema: Policy Denied Rate Alto (>15%)

**Diagnóstico:**
```bash
grep "policy_denied" logs/orchestrator.log | wc -l
```

**Causas comunes:**
1. **Planner no detecta slots faltantes**: Mejorar prompt
2. **Validaciones muy estrictas**: Relajar Policy
3. **Usuario no provee datos**: Mejorar UX de preguntas

**Solución:**
- Revisar `_build_missing_prompt` en `orchestrator_slm_pipeline.py`
- Hacer preguntas más claras y específicas

---

### Problema: Tool Failures (>5%)

**Diagnóstico:**
```bash
grep "tool_status=failed" logs/tool_broker.log
```

**Causas comunes:**
1. **API externa caída**: Implementar circuit breaker
2. **Timeout muy corto**: Aumentar `SLM_BROKER_TIMEOUT_MS`
3. **Args inválidos**: Validar en Policy antes de ejecutar

**Solución:**
```python
# En PolicyEngine
def validate_tool_args(tool: str, args: dict) -> bool:
    spec = manifest.get_spec(tool)
    # Validar contra spec.args_schema
    return jsonschema.validate(args, spec.args_schema)
```

---

## 📚 Referencias

- [ARQUITECTURA_SLM.md](ARQUITECTURA_SLM.md) - Arquitectura detallada
- [RESUMEN_FINAL.md](RESUMEN_FINAL.md) - Resumen ejecutivo
- [config/schemas/](config/schemas/) - Schemas JSON versionados
- [tests/e2e/](tests/e2e/) - Tests end-to-end

---

## ✅ Checklist Pre-Deploy

- [ ] Variables de entorno configuradas (`.env`)
- [ ] Orchestrator integrado en FastAPI (`main.py`)
- [ ] Webhook Twilio configurado
- [ ] Resolvers implementados (`workspace_resolver`, `manifest_loader`)
- [ ] Smoke tests ejecutados y pasando
- [ ] Dashboard de métricas configurado (Grafana)
- [ ] Alertas configuradas (latencia, error rate)
- [ ] Rollback plan documentado
- [ ] Equipo notificado del deploy

---

**Última actualización:** 15 Enero 2025  
**Responsable:** Equipo PulpoAI  
**Estado:** ✅ READY FOR CANARY DEPLOYMENT
