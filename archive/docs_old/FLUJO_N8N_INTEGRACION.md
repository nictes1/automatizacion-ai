# 🔄 Flujo Real con n8n - Integración SLM Pipeline

Documentación del flujo actual con n8n y cómo integrar el SLM Pipeline.

---

## 📊 Arquitectura Actual

```
┌──────────────────────────────────────────────────────────────────┐
│                         TWILIO (WhatsApp)                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                            n8n WORKFLOW                           │
│                                                                   │
│  1️⃣  Webhook Inbound                                             │
│     • Recibe POST de Twilio                                      │
│     • Form data: From, To, Body, MessageSid, etc.               │
│                                                                   │
│  2️⃣  Normalize Input                                             │
│     • Extrae: user_phone, text, wamid, to_phone                 │
│     • Limpia y normaliza números                                 │
│                                                                   │
│  3️⃣  Resolve Channel                                             │
│     • DB query: workspace_id por to_phone                        │
│     • Obtiene display_phone, business_name                       │
│                                                                   │
│  4️⃣  Load Conversation State                                     │
│     • DB query: estado conversación                              │
│     • Parsea: greeted, slots, objective, last_action            │
│                                                                   │
│  5️⃣  Prepare Orchestrator Payload                                │
│     • Arma JSON con todos los datos                              │
│     • conversation_id, vertical, user_input, slots, etc.        │
│                                                                   │
│  6️⃣  Call Orchestrator (HTTP POST)                               │
│     • POST http://orchestrator:8000/orchestrator/decide         │
│     • Header: X-Workspace-Id                                     │
│     • Body: payload preparado                                    │
│                                                                   │
│  7️⃣  Parse Intent                                                │
│     • Lee response.next_action                                   │
│     • Decide si hay tool_calls                                   │
│                                                                   │
│  8️⃣  Execute Action (si hay tool_calls)                          │
│     • Loop por cada tool_call                                    │
│     • Ejecuta: book_appointment, get_services, etc.             │
│     • Persist en DB                                              │
│                                                                   │
│  9️⃣  Prepare Response                                            │
│     • Extrae response.assistant                                  │
│     • Formatea para Twilio                                       │
│                                                                   │
│  🔟 Send Twilio                                                  │
│     • POST a Twilio API                                          │
│     • To: user_phone, From: display_phone, Body: message        │
│                                                                   │
│  1️⃣1️⃣ Persist Response                                          │
│     • Guarda mensaje en DB                                       │
│     • Actualiza estado de conversación                           │
│                                                                   │
│  1️⃣2️⃣ Final Response                                            │
│     • Responde 200 OK a Twilio                                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR SERVICE                            │
│                  (FastAPI /orchestrator/decide)                   │
│                                                                   │
│  Actualmente usa: orchestrator_service.py (Legacy)               │
│                                                                   │
│  Con SLM Pipeline:                                                │
│  ├─ Feature flag: ENABLE_SLM_PIPELINE                            │
│  ├─ Canary: SLM_CANARY_PERCENT                                   │
│  ├─ Routing: SLM vs Legacy                                       │
│  └─ Response compatible con n8n                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔌 Integración SLM Pipeline

### Cambios Mínimos Necesarios

El SLM Pipeline se integra **sin cambiar n8n**. Solo modificamos el endpoint `/orchestrator/decide`:

#### 1. Endpoint actual (api/orchestrator.py)

```python
@router.post("/decide")
async def decide(request: DecideRequest, x_workspace_id: str = Header(None)):
    """
    n8n llama a este endpoint con:
    {
      "conversation_id": "conv-123",
      "vertical": "servicios",
      "user_input": "Quiero turno mañana 15hs",
      "greeted": true,
      "slots": {"service_type": "Corte"},
      "objective": "book",
      "last_action": "gather_info"
    }
    """
    
    # Crear snapshot
    snapshot = ConversationSnapshot(
        conversation_id=request.conversation_id,
        vertical=request.vertical,
        user_input=request.user_input,
        workspace_id=x_workspace_id,
        greeted=request.greeted,
        slots=request.slots,
        objective=request.objective
    )
    
    # ANTES: Legacy orchestrator
    # response = await orchestrator_service.decide(snapshot)
    
    # AHORA: SLM Pipeline con canary
    if ENABLE_SLM_PIPELINE:
        response = await orchestrator_slm_pipeline.decide(snapshot)
    else:
        response = await orchestrator_service.decide(snapshot)
    
    # Response para n8n (sin cambios en formato)
    return DecideResponse(
        assistant=response.assistant,
        next_action=response.next_action.value,
        tool_calls=response.tool_calls,
        slots=response.slots,
        objective=request.objective,
        end=response.end
    )
```

#### 2. Adaptación del Snapshot

El `ConversationSnapshot` que usa el SLM Pipeline necesita algunos campos adicionales que n8n no provee. Los completamos en el endpoint:

```python
# En api/orchestrator.py

# Crear snapshot para SLM Pipeline
from services.tool_manifest import load_tool_manifest
from services.mcp_client import get_mcp_client

snapshot_slm = ConversationSnapshot(
    workspace_id=x_workspace_id,
    conversation_id=request.conversation_id,
    user_message=UserMessage(
        text=request.user_input,
        message_id=f"n8n-{x_request_id}"
    ),
    business_name=await _load_business_name(x_workspace_id),
    tool_manifest=await load_tool_manifest(x_workspace_id, request.vertical),
    mcp_client=await get_mcp_client(x_workspace_id),
    custom_runners={},
    vertical=request.vertical,
    slots=request.slots,
    greeted=request.greeted,
    objective=request.objective
)
```

---

## 📝 Contratos JSON

### Request de n8n → Orchestrator

```json
{
  "conversation_id": "conv-550e8400-e29b-41d4-a716-446655440003",
  "vertical": "servicios",
  "user_input": "Quiero reservar un corte de pelo mañana a las 3pm",
  "greeted": true,
  "slots": {
    "service_type": "Corte de Cabello",
    "preferred_date": "2025-10-16"
  },
  "objective": "book",
  "last_action": "gather_date",
  "attempts_count": 1
}
```

### Response Orchestrator → n8n

```json
{
  "assistant": "¿Te viene bien a las 15:00? Necesito tu nombre y email para confirmar.",
  "next_action": "gather_client_info",
  "tool_calls": [
    {
      "tool": "check_service_availability",
      "args": {
        "workspace_id": "550e8400-e29b-41d4-a716-446655440003",
        "service_type": "Corte de Cabello",
        "date": "2025-10-16"
      }
    }
  ],
  "slots": {
    "service_type": "Corte de Cabello",
    "preferred_date": "2025-10-16",
    "preferred_time": "15:00"
  },
  "objective": "book",
  "end": false,
  "debug": {
    "route": "slm_pipeline",
    "intent": "book",
    "confidence": 0.92,
    "t_total_ms": 850
  }
}
```

---

## 🚀 Plan de Integración

### Fase 1: Preparación (1 día)

**1. Actualizar api/orchestrator.py**
- ✅ Agregar imports de `OrchestratorServiceIntegrated`
- ✅ Agregar feature flags (`ENABLE_SLM_PIPELINE`, `SLM_CANARY_PERCENT`)
- ✅ Agregar field `debug` a `DecideResponse`
- ✅ Documentar flujo con n8n

**2. Crear adapter en api/orchestrator.py**
```python
async def _create_slm_snapshot(
    request: DecideRequest,
    x_workspace_id: str
) -> ConversationSnapshot:
    """
    Convierte DecideRequest (de n8n) a ConversationSnapshot (para SLM Pipeline)
    """
    # Cargar dependencias
    manifest = await load_tool_manifest(x_workspace_id, request.vertical)
    mcp_client = await get_mcp_client(x_workspace_id)
    business_name = await _load_business_name(x_workspace_id)
    
    return ConversationSnapshot(
        workspace_id=x_workspace_id,
        conversation_id=request.conversation_id,
        user_message=UserMessage(
            text=request.user_input,
            message_id=f"n8n-{uuid.uuid4()}"
        ),
        business_name=business_name,
        tool_manifest=manifest,
        mcp_client=mcp_client,
        custom_runners={},
        vertical=request.vertical,
        slots=request.slots,
        greeted=request.greeted,
        objective=request.objective
    )
```

**3. Inicializar orchestrator SLM en startup**
```python
# En services/orchestrator_app.py o main.py

from services.orchestrator_integration import OrchestratorServiceIntegrated
from services.llm_client import get_llm_client

# Startup event
@app.on_event("startup")
async def startup():
    llm_client = get_llm_client()
    
    app.state.orchestrator_slm = OrchestratorServiceIntegrated(
        llm_json_client=llm_client,
        enable_agent_loop=True
    )
    
    logger.info(f"Orchestrator SLM initialized: enabled={app.state.orchestrator_slm.enable_slm_pipeline}")
```

### Fase 2: Testing Local (1 día)

**1. Test unitario del adapter**
```bash
pytest tests/unit/test_orchestrator_n8n_adapter.py -v
```

**2. Test E2E simulando n8n**
```python
# tests/e2e/test_orchestrator_n8n_flow.py

async def test_n8n_to_orchestrator_flow():
    """Simula request de n8n → orchestrator SLM → response"""
    
    # Request simulado de n8n
    request = DecideRequest(
        conversation_id="conv-test-123",
        vertical="servicios",
        user_input="Quiero turno mañana 15hs",
        greeted=True,
        slots={"service_type": "Corte"},
        objective="book"
    )
    
    # Call endpoint
    response = await client.post(
        "/orchestrator/decide",
        json=request.dict(),
        headers={"X-Workspace-Id": "ws-test-123"}
    )
    
    # Validar response
    assert response.status_code == 200
    data = response.json()
    assert "assistant" in data
    assert "tool_calls" in data
    assert "slots" in data
    assert data["debug"]["route"] in ["slm_pipeline", "legacy"]
```

### Fase 3: Staging (2 días)

**1. Deploy a staging**
```bash
# Configurar
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=0  # 100% SLM en staging

# Deploy
docker-compose -f docker-compose.staging.yml up -d orchestrator
```

**2. Validar con n8n staging**
- Enviar mensaje WhatsApp a número de staging
- Ver logs de n8n: webhook → orchestrator → response
- Ver logs de orchestrator: SLM pipeline execution
- Verificar respuesta recibida en WhatsApp

**3. Métricas**
```bash
# Ver telemetría
tail -f logs/orchestrator.log | grep TELEMETRY

# Latencias
grep "t_total_ms" logs/orchestrator.log | awk '{print $NF}' | sort -n

# Route distribution
grep "route=" logs/orchestrator.log | awk -F'route=' '{print $2}' | awk '{print $1}' | sort | uniq -c
```

### Fase 4: Canary 10% (3-5 días)

**1. Deploy canary**
```bash
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=10  # 10% SLM, 90% Legacy

docker-compose -f docker-compose.prod.yml up -d orchestrator
```

**2. Monitoreo**
- Dashboard Grafana con métricas por route
- Alertas si latencia > p90 o error rate > 2%
- Comparar SLM vs Legacy (accuracy, latencia, UX)

**3. Criterios de éxito**
- ✅ p90 latency < 1500ms
- ✅ Error rate < 1%
- ✅ No quejas de usuarios
- ✅ Tool execution rate similar o mejor que legacy

### Fase 5: Full Rollout (1 semana)

**1. Escalar gradualmente**
```bash
# Día 1-2: 10%
export SLM_CANARY_PERCENT=10

# Día 3-4: 50%
export SLM_CANARY_PERCENT=50

# Día 5+: 100%
export SLM_CANARY_PERCENT=0  # 0 = 100% SLM
```

**2. Monitoreo continuo**
- Métricas diarias
- Feedback de usuarios
- Ajustes de prompts si es necesario

---

## 🔧 Troubleshooting

### Problema: "No workspace found"

**Síntoma:**
```
ERROR [WEBHOOK] No workspace found for from=whatsapp:+5491112345678
```

**Causa:** n8n no pudo resolver workspace_id desde to_phone

**Solución:**
```sql
-- Verificar mapping en DB
SELECT workspace_id, display_phone FROM pulpo.channels WHERE display_phone = '+14155238886';
```

### Problema: "Tool manifest not loaded"

**Síntoma:**
```
ERROR [ORCHESTRATOR] tool_manifest is None
```

**Causa:** No se cargó el manifest para el workspace

**Solución:**
```python
# Verificar carga de manifest
manifest = await load_tool_manifest(workspace_id, "servicios")
assert manifest is not None
assert len(manifest.tools) > 0
```

### Problema: "Response format incompatible"

**Síntoma:**
n8n falla al parsear response del orchestrator

**Causa:** Campo faltante o tipo incorrecto en DecideResponse

**Solución:**
```python
# Asegurar todos los campos requeridos
return DecideResponse(
    assistant=response.assistant or "Error",
    next_action=response.next_action.value if hasattr(response.next_action, 'value') else "answer",
    tool_calls=response.tool_calls or [],
    slots=response.slots or {},
    objective=request.objective,
    end=response.end or False
)
```

---

## 📚 Referencias

- **n8n workflow**: `n8n/n8n-workflow.json`
- **Orchestrator API**: `api/orchestrator.py`
- **SLM Pipeline**: `services/orchestrator_slm_pipeline.py`
- **Integration**: `services/orchestrator_integration.py`

---

**Última actualización:** 16 Enero 2025  
**Estado:** ✅ DOCUMENTADO - LISTO PARA INTEGRACIÓN




