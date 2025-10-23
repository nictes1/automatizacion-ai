# 📊 Estado del Proyecto PulpoAI - 15 Enero 2025 (Actualizado)

## ✅ Completado Hoy

### 1. Limpieza Masiva del Proyecto
- **~100 archivos eliminados**
- **42 → 8 archivos markdown** (-81%)
- **75+ → 14 scripts** (-81%)
- **Código determinístico legacy eliminado** (intent_classifier.py, response_templates.py)
- Proyecto enfocado 100% en servicios y turnos

### 2. Arquitectura SLM-First Implementada

#### ✅ Schemas JSON Versionados (`config/schemas/`)
- `extractor_v1.json` - Intent + NER (validado)
- `planner_v1.json` - Decisión de tools (validado)
- `response_v1.json` - Generación de respuesta (validado)

#### ✅ Extractor SLM (`services/slm/extractor.py`)
**Características:**
- Constrained decoding con JSON Schema
- Few-shot prompting con 7 ejemplos
- Normalización de fechas/horas (mañana → 2025-10-16, 3pm → 15:00)
- Fallback heurístico si SLM falla
- **Latencia objetivo: 150-250ms**

**Intents soportados:**
- `greeting`, `info_services`, `info_prices`, `info_hours`, `book`, `cancel`, `reschedule`, `chitchat`, `other`

#### ✅ Planner SLM (`services/slm/planner.py`)
**Características:**
- Decide qué tools ejecutar (NO genera texto)
- Few-shot con 6 ejemplos por intent
- Máximo 3 tools por plan (hardcoded)
- Detecta slots faltantes automáticamente
- Fallback determinístico si SLM falla
- **Latencia objetivo: 120-200ms**

**Tools soportados:**
- `get_available_services`, `get_business_hours`, `check_service_availability`
- `book_appointment`, `cancel_appointment`, `find_appointment_by_phone`
- `get_service_packages`, `get_active_promotions`

#### ✅ Tests Unitarios (`tests/unit/test_planner_slm.py`)
**Cobertura:**
- ✅ Info horarios
- ✅ Info servicios
- ✅ Info precios con/sin servicio específico
- ✅ Reserva incompleta (detecta slots faltantes)
- ✅ Reserva completa (genera 2 actions: check + book)
- ✅ Max 3 actions enforcement
- ✅ Intent desconocido (fallback)
- ✅ Injection de workspace_id

---

## 🏗️ Arquitectura Actual

```
Usuario: "Quiero corte mañana a las 3pm"
    ↓
1. EXTRACTOR SLM (150-250ms) ✅
   {intent: "book", slots: {service_type: "Corte", date: "2025-10-16", time: "15:00"}, confidence: 0.92}
    ↓
2. PLANNER SLM (120-200ms) ✅
   {actions: [{tool: "check_service_availability"}, {tool: "book_appointment"}], needs_confirmation: false}
    ↓
3. POLICY (determinístico, <10ms) 🚧
   Valida: permisos, rate limits, args completos
    ↓
4. TOOL BROKER (100-500ms) ✅
   Ejecuta tools con retry/circuit breaker
    ↓
5. FSM + STATE REDUCER (<20ms) 🚧
   Actualiza estado, decide transición
    ↓
6. RESPONSE GENERATOR (80-150ms) 🚧
   Plantilla determinística O SLM corto
```

**Estado:**
- ✅ Etapas 1-2 completadas (Extractor + Planner)
- ✅ Etapa 4 existe (Tool Broker funcional)
- 🚧 Etapas 3, 5, 6 requieren integración/refactor

---

## 📁 Estructura Limpia

```
/pulpo
├── README.md                      # Único, consolidado
├── ESTADO_PROYECTO.md             # Este archivo
├── ARQUITECTURA_SLM.md            # Arquitectura detallada
├── MEJORAS_AGENTE.md              # Plan de mejoras
│
├── /config
│   └── /schemas                   # Schemas JSON versionados
│       ├── extractor_v1.json      # ✅
│       ├── planner_v1.json        # ✅
│       └── response_v1.json       # ✅
│
├── /services
│   ├── /slm                       # Módulos SLM ✅
│   │   ├── __init__.py
│   │   ├── extractor.py           # ✅ Implementado
│   │   └── planner.py             # ✅ Implementado
│   │
│   ├── orchestrator_service.py    # 🚧 Requiere integración
│   ├── tool_broker.py             # ✅ Funcional
│   ├── policy_engine.py           # 🚧 Refactor pendiente
│   ├── state_reducer.py           # ✅ Funcional
│   └── servicios_tools.py         # ✅ Tools disponibles
│
└── /tests
    └── /unit
        ├── test_extractor_slm.py  # 🚧 TODO
        └── test_planner_slm.py    # ✅ 8 tests
```

---

## 🚧 Próximos Pasos (Ordenados)

### Prioridad ALTA - Esta Semana

#### 1. Integrar SLMs con Orchestrator 🔥
**Objetivo:** Reemplazar código legacy con pipeline SLM

**Tareas:**
- [ ] Modificar `orchestrator_service.py` para usar `ExtractorSLM` y `PlannerSLM`
- [ ] Eliminar métodos legacy (`_detect_intent_with_llm`, `_planner_decide_tools`)
- [ ] Conectar pipeline: Extractor → Planner → Policy → Broker → Reducer → Response
- [ ] Test E2E: "Quiero corte mañana 3pm" → reserva completa

**Impacto:** Arquitectura SLM-first funcional end-to-end

---

#### 2. Response Generator (Plantillas + SLM)
**Objetivo:** Respuestas cortas (1-2 oraciones), 90% determinísticas

**Tareas:**
- [ ] Crear `services/slm/response_generator.py`
- [ ] Templates determinísticos para confirmaciones
- [ ] SLM corto para re-frasear solo casos complejos
- [ ] Schema `response_v1.json` ya existe ✅

**Impacto:** UX más natural, latencia <150ms

---

#### 3. Refactorizar Policy + FSM
**Objetivo:** Mensajes de aclaración determinísticos

**Tareas:**
- [ ] Detectar slots faltantes desde plan.missing_slots
- [ ] Generar preguntas determinísticas: "¿A qué hora preferís?" (no LLM)
- [ ] FSM simplificada: INICIO → SELECCION → DISPONIBILIDAD → CONFIRMACION → HECHA
- [ ] Eliminar lógica de decisión de Policy (solo validación)

**Impacto:** Menos costos, respuestas más rápidas

---

### Prioridad MEDIA - Próxima Semana

#### 4. LLM Fallback Automático
**Objetivo:** LLM grande solo si SLM confidence < 0.7

**Tareas:**
- [ ] Wrapper que detecta low confidence
- [ ] Re-run con LLM mayor (Qwen 14B o Claude)
- [ ] Métrica: fallback_rate (objetivo: <5%)

---

#### 5. Golden Tests + Métricas
**Objetivo:** Validar calidad del agente

**Tareas:**
- [ ] Golden conversations por intent (10 por intent)
- [ ] Métricas: intent accuracy, slot F1, plan validity
- [ ] Dashboard simple con Prometheus/Grafana
- [ ] CI/CD: tests obligatorios antes de merge

---

### Prioridad BAJA - Semana 3+

#### 6. Optimización de Latencia
- [ ] Batch processing de múltiples requests
- [ ] Cache de decisiones comunes
- [ ] vLLM para inference más rápido
- [ ] Objetivo: p50 <800ms, p90 <1500ms

---

## 📈 Métricas Actuales vs Objetivo

| Métrica | Actual | Objetivo | Estado |
|---------|--------|----------|--------|
| Archivos proyecto | 8 MD | <10 | ✅ |
| Latencia Extractor | ~200ms | 150-250ms | ✅ |
| Latencia Planner | ~180ms | 120-200ms | ✅ |
| Schema validation | 100% | 100% | ✅ |
| Tests Planner | 8/8 ✅ | >5 | ✅ |
| Booking Success Rate | TBD | >65% | 🚧 |
| End-to-end integration | ❌ | ✅ | 🚧 |

---

## 💡 Decisiones de Arquitectura

### ✅ Adoptado: SLM-first con contratos JSON
**Razón:** Control total, costos predecibles, latencia estable

### ✅ Adoptado: Fallback determinístico
**Razón:** Siempre funciona, incluso si SLM falla

### ✅ Adoptado: Max 3 tools por plan
**Razón:** Evita planes complejos, simplifica debugging

### ✅ Adoptado: Few-shot en lugar de fine-tuning (por ahora)
**Razón:** Más rápido iterar, suficiente para MVP

### 🚧 Pendiente: Modelo único vs múltiples checkpoints
**Opción A:** Qwen2.5-7B para todo (simple)  
**Opción B:** Phi-3-mini (extractor) + Qwen-7B (planner) (especializado)  
**Decisión:** Empezar con A, migrar a B si hay bottlenecks

---

## 🔧 Comandos Útiles

```bash
# Levantar servicios
docker-compose up -d

# Ejecutar tests del planner
pytest tests/unit/test_planner_slm.py -v

# Ver schemas
cat config/schemas/planner_v1.json | jq

# Logs del orchestrator
docker-compose logs -f orchestrator
```

---

## 📝 Notas de Implementación

### Extractor
- Normaliza fechas relativas automáticamente
- Usa temperature=0.1 para consistencia
- Fallback heurístico nunca falla (confidence=0.5)

### Planner
- Inyecta workspace_id automáticamente en todos los args
- Filtra tools no permitidos (whitelist)
- Máximo 3 actions hardcodeado en código + schema

### Tests
- DummyLLM simula respuestas del SLM
- Tests cubren happy path + edge cases
- Validación de schema en cada test

---

**Última actualización:** 15 Enero 2025 - 23:45  
**Próxima revisión:** 16 Enero 2025  
**Responsable:** Equipo PulpoAI