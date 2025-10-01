#!/usr/bin/env python3
"""
Orquestador LLM para diálogo orientado a tareas
Implementa FSM con slot filling y tools para múltiples verticales
"""

import json
import logging
import requests
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Workspace:
    """Configuración de workspace"""
    id: str
    name: str
    vertical: str  # gastronomia, inmobiliaria, servicios
    language: str
    policies: Dict[str, Any]
    rag_index: str
    payment_methods: List[str]

@dataclass
class Conversation:
    """Estado de conversación"""
    id: str
    state: Dict[str, Any]  # slots y progreso FSM
    window: List[Dict[str, str]]  # historial de mensajes

@dataclass
class ToolCall:
    """Llamada a herramienta"""
    name: str
    arguments: Dict[str, Any]

@dataclass
class ToolResult:
    """Resultado de herramienta"""
    name: str
    result: Dict[str, Any]
    success: bool
    error: Optional[str] = None

@dataclass
class OrchestratorResponse:
    """Respuesta del orquestador"""
    reply: str
    updated_state: Dict[str, Any]
    tool_calls: List[ToolCall]
    end: bool

class LLMOrchestrator:
    """Orquestador LLM para diálogo orientado a tareas"""
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        self.ollama_url = ollama_url
        self.model = model
        self.tools = {}
        
        # Cargar herramientas
        self._load_tools()
    
    def _load_tools(self):
        """Cargar herramientas disponibles"""
        self.tools = {
            "kb_search": self._tool_kb_search,
            "search_menu": self._tool_search_menu,
            "suggest_upsell": self._tool_suggest_upsell,
            "create_order": self._tool_create_order,
            "list_properties": self._tool_list_properties,
            "schedule_visit": self._tool_schedule_visit,
            "list_services": self._tool_list_services,
            "list_slots": self._tool_list_slots,
            "book_slot": self._tool_book_slot
        }
    
    def _get_system_prompt(self, workspace: Workspace) -> str:
        """Generar prompt del sistema según el vertical"""
        base_prompt = """
Rol
Sos un orquestador de diálogo orientado a tareas para WhatsApp. Trabajás por workspace (multitenant) y seguís una Máquina de Estados (FSM) con slots. Hablás en el idioma del workspace. Tu objetivo es completar slots y ejecutar tools para resolver la intención del usuario con el menor número de turnos posible, manteniendo UX natural.

Principios
1) Una pregunta por turno. Respuestas cortas (1–2 oraciones) + siguiente paso claro.
2) No inventes datos. Cuando falte info, pedila. Para datos del negocio, usá tools o RAG (kb_search) sólo si suma.
3) No envíes menús/catálogos completos salvo que el usuario lo pida explícitamente ("ver menú", "pasame el catálogo").
4) Mostrá 3–5 opciones relevantes como máximo cuando listás resultados.
5) Confirmá antes de cerrar (resumen, total/ETA, fecha/hora, dirección, etc.).
6) Si el usuario manda varios mensajes en pocos segundos, respondé al último contexto (el orquestador ya te entregó un "user_turn" consolidado por debounce).
7) Respetá políticas del workspace (horarios, zonas, pagos). Si un pedido es imposible, proponé alternativa válida.

Contexto disponible
- workspace: { id, name, vertical, policies, rag_index, payment_methods, … }
- conversation: { id, state: {slots…}, window: [historial breve] }
- user_turn: texto agregado tras debounce
- tools disponibles: kb_search, search_menu, suggest_upsell, create_order, list_properties, filter_properties, schedule_visit, list_services, list_slots, book_slot

Tareas del orquestador
A) Detectar intención.
B) Decidir próxima acción de la FSM: preguntar un slot, ejecutar una tool o presentar opciones.
C) Mantener y devolver `updated_state` con los slots llenados o pendientes.
D) Devolver `reply` breve y clara. Si hace falta tool, emitir `tool_calls` y esperar `tool_results` para responder.

Formato de salida SIEMPRE en JSON plano:
{
  "reply": "texto para el usuario",
  "updated_state": {...},          // slots y progreso FSM
  "tool_calls": [                  // vacío si no llamás herramientas
    {"name":"<tool>", "arguments":{...}}
  ],
  "end": false                     // true sólo cuando el objetivo final esté cumplido
}
"""
        
        # Agregar reglas específicas del vertical
        if workspace.vertical == "gastronomia":
            base_prompt += self._get_gastronomia_rules()
        elif workspace.vertical == "inmobiliaria":
            base_prompt += self._get_inmobiliaria_rules()
        elif workspace.vertical == "servicios":
            base_prompt += self._get_servicios_rules()
        
        return base_prompt
    
    def _get_gastronomia_rules(self) -> str:
        """Reglas específicas para gastronomía"""
        return """

[VERTICAL: GASTRONOMÍA]

Objetivo final: pedido confirmado.

Slots (orden sugerido):
- categoria          // ej. empanadas, pizzas, pastas
- items              // [{sku, qty, notes}]
- metodo_entrega     // "retiro" | "delivery"
- direccion          // si delivery
- metodo_pago        // efectivo | qr | tarjeta

Política de diálogo:
- Si el usuario pide algo fuera del menú, ofrecé alternativas cercanas usando search_menu.
- No muestres el menú completo salvo que lo pidan. Preferí: top vendidos o submenú de la categoría actual.
- Validá SKUs con search_menu antes de confirmar.
- CUANDO TENGAS ITEMS CONFIRMADOS: pregunta naturalmente "¿Querés agregar algo más? Una bebida, postre o algo más del menú?"
- Si el usuario dice "sí" o menciona algo específico, usa search_menu para encontrar opciones.
- Si el usuario dice "no" o "ya está", procede con método de entrega.
- Antes de cerrar: resume items + total + ETA.

Flujo natural de upsell (MANEJADO POR TI, NO POR TOOLS):
1. Usuario confirma items → "¿Querés agregar algo más?"
2. Si dice "sí" → "¿Qué te gustaría? Bebida, postre, o algo más del menú?"
3. Si menciona algo específico → usar search_menu para encontrar opciones
4. Si dice "no" → proceder con entrega

IMPORTANTE: El upsell es CONVERSACIONAL. Tú decides cuándo preguntar y cómo manejar las respuestas.
No hay tool automático para upsell - es parte del flujo natural de la conversación.

Tools disponibles:
- search_menu({categoria?, query?}) - para buscar items específicos
- create_order({items, metodo_entrega, direccion?, metodo_pago}) - para crear pedido final
- kb_search({query, top_k}) para FAQ/políticas (no para listar menú).
"""
    
    def _get_inmobiliaria_rules(self) -> str:
        """Reglas específicas para inmobiliaria"""
        return """

[VERTICAL: INMOBILIARIA]

Objetivo final: visita agendada.

Slots:
- operation      // compra | alquiler
- type           // departamento | casa | ph | ...
- zone
- budget_min
- budget_max
- bedrooms
- visit_property_id   // propiedad elegida
- visit_datetime      // ISO 8601

Política de diálogo:
- Primero acotá: operation + type + zone; luego presupuesto y dormitorios.
- Mostrá 3–5 propiedades relevantes con título, zona, precio y referencia (id o link corto).
- Si la persona duda, ofrecé acotar por zona o presupuesto.
- Proponé agendar visita con 2–3 horarios sugeridos.

Tools:
- list_properties({operation, type, zone, budget_min, budget_max, bedrooms})
- schedule_visit({property_id, visit_datetime})
- kb_search para descripciones largas o políticas del edificio.
"""
    
    def _get_servicios_rules(self) -> str:
        """Reglas específicas para servicios"""
        return """

[VERTICAL: SERVICIOS]

Objetivo final: turno confirmado.

Slots:
- service_code
- date
- time
- staff_id (opcional si aplica)
- payment_method

Política de diálogo:
- Identificá servicio. Sugerí fechas/horas próximas disponibles (2–3 opciones).
- Confirmá duración y precio antes de reservar.
- Si el profesional no está disponible en ese horario, ofrecé alternativas cercanas.

Tools:
- list_services()
- list_slots({service_code, date, staff_id?})
- book_slot({service_code, date, time, staff_id?, payment_method})
- kb_search para FAQ/políticas (cancelaciones, preparación, etc.).
"""
    
    async def process_turn(self, workspace: Workspace, conversation: Conversation, 
                          user_turn: str, tool_results: List[ToolResult] = None) -> OrchestratorResponse:
        """Procesar un turno de conversación"""
        try:
            # Construir prompt completo
            system_prompt = self._get_system_prompt(workspace)
            
            # Construir contexto del usuario
            user_context = self._build_user_context(workspace, conversation, user_turn, tool_results)
            
            # Llamar al LLM
            response = await self._call_llm(system_prompt, user_context)
            
            # Parsear respuesta
            orchestrator_response = self._parse_response(response)
            
            return orchestrator_response
            
        except Exception as e:
            logger.error(f"Error procesando turno: {e}")
            return OrchestratorResponse(
                reply="Lo siento, hubo un error. ¿Podrías intentar de nuevo?",
                updated_state=conversation.state,
                tool_calls=[],
                end=False
            )
    
    def _build_user_context(self, workspace: Workspace, conversation: Conversation, 
                           user_turn: str, tool_results: List[ToolResult] = None) -> str:
        """Construir contexto del usuario"""
        context = f"""
Workspace: {json.dumps({
    'id': workspace.id,
    'name': workspace.name,
    'vertical': workspace.vertical,
    'language': workspace.language,
    'policies': workspace.policies,
    'payment_methods': workspace.payment_methods
}, indent=2)}

Conversation: {json.dumps({
    'id': conversation.id,
    'state': conversation.state
}, indent=2)}

Window: {json.dumps(conversation.window[-6:], indent=2)}  # últimos 6 mensajes

User turn: "{user_turn}"
"""
        
        if tool_results:
            context += f"\nTool results: {json.dumps([{'name': tr.name, 'result': tr.result} for tr in tool_results], indent=2)}"
        
        return context
    
    async def _call_llm(self, system_prompt: str, user_context: str) -> str:
        """Llamar al LLM"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_context}
                    ],
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("message", {}).get("content", "")
            else:
                logger.error(f"Error en LLM: {response.status_code}")
                return ""
                
        except Exception as e:
            logger.error(f"Error llamando LLM: {e}")
            return ""
    
    def _parse_response(self, response: str) -> OrchestratorResponse:
        """Parsear respuesta del LLM"""
        try:
            # Buscar JSON en la respuesta
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                # Convertir tool_calls
                tool_calls = []
                for tc in data.get("tool_calls", []):
                    tool_calls.append(ToolCall(
                        name=tc["name"],
                        arguments=tc["arguments"]
                    ))
                
                return OrchestratorResponse(
                    reply=data.get("reply", ""),
                    updated_state=data.get("updated_state", {}),
                    tool_calls=tool_calls,
                    end=data.get("end", False)
                )
            else:
                # Fallback si no hay JSON
                return OrchestratorResponse(
                    reply=response,
                    updated_state={},
                    tool_calls=[],
                    end=False
                )
                
        except Exception as e:
            logger.error(f"Error parseando respuesta: {e}")
            return OrchestratorResponse(
                reply=response,
                updated_state={},
                tool_calls=[],
                end=False
            )
    
    async def execute_tool(self, tool_call: ToolCall, workspace: Workspace) -> ToolResult:
        """Ejecutar una herramienta"""
        try:
            if tool_call.name in self.tools:
                result = await self.tools[tool_call.name](tool_call.arguments, workspace)
                return ToolResult(
                    name=tool_call.name,
                    result=result,
                    success=True
                )
            else:
                return ToolResult(
                    name=tool_call.name,
                    result={},
                    success=False,
                    error=f"Tool {tool_call.name} not found"
                )
                
        except Exception as e:
            logger.error(f"Error ejecutando tool {tool_call.name}: {e}")
            return ToolResult(
                name=tool_call.name,
                result={},
                success=False,
                error=str(e)
            )
    
    # Implementación de herramientas
    async def _tool_kb_search(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Búsqueda en base de conocimientos"""
        # Implementar búsqueda RAG
        return {"results": [], "query": args.get("query", "")}
    
    async def _tool_search_menu(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Buscar en menú"""
        # Implementar búsqueda en menú estructurado
        return {"items": [], "categoria": args.get("categoria", "")}
    
    async def _tool_suggest_upsell(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Sugerir extras"""
        # Implementar lógica de upsell
        return {"suggestions": []}
    
    async def _tool_create_order(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Crear pedido"""
        # Implementar creación de pedido
        return {"order_id": "ORD-001", "total": 0, "eta_minutes": 30}
    
    async def _tool_list_properties(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Listar propiedades"""
        # Implementar búsqueda de propiedades
        return {"properties": []}
    
    async def _tool_schedule_visit(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Agendar visita"""
        # Implementar agendamiento
        return {"visit_id": "VIS-001", "confirmed": True}
    
    async def _tool_list_services(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Listar servicios"""
        # Implementar listado de servicios
        return {"services": []}
    
    async def _tool_list_slots(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Listar horarios disponibles"""
        # Implementar listado de horarios
        return {"slots": []}
    
    async def _tool_book_slot(self, args: Dict[str, Any], workspace: Workspace) -> Dict[str, Any]:
        """Reservar turno"""
        # Implementar reserva
        return {"booking_id": "BK-001", "confirmed": True}

# Función de conveniencia
def create_orchestrator(ollama_url: str = "http://localhost:11434", 
                       model: str = "llama3.1:8b") -> LLMOrchestrator:
    """Crear orquestador LLM"""
    return LLMOrchestrator(ollama_url, model)
