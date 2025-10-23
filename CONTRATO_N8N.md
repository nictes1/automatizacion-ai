# 📋 Contrato n8n ⇄ Orchestrator

Documentación completa del contrato de API entre n8n y Orchestrator.

---

## 🔄 Request Format (n8n → Orchestrator)

### HTTP Request

```http
POST /orchestrator/decide
Content-Type: application/json
X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003
X-Channel: whatsapp
X-Conversation-Id: wa-5492235261872
X-Request-Id: 2025-01-15T23:59:01Z-SM010
```

### JSON Body

```json
{
  "user_message": {
    "text": "quiero reservar mañana 15hs",
    "message_id": "SM010",
    "from": "+5492235261872",
    "to": "+14155238886",
    "waid": "5492235261872",
    "timestamp_iso": "2025-01-15T23:59:01Z",
    "locale": "es-AR"
  },
  "context": {
    "platform": "twilio",
    "channel": "whatsapp",
    "business_name": "Estilo Total - Peluquería & Spa",
    "vertical": "servicios"
  },
  "state": {
    "fsm_state": null,
    "slots": {},
    "last_k_observations": []
  }
}
```

### Field Descriptions

**Headers:**
- `X-Workspace-Id`: UUID del workspace (tenant)
- `X-Channel`: Canal de origen (`whatsapp`, `telegram`, etc.)
- `X-Conversation-Id`: ID único de la conversación (`wa-{waid}`)
- `X-Request-Id`: ID para idempotencia y tracing

**user_message:**
- `text`: Mensaje del usuario (string, max 4096 chars)
- `message_id`: ID del mensaje de Twilio (ej: `SM...`)
- `from`: Número del usuario (con +)
- `to`: Número del negocio (con +)
- `waid`: WhatsApp ID (número sin +)
- `timestamp_iso`: Timestamp ISO 8601
- `locale`: Locale del usuario (default: `es-AR`)

**context:**
- `platform`: Siempre `twilio` por ahora
- `channel`: Siempre `whatsapp` por ahora
- `business_name`: Nombre del negocio para contexto
- `vertical`: `servicios`, `e-commerce`, `generico`

**state:**
- `fsm_state`: Estado actual de FSM (null si nueva conversación)
- `slots`: Slots acumulados de conversación
- `last_k_observations`: Últimas observaciones de tools (para contexto)

---

## ✅ Response Format (Orchestrator → n8n)

### JSON Response

```json
{
  "assistant": {
    "text": "¿A nombre de quién y un email para confirmar el turno?",
    "suggested_replies": [
      "Juan Pérez, juan@correo.com",
      "Prefiero con Carlos"
    ]
  },
  "tool_calls": [
    {
      "tool": "check_service_availability",
      "args": {
        "workspace_id": "550e8400-e29b-41d4-a716-446655440003",
        "service_type": "Corte de Cabello",
        "date": "2025-01-16"
      }
    }
  ],
  "patch": {
    "slots": {
      "service_type": "Corte de Cabello",
      "preferred_date": "2025-01-16",
      "preferred_time": "15:00"
    },
    "slots_to_remove": [],
    "cache_invalidation_keys": []
  },
  "telemetry": {
    "route": "slm_pipeline",
    "extractor_ms": 190,
    "planner_ms": 160,
    "policy_ms": 7,
    "broker_ms": 0,
    "reducer_ms": 12,
    "nlg_ms": 95,
    "total_ms": 464,
    "intent": "book",
    "confidence": 0.92
  }
}
```

### Field Descriptions

**assistant:**
- `text`: Mensaje para enviar al usuario (max ~200 chars para saludos, ~400 para otros)
- `suggested_replies`: Sugerencias de respuesta rápida (opcional)

**tool_calls:**
- Array de tools a ejecutar
- n8n ejecuta cada tool en orden
- Cada tool tiene `tool` (nombre) y `args` (argumentos)

**patch:**
- `slots`: Slots actualizados para merge con state
- `slots_to_remove`: Slots para eliminar
- `cache_invalidation_keys`: Keys de cache para invalidar

**telemetry:**
- `route`: `slm_pipeline`, `legacy`, `error`
- `*_ms`: Latencias por etapa (en milisegundos)
- `total_ms`: Latencia total end-to-end
- `intent`: Intent detectado (opcional)
- `confidence`: Confidence del intent (0.0-1.0, opcional)

---

## 🧪 Testing

### cURL Examples

Ver `tests/smoke/curl_examples.sh` para ejemplos completos.

**Ejemplo rápido:**

```bash
curl -s -X POST "http://localhost:8000/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: $(date -u +%Y-%m-%dT%H:%M:%SZ)-SM001" \
  -d '{
  "user_message": {
    "text": "hola",
    "message_id": "SM001",
    "from": "+5492235261872",
    "to": "+14155238886",
    "waid": "5492235261872",
    "timestamp_iso": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "locale": "es-AR"
  },
  "context": {
    "platform": "twilio",
    "channel": "whatsapp",
    "business_name": "Estilo Total",
    "vertical": "servicios"
  },
  "state": {
    "fsm_state": null,
    "slots": {},
    "last_k_observations": []
  }
}' | jq
```

### Automated Tests

```bash
# Test contrato completo
./tests/smoke/test_n8n_contract.sh

# Ejemplos interactivos
./tests/smoke/curl_examples.sh
```

---

## 📝 n8n Function Node

### Preparar Request (antes del HTTP Request node)

```javascript
// Input: datos normalizados de nodos previos de n8n
const body = {
  user_message: {
    text: $json.Body || "",
    message_id: $json.SmsMessageSid || $json.MessageSid || "",
    from: ($json.From || "").replace("whatsapp:", ""),
    to: ($json.To || "").replace("whatsapp:", ""),
    waid: $json.WaId || "",
    timestamp_iso: new Date().toISOString(),
    locale: "es-AR"
  },
  context: {
    platform: "twilio",
    channel: "whatsapp",
    business_name: $json.business_name || "Mi Negocio",
    vertical: "servicios"
  },
  state: {
    fsm_state: $json.fsm_state || null,
    slots: $json.slots || {},
    last_k_observations: $json.last_k_observations || []
  }
};

return [{ json: body }];
```

### HTTP Request Node Config

**Settings:**
- Method: `POST`
- URL: `http://pulpo-app:8000/orchestrator/decide`
- Authentication: None (internal)
- Response Format: JSON

**Headers:**
```
Content-Type: application/json
X-Workspace-Id: {{$json.workspace_id}}
X-Channel: whatsapp
X-Conversation-Id: wa-{{$json.user_message.waid}}
X-Request-Id: {{$json.user_message.timestamp_iso}}-{{$json.user_message.message_id}}
```

**Body:**
- Type: JSON
- Value: `{{$json}}`

### Procesar Response (después del HTTP Request node)

```javascript
// Parse response
const response = $json;

// Extraer datos para n8n
return [{
  json: {
    // Para enviar via Twilio
    assistant_text: response.assistant.text,
    suggested_replies: response.assistant.suggested_replies || [],
    
    // Para ejecutar tools (si los hay)
    tool_calls: response.tool_calls || [],
    has_tools: (response.tool_calls || []).length > 0,
    
    // Para actualizar estado en DB
    updated_slots: response.patch.slots || {},
    slots_to_remove: response.patch.slots_to_remove || [],
    
    // Para métricas
    route: response.telemetry.route,
    total_ms: response.telemetry.total_ms,
    intent: response.telemetry.intent,
    confidence: response.telemetry.confidence
  }
}];
```

---

## 🚨 Error Handling

### Status Codes

| Code | Meaning | n8n Action |
|------|---------|------------|
| 200 | Success | Procesar response normalmente |
| 400 | Bad Request (schema inválido) | Loguear y responder mensaje genérico |
| 409 | Conflict (Policy deny) | Usar `assistant.text` (ya incluye qué falta) |
| 429 | Rate Limit | Reintenta con backoff (5s, 10s, 30s) |
| 500 | Internal Error | Respuesta fallback + alerta |
| 503 | Service Unavailable | Reintenta hasta 3 veces |

### Fallback Response

Si Orchestrator falla completamente, n8n debe responder:

```javascript
const fallbackText = "Disculpá, tuve un problema técnico. ¿Podés intentar de nuevo en un momento?";
```

---

## 🎯 Reglas de UX

### Respuestas del Asistente

1. **Saludo**: Máximo ~80 chars
   - ✅ "Hola! ¿En qué puedo ayudarte?"
   - ❌ "Hola! Somos Estilo Total, ofrecemos corte, color, barba..."

2. **Consulta de info**: Máximo ~200 chars
   - ✅ "Corte de Cabello: $3500-$6000"
   - ❌ Lista completa de 15 servicios

3. **Reserva**: Una pregunta por mensaje
   - ✅ "¿Para qué día querés el turno?"
   - ❌ "¿Para qué día, hora, y a nombre de quién?"

4. **Confirmación**: Corta + datos clave
   - ✅ "Listo! Turno de Corte el 16/01 a las 15:00."
   - ❌ "Tu turno ha sido reservado exitosamente en nuestro sistema..."

### Tool Calls

- **check_service_availability**: SIEMPRE antes de `book_appointment`
- **find_appointment_by_phone**: Para cancelaciones sin booking_id
- **get_available_services**: Solo cuando piden precios o listado

---

## 📈 Métricas Esperadas

| Métrica | Objetivo | Alerta si |
|---------|----------|-----------|
| `total_ms` p50 | < 800ms | > 1200ms |
| `total_ms` p90 | < 1500ms | > 2000ms |
| `total_ms` p99 | < 2500ms | > 3500ms |
| `route=error` rate | < 0.5% | > 2% |
| `confidence` avg | > 0.8 | < 0.7 |
| tool_calls count | 0-2 (promedio) | > 3 |

---

## 🔐 Seguridad

### Headers Obligatorios

- `X-Workspace-Id`: SIEMPRE requerido
- `X-Request-Id`: Para idempotencia de tools

### Validaciones

- `user_message.text`: Max 4096 chars
- `workspace_id`: UUID válido
- `waid`: Solo números

### Rate Limiting

Por `workspace_id`:
- 60 requests / minuto (normal)
- 10 requests / segundo (burst)

Por `conversation_id`:
- 10 requests / minuto
- Previene loops infinitos

---

## 📚 Referencias

- **Código**: `api/orchestrator.py`
- **Tests**: `tests/smoke/test_n8n_contract.sh`
- **Ejemplos**: `tests/smoke/curl_examples.sh`
- **Workflow n8n**: `n8n/n8n-workflow.json`

---

**Última actualización:** 16 Enero 2025  
**Versión del contrato:** v1  
**Estado:** ✅ PRODUCTION-READY




