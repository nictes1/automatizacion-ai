# ⚡ Quick Start: Activación Canary en 3 Pasos

**Tiempo estimado**: 25 minutos  
**Riesgo**: Bajo (rollback instantáneo disponible)

---

## 🚦 Paso 1: Validar Legacy (5 min)

```bash
# Configurar Legacy 100%
./scripts/set_canary.sh legacy

# Validar contrato n8n
./tests/smoke/validate_legacy.sh
```

**Esperado**: ✅ `PASO 1 COMPLETADO` - `Passed: 3, Failed: 0`

**Si falla**: Ver `RUNBOOK_ACTIVACION_CANARY.md` → Sección "1.5. ¿Qué hacer si falla?"

---

## 🔧 Paso 2: Aplicar Patches SLM (10 min)

**SOLO SI PASO 1 ESTÁ VERDE ✅**

### 2.1. Aplicar Patch 1: `api/orchestrator.py`

Abrir `PATCH_SLM_PIPELINE.md` → Sección "Patch 1"

Reemplazar la función `_decide_with_slm_pipeline()` (líneas 170-183) con el código del patch.

### 2.2. Aplicar Patch 2: `main.py`

Abrir `PATCH_SLM_PIPELINE.md` → Sección "Patch 2"

Insertar código después de la línea 98 (dentro de `lifespan()`, después de `await validate_dependencies()`).

### 2.3. Rebuild

```bash
docker compose build pulpo-app
docker compose up -d pulpo-app
```

### 2.4. Verificar logs

```bash
docker compose logs pulpo-app | grep "SLM Pipeline"
```

**Esperado**: 
```
ℹ️  SLM Pipeline deshabilitado (ENABLE_SLM_PIPELINE=false)
```

(Normal porque todavía estamos en Legacy)

---

## 🐤 Paso 3: Activar Canary 10% (10 min)

**SOLO SI PASO 2 ESTÁ VERDE ✅**

```bash
# Configurar Canary 10%
./scripts/set_canary.sh canary10

# Validar SLM Pipeline
./tests/smoke/validate_slm_canary.sh
```

**Esperado**: ✅ `PASO 2 COMPLETADO` - Distribución OK, Latencias OK

### Verificar logs en vivo

```bash
# Ver routing
docker compose logs -f pulpo-app | grep -E "ROUTING|route="

# Esperado (~10% SLM):
# [ROUTING] route=slm_pipeline ...
# [ROUTING] route=legacy ...
# [ROUTING] route=legacy ...
# ...
```

---

## 🔥 Rollback Instantáneo (si algo falla)

```bash
./scripts/set_canary.sh rollback
```

Vuelve a 100% Legacy en < 10 segundos.

---

## 📊 Monitoreo Post-Activación

### Distribución de routes (últimos 100 requests)

```bash
docker compose logs pulpo-app | grep '"route":"' | tail -100 | sort | uniq -c
```

**Esperado**:
```
     12 "route":"slm_pipeline"
     88 "route":"legacy"
```

### Latencias

```bash
docker compose logs pulpo-app | grep -E "total_ms" | tail -20
```

**Esperado**: `total_ms` < 2000 para ambos routes

### Errores

```bash
docker compose logs pulpo-app | grep -E "ERROR|EXCEPTION" | tail -20
```

**Esperado**: Sin errores recurrentes

---

## 🎯 Escalado (después de 48hs estables)

### Canary 50%

```bash
./scripts/set_canary.sh canary50
./tests/smoke/test_deterministic_routing.sh
```

### Full SLM (100%)

```bash
./scripts/set_canary.sh full
docker compose logs pulpo-app | grep "SLM Pipeline"
# Esperado: enabled=true, canary=0%
```

---

## 📋 Checklist Visual

```
┌─────────────────────────────────────────────────────────────┐
│                     ESTADO DE ACTIVACIÓN                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [ ] Paso 1: Legacy 100% validado                          │
│      └─ ./scripts/set_canary.sh legacy                     │
│      └─ ./tests/smoke/validate_legacy.sh                   │
│                                                             │
│  [ ] Paso 2: Patches aplicados                             │
│      └─ Patch 1 en api/orchestrator.py                     │
│      └─ Patch 2 en main.py                                 │
│      └─ docker compose build pulpo-app                     │
│                                                             │
│  [ ] Paso 3: Canary 10% activo                             │
│      └─ ./scripts/set_canary.sh canary10                   │
│      └─ ./tests/smoke/validate_slm_canary.sh               │
│                                                             │
│  [ ] Monitoreo activo (48hs)                               │
│      └─ Logs limpios                                       │
│      └─ Latencias < 2s                                     │
│      └─ Error rate < 1%                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🆘 Ayuda Rápida

| Problema | Solución |
|----------|----------|
| Paso 1 falla | Ver `RUNBOOK_ACTIVACION_CANARY.md` → Sección "1.5" |
| Build falla | Ver `PATCH_SLM_PIPELINE.md` → Sección "Troubleshooting" |
| Latencia alta | Verificar Ollama: `docker compose logs ollama` |
| Route siempre legacy | Verificar feature flags: `docker compose exec pulpo-app env \| grep SLM` |
| Errores 5xx | Rollback: `./scripts/set_canary.sh rollback` |

---

## 📚 Documentación Completa

- **Runbook detallado**: `RUNBOOK_ACTIVACION_CANARY.md`
- **Patches completos**: `PATCH_SLM_PIPELINE.md`
- **Estado actual**: `ESTADO_ACTUAL_CANARY.md`
- **Contrato n8n**: `CONTRATO_N8N.md`
- **Arquitectura SLM**: `INTEGRACION_SLM.md`

---

## ✅ ¿Todo listo?

**EJECUTÁ AHORA EL PASO 1**:

```bash
./scripts/set_canary.sh legacy
./tests/smoke/validate_legacy.sh
```

**Cuando veas** `✅ PASO 1 COMPLETADO`, abrí `PATCH_SLM_PIPELINE.md` y seguí con el Paso 2.

---

**¡Éxito! 🚀**



