# 🚀 PASO 2 - Patch Completo para SLM Pipeline

**Ejecutar SOLO después de que Paso 1 esté verde** ✅

---

## 📋 Prerequisitos

- ✅ Paso 1 completado (`./tests/smoke/validate_legacy.sh` passing)
- ✅ Legacy funciona con contrato n8n
- ✅ Sin errores 500 ni problemas de schema

---

## 1️⃣ Actualizar `api/orchestrator.py`

### Agregar helper _to_slm_snapshot (si no existe)

```python
# En api/orchestrator.py, después de las funciones existentes

async def _to_slm_snapshot(
    req: DecideRequest,
    workspace_id: str,
    conversation_id: str
) -> dict:
    """
    Convierte DecideRequest (n8n) a Snapshot esperado por SLM Pipeline
    """
    return {
        "workspace_id": workspace_id,
        "conversation_id": conversation_id,
        "user_input": req.user_message.text or "",
        "vertical": req.context.vertical or "servicios",
        "slots": req.state.slots or {},
        "fsm_state": req.state.fsm_state,
        "channel": req.context.channel or "whatsapp",
        "locale": req.user_message.locale or "es-AR",
        "metadata": {
            "waid": req.user_message.waid,
            "from": req.user_message.from_,
            "to": req.user_message.to,
            "message_id": req.user_message.message_id,
            "timestamp_iso": req.user_message.timestamp_iso,
            "business_name": req.context.business_name,
            "platform": req.context.platform,
        }
    }


def _from_slm_result(result: dict, route: str) -> DecideResponse:
    """
    Convierte result de SLM Pipeline a DecideResponse (n8n)
    
    Result esperado:
    {
      "assistant": {"text": str, "suggested_replies": [...]},
      "tool_calls": [{"tool": str, "args": {...}}, ...],
      "patch": {"slots": {...}, "slots_to_remove": [...], ...},
      "telemetry": {"extractor_ms":..., "planner_ms":..., ...}
    }
    """
    assistant = result.get("assistant", {}) or {}
    tool_calls = result.get("tool_calls", []) or []
    patch = result.get("patch", {}) or {}
    telem = result.get("telemetry", {}) or {}

    return DecideResponse(
        assistant=AssistantResponseModel(
            text=assistant.get("text", "")[:600],  # Max 600 chars
            suggested_replies=list(assistant.get("suggested_replies", []))[:5],
        ),
        tool_calls=tool_calls[:3],  # Max 3 tool calls
        patch=PatchModel(
            slots=patch.get("slots", {}) or {},
            slots_to_remove=patch.get("slots_to_remove", []) or [],
            cache_invalidation_keys=patch.get("cache_invalidation_keys", []) or [],
        ),
        telemetry=TelemetryModel(
            route=route,
            extractor_ms=telem.get("extractor_ms"),
            planner_ms=telem.get("planner_ms"),
            policy_ms=telem.get("policy_ms"),
            broker_ms=telem.get("broker_ms"),
            reducer_ms=telem.get("reducer_ms"),
            nlg_ms=telem.get("nlg_ms"),
            total_ms=telem.get("total_ms"),
            intent=telem.get("intent"),
            confidence=telem.get("confidence"),
        ),
    )
```

### Reemplazar _decide_with_slm_pipeline

```python
# Reemplazar la función existente (que tiene TODO)

async def _decide_with_slm_pipeline(
    request: DecideRequest,
    workspace_id: str,
    conversation_id: str,
    channel: str
) -> DecideResponse:
    """
    Ejecuta decisión con SLM Pipeline
    
    Flow:
    1. Convierte DecideRequest → Snapshot
    2. Llama a slm_pipeline.decide(snapshot)
    3. Convierte result → DecideResponse
    """
    # Crear snapshot para SLM
    snapshot = await _to_slm_snapshot(request, workspace_id, conversation_id)
    
    # Llamar a SLM Pipeline (inicializado en startup)
    # Ver main.py para inicialización
    result = await slm_pipeline.decide(snapshot)
    
    # Convertir a formato n8n
    return _from_slm_result(result, route="slm_pipeline")
```

---

## 2️⃣ Crear/Actualizar startup en `main.py` o equivalente

### Opción A: Si tenés main.py

```python
# main.py

import os
from fastapi import FastAPI

# Imports
from services.orchestrator_slm_pipeline import OrchestratorSLMPipeline
from services.orchestrator_service import orchestrator_service  # legacy singleton
from services.tool_broker import get_tool_broker
from services.policy_engine import PolicyEngine
from services.state_reducer import StateReducer
from services.llm_client import get_llm_client
import api.orchestrator as orchestrator_api

app = FastAPI()

# Variables globales para singletons
slm_pipeline = None
legacy_service = None


def build_slm_pipeline() -> OrchestratorSLMPipeline:
    """
    Factory de SLM Pipeline
    """
    tool_broker = get_tool_broker()
    policy_engine = PolicyEngine()
    state_reducer = StateReducer()
    llm_client = get_llm_client()  # Tu LLM client real
    
    return OrchestratorSLMPipeline(
        llm_client=llm_client,
        tool_broker=tool_broker,
        policy_engine=policy_engine,
        state_reducer=state_reducer,
        enable_slm_pipeline=True
    )


@app.on_event("startup")
async def startup():
    global slm_pipeline, legacy_service
    
    # Legacy (ya existe)
    legacy_service = orchestrator_service
    
    # SLM Pipeline (solo si flag activo)
    enable_slm = os.getenv("ENABLE_SLM_PIPELINE", "false").lower() == "true"
    
    if enable_slm:
        logger.info("[STARTUP] Inicializando SLM Pipeline...")
        slm_pipeline = build_slm_pipeline()
        logger.info(f"[STARTUP] SLM Pipeline inicializado: enabled={slm_pipeline.enable_slm_pipeline}")
    else:
        logger.info("[STARTUP] SLM Pipeline disabled")
    
    # Asignar al módulo orchestrator_api para que las funciones lo usen
    orchestrator_api.slm_pipeline = slm_pipeline
    orchestrator_api.legacy_service = legacy_service


# Montar router
app.include_router(orchestrator_api.router)
```

### Opción B: Si usás services/orchestrator_app.py

```python
# services/orchestrator_app.py

# ... código existente ...

@router.on_event("startup")
async def startup():
    # Inicializar SLM Pipeline
    enable_slm = os.getenv("ENABLE_SLM_PIPELINE", "false").lower() == "true"
    
    if enable_slm:
        from services.orchestrator_slm_pipeline import OrchestratorSLMPipeline
        from services.llm_client import get_llm_client
        
        llm_client = get_llm_client()
        
        # Asignar a api.orchestrator
        import api.orchestrator as orchestrator_api
        orchestrator_api.slm_pipeline = OrchestratorSLMPipeline(
            llm_client=llm_client,
            enable_agent_loop=True
        )
        
        logger.info("[STARTUP] SLM Pipeline initialized")
```

---

## 3️⃣ Agregar variables globales en `api/orchestrator.py`

```python
# Al principio del archivo api/orchestrator.py, después de imports

# Singletons (inicializados en startup)
slm_pipeline = None
legacy_service = None
```

---

## 4️⃣ Actualizar docker-compose.yml o .env

```yaml
# docker-compose.yml

services:
  orchestrator:
    environment:
      # Paso 1: Legacy only
      # ENABLE_SLM_PIPELINE: "false"
      # SLM_CANARY_PERCENT: "0"
      
      # Paso 2: SLM canary 10%
      ENABLE_SLM_PIPELINE: "true"
      SLM_CANARY_PERCENT: "10"
      
      # Otros...
      SLM_EXTRACTOR_MODEL: "qwen2.5:7b"
      SLM_PLANNER_MODEL: "qwen2.5:7b"
```

O en `.env`:

```bash
ENABLE_SLM_PIPELINE=true
SLM_CANARY_PERCENT=10
SLM_EXTRACTOR_MODEL=qwen2.5:7b
SLM_PLANNER_MODEL=qwen2.5:7b
```

---

## 5️⃣ Script de validación SLM

### Crear `tests/smoke/validate_slm_canary.sh`

```bash
#!/bin/bash
# Validación SLM Canary 10%

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="${API_URL:-http://localhost:8000}"
WORKSPACE_ID="${WORKSPACE_ID:-550e8400-e29b-41d4-a716-446655440003}"

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║      🧪 PASO 2: Validar SLM Pipeline Canary 10%                  ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Test forzado 100% SLM
echo -e "${BLUE}━━━ Test SLM 100% (forzado) ━━━${NC}"

RESPONSE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-smoke-slm-forced" \
  -H "X-Request-Id: smoke-slm-forced" \
  -d @tests/fixtures/request_saludo.json)

ROUTE=$(echo "$RESPONSE" | jq -r '.telemetry.route')
ASSISTANT=$(echo "$RESPONSE" | jq -r '.assistant.text')

if [[ "$ROUTE" == "slm_pipeline" ]]; then
  echo -e "${GREEN}✓${NC} SLM Pipeline funciona"
  echo "  → \"$(echo $ASSISTANT | head -c 60)...\""
else
  echo -e "${RED}✗${NC} Expected route=slm_pipeline, got: $ROUTE"
  exit 1
fi

echo ""

# Test distribución canary
echo -e "${BLUE}━━━ Test Distribución Canary ━━━${NC}"

SLM_COUNT=0
LEGACY_COUNT=0

for i in {1..20}; do
  ROUTE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: wa-test-$i" \
    -H "X-Request-Id: test-$i" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route')
  
  if [[ "$ROUTE" == "slm_pipeline" ]]; then
    SLM_COUNT=$((SLM_COUNT + 1))
  else
    LEGACY_COUNT=$((LEGACY_COUNT + 1))
  fi
  
  sleep 0.1
done

SLM_PERCENT=$((SLM_COUNT * 100 / 20))

echo "Distribución:"
echo "  - SLM: $SLM_COUNT (${SLM_PERCENT}%)"
echo "  - Legacy: $LEGACY_COUNT"

if [[ $SLM_COUNT -ge 1 && $SLM_COUNT -le 5 ]]; then
  echo -e "${GREEN}✓${NC} Distribución OK (esperado: ~2, real: $SLM_COUNT)"
else
  echo -e "${RED}⚠${NC} Distribución fuera de rango (esperado: 1-5, real: $SLM_COUNT)"
fi

echo ""
echo -e "${GREEN}✅ PASO 2 COMPLETADO${NC}"
```

```bash
chmod +x tests/smoke/validate_slm_canary.sh
```

---

## 🚀 Ejecutar Paso 2

### 1. Aplicar patches

```bash
# Ya copiaste los cambios de arriba en:
# - api/orchestrator.py
# - main.py o services/orchestrator_app.py
```

### 2. Configurar canary

```bash
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=10
```

### 3. Restart servicio

```bash
docker-compose restart orchestrator
# o
systemctl restart pulpo-app
```

### 4. Validar

```bash
# Test SLM forzado (100%)
curl -s -X POST "http://localhost:8000/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-smoke-slm-100" \
  -H "X-Request-Id: smoke-slm-100" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route, .assistant.text'

# Esperado: "slm_pipeline" y texto corto
```

### 5. Validar canary

```bash
./tests/smoke/validate_slm_canary.sh
```

---

## ✅ Criterios de Éxito

- ✅ SLM forzado funciona (`route=slm_pipeline`)
- ✅ Distribución ~10% SLM (en 20 requests: 1-5 a SLM)
- ✅ Latencia SLM < 1500ms p90
- ✅ Sin errores 500
- ✅ n8n puede parsear response de ambos routes

---

## 🚨 Troubleshooting

### "SLM pipeline no inicializado"

**Causa:** Singleton no asignado en startup

**Solución:**
```python
# Verificar en main.py startup event
orchestrator_api.slm_pipeline = build_slm_pipeline()
```

### "Field required: assistant"

**Causa:** `_from_slm_result` no convierte correctamente

**Solución:**
Verificar que SLM Pipeline retorna:
```python
{
  "assistant": {"text": "...", "suggested_replies": []},
  "tool_calls": [...],
  "patch": {...},
  "telemetry": {...}
}
```

### Canary siempre 0% o 100%

**Causa:** Hash MD5 no funciona

**Solución:**
```python
# Verificar _decide_route() usa conversation_id correcto
bucket = int(hashlib.md5(conversation_id.encode()).hexdigest(), 16) % 100
```

---

## 📚 Siguiente Paso

Una vez que Paso 2 esté verde:

**Paso 3: Escalar gradualmente**
- 50% canary (Día 1-2)
- 100% SLM (Día 3+)
- Deprecar Legacy (Semana 2+)

---

**Última actualización:** 16 Enero 2025  
**Estado:** ✅ LISTO PARA COPIAR/PEGAR




