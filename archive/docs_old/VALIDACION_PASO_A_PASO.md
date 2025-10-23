# 🧪 Validación Paso a Paso - Integración n8n

Guía para validar la integración de forma incremental.

---

## 📋 Estrategia de Validación

**Paso 1**: Validar contrato n8n con Legacy 100% (aislar variables)  
**Paso 2**: Activar SLM Pipeline canary 10% (validar integración)  
**Paso 3**: Escalar gradualmente (50% → 100%)

---

## 🔹 PASO 1: Validar Legacy (Contrato n8n)

### Objetivo
Verificar que el nuevo formato de API funciona perfectamente con Legacy, **antes** de introducir SLM Pipeline.

### Config

```bash
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0
```

### Tests Manuales

**1. Saludo**
```bash
curl -s -X POST "http://localhost:8000/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: 2025-01-16T10:00:00Z-SM001" \
  -d @tests/fixtures/request_saludo.json | jq
```

**Validar:**
- ✅ `assistant.text` presente (< 200 chars)
- ✅ `tool_calls` es array (vacío o con tools)
- ✅ `patch.slots` existe (dict)
- ✅ `telemetry.route` = "legacy"
- ✅ `telemetry.total_ms` < 2000

**2. Consulta precio**
```bash
curl -s -X POST "http://localhost:8000/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: 2025-01-16T10:01:00Z-SM002" \
  -d @tests/fixtures/request_precio.json | jq
```

**Validar:**
- ✅ `assistant.text` menciona precio
- ✅ `tool_calls` puede contener `get_available_services`
- ✅ Response < 2s

**3. Reserva**
```bash
curl -s -X POST "http://localhost:8000/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: 2025-01-16T10:02:00Z-SM003" \
  -d @tests/fixtures/request_reserva.json | jq
```

**Validar:**
- ✅ `assistant.text` pide dato faltante (nombre/email/servicio)
- ✅ `patch.slots` contiene slots extraídos
- ✅ `tool_calls` puede estar vacío (si faltan datos)

### Tests Automatizados

```bash
# Con Legacy forzado
export ENABLE_SLM_PIPELINE=false
./tests/smoke/test_n8n_contract.sh
```

**Criterios de éxito:**
- ✅ 100% tests passing
- ✅ Latencia p90 < 1500ms
- ✅ Sin errores 500
- ✅ Response format compatible con n8n

### Checklist Paso 1

- [ ] Tests manuales (saludo, precio, reserva) funcionan
- [ ] Tests automatizados pasan
- [ ] Formato de response es exacto (n8n lo puede parsear)
- [ ] Logs muestran `route=legacy`
- [ ] No hay errores en logs

---

## 🔹 PASO 2: SLM Pipeline Canary 10%

### Objetivo
Activar SLM Pipeline para 10% del tráfico y validar que funciona igual o mejor que Legacy.

### Config

```bash
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=10  # 10% SLM, 90% Legacy
```

### Implementación Previa

**1. Implementar `_decide_with_slm_pipeline()` en api/orchestrator.py:**

Ver código completo en siguiente sección.

**2. Inicializar singletons en startup:**

```python
# En services/orchestrator_app.py o main.py

from services.orchestrator_integration import OrchestratorServiceIntegrated
from services.llm_client import get_llm_client

@app.on_event("startup")
async def startup():
    # LLM client
    llm_client = get_llm_client()
    
    # SLM Pipeline
    app.state.orchestrator_slm = OrchestratorServiceIntegrated(
        llm_json_client=llm_client,
        enable_agent_loop=True
    )
    
    logger.info(f"SLM Pipeline initialized: enabled={app.state.orchestrator_slm.enable_slm_pipeline}")
```

### Tests con Canary

**Ejecutar múltiples requests:**

```bash
# Ejecutar 20 requests → ~2 deberían ir a SLM
for i in {1..20}; do
  curl -s -X POST "http://localhost:8000/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: wa-test-$i" \
    -H "X-Request-Id: 2025-01-16T10:00:$i-SM$i" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route'
done | sort | uniq -c
```

**Output esperado:**
```
     18 legacy
      2 slm_pipeline
```

### Métricas a Observar

**En logs:**
```bash
# Distribución de routes
grep "ROUTING" logs/orchestrator.log | awk '{print $2}' | sort | uniq -c

# Latencias
grep "total_ms" logs/orchestrator.log | jq .telemetry.total_ms | sort -n

# Errores
grep "ERROR" logs/orchestrator.log | wc -l
```

**Métricas clave:**
- ✅ `slm_pipeline` aparece ~10% del tiempo
- ✅ p90 latency SLM < 1500ms
- ✅ Error rate SLM < 1%
- ✅ Respuestas SLM igual de buenas que Legacy

### Checklist Paso 2

- [ ] `_decide_with_slm_pipeline()` implementado
- [ ] Singletons inicializados en startup
- [ ] Canary 10% activo
- [ ] Logs muestran mix de `route=slm_pipeline` y `route=legacy`
- [ ] Latencia SLM similar o mejor que Legacy
- [ ] Sin errores en SLM Pipeline
- [ ] n8n procesa respuestas de ambos routes sin problemas

---

## 🔹 PASO 3: Escalar Gradualmente

### Fase 1: Canary 50% (Día 1-2)

```bash
export SLM_CANARY_PERCENT=50
systemctl restart orchestrator  # o docker-compose restart
```

**Validar:**
- Distribución 50/50 en logs
- Comparar métricas SLM vs Legacy
- Identificar edge cases donde SLM falla

### Fase 2: Full SLM (Día 3+)

```bash
export SLM_CANARY_PERCENT=0  # 0 = 100% SLM
systemctl restart orchestrator
```

**Validar:**
- 100% tráfico a SLM
- Legacy solo como fallback (en caso de error)
- Monitorear 48hs continuas

### Fase 3: Deprecar Legacy (Semana 2+)

Una vez que SLM esté estable:
- Mantener Legacy solo para rollback
- Documentar lecciones aprendidas
- Ajustar prompts basado en feedback

---

## 🚨 Troubleshooting

### Problema: Legacy no responde con nuevo formato

**Síntoma:**
```json
{
  "detail": "Field required: assistant"
}
```

**Causa:** Adapter Legacy → DecideResponse no funciona

**Solución:**
Verificar `_decide_with_legacy()` en api/orchestrator.py

### Problema: SLM Pipeline falla con 500

**Síntoma:**
```
HTTPException: SLM pipeline no inicializado
```

**Causa:** Singleton no inicializado en startup

**Solución:**
```python
# En startup event
app.state.orchestrator_slm = OrchestratorServiceIntegrated(llm_client)
```

### Problema: Routing no respeta canary %

**Síntoma:** Siempre va a Legacy o siempre a SLM

**Causa:** Hash MD5 no funciona

**Solución:**
```python
# Verificar función _decide_route()
bucket = int(hashlib.md5(conversation_id.encode()).hexdigest(), 16) % 100
```

### Problema: n8n no parsea response

**Síntoma:** n8n workflow falla en "Parse Response"

**Causa:** Campo faltante o tipo incorrecto

**Solución:**
Validar schema con:
```bash
curl ... | jq . > response.json
python -c "
from pydantic import ValidationError
from api.orchestrator import DecideResponse
import json
try:
    DecideResponse(**json.load(open('response.json')))
    print('✅ Valid')
except ValidationError as e:
    print('❌ Invalid:', e)
"
```

---

## 📊 Criterios de Éxito Final

### Paso 1: Legacy ✅

- [x] Contrato n8n funciona 100%
- [x] Tests pasan
- [x] Latencia < 1500ms p90
- [x] Sin errores

### Paso 2: SLM Canary 10% ✅

- [ ] Routing funciona (10% SLM, 90% Legacy)
- [ ] Latencia SLM similar a Legacy
- [ ] Sin errores en SLM
- [ ] n8n procesa ambos routes

### Paso 3: Full Rollout ✅

- [ ] 100% SLM estable
- [ ] Métricas iguales o mejores que Legacy
- [ ] Sin quejas de usuarios
- [ ] Legacy disponible para rollback

---

## 📚 Referencias

- **Código**: `api/orchestrator.py`
- **Contrato**: `CONTRATO_N8N.md`
- **Tests**: `tests/smoke/test_n8n_contract.sh`
- **Fixtures**: `tests/fixtures/*.json`

---

**Última actualización:** 16 Enero 2025  
**Estado:** Paso 1 en progreso




