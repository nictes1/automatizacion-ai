# 🔧 Plan de Integración - Tools en Orchestrator

## 🎯 Objetivo

Reemplazar llamadas a RAG con llamadas a **tools** (funciones de base de datos) para vertical servicios.

## 📋 Estado Actual vs Deseado

### Estado Actual
```
Usuario: "Quiero turno mañana"
    ↓
Orchestrator extrae slots
    ↓
RETRIEVE_CONTEXT → RAG Service (busca en documents)
    ↓
Respuesta basada en documents embeddings
```

### Estado Deseado
```
Usuario: "Quiero turno mañana"
    ↓
Orchestrator extrae slots
    ↓
RETRIEVE_CONTEXT → Tools (consulta DB directa)
    ├─ get_available_services() → Lista servicios
    ├─ check_service_availability() → Verifica horarios
    └─ get_active_promotions() → Promociones vigentes
    ↓
Respuesta basada en datos en tiempo real
```

## 🔄 Cambios Necesarios

### 1. Modificar `orchestrator_service.py`

#### A. Importar tools
```python
from services.servicios_tools import SERVICIOS_TOOLS, execute_tool
```

#### B. Cambiar decisión de RETRIEVE_CONTEXT

**Antes:**
```python
if self._has_slots_for_query(snapshot):
    return NextStep(
        next_action=NextAction.RETRIEVE_CONTEXT,
        args={"query": self._build_query_from_slots(snapshot)},
        reason="Slots suficientes para orientar consulta RAG"
    )
```

**Después:**
```python
if self._has_slots_for_query(snapshot):
    # Decidir qué tool llamar según slots
    tool_name, tool_args = self._decide_tool(snapshot)

    return NextStep(
        next_action=NextAction.RETRIEVE_CONTEXT,  # O crear nuevo: CALL_TOOL
        args={
            "tool_name": tool_name,
            "tool_args": tool_args
        },
        reason=f"Llamar tool: {tool_name}"
    )
```

#### C. Agregar método `_decide_tool`

```python
def _decide_tool(self, snapshot: ConversationSnapshot) -> tuple[str, dict]:
    """
    Decide qué tool llamar basado en slots y vertical

    Returns:
        (tool_name, tool_args)
    """
    workspace_id = snapshot.get("workspace_id")  # Necesitamos agregar al snapshot

    if snapshot.vertical == "servicios":
        slots = snapshot.slots

        # Si no tiene servicio → listar servicios disponibles
        if not slots.get("service_type"):
            return ("get_available_services", {"workspace_id": workspace_id})

        # Si tiene servicio + fecha → verificar disponibilidad
        if slots.get("service_type") and slots.get("preferred_date"):
            return ("check_service_availability", {
                "workspace_id": workspace_id,
                "service_name": slots["service_type"],
                "date_str": slots["preferred_date"],
                "time_str": slots.get("preferred_time")
            })

        # Si pregunta por promociones
        if "promocion" in snapshot.user_input.lower() or "descuento" in snapshot.user_input.lower():
            return ("get_active_promotions", {"workspace_id": workspace_id})

        # Si pregunta por paquetes
        if "paquete" in snapshot.user_input.lower() or "combo" in snapshot.user_input.lower():
            return ("get_service_packages", {"workspace_id": workspace_id})

        # Si pregunta por horarios
        if "horario" in snapshot.user_input.lower() or "abr" in snapshot.user_input.lower():
            return ("get_business_hours", {"workspace_id": workspace_id})

        # Default: listar servicios
        return ("get_available_services", {"workspace_id": workspace_id})

    # Otros verticales → usar RAG por ahora
    return (None, {})
```

#### D. Modificar ejecución de RETRIEVE_CONTEXT

En el punto donde se ejecuta RETRIEVE_CONTEXT:

```python
async def execute_retrieve_context(self, args: dict, context: dict):
    """Ejecuta RETRIEVE_CONTEXT (RAG o Tool según vertical)"""

    # Si es tool
    if "tool_name" in args:
        tool_result = await execute_tool(args["tool_name"], **args["tool_args"])
        return {
            "context_used": [tool_result],
            "source": "tool",
            "tool_name": args["tool_name"]
        }

    # Si es RAG (legacy)
    else:
        # Llamada actual a RAG service
        rag_result = await self.rag_service.search(args["query"])
        return {
            "context_used": rag_result,
            "source": "rag"
        }
```

### 2. Actualizar `ConversationSnapshot`

Agregar `workspace_id` al snapshot:

```python
class ConversationSnapshot(BaseModel):
    conversation_id: str
    vertical: str
    user_input: str
    workspace_id: str  # ← AGREGAR
    greeted: bool
    slots: Dict[str, Any]
    objective: str
    last_action: Optional[str] = None
    attempts_count: int = 0
```

### 3. Generar respuesta usando tool result

En el paso de generación de respuesta (LLM):

```python
async def generate_response_with_context(self, user_input: str, tool_result: dict):
    """Genera respuesta usando resultado de tool"""

    # Formatear tool result para el LLM
    context_text = self._format_tool_result(tool_result)

    prompt = f"""Eres Sofía, recepcionista virtual de peluquería.

Información del sistema:
{context_text}

Usuario pregunta: {user_input}

Responde de forma natural y amigable basándote en la información del sistema.
Si hay horarios disponibles, menciónelos.
Si hay promociones, méncionalas brevemente.
"""

    # Llamar a LLM
    response = await self.llm_client.chat(prompt)
    return response
```

### 4. Helper para formatear tool results

```python
def _format_tool_result(self, tool_result: dict) -> str:
    """Formatea resultado de tool para el prompt del LLM"""

    if not tool_result.get("success"):
        return f"Error: {tool_result.get('error', 'Error desconocido')}"

    # get_available_services
    if "services" in tool_result:
        services = tool_result["services"]
        text = "Servicios disponibles:\n"
        for svc in services:
            text += f"- {svc['name']}: ${svc['price']} ({svc['duration_minutes']} min)\n"
        return text

    # check_service_availability
    if "time_slots" in tool_result:
        if tool_result["available"]:
            slots = tool_result["time_slots"]
            text = f"Horarios disponibles para {tool_result['service_info']['name']}:\n"
            text += ", ".join(slots[:5])  # Primeros 5
            return text
        else:
            return f"No hay disponibilidad. Razón: {tool_result.get('reason', 'Desconocida')}"

    # get_active_promotions
    if "promotions" in tool_result:
        promos = tool_result["promotions"]
        if not promos:
            return "No hay promociones activas en este momento."
        text = "Promociones activas:\n"
        for promo in promos:
            if promo["discount_type"] == "percentage":
                text += f"- {promo['name']}: {promo['discount_value']}% de descuento\n"
            else:
                text += f"- {promo['name']}: ${promo['discount_value']} de descuento\n"
        return text

    # Default
    return json.dumps(tool_result, ensure_ascii=False, indent=2)
```

## 🧪 Flujo de Ejemplo

### Conversación Completa

```
👤 Usuario: "Hola, quiero sacar turno"

1. GREET
   - Saludo inicial
   - Extrae objetivo: agendar turno

2. RETRIEVE_CONTEXT (Tool)
   - Tool: get_available_services()
   - Resultado: ["Corte $2500", "Coloración $6500", ...]

3. ANSWER
   🤖 "¡Hola! Claro, te ayudo. Ofrecemos:
       - Corte de cabello: $2500 (45 min)
       - Coloración completa: $6500 (120 min)
       - Brushing: $1800 (30 min)
       ¿Qué servicio te interesa?"

───────────────────────────────────────

👤 Usuario: "Corte para mañana a las 3pm"

1. SLOT_FILL
   - Extrae: service_type="Corte", preferred_date="2025-10-07", preferred_time="15:00"

2. RETRIEVE_CONTEXT (Tool)
   - Tool: check_service_availability()
   - Args: {service_name="Corte", date="2025-10-07", time="15:00"}
   - Resultado: {"available": true, "staff_assigned": "María García"}

3. ANSWER
   🤖 "Perfecto, tenemos disponibilidad para corte mañana a las 15:00 con María.
       ¿Confirmamos? Necesito tu nombre y email."

───────────────────────────────────────

👤 Usuario: "Sí, soy Juan Pérez, juan@gmail.com"

1. SLOT_FILL
   - Extrae: client_name="Juan Pérez", client_email="juan@gmail.com"
   - Todos los slots completos

2. EXECUTE_ACTION
   - Llama a actions_service: schedule_appointment()
   - Crea turno en DB + Google Calendar

3. ANSWER
   🤖 "¡Listo! Tu turno está confirmado:
       📅 Mañana 07/10 a las 15:00
       💇 Corte de cabello con María García
       💰 $2500
       Te enviamos confirmación a juan@gmail.com"
```

## 🚀 Próximos Pasos

### Fase 1: Integración Básica (Ahora)
- [x] Crear servicios_tools.py
- [ ] Modificar orchestrator_service.py
- [ ] Agregar workspace_id a snapshot
- [ ] Implementar _decide_tool()
- [ ] Implementar _format_tool_result()

### Fase 2: Testing
- [ ] Test con usuario preguntando servicios
- [ ] Test con verificación de disponibilidad
- [ ] Test con promociones
- [ ] Test end-to-end completo

### Fase 3: Optimización
- [ ] Caché de tool results
- [ ] Parallel tool calls (si es necesario)
- [ ] Mejora de prompts con tool results
- [ ] Analytics de qué tools se usan más

## 📚 Referencias

- `services/servicios_tools.py` - Tools disponibles
- `services/orchestrator_service.py` - Lógica de decisión
- `database/init/07_servicios_complete.sql` - Schema con funciones

---

**Nota**: Esta integración reemplaza RAG solo para vertical servicios.
Otros verticales (gastronomía, inmobiliaria) seguirán usando RAG hasta que se implementen sus tools.
