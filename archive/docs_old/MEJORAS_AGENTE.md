# 🧠 Mejoras del Core del Agente

## 🎯 Objetivo
Convertir PulpoAI en un verdadero agente inteligente eliminando reglas hardcode y potenciando el LLM.

## 📋 Mejoras Identificadas

### 1. ❌ Eliminar Intent Classifier con Regex
**Problema Actual:**
- `services/intent_classifier.py` usa regex patterns para clasificar intents
- Esto es un bot tradicional, no un agente inteligente
- El LLM ya detecta intents en `_detect_intent_with_llm`

**Solución:**
- Eliminar `intent_classifier.py` completamente
- Usar solo `_detect_intent_with_llm` del orchestrator
- El LLM es mucho mejor entendiendo intenciones

### 2. 🔧 Mejorar Extracción de Entidades
**Problema Actual:**
- `_extract_slots_from_current_message` tiene prompt muy simple
- No usa conocimiento del negocio (servicios disponibles, horarios)
- No valida ni normaliza bien

**Solución:**
- Pasar contexto del negocio al extractor
- Mejor normalización de fechas/horas
- Validación en el mismo paso

### 3. 📝 Simplificar Planner Prompt
**Problema Actual:**
- Prompt del planner muy largo (~100 líneas)
- Muchas reglas que confunden al LLM
- Mix de instrucciones de extracción + decisión de tools

**Solución:**
- Separar extracción de decisión
- Prompt más corto y directo
- Focus en ejemplos, no reglas

### 4. 🗑️ Eliminar Código Determinístico Legacy
**Problema Actual:**
- `_handle_deterministic_greeting` y `_handle_deterministic_intent`
- `_decide_tool` con 200 líneas de regex
- PolicyEngine con lógica de decisión hardcodeada

**Solución:**
- Eliminar flujos determinísticos
- Todo pasa por agent loop con LLM
- PolicyEngine solo valida permisos, no decide

### 5. ⚡ Optimizar Response Generation
**Problema Actual:**
- `_generate_response_with_context` genera prompt en cada llamada
- No usa templates para casos comunes
- Respuestas a veces muy largas

**Solución:**
- Templates para confirmaciones simples
- LLM solo para respuestas complejas
- Respuestas más cortas (1-2 oraciones)

---

## ✅ Plan de Implementación

### Fase 1: Limpieza (Hoy)
- [x] Eliminar servicios no core
- [x] Eliminar scripts experimentales
- [x] Consolidar READMEs
- [ ] Eliminar `intent_classifier.py`
- [ ] Eliminar métodos determinísticos del orchestrator

### Fase 2: Mejora de Extracción (Mañana)
- [ ] Mejorar prompt de extracción de slots
- [ ] Agregar contexto del negocio
- [ ] Mejor normalización de fechas/horas
- [ ] Tests de extracción

### Fase 3: Optimización de Planner (Esta semana)
- [ ] Simplificar prompt del planner
- [ ] Separar extracción de decisión
- [ ] Mejorar ejemplos en prompts
- [ ] Tests de planner

### Fase 4: Response Templates (Esta semana)
- [ ] Templates para confirmaciones
- [ ] Respuestas más cortas
- [ ] Mejor manejo de errores
- [ ] Tests E2E

---

## 🔍 Código a Eliminar

```python
# services/intent_classifier.py - TODO EL ARCHIVO
# services/response_templates.py - TODO EL ARCHIVO (usar LLM)

# En orchestrator_service.py:
- _handle_deterministic_greeting()
- _handle_deterministic_intent()
- PolicyEngine._decide_tool()  # 200 líneas de regex
- Todo el bloque de intent classification con regex
```

---

## 🚀 Arquitectura Mejorada

```
Usuario: "Hola, quiero corte mañana a las 3pm"
    ↓
1. EXTRACCIÓN (LLM + contexto negocio)
   → slots: {service_type: "corte", date: "2025-10-16", time: "15:00"}
   ↓
2. PLANNER (LLM simple y directo)
   → tools: [check_service_availability]
   ↓
3. VALIDATION (solo permisos)
   → ✅ permitido
   ↓
4. EXECUTION
   → check_service_availability() → disponible
   ↓
5. RESPONSE (LLM o template)
   → "Perfecto, corte mañana 16/10 a las 15:00. ¿Tu nombre y email?"
```

**Diferencia clave:**
- Antes: 3 llamadas al LLM (intent + extract + plan) + reglas hardcode
- Después: 2 llamadas al LLM (extract + response), planner usa cache
- Más rápido, más inteligente, menos código


