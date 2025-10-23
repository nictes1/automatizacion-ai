# 🚀 Runbook: Activación SLM Pipeline Canary

**Objetivo**: Validar el contrato n8n con Legacy y luego activar el SLM Pipeline en canary 10% sin fricción.

---

## 📋 Pre-requisitos

Verificar que los servicios críticos estén levantados:

```bash
docker compose ps
```

Esperado: `pulpo-app`, `postgres`, `redis`, `mcp`, `ollama` en estado `Up`.

Si alguno está caído:

```bash
docker compose up -d
docker compose logs -f pulpo-app
```

---

## 🧪 Paso 1: Validar Legacy 100%

**Objetivo**: Aislar variables. Si el contrato n8n falla con Legacy, sabemos que NO es problema del SLM.

### 1.1. Configurar feature flags para Legacy

```bash
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0
```

### 1.2. Levantar servicio

```bash
docker compose up -d pulpo-app
```

Esperar 5 segundos para que el servicio inicialice.

### 1.3. Ejecutar smoke tests

```bash
chmod +x tests/smoke/validate_legacy.sh
./tests/smoke/validate_legacy.sh
```

### 1.4. Éxito esperado

```
✅ PASO 1 COMPLETADO

Passed: 3
Failed: 0
Total: 3
```

Todos los tests deben tener:
- `route=legacy`
- `assistant.text` presente
- `patch` y `tool_calls` presentes
- Latencia < 2000ms

### 1.5. ¿Qué hacer si falla?

#### Error 404/422 (Request inválido)
```bash
# Revisar fixtures
cat tests/fixtures/request_saludo.json | jq
cat tests/fixtures/request_precio.json | jq
cat tests/fixtures/request_reserva.json | jq

# Verificar endpoint
curl -s http://localhost:8000/health | jq
```

#### Error 500 (Error interno)
```bash
# Ver logs
docker compose logs -f pulpo-app | grep -A 5 -B 5 "ERROR"

# Verificar dependencias
docker compose ps
docker compose logs postgres | tail -20
docker compose logs redis | tail -20
docker compose logs mcp | tail -20
```

#### route ≠ legacy
```bash
# Verificar feature flags
docker compose exec pulpo-app env | grep SLM

# Si está mal, re-exportar y rebuild
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0
docker compose up -d --force-recreate pulpo-app
```

---

## 🔧 Paso 2: Implementar SLM Pipeline

**SOLO EJECUTAR SI PASO 1 ESTÁ VERDE ✅**

### 2.1. Aplicar patch

Abrir el archivo `PATCH_SLM_PIPELINE.md` y aplicar los 2 patches:

1. **Patch 1**: `_decide_with_slm_pipeline()` en `api/orchestrator.py`
2. **Patch 2**: Startup con singletons en `main.py`

Ver detalles completos en `PATCH_SLM_PIPELINE.md`.

### 2.2. Verificar que los archivos existen

```bash
# Verificar módulos SLM
ls -lh services/slm/extractor.py
ls -lh services/slm/planner.py
ls -lh services/orchestrator_slm_pipeline.py
ls -lh services/response/simple_nlg.py

# Verificar schemas
ls -lh config/schemas/extractor_v1.json
ls -lh config/schemas/planner_v1.json
```

Si falta alguno, ver `INTEGRACION_SLM.md` para crearlos.

### 2.3. Rebuild del contenedor

```bash
docker compose build pulpo-app
```

---

## 🐤 Paso 3: Activar SLM Canary 10%

### 3.1. Configurar feature flags

```bash
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=10
```

### 3.2. Levantar servicio

```bash
docker compose up -d pulpo-app
```

Esperar 5 segundos para que el servicio inicialice.

### 3.3. Verificar logs de startup

```bash
docker compose logs pulpo-app | grep "SLM Pipeline"
```

Esperado:
```
[ORCHESTRATOR] SLM Pipeline: enabled=true, canary=10%
[ORCHESTRATOR_SLM] Inicializado con SLM pipeline
```

Si no ves esto, el feature flag no se aplicó correctamente.

### 3.4. Ejecutar smoke tests canary

```bash
chmod +x tests/smoke/validate_slm_canary.sh
./tests/smoke/validate_slm_canary.sh
```

### 3.5. Éxito esperado

```
✅ PASO 2 COMPLETADO

✓ SLM Pipeline funcional
✓ Distribución canary correcta
✓ Latencias aceptables
```

Validaciones:
- Al menos 1 request con `route=slm_pipeline`
- Mayoría (~18/20) con `route=legacy`
- Latencia SLM < 2000ms

---

## 📊 Paso 4: Monitoreo en Vivo

### 4.1. Ver routing en tiempo real

```bash
docker compose logs -f pulpo-app | grep -E "ROUTING|route="
```

Esperado (cada ~10 requests):
```
[ROUTING] route=slm_pipeline workspace=... conv=...
[ROUTING] route=legacy workspace=... conv=...
[ROUTING] route=legacy workspace=... conv=...
...
```

### 4.2. Ver telemetría detallada

```bash
docker compose logs -f pulpo-app | grep -E "PIPELINE|EXTRACT|PLANNER|BROKER"
```

Esperado para SLM:
```
[EXTRACT] intent=greeting, confidence=0.95, slots=0, time=180ms
[PLANNER] actions=1, needs_confirmation=false, time=140ms
[BROKER] executed=1, time=120ms
[PIPELINE] Total: 480ms (extract=180ms, plan=140ms, policy=5ms, broker=120ms, reduce=10ms, nlg=90ms)
```

### 4.3. Comparar distribución de routes

```bash
# Últimos 100 requests
docker compose logs pulpo-app | grep '"route":"' | tail -100 | sort | uniq -c
```

Esperado (~10% SLM):
```
     12 "route":"slm_pipeline"
     88 "route":"legacy"
```

---

## 🔥 Rollback Instantáneo

Si algo sale mal en cualquier momento:

```bash
# Desactivar SLM
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0

# Restart
docker compose up -d pulpo-app

# Verificar
docker compose logs pulpo-app | grep "SLM Pipeline"
# Esperado: enabled=false
```

Esto vuelve 100% a Legacy sin necesidad de rebuild.

---

## 🎯 Señales de Éxito

### ✅ Todo está bien si:
- `route=slm_pipeline` aparece ~10% del tiempo
- Latencia SLM p90 < 1500ms
- `assistant.text` siempre presente (no null)
- `tool_calls` válidos (máximo 3)
- Sin errores 5xx en logs

### ⚠️ Señales de alerta:
- `route=slm_pipeline` nunca aparece → feature flag mal configurado
- Latencia SLM p90 > 2000ms → revisar Ollama/LLM
- Errores `schema_invalid` en logs → revisar prompts Extractor/Planner
- Respuestas muy largas (> 300 chars) → ajustar `simple_nlg`

### 🚨 Rollback inmediato si:
- Error rate > 5%
- Latencia p90 > 3000ms sostenida
- Respuestas incorrectas (diagnósticos, promesas, off-topic)

---

## 📈 Próximos Pasos (Post-Canary)

Después de 48hs con canary 10% estable:

### Escalar a 50%
```bash
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=50
docker compose up -d pulpo-app
```

### Escalar a 100% (Full SLM)
```bash
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=0  # 0 = 100% SLM
docker compose up -d pulpo-app
```

### Deshabilitar Legacy completamente
```bash
# En api/orchestrator.py, eliminar _decide_with_legacy()
# En docker-compose.yml, remover ENABLE_SLM_PIPELINE
```

---

## 🧪 Tests Adicionales (Opcional)

### Test de routing determinístico

Verificar que el mismo `conversation_id` siempre va al mismo route:

```bash
./tests/smoke/test_deterministic_routing.sh
```

### Test de stress

```bash
# 100 requests concurrentes
ab -n 100 -c 10 -T 'application/json' \
  -p tests/fixtures/request_saludo.json \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-stress-test" \
  http://localhost:8000/orchestrator/decide
```

---

## 📝 Checklist Final

Antes de considerar completada la activación:

- [ ] Paso 1: Legacy 100% validado (3/3 tests OK)
- [ ] Paso 2: Patch SLM aplicado y build exitoso
- [ ] Paso 3: Canary 10% validado (distribución OK, latencias OK)
- [ ] Paso 4: Monitoreo activo (logs limpios, sin errores)
- [ ] Rollback test (desactivar SLM y volver a activar funciona)
- [ ] Documentación actualizada (RESUMEN_FINAL.md)

---

## 🆘 Troubleshooting Rápido

| Problema | Causa probable | Solución |
|----------|----------------|----------|
| `route` siempre `legacy` | Feature flag no se lee | Verificar env vars, rebuild container |
| `route` siempre `slm_pipeline` | `SLM_CANARY_PERCENT=0` | Cambiar a 10 |
| Error `SLM pipeline no inicializado` | Startup falló | Ver logs de startup, verificar schemas |
| Latencia alta (> 3s) | Ollama lento / modelo no cargado | `docker compose logs ollama`, pre-cargar modelo |
| Schema validation fails | Prompt devuelve JSON inválido | Ver logs `[EXTRACT]` o `[PLANNER]`, revisar few-shot |
| PII en logs | `_redact_pii` no aplicado | Verificar `orchestrator_slm_pipeline.py:339` |

---

**Autor**: PulpoAI Team  
**Fecha**: 2025-01-16  
**Versión**: 1.0  




