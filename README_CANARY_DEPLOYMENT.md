# 🚀 PulpoAI - Canary Deployment del SLM Pipeline

**Sistema de agentes conversacionales inteligentes para servicios y reservas de turnos**

---

## 📋 Índice

- [¿Qué es esto?](#qué-es-esto)
- [Quick Start (3 pasos, 25 min)](#quick-start)
- [Arquitectura](#arquitectura)
- [Feature Flags](#feature-flags)
- [Tests y Validación](#tests-y-validación)
- [Monitoreo](#monitoreo)
- [Rollback](#rollback)
- [Documentación Completa](#documentación-completa)

---

## 🎯 ¿Qué es esto?

**PulpoAI** es un agente conversacional inteligente (no un bot) que:
- 🧠 **Entiende** intención del usuario (clasificación + extracción de entidades)
- 🔍 **Consulta** información real (servicios, horarios, disponibilidad)
- ⚡ **Ejecuta** acciones concretas (reservar, confirmar, cancelar turnos)
- 🎯 **Decide** con IA (SLM-first) + software determinístico (FSM + Policy + Tools)

### Arquitectura SLM-First

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Twilio    │────▶│     n8n     │────▶│ Orchestrator│
│  (WhatsApp) │     │ (Normalize) │     │   /decide   │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │       SLM Pipeline (Canary 10%)      │
                    ├──────────────────────────────────────┤
                    │  1. Extractor SLM → intent + slots   │
                    │  2. Planner SLM → tools to execute   │
                    │  3. Policy → validation              │
                    │  4. Tool Broker → execution          │
                    │  5. State Reducer → update           │
                    │  6. NLG → response                   │
                    └──────────────────────────────────────┘
                                               │
                                               ▼
                    ┌──────────────────────────────────────┐
                    │       Legacy Path (90%)              │
                    │  (Fallback determinístico)           │
                    └──────────────────────────────────────┘
```

---

## ⚡ Quick Start

### Pre-requisitos

```bash
# Verificar servicios
docker compose ps

# Esperado: pulpo-app, postgres, redis, mcp, ollama en estado Up
```

### Paso 1: Validar Legacy 100% (5 min)

```bash
# Configurar Legacy
./scripts/set_canary.sh legacy

# Validar contrato n8n
./tests/smoke/validate_legacy.sh
```

**Esperado**: ✅ `PASO 1 COMPLETADO` - `Passed: 3, Failed: 0`

### Paso 2: Aplicar Patches SLM (10 min)

Abrir `PATCH_SLM_PIPELINE.md` y aplicar:
1. Patch 1: `_decide_with_slm_pipeline()` en `api/orchestrator.py`
2. Patch 2: Inicialización de singletons en `main.py`

```bash
# Rebuild
docker compose build pulpo-app
docker compose up -d pulpo-app
```

### Paso 3: Activar Canary 10% (10 min)

```bash
# Configurar Canary 10%
./scripts/set_canary.sh canary10

# Validar SLM Pipeline
./tests/smoke/validate_slm_canary.sh
```

**Esperado**: ✅ `PASO 2 COMPLETADO` - Distribución OK, Latencias OK

---

## 🏗️ Arquitectura

### Componentes SLM

| Componente | Archivo | Latencia | Responsabilidad |
|------------|---------|----------|-----------------|
| **Extractor SLM** | `services/slm/extractor.py` | 150-250ms | Intent + NER |
| **Planner SLM** | `services/slm/planner.py` | 120-200ms | Tool selection |
| **Simple NLG** | `services/response/simple_nlg.py` | 80-150ms | Response generation |
| **Orchestrator** | `services/orchestrator_slm_pipeline.py` | <1500ms total | Pipeline E2E |

### Componentes Determinísticos

| Componente | Archivo | Responsabilidad |
|------------|---------|-----------------|
| **Policy Engine** | `services/policy_engine.py` | Validación de reglas |
| **Tool Broker** | `services/tool_broker.py` | Ejecución con retry/CB |
| **State Reducer** | `services/state_reducer.py` | Actualización de estado |
| **FSM** | `services/fsm/` | Flujo conversacional |

### Schemas JSON

| Schema | Archivo | Versión | Propósito |
|--------|---------|---------|-----------|
| Extractor | `config/schemas/extractor_v1.json` | v1 | Intent + 8 slots |
| Planner | `config/schemas/planner_v1.json` | v1 | Max 3 actions |

---

## 🎛️ Feature Flags

### Configuración

```bash
# Opción 1: Helper script (recomendado)
./scripts/set_canary.sh [legacy|canary10|canary50|full|rollback]

# Opción 2: Manual
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=10
docker compose up -d pulpo-app
```

### Modos Disponibles

| Modo | `ENABLE_SLM_PIPELINE` | `SLM_CANARY_PERCENT` | Comportamiento |
|------|----------------------|---------------------|----------------|
| **legacy** | `false` | `0` | 100% Legacy |
| **canary10** | `true` | `10` | 10% SLM, 90% Legacy |
| **canary50** | `true` | `50` | 50% SLM, 50% Legacy |
| **full** | `true` | `0` | 100% SLM |
| **rollback** | `false` | `0` | 100% Legacy (instantáneo) |

### Routing Determinístico

El routing es **determinístico** por `conversation_id`:
- Mismo `conversation_id` → siempre mismo route (SLM o Legacy)
- Hash MD5 → bucket 0-99 → `< SLM_CANARY_PERCENT` va a SLM

---

## 🧪 Tests y Validación

### Scripts Disponibles

| Script | Propósito | Uso |
|--------|-----------|-----|
| `validate_legacy.sh` | Validar Legacy 100% | Paso 1 |
| `validate_slm_canary.sh` | Validar Canary 10% | Paso 3 |
| `test_deterministic_routing.sh` | Validar consistencia | Post-activación |

### Fixtures de Test

- `tests/fixtures/request_saludo.json` - Saludo simple
- `tests/fixtures/request_precio.json` - Consulta de precio
- `tests/fixtures/request_reserva.json` - Reserva de turno

### Ejecutar Tests

```bash
# Test completo (3 pasos)
./tests/smoke/validate_legacy.sh         # Paso 1
# (aplicar patches)
./tests/smoke/validate_slm_canary.sh     # Paso 3

# Test adicional
./tests/smoke/test_deterministic_routing.sh
```

---

## 📊 Monitoreo

### Logs en Tiempo Real

```bash
# Ver routing
docker compose logs -f pulpo-app | grep -E "ROUTING|route="

# Ver telemetría completa
docker compose logs -f pulpo-app | grep -E "PIPELINE|EXTRACT|PLANNER"

# Ver errores
docker compose logs -f pulpo-app | grep -E "ERROR|EXCEPTION"
```

### Distribución de Routes

```bash
# Últimos 100 requests
docker compose logs pulpo-app | grep '"route":"' | tail -100 | sort | uniq -c

# Esperado con canary 10%:
#      12 "route":"slm_pipeline"
#      88 "route":"legacy"
```

### Métricas Clave

| Métrica | Objetivo | Alerta si |
|---------|----------|-----------|
| SLM Latency p90 | < 1500ms | > 2000ms |
| Legacy Latency p90 | < 1000ms | > 1500ms |
| Error rate | < 1% | > 5% |
| Route distribution | ~10% SLM | 0% o > 20% |
| Tool success rate | > 95% | < 90% |

---

## 🔥 Rollback

### Rollback Instantáneo (< 10s, sin rebuild)

```bash
./scripts/set_canary.sh rollback
```

O manualmente:

```bash
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0
docker compose up -d pulpo-app
```

### ¿Cuándo hacer rollback?

- ❌ Error rate > 5% sostenido
- ❌ Latencia p90 > 3000ms sostenida
- ❌ Respuestas incorrectas (diagnósticos, promesas, off-topic)
- ❌ Schema validation fails > 20%

---

## 📚 Documentación Completa

### Para Empezar

1. **`QUICK_START_CANARY.md`** ⭐ - Guía visual de 3 pasos (25 min)
2. **`RUNBOOK_ACTIVACION_CANARY.md`** - Runbook completo con troubleshooting
3. **`ESTADO_ACTUAL_CANARY.md`** - Estado actual y checklist

### Implementación

4. **`PATCH_SLM_PIPELINE.md`** ⭐ - Patches listos para aplicar
5. **`CONTRATO_N8N.md`** - API contract request/response
6. **`FLUJO_N8N_INTEGRACION.md`** - Diagrama de flujo completo

### Arquitectura

7. **`INTEGRACION_SLM.md`** - Arquitectura SLM-first detallada
8. **`RESUMEN_FINAL.md`** - Resumen ejecutivo de implementación

---

## 🎯 Roadmap de Escalado

### Fase 1: Canary 10% (Semana 1)

- [x] Implementar SLM Pipeline
- [x] Integrar con n8n
- [x] Feature flags + routing
- [x] Tests de validación
- [ ] **Activar canary 10%** ← PRÓXIMO
- [ ] Monitorear 48hs

### Fase 2: Escalado 50% (Semana 2)

- [ ] Validar métricas Fase 1
- [ ] Ajustar prompts si es necesario
- [ ] Activar canary 50%
- [ ] Monitorear 48hs

### Fase 3: Full SLM (Semana 3)

- [ ] Validar métricas Fase 2
- [ ] Activar 100% SLM
- [ ] Monitorear 1 semana
- [ ] Deprecar Legacy

### Fase 4: Optimización (Mes 2)

- [ ] Dataset de 1000+ conversaciones
- [ ] Fine-tuning PEFT (LoRA adapters)
- [ ] A/B test fine-tuned vs few-shot
- [ ] Critic SLM (opcional)

---

## 🆘 Soporte

### Errores Comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `route` siempre `legacy` | Feature flag mal configurado | Verificar env vars, rebuild |
| Error 500 | Dependencia caída | `docker compose ps`, revisar logs |
| Latencia alta | Ollama lento | Ver `docker compose logs ollama` |
| Schema validation fails | Prompt devuelve JSON inválido | Ver logs `[EXTRACT]` o `[PLANNER]` |

### Troubleshooting Detallado

Ver **`RUNBOOK_ACTIVACION_CANARY.md`** → Sección "Troubleshooting Rápido"

---

## ✅ Checklist Final

```
[ ] Paso 1: Legacy 100% validado
    └─ ./scripts/set_canary.sh legacy
    └─ ./tests/smoke/validate_legacy.sh

[ ] Paso 2: Patches aplicados
    └─ Patch 1 en api/orchestrator.py
    └─ Patch 2 en main.py
    └─ docker compose build pulpo-app

[ ] Paso 3: Canary 10% activo
    └─ ./scripts/set_canary.sh canary10
    └─ ./tests/smoke/validate_slm_canary.sh

[ ] Monitoreo activo
    └─ Logs limpios
    └─ Latencias < 2s
    └─ Error rate < 1%
```

---

## 🏆 Equipo

**Desarrollado por**: PulpoAI Team  
**Fecha**: 16 Enero 2025  
**Versión**: v1.0 - Canary Deployment Ready  
**Estado**: ✅ PRODUCTION-READY

---

## 📞 Contacto

Para dudas o soporte:
- Revisar documentación en `/docs`
- Ver runbook en `RUNBOOK_ACTIVACION_CANARY.md`
- Consultar troubleshooting en cada archivo

---

**¡Listo para activar! 🚀**

```bash
./scripts/set_canary.sh legacy
./tests/smoke/validate_legacy.sh
```



