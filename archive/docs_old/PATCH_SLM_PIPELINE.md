# 🔧 Patch: Integración SLM Pipeline

Este archivo contiene los 2 patches necesarios para integrar el SLM Pipeline en el orquestador.

**Aplicar SOLO después de validar Paso 1 (Legacy 100%) ✅**

---

## 📦 Patch 1: `_decide_with_slm_pipeline()` en `api/orchestrator.py`

### Ubicación
Reemplazar la función `_decide_with_slm_pipeline()` actual (líneas 170-183) con esta implementación completa.

### Código completo

```python
async def _decide_with_slm_pipeline(
    request: DecideRequest,
    workspace_id: str,
    conversation_id: str,
    channel: str
) -> DecideResponse:
    """
    Ejecuta decisión con SLM Pipeline
    
    Convierte DecideRequest (n8n) → Snapshot (SLM) → DecideResponse (n8n)
    
    Pipeline:
    1. Extractor SLM → intent + slots
    2. Planner SLM → tools a ejecutar
    3. Policy → validación
    4. Tool Broker → ejecución
    5. State Reducer → actualización
    6. NLG → respuesta determinística
    """
    from services.orchestrator_slm_pipeline import orchestrator_slm_pipeline
    from services.orchestrator_service import ConversationSnapshot
    import time
    
    t0 = time.time()
    
    try:
        # Convertir DecideRequest → Snapshot (formato interno)
        snapshot = ConversationSnapshot(
            conversation_id=conversation_id,
            vertical=request.context.vertical,
            user_input=request.user_message.text,
            workspace_id=workspace_id,
            greeted=False,
            slots=request.state.slots,
            objective="",  # SLM infiere objective
            last_action=None,
            attempts_count=0
        )
        
        # Ejecutar pipeline SLM
        slm_response = await orchestrator_slm_pipeline.decide(snapshot)
        
        # Convertir response SLM → DecideResponse (n8n)
        # slm_response es un OrchestratorResponse del pipeline
        
        # Extraer telemetría del debug
        debug_info = slm_response.debug or {}
        
        return DecideResponse(
            assistant=AssistantResponseModel(
                text=slm_response.assistant,
                suggested_replies=[]  # Opcional: extraer de context
            ),
            tool_calls=slm_response.tool_calls or [],
            patch=PatchModel(
                slots=slm_response.slots or {},
                slots_to_remove=[],
                cache_invalidation_keys=[]
            ),
            telemetry=TelemetryModel(
                route="slm_pipeline",
                extractor_ms=debug_info.get("t_extract_ms", 0),
                planner_ms=debug_info.get("t_plan_ms", 0),
                policy_ms=debug_info.get("t_policy_ms", 0),
                broker_ms=debug_info.get("t_broker_ms", 0),
                reducer_ms=debug_info.get("t_reduce_ms", 0),
                nlg_ms=debug_info.get("t_nlg_ms", 0),
                total_ms=int((time.time() - t0) * 1000),
                intent=debug_info.get("intent"),
                confidence=debug_info.get("confidence")
            )
        )
    
    except Exception as e:
        logger.exception(f"[SLM_PIPELINE_ERROR] workspace={workspace_id} error={e}")
        
        # Fallback a legacy en caso de error
        logger.warning(f"[SLM_PIPELINE] Error, falling back to legacy")
        return await _decide_with_legacy(request, workspace_id, conversation_id)
```

### Dónde pegar

Reemplazar desde la línea 170 hasta la línea 183 en `api/orchestrator.py`.

**Antes**:
```python
async def _decide_with_slm_pipeline(
    request: DecideRequest,
    workspace_id: str,
    conversation_id: str,
    channel: str
) -> DecideResponse:
    """
    Ejecuta decisión con SLM Pipeline
    
    TODO: Implementar una vez que tengamos orchestrator_slm_pipeline configurado
    """
    # TODO: Implementar
    logger.warning(f"[SLM_PIPELINE] Not yet implemented, falling back to legacy")
    return await _decide_with_legacy(request, workspace_id, conversation_id)
```

**Después**: (usar el código completo de arriba)

---

## 🚀 Patch 2: Inicialización de Singletons en `main.py`

### Objetivo
Inicializar `orchestrator_slm_pipeline` como singleton al startup para que esté disponible en `api/orchestrator.py`.

### Código a agregar

**Ubicación**: Después de la línea 98 (dentro de la función `lifespan`, justo después de `await validate_dependencies()`)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle de la aplicación"""
    # Startup
    logger.info("🚀 Starting PulpoAI application...")

    # Validar dependencias (FAIL-FAST)
    await validate_dependencies()

    # ========================================
    # NUEVO: Inicializar Singletons SLM Pipeline
    # ========================================
    enable_slm = os.getenv("ENABLE_SLM_PIPELINE", "false").lower() == "true"
    
    if enable_slm:
        logger.info("🧠 Inicializando SLM Pipeline...")
        
        try:
            # 1. LLM Client
            from services.llm_client import get_llm_client
            llm_client = get_llm_client()
            
            # 2. Tool Broker
            from services.tool_broker import get_tool_broker
            tool_broker = get_tool_broker()
            
            # 3. Policy Engine
            from services.policy_engine import PolicyEngine
            policy_engine = PolicyEngine()
            
            # 4. State Reducer
            from services.state_reducer import StateReducer
            state_reducer = StateReducer()
            
            # 5. Orchestrator SLM Pipeline (singleton)
            from services.orchestrator_slm_pipeline import OrchestratorSLMPipeline
            from services import orchestrator_slm_pipeline as slm_module
            
            slm_module.orchestrator_slm_pipeline = OrchestratorSLMPipeline(
                llm_client=llm_client,
                tool_broker=tool_broker,
                policy_engine=policy_engine,
                state_reducer=state_reducer,
                enable_slm_pipeline=True
            )
            
            logger.info("✅ SLM Pipeline inicializado correctamente")
        
        except Exception as e:
            logger.error(f"❌ Error inicializando SLM Pipeline: {e}")
            logger.error("⚠️  El sistema continuará con Legacy solamente")
            # No hacer sys.exit() para permitir fallback a Legacy
    
    else:
        logger.info("ℹ️  SLM Pipeline deshabilitado (ENABLE_SLM_PIPELINE=false)")

    yield

    # Shutdown
    logger.info("🛑 Shutting down PulpoAI application...")

    # Aquí podrías cerrar conexiones, limpiar recursos, etc.
```

### Imports adicionales a agregar

**Ubicación**: Al inicio de `main.py`, junto con los otros imports (después de la línea 15)

```python
import os
```

(Probablemente ya exista, verificar)

---

## 📝 Verificación Post-Patch

### 1. Verificar sintaxis Python

```bash
python -m py_compile api/orchestrator.py
python -m py_compile main.py
```

Si hay errores de sintaxis, corregir antes de continuar.

### 2. Verificar imports

```bash
# Verificar que los módulos SLM existan
ls -lh services/orchestrator_slm_pipeline.py
ls -lh services/slm/extractor.py
ls -lh services/slm/planner.py
ls -lh services/response/simple_nlg.py
```

Si falta alguno, ver `INTEGRACION_SLM.md`.

### 3. Rebuild del contenedor

```bash
docker compose build pulpo-app
```

Esperado: Build exitoso sin errores.

### 4. Verificar logs de startup

```bash
docker compose up -d pulpo-app
docker compose logs pulpo-app | grep -E "SLM Pipeline|FAIL"
```

**Con `ENABLE_SLM_PIPELINE=true`**:
```
🧠 Inicializando SLM Pipeline...
✅ SLM Pipeline inicializado correctamente
[ORCHESTRATOR] SLM Pipeline: enabled=true, canary=10%
```

**Con `ENABLE_SLM_PIPELINE=false`**:
```
ℹ️  SLM Pipeline deshabilitado (ENABLE_SLM_PIPELINE=false)
[ORCHESTRATOR] SLM Pipeline: enabled=false, canary=0%
```

---

## 🧪 Test Rápido Post-Patch

Probar un request simple para verificar que el routing funciona:

```bash
# Test Legacy (ENABLE_SLM_PIPELINE=false)
curl -s -X POST "http://localhost:8000/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Conversation-Id: wa-test-legacy" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route'

# Esperado: "legacy"
```

```bash
# Test SLM (ENABLE_SLM_PIPELINE=true, forzar con conversation_id específico)
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=100  # Forzar 100% SLM para test

curl -s -X POST "http://localhost:8000/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Conversation-Id: wa-test-slm" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route'

# Esperado: "slm_pipeline"
```

Si ambos funcionan, el patch está correctamente aplicado ✅

---

## ⚠️ Troubleshooting

### Error: `ModuleNotFoundError: No module named 'services.orchestrator_slm_pipeline'`

**Causa**: El módulo no existe o hay un error de sintaxis que impide su importación.

**Solución**:
```bash
# Verificar que existe
ls -lh services/orchestrator_slm_pipeline.py

# Verificar sintaxis
python -m py_compile services/orchestrator_slm_pipeline.py

# Ver error completo
docker compose logs pulpo-app | grep -A 10 "ModuleNotFoundError"
```

### Error: `AttributeError: module 'services.orchestrator_slm_pipeline' has no attribute 'orchestrator_slm_pipeline'`

**Causa**: El singleton no se inicializó correctamente en `main.py`.

**Solución**:
1. Verificar que el código del Patch 2 está presente en `main.py` dentro de `lifespan()`.
2. Verificar que `ENABLE_SLM_PIPELINE=true`.
3. Ver logs de startup para ver si hubo error en la inicialización.

### Error: `ImportError: cannot import name 'OrchestratorSLMPipeline'`

**Causa**: Hay un error de sintaxis en `services/orchestrator_slm_pipeline.py`.

**Solución**:
```bash
python -m py_compile services/orchestrator_slm_pipeline.py
# Corregir errores reportados
```

### Warning: `[SLM_PIPELINE] Not yet implemented, falling back to legacy`

**Causa**: El patch 1 no se aplicó correctamente, sigue usando el placeholder.

**Solución**:
1. Verificar que reemplazaste la función `_decide_with_slm_pipeline()` completa.
2. Rebuild: `docker compose build pulpo-app`
3. Restart: `docker compose up -d pulpo-app`

---

## ✅ Checklist Pre-Activación

Antes de pasar al Paso 3 (Canary 10%):

- [ ] Patch 1 aplicado en `api/orchestrator.py` (función `_decide_with_slm_pipeline()`)
- [ ] Patch 2 aplicado en `main.py` (inicialización de singletons en `lifespan()`)
- [ ] Imports adicionales agregados (si faltaban)
- [ ] `docker compose build pulpo-app` exitoso (sin errores)
- [ ] Logs de startup muestran "✅ SLM Pipeline inicializado correctamente"
- [ ] Test rápido con `ENABLE_SLM_PIPELINE=true` retorna `route=slm_pipeline`

Si todos los checks están ✅, proceder al **Paso 3** del runbook.

---

**Autor**: PulpoAI Team  
**Fecha**: 2025-01-16  
**Versión**: 1.0  




