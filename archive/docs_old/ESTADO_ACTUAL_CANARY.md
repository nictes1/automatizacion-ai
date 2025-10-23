# 📍 Estado Actual: Preparación para Canary Deployment

**Fecha**: 2025-01-16  
**Versión**: v1.0 - Pre-Canary  
**Estado**: ✅ Listo para ejecutar Paso 1 (Validación Legacy)

---

## 🎯 Objetivo

Activar el **SLM Pipeline en canary 10%** de forma controlada y sin riesgo, validando primero el contrato n8n con Legacy.

---

## 📦 Estado de Componentes

### ✅ Componentes SLM (Implementados)

| Componente | Estado | Archivo | Notas |
|------------|--------|---------|-------|
| Extractor SLM | ✅ | `services/slm/extractor.py` | Intent + NER con JSON schema |
| Planner SLM | ✅ | `services/slm/planner.py` | Tool selection con fallback |
| Simple NLG | ✅ | `services/response/simple_nlg.py` | Respuestas determinísticas |
| Orchestrator Pipeline | ✅ | `services/orchestrator_slm_pipeline.py` | Pipeline E2E completo |
| Schema Extractor | ✅ | `config/schemas/extractor_v1.json` | Contrato JSON v1 |
| Schema Planner | ✅ | `config/schemas/planner_v1.json` | Contrato JSON v1 |

### 🔧 Componentes Existentes (Reutilizados)

| Componente | Estado | Archivo | Notas |
|------------|--------|---------|-------|
| Tool Broker | ✅ | `services/tool_broker.py` | Ejecución con retry/CB |
| Policy Engine | ✅ | `services/policy_engine.py` | Validación de reglas |
| State Reducer | ✅ | `services/state_reducer.py` | Aplicación de observaciones |
| Orchestrator Legacy | ✅ | `services/orchestrator_service.py` | Fallback path |

### 🚧 Componentes a Integrar (Pendientes)

| Componente | Estado | Archivo | Acción requerida |
|------------|--------|---------|------------------|
| API Router | 🔧 | `api/orchestrator.py` | Aplicar Patch 1 |
| Startup Logic | 🔧 | `main.py` | Aplicar Patch 2 |

---

## 📋 Documentación Creada

### Runbooks y Guías

1. **`RUNBOOK_ACTIVACION_CANARY.md`** ⭐
   - Paso 1: Validar Legacy 100%
   - Paso 2: Implementar SLM Pipeline
   - Paso 3: Activar Canary 10%
   - Paso 4: Monitoreo en vivo
   - Rollback instantáneo
   - Troubleshooting completo

2. **`PATCH_SLM_PIPELINE.md`** ⭐
   - Patch 1: `_decide_with_slm_pipeline()` en `api/orchestrator.py`
   - Patch 2: Inicialización de singletons en `main.py`
   - Verificaciones post-patch
   - Troubleshooting de errores comunes

3. **`CONTRATO_N8N.md`**
   - Request/Response schemas
   - Ejemplos de cURL
   - Headers requeridos

4. **`FLUJO_N8N_INTEGRACION.md`**
   - Diagrama de flujo completo
   - Responsabilidades de cada componente

5. **`INTEGRACION_SLM.md`**
   - Arquitectura SLM-first
   - Contratos JSON
   - Latency budgets

### Scripts de Validación

1. **`tests/smoke/validate_legacy.sh`** ✅
   - Valida contrato n8n con Legacy 100%
   - 3 tests: saludo, precio, reserva
   - Verifica campos, route, latencia

2. **`tests/smoke/validate_slm_canary.sh`** ✅
   - Valida SLM Pipeline canary 10%
   - Verifica distribución de tráfico
   - Compara latencias SLM vs Legacy

3. **`tests/smoke/test_deterministic_routing.sh`** ✅
   - Verifica que mismo conversation_id → mismo route
   - Valida distribución estadística
   - Re-verifica consistencia

### Fixtures de Test

1. **`tests/fixtures/request_saludo.json`** ✅
2. **`tests/fixtures/request_precio.json`** ✅
3. **`tests/fixtures/request_reserva.json`** ✅

---

## 🚀 Plan de Ejecución (Próximos Pasos)

### Paso 0: Pre-requisitos ✅ COMPLETADO

- [x] Extractor SLM implementado
- [x] Planner SLM implementado
- [x] Simple NLG implementado
- [x] Orchestrator SLM Pipeline implementado
- [x] Schemas JSON v1 definidos
- [x] Runbook completo
- [x] Scripts de validación
- [x] Fixtures de test

### Paso 1: Validar Legacy 100% 🎯 PRÓXIMO

**Ejecutar AHORA**:

```bash
# Configurar feature flags
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0

# Levantar servicio
docker compose up -d pulpo-app

# Validar contrato n8n con Legacy
./tests/smoke/validate_legacy.sh
```

**Éxito esperado**:
- ✅ 3/3 tests OK
- ✅ `route=legacy` en todos
- ✅ Latencia < 2000ms

**Si falla**: Ver sección "Troubleshooting" en `RUNBOOK_ACTIVACION_CANARY.md`

### Paso 2: Implementar SLM Pipeline ⏳ DESPUÉS DEL PASO 1

**SOLO si Paso 1 está verde ✅**

1. Abrir `PATCH_SLM_PIPELINE.md`
2. Aplicar Patch 1 en `api/orchestrator.py`
3. Aplicar Patch 2 en `main.py`
4. Rebuild: `docker compose build pulpo-app`
5. Verificar logs de startup

### Paso 3: Activar Canary 10% ⏳ DESPUÉS DEL PASO 2

**SOLO si Paso 2 está verde ✅**

```bash
# Configurar feature flags
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=10

# Levantar servicio
docker compose up -d pulpo-app

# Validar canary
./tests/smoke/validate_slm_canary.sh
```

### Paso 4: Monitoreo (48hs) ⏳ DESPUÉS DEL PASO 3

```bash
# Ver routing en vivo
docker compose logs -f pulpo-app | grep -E "ROUTING|route="

# Ver telemetría
docker compose logs -f pulpo-app | grep -E "PIPELINE|EXTRACT|PLANNER"

# Distribución de routes
docker compose logs pulpo-app | grep '"route":"' | tail -100 | sort | uniq -c
```

---

## 🎛️ Feature Flags

### Estado Actual

```bash
ENABLE_SLM_PIPELINE=false  # Cambiar a true en Paso 3
SLM_CANARY_PERCENT=0       # Cambiar a 10 en Paso 3
```

### Configuración por Fase

| Fase | `ENABLE_SLM_PIPELINE` | `SLM_CANARY_PERCENT` | Comportamiento |
|------|----------------------|---------------------|----------------|
| Paso 1: Validar Legacy | `false` | `0` | 100% Legacy |
| Paso 3: Canary 10% | `true` | `10` | 10% SLM, 90% Legacy |
| Escalado 50% | `true` | `50` | 50% SLM, 50% Legacy |
| Full SLM | `true` | `0` | 100% SLM |
| Rollback | `false` | `0` | 100% Legacy |

---

## 📊 Métricas a Monitorear

### Métricas Clave

| Métrica | Objetivo | Alerta si |
|---------|----------|-----------|
| SLM Latency p90 | < 1500ms | > 2000ms |
| Legacy Latency p90 | < 1000ms | > 1500ms |
| Error rate | < 1% | > 5% |
| Schema validation fails | < 5% | > 10% |
| Route distribution | ~10% SLM | 0% o > 20% |
| Tool success rate | > 95% | < 90% |

### Logs Críticos

```bash
# Buscar errores
docker compose logs pulpo-app | grep -E "ERROR|EXCEPTION"

# Buscar schema validation fails
docker compose logs pulpo-app | grep "schema_invalid"

# Buscar fallbacks inesperados
docker compose logs pulpo-app | grep "falling back to legacy"
```

---

## 🔥 Rollback

### Rollback Instantáneo (sin rebuild)

```bash
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0
docker compose up -d pulpo-app
```

Vuelve a 100% Legacy en < 10 segundos.

### Cuándo hacer rollback

- Error rate > 5% sostenido
- Latencia p90 > 3000ms sostenida
- Respuestas incorrectas (off-topic, diagnósticos, promesas)
- Schema validation fails > 20%

---

## 🧪 Tests Disponibles

| Test | Comando | Propósito |
|------|---------|-----------|
| Legacy 100% | `./tests/smoke/validate_legacy.sh` | Validar contrato n8n |
| SLM Canary | `./tests/smoke/validate_slm_canary.sh` | Validar distribución + latencias |
| Routing Determinístico | `./tests/smoke/test_deterministic_routing.sh` | Validar consistencia de hash |

---

## 📝 Checklist de Preparación

### Pre-Paso 1

- [x] Servicios críticos levantados (`docker compose ps`)
- [x] Fixtures de test creadas
- [x] Scripts de validación ejecutables
- [x] Runbook completo
- [x] Patches preparados

### Pre-Paso 2

- [ ] Paso 1 exitoso (3/3 tests OK)
- [ ] Patches revisados
- [ ] Backup de `api/orchestrator.py` y `main.py` (opcional)

### Pre-Paso 3

- [ ] Paso 2 exitoso (build OK, startup sin errores)
- [ ] Test rápido con `ENABLE_SLM_PIPELINE=true` funciona
- [ ] Logs de startup muestran "✅ SLM Pipeline inicializado"

---

## 🆘 Soporte

### Si algo falla

1. **Consultar runbook**: `RUNBOOK_ACTIVACION_CANARY.md` → Sección "Troubleshooting"
2. **Ver logs completos**: `docker compose logs pulpo-app | tail -100`
3. **Verificar dependencias**: `docker compose ps` + health checks
4. **Rollback si es crítico**: Feature flags a `false`/`0`

### Archivos de referencia

- **Arquitectura SLM**: `INTEGRACION_SLM.md`
- **Contrato n8n**: `CONTRATO_N8N.md`
- **Flujo completo**: `FLUJO_N8N_INTEGRACION.md`
- **Patches**: `PATCH_SLM_PIPELINE.md`

---

## 🎯 Resumen Ejecutivo

**Estado**: ✅ Todo listo para ejecutar Paso 1

**Próxima acción**: Ejecutar `./tests/smoke/validate_legacy.sh`

**Riesgo**: Bajo (validando Legacy primero, rollback instantáneo disponible)

**Duración estimada**: 
- Paso 1: 5 minutos
- Paso 2: 10 minutos
- Paso 3: 10 minutos
- **Total**: ~25 minutos hasta canary activo

**Confianza**: Alta (código testeado, runbook completo, rollback disponible)

---

**¿Listo para empezar?**

```bash
# EJECUTÁ AHORA:
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0
docker compose up -d pulpo-app
./tests/smoke/validate_legacy.sh
```

**CUANDO PASO 1 ESTÉ VERDE**:
1. Abrir `PATCH_SLM_PIPELINE.md`
2. Copiar/pegar los patches
3. Rebuild + `validate_slm_canary.sh`

---

**Autor**: PulpoAI Team  
**Última actualización**: 2025-01-16  
**Versión**: 1.0  



