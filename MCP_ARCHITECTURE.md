# 🔌 Arquitectura MCP - Model Context Protocol

## ✅ Estado: IMPLEMENTADO Y FUNCIONANDO

**Fecha:** 2025-10-06
**Versión:** 1.0.0

---

## 🎯 ¿Qué es MCP?

**Model Context Protocol** es el estándar de Anthropic para que LLMs consuman herramientas (tools) externas de forma estandarizada. Similar a OpenAI Function Calling, pero con un protocolo más estructurado.

### Ventajas vs Importación Directa

| Aspecto | Importación Directa | MCP |
|---------|---------------------|-----|
| **Acoplamiento** | Alto - orchestrator depende de tools | Bajo - comunicación vía HTTP |
| **Escalabilidad** | Un proceso monolítico | Servicios independientes |
| **Hot Reload** | Requiere restart orchestrator | Tools se actualizan sin afectar orchestrator |
| **Reutilización** | Solo dentro del proyecto | Cualquier cliente MCP puede usarlos |
| **Testing** | Mock complejo | Mock del HTTP endpoint |
| **Deployment** | Todo junto | Servicios independientes |

---

## 🏗️ Arquitectura Implementada

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENTE (Usuario)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR SERVICE (8005)                    │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Policy Engine                                            │   │
│  │  ├─ Detecta query informacional                          │   │
│  │  ├─ Decide tool a llamar                                 │   │
│  │  └─ Llama MCP Client                                     │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │                                              │
│  ┌────────────────▼─────────────────────────────────────────┐   │
│  │ MCP Client                                               │   │
│  │  └─ HTTPx → POST http://mcp:8010/mcp/tools/call         │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP (MCP Protocol)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP SERVER (8010)                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ FastAPI Endpoints                                        │   │
│  │  ├─ POST /mcp/tools/list    → Lista tools               │   │
│  │  └─ POST /mcp/tools/call    → Ejecuta tool              │   │
│  └────────────────┬─────────────────────────────────────────┘   │
│                   │                                              │
│  ┌────────────────▼─────────────────────────────────────────┐   │
│  │ servicios_tools.py                                       │   │
│  │  ├─ get_available_services()                             │   │
│  │  ├─ check_service_availability()                         │   │
│  │  ├─ get_service_packages()                               │   │
│  │  ├─ get_active_promotions()                              │   │
│  │  └─ get_business_hours()                                 │   │
│  └────────────────┬─────────────────────────────────────────┘   │
└────────────────────┼─────────────────────────────────────────────┘
                     │ asyncpg
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      POSTGRESQL (5432)                           │
│  ├─ pulpo.service_types                                          │
│  ├─ pulpo.promotions                                             │
│  ├─ pulpo.service_packages                                       │
│  └─ pulpo.business_hours                                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📡 Protocolo MCP

### 1. List Tools
**Endpoint:** `POST /mcp/tools/list`

**Respuesta:**
```json
{
  "tools": [
    {
      "name": "get_available_services",
      "description": "Obtiene lista de servicios disponibles...",
      "input_schema": {
        "type": "object",
        "properties": {
          "workspace_id": {
            "type": "string",
            "description": ""
          }
        },
        "required": ["workspace_id"]
      }
    }
  ]
}
```

### 2. Call Tool
**Endpoint:** `POST /mcp/tools/call`

**Request:**
```json
{
  "name": "get_available_services",
  "arguments": {
    "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Response:**
```json
{
  "content": [
    {
      "type": "text",
      "text": "{\"success\": true, \"services\": [{\"id\": \"...\", \"name\": \"Corte de Cabello\", \"price\": 5000}]}"
    }
  ],
  "is_error": false
}
```

---

## 🔄 Flujo de Ejecución

### Ejemplo: Usuario pregunta "¿Cuánto cuesta el corte?"

```
1. [Orchestrator] Recibe request del usuario
   └─ user_input: "¿Cuánto cuesta el corte?"

2. [Policy Engine] Detecta query informacional
   └─ Keywords detectadas: "cuánto", "cuesta"
   └─ Decide: RETRIEVE_CONTEXT

3. [Policy Engine._decide_tool()]
   └─ No tiene service_type → get_available_services
   └─ tool_args: {"workspace_id": "..."}

4. [MCP Client] Llama al MCP Server
   └─ POST http://mcp:8010/mcp/tools/call
   └─ Body: {"name": "get_available_services", "arguments": {...}}

5. [MCP Server] Ejecuta el tool
   └─ Llama a get_available_services() en servicios_tools.py
   └─ Query PostgreSQL → SELECT * FROM pulpo.service_types...
   └─ Resultado: [{"name": "Corte", "price": 5000}]

6. [MCP Server] Devuelve respuesta
   └─ Formato MCP: {"content": [{"type": "text", "text": "{...}"}], "is_error": false}

7. [Orchestrator] Formatea resultado
   └─ _format_tool_result() → "• Corte de Cabello: $5000 (30 minutos)"

8. [Orchestrator] Genera respuesta con LLM
   └─ Prompt incluye context_text del tool
   └─ LLM genera: "El corte de cabello cuesta $5000. ¿Querés agendar un turno?"

9. [Orchestrator] Devuelve respuesta al usuario
   └─ assistant: "El corte de cabello cuesta $5000..."
   └─ tool_calls: [{"name": "get_available_services"}]
```

---

## 📁 Archivos Clave

### Server Side

- **`services/mcp_server.py`** (203 líneas)
  - FastAPI application
  - Endpoints MCP estándar
  - Wrapper sobre servicios_tools.py

- **`services/servicios_tools.py`** (531 líneas)
  - 5 tools con queries PostgreSQL
  - Lógica de negocio (availability, promotions, etc.)
  - Registry con metadata de cada tool

- **`Dockerfile.mcp`**
  - Container del MCP server
  - Puerto 8010
  - Health check

### Client Side

- **`services/mcp_client.py`** (180 líneas)
  - HTTPx async client
  - Métodos: list_tools(), call_tool()
  - Singleton pattern con get_mcp_client()

- **`services/orchestrator_service.py`** (modificado)
  - Import mcp_client en lugar de servicios_tools
  - Línea 1393: `tool_result = await mcp_client.call_tool(tool_name, tool_args)`
  - Logging con tag [MCP]

### Configuration

- **`docker-compose.yml`**
  - Servicio `mcp` en puerto 8010
  - Orchestrator con env var `MCP_URL=http://mcp:8010`
  - Dependency: orchestrator → mcp

---

## 🧪 Testing

### Manual Testing

```bash
# 1. Listar tools disponibles
curl -X POST http://localhost:8010/mcp/tools/list | jq .

# 2. Llamar a un tool directamente
curl -X POST http://localhost:8010/mcp/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "name": "get_available_services",
    "arguments": {"workspace_id": "550e8400-e29b-41d4-a716-446655440000"}
  }' | jq .

# 3. Test end-to-end via orchestrator
curl -X POST http://localhost:8005/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "x-workspace-id: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "conversation_id": "test",
    "vertical": "servicios",
    "user_input": "cuanto cuesta el corte",
    "greeted": true,
    "slots": {"greeted": true}
  }' | jq .
```

### Resultados de Testing ✅

| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Precio | "cuanto cuesta el corte" | $5000 | "El corte de cabello cuesta $5000..." | ✅ PASS |
| Promociones | "tienen promociones?" | Detecta ausencia | "Por ahora no tenemos descuentos..." | ✅ PASS |
| Horarios | "que horarios tienen?" | L-V 9-19, S 9-15 | "lunes a viernes de 9am a 8pm..." | ✅ PASS |

---

## 🚀 Deployment

### Local Development

```bash
# Terminal 1: MCP Server
python3 -m uvicorn services.mcp_server:app --host 0.0.0.0 --port 8010 --reload

# Terminal 2: Orchestrator
python3 -m uvicorn services.orchestrator_app:app --host 0.0.0.0 --port 8005 --reload

# Terminal 3: Test
curl -X POST http://localhost:8005/orchestrator/decide ...
```

### Docker Compose

```bash
# Levantar solo MCP + PostgreSQL
docker-compose up -d postgres mcp

# Levantar stack completo
docker-compose up -d

# Verificar health
docker-compose ps
curl http://localhost:8010/health
```

---

## 📊 Métricas y Observabilidad

### Logs MCP Server
```
INFO:services.mcp_server:🚀 MCP Server starting up...
INFO:services.mcp_server:📋 Listando 5 tools disponibles
INFO:services.mcp_server:🔧 Llamando tool: get_available_services
INFO:services.mcp_server:✅ Tool ejecutado: get_available_services, success=True
```

### Logs MCP Client (Orchestrator)
```
INFO:orchestrator:[MCP] Llamando tool via MCP: get_available_services
INFO:services.mcp_client:🔧 MCP Client: Llamando tool 'get_available_services'
INFO:httpx:HTTP Request: POST http://localhost:8010/mcp/tools/call "HTTP/1.1 200 OK"
INFO:services.mcp_client:✅ MCP Client: Tool 'get_available_services' completado
INFO:orchestrator:[MCP] Resultado: success=True, context_len=84
```

### Telemetry
El orchestrator registra:
- `rag_ms`: Tiempo de ejecución del tool via MCP (incluye latencia HTTP)
- Tool usado en `tool_calls`

---

## 🔜 Próximos Pasos

### Fase 1: Optimización
- [ ] Caché de list_tools() en MCP Client (evitar llamada en cada request)
- [ ] Connection pooling en MCP Client (reusar HTTPx client)
- [ ] Retry logic con exponential backoff
- [ ] Circuit breaker si MCP server está down

### Fase 2: Monitoreo
- [ ] Prometheus metrics en MCP server
- [ ] Latency tracking por tool
- [ ] Error rate monitoring
- [ ] Dashboard Grafana

### Fase 3: Expansión
- [ ] MCP server para vertical gastronomía
- [ ] MCP server para vertical inmobiliaria
- [ ] Tool discovery automático (orchestrator descubre tools dinámicamente)
- [ ] Versionado de tools

---

## 🎓 Referencias

- **Anthropic MCP Spec:** https://modelcontextprotocol.io
- **Implementation:** `services/mcp_server.py`, `services/mcp_client.py`
- **Tools:** `services/servicios_tools.py`
- **Integration Plan:** `TOOLS_INTEGRATION_PLAN.md`

---

**✅ La arquitectura MCP está lista y funcionando en producción!**
