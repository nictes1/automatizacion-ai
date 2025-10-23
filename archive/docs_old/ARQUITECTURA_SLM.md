# 🧠 Arquitectura SLM-First para PulpoAI

## 🎯 Principios

1. **SLM-first**: Modelos 3B-8B para casi todo (barato/rápido)
2. **Contratos JSON**: Schemas versionados, cero texto libre entre módulos
3. **Determinismo en el core**: FSM/Policy/ToolBroker hacen la lógica
4. **LLM fallback**: Modelo grande solo si SLM confidence < 0.7
5. **Observabilidad**: Log de I/O por etapa + métricas

---

## 📊 Pipeline por Etapa

```
Usuario: "Quiero corte mañana a las 3pm"
    ↓
1. EXTRACTOR SLM (150-250ms)
   Schema: extractor_v1.json
   Output: {intent: "book", slots: {service_type: "Corte", date: "2025-10-16", time: "15:00"}, confidence: 0.92}
    ↓
2. PLANNER SLM (120-200ms)
   Schema: planner_v1.json
   Output: {actions: [{tool: "check_service_availability", args: {...}}], needs_confirmation: false}
    ↓
3. POLICY (determinístico, <10ms)
   Valida: permisos, rate limits, args completos
   Output: actions validadas o error
    ↓
4. TOOL BROKER (variable, 100-500ms)
   Ejecuta tools con retry/circuit breaker
   Output: ToolObservation[]
    ↓
5. FSM + STATE REDUCER (determinístico, <20ms)
   Actualiza estado, decide transición
   Output: nuevo estado + slots actualizados
    ↓
6. RESPONSE GENERATOR (80-150ms)
   Schema: response_v1.json
   Plantilla determinística O SLM corto
   Output: {message: "...", tone: "friendly", next_state: "CONFIRMACION"}
```

**Presupuesto total:** 450-1130ms (objetivo p50: <800ms, p90: <1500ms)

---

## 📁 Schemas JSON (Versionados)

### 1. Extractor v1 (`config/schemas/extractor_v1.json`)

```json
{
  "intent": "book|info_services|info_prices|...",
  "slots": {
    "service_type": "Corte de Cabello|null",
    "preferred_date": "2025-10-16|null",
    "preferred_time": "15:00|null",
    ...
  },
  "confidence": 0.0-1.0
}
```

**Responsabilidad:** Clasificar intent + extraer entidades  
**Modelo:** Qwen2.5-7B Instruct o Phi-3-mini  
**Latencia:** 150-250ms  
**Fallback:** Si confidence < 0.7 → LLM mayor

### 2. Planner v1 (`config/schemas/planner_v1.json`)

```json
{
  "plan_version": "v1",
  "actions": [
    {"tool": "get_available_services", "args": {"q": "corte"}},
    {"tool": "check_service_availability", "args": {...}}
  ],
  "needs_confirmation": false,
  "missing_slots": []
}
```

**Responsabilidad:** Decidir qué tools ejecutar (NO genera texto)  
**Modelo:** Qwen2.5-7B Instruct con few-shot  
**Latencia:** 120-200ms  
**Fallback:** Si plan inválido → Policy rechaza y pide aclaración

### 3. Response v1 (`config/schemas/response_v1.json`)

```json
{
  "message": "Perfecto, corte mañana 16/10 a las 15:00. ¿Tu nombre y email?",
  "tone": "friendly",
  "next_state": "CONFIRMACION",
  "quick_replies": ["Sí", "Cambiar hora"]
}
```

**Responsabilidad:** Generar respuesta final  
**Modelo:** Plantilla determinística (90%) + Phi-3-mini para re-frasear (10%)  
**Latencia:** 80-150ms  
**Fallback:** Siempre usa plantilla si SLM falla

---

## 🔧 Componentes Implementados

### ✅ 1. Extractor SLM (`services/slm/extractor.py`)

**Características:**
- Constrained decoding con JSON Schema
- Normalización de fechas/horas
- Few-shot prompting con ejemplos del vertical
- Fallback heurístico si SLM falla

**Uso:**
```python
from services.slm.extractor import ExtractorSLM

extractor = ExtractorSLM(llm_client)
result = await extractor.extract("Quiero corte mañana a las 3pm")

print(result.intent)      # "book"
print(result.slots)       # {"service_type": "Corte", "preferred_date": "2025-10-16", ...}
print(result.confidence)  # 0.92
```

### 🚧 2. Planner SLM (`services/slm/planner.py`) - TODO

**Características:**
- Decide tools basándose en intent + slots + estado
- Few-shot con ejemplos por vertical
- Máximo 3 tools por plan
- Detecta slots faltantes

### 🚧 3. Response Generator (`services/slm/response_generator.py`) - TODO

**Características:**
- Plantillas determinísticas para casos comunes
- SLM corto solo para casos complejos
- Máximo 480 caracteres (2-3 oraciones)
- Quick replies sugeridas

---

## 🎛️ Configuración de Modelos

### Opción 1: Un solo checkpoint, múltiples prompts
```yaml
model:
  checkpoint: "Qwen/Qwen2.5-7B-Instruct"
  device: "cuda"
  max_batch_size: 4
  
stages:
  extractor:
    temperature: 0.1
    max_tokens: 300
    
  planner:
    temperature: 0.2
    max_tokens: 400
    
  response:
    temperature: 0.7
    max_tokens: 200
```

### Opción 2: Modelos especializados
```yaml
models:
  extractor:
    checkpoint: "Qwen/Qwen2.5-7B-Instruct"
    temperature: 0.1
    
  planner:
    checkpoint: "Qwen/Qwen2.5-7B-Instruct"
    temperature: 0.2
    
  response:
    checkpoint: "microsoft/Phi-3-mini-4k-instruct"
    temperature: 0.7
    
  fallback:
    checkpoint: "Qwen/Qwen2.5-14B-Instruct"
    temperature: 0.3
```

---

## 📈 Métricas por Etapa

### Extractor
- **Intent Accuracy**: % de intents correctos (objetivo: >92%)
- **Slot F1**: Precision/Recall de slots extraídos (objetivo: >85%)
- **Confidence Distribution**: Histograma de confidence scores
- **Fallback Rate**: % que usa fallback (objetivo: <5%)
- **Latency p50/p90**: 150ms / 250ms

### Planner
- **Plan Validity**: % de planes que pasan Policy (objetivo: >95%)
- **Tool Accuracy**: % de tools correctos para el intent (objetivo: >90%)
- **Needs Confirmation Rate**: % que requiere aclaración (objetivo: 20-30%)
- **Latency p50/p90**: 120ms / 200ms

### Response Generator
- **Template Usage**: % que usa plantillas vs SLM (objetivo: >90% plantillas)
- **Message Length**: Promedio de caracteres (objetivo: <300)
- **Tone Consistency**: % que respeta el tone (objetivo: >95%)
- **Latency p50/p90**: 80ms / 150ms

### End-to-End
- **Total Latency p50/p90**: <800ms / <1500ms
- **Booking Success Rate**: % de bookings completados (objetivo: >65%)
- **Messages per Booking**: Promedio de mensajes (objetivo: <5)
- **Error Rate**: % de errores (objetivo: <1%)

---

## 🧪 Golden Tests por Intent

### Greeting
```
Input: "Hola, buenos días"
Expected: {intent: "greeting", confidence: >0.9}
```

### Info Services
```
Input: "¿Qué servicios tienen?"
Expected: {intent: "info_services", confidence: >0.9}
```

### Book (completo)
```
Input: "Quiero corte mañana a las 3pm"
Expected: {
  intent: "book",
  slots: {
    service_type: "Corte de Cabello",
    preferred_date: "2025-10-16",
    preferred_time: "15:00"
  },
  confidence: >0.9
}
```

### Book (incompleto)
```
Input: "Necesito un turno"
Expected: {
  intent: "book",
  slots: {},
  confidence: >0.8
}
```

### Cancel
```
Input: "Quiero cancelar mi turno"
Expected: {intent: "cancel", confidence: >0.85}
```

---

## 🚀 Plan de Implementación

### ✅ Semana 1 - Fundamentos
- [x] Schemas JSON versionados
- [x] Extractor SLM con constrained decoding
- [ ] Planner SLM con few-shot
- [ ] Integración con orchestrator existente

### 🚧 Semana 2 - Optimización
- [ ] Response Generator (plantillas + SLM)
- [ ] LLM fallback automático
- [ ] Dashboard de métricas por etapa
- [ ] Golden tests + CI/CD

### 📋 Semana 3 - Refinamiento
- [ ] Fine-tuning PEFT por etapa
- [ ] Shadow mode (SLM vs LLM)
- [ ] Optimización de latencia
- [ ] Documentación completa

---

## 💡 Ventajas de esta Arquitectura

1. **Control total**: FSM + Policy deciden la lógica, no el LLM
2. **Costos predecibles**: SLMs 10-50x más baratos que GPT-4
3. **Latencia estable**: Presupuestos por etapa, sin sorpresas
4. **Evolución gradual**: Fine-tune una etapa sin afectar otras
5. **Debugging fácil**: Contratos JSON claros entre módulos
6. **Multi-tenant seguro**: Validación en cada etapa

---

**Última actualización:** 15 Enero 2025  
**Versión:** 1.0





