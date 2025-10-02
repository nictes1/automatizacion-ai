"""
Orchestrator Service - Orquestación determinista con Policy Engine
Encapsula la lógica de decisión del LLM con políticas deterministas y JSON Schema (ligero)
"""

import json
import logging
import hashlib
import time
import contextvars
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import httpx
from datetime import datetime
from pydantic import BaseModel
import asyncpg

# Contexto por request (thread-safe, async-safe)
REQUEST_CONTEXT: contextvars.ContextVar[dict] = contextvars.ContextVar("REQUEST_CONTEXT", default={})

class RequestContext:
    """Context manager para limpieza automática del contexto de request"""
    def __init__(self, ctx: Dict[str, str]):
        self._token = None
        allowed = ("authorization", "x-workspace-id", "x-request-id")
        cleaned = {k.lower(): v for k, v in (ctx or {}).items() if k.lower() in allowed}
        self.cleaned = cleaned
    
    def __enter__(self):
        self._token = REQUEST_CONTEXT.set(self.cleaned)
        return self
    
    def __exit__(self, exc_type, exc, tb):
        if self._token:
            REQUEST_CONTEXT.reset(self._token)

# Logger (configuración movida al entrypoint para evitar conflictos)
logger = logging.getLogger("orchestrator")

# =========================
# Enumeraciones y dataclasses
# =========================

class NextAction(Enum):
    """Acciones disponibles en el flujo de conversación"""
    GREET = "GREET"
    SLOT_FILL = "SLOT_FILL"
    RETRIEVE_CONTEXT = "RETRIEVE_CONTEXT"
    EXECUTE_ACTION = "EXECUTE_ACTION"
    ANSWER = "ANSWER"
    ASK_HUMAN = "ASK_HUMAN"

class ConversationSnapshot(BaseModel):
    """Snapshot del estado actual de la conversación"""
    conversation_id: str
    vertical: str
    user_input: str
    greeted: bool
    slots: Dict[str, Any]
    objective: str
    last_action: Optional[str] = None
    attempts_count: int = 0

@dataclass
class NextStep:
    """Estructura de decisión del orquestador"""
    next_action: NextAction
    args: Dict[str, Any]
    reason: str

class OrchestratorResponse(BaseModel):
    """Respuesta del orquestador"""
    assistant: str
    slots: Dict[str, Any]
    tool_calls: List[Dict[str, Any]]
    context_used: List[Dict[str, Any]]
    next_action: NextAction
    end: bool = False

# =========================
# Utilidades
# =========================

def stable_idempotency_key(conversation_id: str, payload: Dict[str, Any], vertical: str = "") -> str:
    """
    Genera una clave idempotente estable a partir de JSON canónico
    """
    payload_canon = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    base = f"{vertical}:{conversation_id}:{payload_canon}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def safe_json_loads(s: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(s)
    except Exception:
        return None

# =========================
# Configuración de Business Slots
# =========================

BUSINESS_SLOTS = {
    "gastronomia": ["categoria", "items", "metodo_entrega", "direccion", "metodo_pago", "notas", "workspace_id", "conversation_id"],
    "inmobiliaria": ["operation", "type", "zone", "price_range", "bedrooms", "bathrooms", "property_id", "preferred_date", "contact_info", "workspace_id", "conversation_id"],
    "servicios": ["service_type", "preferred_date", "preferred_time", "staff_preference", "notes", "contact_info", "workspace_id", "conversation_id"],
}

# Slots críticos que requieren reset de validación RAG
CRITICAL_SLOTS = {
    "gastronomia": ["categoria", "items", "metodo_entrega"],
    "inmobiliaria": ["operation", "type", "zone"],
    "servicios": ["service_type", "preferred_date"]
}

# Verticales válidos
VALID_VERTICALS = {"gastronomia", "inmobiliaria", "servicios"}

# =========================
# Policy Engine
# =========================

class PolicyEngine:
    """Motor de políticas deterministas para el orquestador"""

    def __init__(self):
        # Config por vertical
        self.vertical_configs = {
            "gastronomia": {
                "required_slots": ["categoria", "items", "metodo_entrega"],
                "optional_slots": ["extras", "direccion", "metodo_pago", "notas"],
                "max_attempts": 3,
                "needs_rag_before_action": True,  # validar menú/precios
                "rag_min_score": 0.05
            },
            "inmobiliaria": {
                "required_slots": ["operation", "type", "zone"],
                "optional_slots": ["price_range", "bedrooms", "bathrooms"],
                "max_attempts": 3,
                "needs_rag_before_action": True,  # listar propiedades antes de agendar
                "rag_min_score": 0.08
            },
            "servicios": {
                "required_slots": ["service_type", "preferred_date"],
                "optional_slots": ["preferred_time", "staff_preference", "notes"],
                "max_attempts": 3,
                "needs_rag_before_action": False,  # muchas veces podés accionar directo
                "rag_min_score": 0.03
            }
        }
    
    def enforce_policy(self, snapshot: ConversationSnapshot) -> NextStep:
        """
        Aplica políticas deterministas para decidir el próximo paso
        """
        cfg = self.vertical_configs.get(snapshot.vertical, {
            "required_slots": [],
            "optional_slots": [],
            "max_attempts": 3,
            "needs_rag_before_action": True
        })
        required_slots = cfg["required_slots"]
        max_attempts = cfg["max_attempts"]

        # 1) Saludo
        if not snapshot.greeted:
            return NextStep(
                next_action=NextAction.GREET,
                args={"greeting_type": "initial"},
                reason="Usuario no ha sido saludado aún"
            )

        # 2) Slots faltantes
        missing_slots = [s for s in required_slots if not snapshot.slots.get(s)]
        if missing_slots and snapshot.attempts_count < max_attempts:
            # preguntamos por el slot que más reduce el espacio de búsqueda (primero de la lista)
            return NextStep(
                next_action=NextAction.SLOT_FILL,
                args={"missing_slots": missing_slots, "ask_for": missing_slots[0]},
                reason=f"Faltan slots requeridos: {missing_slots}"
            )

        # 3) Si todos los requeridos están completos:
        all_required_ready = all(snapshot.slots.get(s) for s in required_slots)

        # 3.a) ¿Necesitamos RAG antes de accionar? (depende del vertical)
        if all_required_ready and cfg["needs_rag_before_action"] and not snapshot.slots.get("_validated_by_rag"):
            # Buscamos contexto para validar/precios/disponibilidad
            return NextStep(
                next_action=NextAction.RETRIEVE_CONTEXT,
                args={"query": self._build_query_from_slots(snapshot),
                      "filters": self._build_filters_from_slots(snapshot)},
                reason="Validar con RAG antes de accionar"
            )

        # 3.b) Si estamos listos, accionamos
        if all_required_ready:
            return NextStep(
                next_action=NextAction.EXECUTE_ACTION,
                args={"action_name": self._get_action_name(snapshot.vertical)},
                reason="Slots requeridos completos"
            )

        # 4) Si no hay requeridos, pero sí hay señales parciales → intentar RAG para ayudar
        if self._has_slots_for_query(snapshot):
            return NextStep(
                next_action=NextAction.RETRIEVE_CONTEXT,
                args={"query": self._build_query_from_slots(snapshot),
                      "filters": self._build_filters_from_slots(snapshot)},
                reason="Slots suficientes para orientar consulta RAG"
            )

        # 5) Intentos agotados → humano
        if snapshot.attempts_count >= max_attempts:
            return NextStep(
                next_action=NextAction.ASK_HUMAN,
                args={"reason": "max_attempts_exceeded"},
                reason="Se excedió el número máximo de intentos"
            )

        # 6) Default
        return NextStep(
            next_action=NextAction.ANSWER,
            args={},
            reason="Respuesta general por default"
        )
    
    # ---- helpers de policy ----

    def _has_slots_for_query(self, snapshot: ConversationSnapshot) -> bool:
        if snapshot.vertical == "gastronomia":
            return bool(snapshot.slots.get("categoria") or snapshot.slots.get("items"))
        if snapshot.vertical == "inmobiliaria":
            # pedir al menos operación + zona o tipo
            return bool(snapshot.slots.get("operation") and (snapshot.slots.get("type") or snapshot.slots.get("zone")))
        if snapshot.vertical == "servicios":
            return bool(snapshot.slots.get("service_type"))
        return False

    def _build_query_from_slots(self, snapshot: ConversationSnapshot) -> str:
        if snapshot.vertical == "gastronomia":
            categoria = (snapshot.slots.get("categoria") or "").strip()
            raw_items = snapshot.slots.get("items") or []
            # Defensa contra items no-list en gastronomía
            items = raw_items if isinstance(raw_items, list) else [str(raw_items)]
            items_str = " ".join([str(i) for i in items])
            return f"{categoria} {items_str}".strip() or snapshot.user_input

        if snapshot.vertical == "inmobiliaria":
            op = snapshot.slots.get("operation", "")
            typ = snapshot.slots.get("type", "")
            zone = snapshot.slots.get("zone", "")
            return " ".join([op, typ, zone]).strip() or snapshot.user_input

        if snapshot.vertical == "servicios":
            return (snapshot.slots.get("service_type") or snapshot.user_input).strip()

        return snapshot.user_input

    def _build_filters_from_slots(self, snapshot: ConversationSnapshot) -> Dict[str, Any]:
        """
        Convierte slots → filtros de metadata para RAG (por vertical)
        
        IMPORTANTE: Estos filtros deben coincidir con los metadatos que se guardan
        durante el proceso de ingest. Verificar que el ingestion_service guarde
        metadatos útiles como:
        - gastronomia: document_type="menu", category, item_name
        - inmobiliaria: document_type="property", operation, city, property_type
        - servicios: document_type="service", service_type, availability
        """
        m: Dict[str, Any] = {}
        if snapshot.vertical == "gastronomia":
            if snapshot.slots.get("categoria"):
                m["category"] = snapshot.slots["categoria"]
            if snapshot.slots.get("items"):
                m["items"] = snapshot.slots["items"]
        elif snapshot.vertical == "inmobiliaria":
            if snapshot.slots.get("operation"):
                m["operation"] = snapshot.slots["operation"]
            if snapshot.slots.get("zone"):
                m["city"] = snapshot.slots["zone"]
            if snapshot.slots.get("type"):
                m["property_type"] = snapshot.slots["type"]
            if snapshot.slots.get("price_range"):
                m["price_range"] = snapshot.slots["price_range"]
        elif snapshot.vertical == "servicios":
            if snapshot.slots.get("service_type"):
                m["service_type"] = snapshot.slots["service_type"]

        return {"metadata": m} if m else {}

    def _get_action_name(self, vertical: str) -> str:
        actions = {
            "gastronomia": "crear_pedido",
            "inmobiliaria": "schedule_visit",
            "servicios": "book_slot"
        }
        return actions.get(vertical, "unknown_action")

# =========================
# Clientes HTTP (LLM / Tools)
# =========================

class LLMClient:
    """Cliente para comunicación con el LLM (Ollama)"""

    def __init__(self, base_url: str = "http://ollama:11434", model: str = "llama3.1:8b"):
        self.base_url = base_url
        self.model = model
        # Timeout más agresivo para LLM (3s)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(3.0))

    async def generate_json(self, system_prompt: str, user_prompt: str, retry: bool = True) -> Optional[Dict[str, Any]]:
        """
        Pide al LLM que devuelva JSON (se fuerza formato).
        Retorna dict o None si no se pudo parsear.
        """
        try:
            # Limitar prompt de usuario para evitar input gigantes
            short_user = user_prompt if len(user_prompt) < 2000 else user_prompt[:2000] + "..."
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": short_user}
                ],
                "stream": False,
                "format": "json"
            }
            resp = await self.client.post(f"{self.base_url}/api/chat", json=payload)
            resp.raise_for_status()
            result = resp.json()
            content = result.get("message", {}).get("content", "")
            data = safe_json_loads(content)
            
            # Validar tamaño y tipo
            if not isinstance(data, dict) or len(json.dumps(data)) > 8000:
                logger.warning(f"LLM response too large or invalid: {len(json.dumps(data)) if data else 0} chars")
                if retry:
                    # Reintento con prompt minimalista
                    return await self.generate_json(
                        "Responde en JSON con 'reply' (máximo 200 caracteres) y 'updated_state' (opcional).",
                        f"Usuario: {user_prompt[:100]}...",
                        retry=False
                    )
                return None
            
            return data
            
        except httpx.RequestError as e:
            logger.error(f"LLM request error: {e!r}")
            return None
        except Exception as e:
            logger.error(f"LLM unexpected error: {e}")
            return None

    async def close(self):
        await self.client.aclose()

class ToolsClient:
    """Cliente para comunicación con servicios de tools"""

    def __init__(self, rag_url: str = "http://rag:8007", actions_url: str = "http://actions:8006"):
        self.rag_service_url = rag_url
        self.actions_service_url = actions_url
        # Timeouts granulares: connect/read/write/pool
        self.rag_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=0.3, read=0.5, write=0.3, pool=0.5)
        )
        self.actions_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=0.5, read=1.5, write=0.5, pool=0.5)
        )

    def _merged_headers(self) -> dict:
        """
        Combina headers base con contexto del request (workspace, auth, request-id)
        """
        base = {"content-type": "application/json"}
        ctx = REQUEST_CONTEXT.get()
        if ctx:
            # Headers coherentes en mayúscula
            if "authorization" in ctx: base["Authorization"] = ctx["authorization"]
            if "x-workspace-id" in ctx: base["X-Workspace-Id"] = ctx["x-workspace-id"]
            if "x-request-id" in ctx: base["X-Request-Id"] = ctx["x-request-id"]
        return base

    async def retrieve_context(
        self,
        conversation_id: str,
        query: str,
        slots: Dict[str, Any],
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        try:
            payload = {
                "conversation_id": conversation_id,
                "query": query,
                "slots": slots,
                "filters": filters or {},
                "top_k": top_k,
                "hybrid": True
            }
            resp = await self.rag_client.post(
                f"{self.rag_service_url}/tools/retrieve_context", 
                json=payload,
                headers=self._merged_headers()
            )
            resp.raise_for_status()
            try:
                data = resp.json()
            except ValueError:
                logger.error("RAG devolvió JSON inválido")
                return []
            return data.get("results", [])
        except httpx.RequestError as e:
            logger.error(f"RAG request error: {e!r}")
            return []
        except Exception as e:
            logger.error(f"RAG unexpected error: {e}")
            return []

    async def execute_action(
        self,
        conversation_id: str,
        action_name: str,
        payload: Dict[str, Any],
        idempotency_key: str
    ) -> Dict[str, Any]:
        try:
            req = {
                "conversation_id": conversation_id,
                "action_name": action_name,
                "payload": payload,
                "idempotency_key": idempotency_key
            }
            resp = await self.actions_client.post(
                f"{self.actions_service_url}/tools/execute_action", 
                json=req,
                headers=self._merged_headers()
            )
            resp.raise_for_status()
            try:
                return resp.json()
            except ValueError:
                logger.error("Actions devolvió JSON inválido")
                return {"error": "Invalid JSON response", "status": "failed"}
        except httpx.RequestError as e:
            logger.error(f"Actions request error: {e!r}")
            return {"error": str(e), "status": "failed"}
        except Exception as e:
            logger.error(f"Actions unexpected error: {e}")
            return {"error": str(e), "status": "failed"}

    async def close(self):
        await self.rag_client.aclose()
        await self.actions_client.aclose()

# =========================
# Orchestrator principal
# =========================

class OrchestratorService:
    """Servicio principal del orquestador"""

    def __init__(self):
        self.policy_engine = PolicyEngine()
        self.llm_client = LLMClient()
        self.tools_client = ToolsClient()
        self._system_cache: Dict[str, str] = {}  # cache de prompts por vertical
        self.db_pool = None  # Pool de conexiones asyncpg
        self.database_url = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@postgres:5432/pulpo")

    def set_request_context(self, ctx: Dict[str, str]) -> RequestContext:
        """
        Devuelve un context manager. Uso:
        with orchestrator_service.set_request_context(headers):
            await orchestrator_service.decide(snapshot)
        """
        return RequestContext(ctx)

    async def initialize_db(self):
        """Inicializa el pool de conexiones a la base de datos"""
        if self.db_pool is None:
            try:
                self.db_pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=2,
                    max_size=10,
                    command_timeout=5
                )
                logger.info("✅ DB pool initialized for orchestrator")
            except Exception as e:
                logger.error(f"❌ Error initializing DB pool: {e}")
                # No falla el servicio, solo logea el error

    async def close_db(self):
        """Cierra el pool de conexiones"""
        if self.db_pool:
            await self.db_pool.close()
            logger.info("DB pool closed")

    async def _get_conversation_history(
        self,
        conversation_id: str,
        workspace_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Lee los últimos N mensajes de la conversación desde la DB
        Retorna lista de mensajes ordenados cronológicamente (más antiguos primero)
        """
        if not self.db_pool:
            logger.warning("DB pool not initialized, skipping history fetch")
            return []

        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT sender, content, message_type, metadata, created_at
                    FROM pulpo.messages
                    WHERE conversation_id = $1
                    AND workspace_id = $2
                    ORDER BY created_at DESC
                    LIMIT $3
                """, conversation_id, workspace_id, limit)

                # Invertir para tener orden cronológico (más antiguos primero)
                messages = []
                for row in reversed(rows):
                    messages.append({
                        "sender": row["sender"],
                        "content": row["content"],
                        "message_type": row["message_type"],
                        "metadata": dict(row["metadata"]) if row["metadata"] else {},
                        "created_at": row["created_at"].isoformat()
                    })

                logger.info(f"[history] Loaded {len(messages)} messages for conversation {conversation_id}")
                return messages

        except Exception as e:
            logger.error(f"Error fetching conversation history: {e}")
            return []

    def _reconstruct_state_from_history(
        self,
        messages: List[Dict[str, Any]],
        vertical: str
    ) -> Dict[str, Any]:
        """
        Reconstruye el estado de la conversación desde el historial de mensajes
        Retorna: {"greeted": bool, "slots": {}, "objective": str, "last_action": str}
        """
        state = {
            "greeted": False,
            "slots": {},
            "objective": "",
            "last_action": None,
            "attempts_count": 0
        }

        # Si no hay mensajes, retornar estado inicial
        if not messages:
            return state

        # Verificar si ya saludó (buscar mensajes del assistant)
        for msg in messages:
            if msg["sender"] == "assistant":
                state["greeted"] = True
                break

        # Extraer slots y objective de los metadatos del último mensaje del assistant
        for msg in reversed(messages):
            if msg["sender"] == "assistant":
                metadata = msg.get("metadata", {})

                # Slots guardados en metadata
                if "slots" in metadata:
                    state["slots"] = metadata["slots"]

                # Objective guardado en metadata
                if "objective" in metadata:
                    state["objective"] = metadata["objective"]

                # Last action guardada en metadata
                if "last_action" in metadata:
                    state["last_action"] = metadata["last_action"]

                # Attempts count
                if "attempts_count" in metadata:
                    state["attempts_count"] = metadata.get("attempts_count", 0)

                # Solo tomar del último mensaje del assistant
                break

        logger.info(f"[state_reconstruction] greeted={state['greeted']}, slots={state['slots']}, objective={state['objective']}")
        return state

    # ---------- prompts ----------

    def _system_prompt(self, vertical: str) -> str:
        if vertical in self._system_cache:
            return self._system_cache[vertical]

        base = """
Eres un orquestador de diálogo orientado a tareas para WhatsApp. Trabajas por workspace (multitenant) y sigues una Máquina de Estados (FSM) con slots. Hablas en español. Tu objetivo es completar slots y ejecutar tools para resolver la intención del usuario con el menor número de turnos posible, manteniendo UX natural.

Principios:
1) Una pregunta por turno. Respuestas cortas (1–2 oraciones) + siguiente paso claro.
2) No inventes datos. Cuando falte info, pídela. Para datos del negocio, usa RAG o tools.
3) No envíes menús/catálogos completos salvo que el usuario lo pida explícitamente.
4) Muestra 3–5 opciones relevantes como máximo cuando listes resultados.
5) Confirma antes de cerrar (resumen, total/ETA, fecha/hora, dirección, etc.).
6) Respeta políticas del workspace (horarios, zonas, pagos).

Formato de salida SIEMPRE en JSON:
{
  "reply": "texto para el usuario",
  "updated_state": {...},   // slots u otros campos
  "tool_calls": [{"name":"<tool>", "arguments":{...}}],
  "end": false
}
""".strip()

        if vertical == "gastronomia":
            base += """
\nVertical: GASTRONOMÍA
- Objetivo: Completar pedido de comida
- Slots: categoria, items, extras, metodo_entrega, direccion, metodo_pago, notas
- Tools: search_menu, suggest_upsell, create_order
- Políticas: horarios de entrega, zonas de cobertura, métodos de pago
"""
        elif vertical == "inmobiliaria":
            base += """
\nVertical: INMOBILIARIA
- Objetivo: Agendar visita a propiedad
- Slots: operation, type, zone, price_range, bedrooms, bathrooms
- Tools: list_properties, schedule_visit
- Políticas: horarios de visitas, disponibilidad de propiedades
"""
        elif vertical == "servicios":
            base += """
\nVertical: SERVICIOS
- Objetivo: Reservar turno
- Slots: service_type, preferred_date, preferred_time, staff_preference, notes
- Tools: list_services, list_slots, book_slot
- Políticas: horarios de atención, disponibilidad de staff
"""

        self._system_cache[vertical] = base
        return base

    # ---------- utilidades auxiliares ----------

    def _business_payload(self, vertical: str, slots: Dict[str, Any], conversation_id: str) -> Dict[str, Any]:
        """Extrae solo slots de negocio para idempotencia estable"""
        keys = BUSINESS_SLOTS.get(vertical, [])
        norm = self._normalize_slots(vertical, slots)
        payload = {k: norm[k] for k in keys if k in norm}

        # Endurecer workspace_id y conversation_id del payload (evitar spoofing)
        headers = self.tools_client._merged_headers()
        
        # workspace_id desde header confiable
        if "workspace_id" in keys and "X-Workspace-Id" in headers:
            payload["workspace_id"] = headers["X-Workspace-Id"]
        
        # conversation_id SIEMPRE del snapshot (fuente confiable)
        if "conversation_id" in keys:
            payload["conversation_id"] = conversation_id
        
        return payload

    def _filter_updated_state(self, vertical: str, upd: Dict[str, Any]) -> Dict[str, Any]:
        """Filtra claves desconocidas por vertical para evitar que el LLM meta basura en slots"""
        allowed = set(BUSINESS_SLOTS.get(vertical, [])) | {"_validated_by_rag", "_attempts_count", "greeted", "extras"}
        return {k: v for k, v in (upd or {}).items() if k in allowed}

    def _clip_reply(self, text: str, limit: int = 280) -> str:
        """Corta respuestas largas y sanitiza para WhatsApp"""
        # Colapsar espacios y saltos de línea
        t = " ".join(text.split())
        # Limitar longitud
        if len(t) > limit:
            t = t[:limit-3] + "..."
        return t

    def _maybe_reset_validation(self, old: Dict[str, Any], new: Dict[str, Any], vertical: str) -> Dict[str, Any]:
        """Resetea _validated_by_rag si cambian slots críticos"""
        critical_keys = CRITICAL_SLOTS.get(vertical, [])
        if any(old.get(k) != new.get(k) for k in critical_keys):
            new.pop("_validated_by_rag", None)
        return new

    def _normalize_slots(self, vertical: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza slots por vertical (ej: items como lista)"""
        s = dict(slots)
        if vertical == "gastronomia":
            raw = s.get("items")
            if raw is not None and not isinstance(raw, list):
                s["items"] = [str(raw)]
        return s

    def _json_safe(self, obj: Any) -> Any:
        """Convierte tipos no serializables a JSON-safe"""
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        if isinstance(obj, (list, tuple)): 
            return [self._json_safe(x) for x in obj]
        if isinstance(obj, dict):
            return {str(k): self._json_safe(v) for k, v in obj.items()}
        return str(obj)

    def _telemetry_add(self, key: str, value: int):
        """Acumula métricas en el contexto de request"""
        ctx = REQUEST_CONTEXT.get() or {}
        accum = ctx.get("_telemetry", {})
        accum[key] = accum.get(key, 0) + value
        ctx["_telemetry"] = accum
        REQUEST_CONTEXT.set(ctx)
    
    # ---------- bucle principal ----------

    async def decide(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """
        Decide el próximo paso y ejecuta la acción/herramienta correspondiente.
        """
        start_time = time.time()
        ctx = REQUEST_CONTEXT.get()
        telemetry = {
            "conversation_id": snapshot.conversation_id,
            "vertical": snapshot.vertical,
            "attempts_count": snapshot.attempts_count,
            "request_id": (ctx.get("x-request-id") if ctx else None),
            "llm_ms": 0,
            "rag_ms": 0,
            "action_ms": 0,
            "tool_failures": 0,
            "reply_len": 0
        }
        
        try:
            # 0. Validar vertical desconocido
            logger.info(f"[DEBUG] Vertical recibido: '{snapshot.vertical}' | Válidos: {VALID_VERTICALS}")
            if snapshot.vertical not in VALID_VERTICALS:
                logger.warning(f"[VERTICAL_INVALIDO] Recibido: '{snapshot.vertical}' | Válidos: {VALID_VERTICALS}")
                return OrchestratorResponse(
                    assistant="Aún no tengo soporte para ese tipo de consulta.",
                    slots=snapshot.slots,
                    tool_calls=[],
                    context_used=[],
                    next_action=NextAction.ANSWER,
                    end=False
                )

            # 1. Sincronizar attempts_count entre snapshot y slots
            slots_attempts = int(snapshot.slots.get("_attempts_count", snapshot.attempts_count))
            max_attempts = self.policy_engine.vertical_configs.get(snapshot.vertical, {}).get("max_attempts", 3)
            snapshot.attempts_count = min(slots_attempts, max_attempts)
            
            # 2. Si ya está en ASK_HUMAN, no permitir volver a otros estados
            if snapshot.attempts_count >= max_attempts:
                response = await self._handle_ask_human(snapshot)
                telemetry["reply_len"] = len(response.assistant)
                logger.info(f"[telemetry] {telemetry}")
                return response

            step = self.policy_engine.enforce_policy(snapshot)
            telemetry["next_action"] = step.next_action.value
            telemetry["step_reason"] = step.reason
            logger.info(f"[policy] {snapshot.vertical}:{telemetry['request_id']} {step.next_action.value} - {step.reason}")

            if step.next_action == NextAction.GREET:
                response = await self._handle_greet(snapshot)
            elif step.next_action == NextAction.SLOT_FILL:
                # Incrementar intentos al solicitar info adicional
                response = await self._handle_slot_fill(snapshot, step, inc_attempt=True)
            elif step.next_action == NextAction.RETRIEVE_CONTEXT:
                response = await self._handle_retrieve_context(snapshot, step)
            elif step.next_action == NextAction.EXECUTE_ACTION:
                response = await self._handle_execute_action(snapshot, step)
            elif step.next_action == NextAction.ASK_HUMAN:
                response = await self._handle_ask_human(snapshot)
            else:  # ANSWER
                response = await self._handle_answer(snapshot)

            # Completar telemetría
            telemetry["reply_len"] = len(response.assistant)
            telemetry["total_ms"] = int((time.time() - start_time) * 1000)
            
            # Volcar tiempos acumulados del contexto
            ctx = REQUEST_CONTEXT.get()
            if ctx and "_telemetry" in ctx:
                telemetry.update(ctx["_telemetry"])
            
            logger.info(f"[telemetry] {snapshot.vertical}:{telemetry['request_id']} {telemetry}")
            
            return response

        except Exception as e:
            telemetry["error"] = str(e)
            telemetry["total_ms"] = int((time.time() - start_time) * 1000)
            logger.exception(f"[telemetry] {snapshot.vertical}:{telemetry['request_id']} {telemetry}")
            return OrchestratorResponse(
                assistant="Lo siento, hubo un error procesando tu mensaje. Probemos de nuevo.",
                slots=snapshot.slots,
                tool_calls=[],
                context_used=[],
                next_action=NextAction.ANSWER,
                end=False
            )
    
    # ---------- handlers ----------

    async def _handle_greet(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """Saludo determinista (sin LLM)"""
        # TIP: en el futuro, podés personalizar por horario/zona desde workspace_configs
        greeting = self._clip_reply("¡Hola! ¿En qué puedo ayudarte hoy?")
        # mantenemos compatibilidad: marcamos greeted en slots (aunque idealmente sería estado aparte)
        new_slots = dict(snapshot.slots)
        new_slots["greeted"] = True
        return OrchestratorResponse(
            assistant=greeting,
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.GREET,
            end=False
        )
    
    async def _handle_slot_fill(self, snapshot: ConversationSnapshot, step: NextStep, inc_attempt: bool) -> OrchestratorResponse:
        """Pedir un slot puntual con LLM, validando JSON de salida"""
        ask_for = step.args.get("ask_for", "")
        sys = self._system_prompt(snapshot.vertical)
        usr = f"""
Usuario dice: "{snapshot.user_input}"

Slots actuales: {json.dumps(snapshot.slots, ensure_ascii=False)}
Necesitas obtener información sobre: {ask_for}

Pide SOLO esa información, en una oración, tono cordial. 
Devuelve JSON con "reply" y "updated_state" si el usuario ya la dio.
""".strip()

        # Medir tiempo de LLM
        t0 = time.perf_counter()
        data = await self.llm_client.generate_json(sys, usr)
        llm_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("llm_ms", llm_ms)
        new_slots = dict(snapshot.slots)

        # Incremento de intentos si corresponde
        if inc_attempt:
            new_slots["_attempts_count"] = int(snapshot.attempts_count) + 1

        if not data:
            # fallback seguro
            text = f"¿Podrías decirme {ask_for}?"
            return OrchestratorResponse(
                assistant=text,
                slots=new_slots,
                tool_calls=[],
                context_used=[],
                next_action=NextAction.SLOT_FILL,
                end=False
            )

        # merge de updated_state si vino (con schema-guard)
        upd = self._filter_updated_state(snapshot.vertical, data.get("updated_state") if data else {})
        if upd:
            # Reset validación si cambian slots críticos
            new_slots = self._maybe_reset_validation(snapshot.slots, {**new_slots, **upd}, snapshot.vertical)
            new_slots.update(upd)

        reply = data.get("reply") or f"¿Podrías decirme {ask_for}?"
        # Normalizar slots después de merge
        new_slots = self._normalize_slots(snapshot.vertical, new_slots)
        return OrchestratorResponse(
            assistant=self._clip_reply(reply),
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.SLOT_FILL,
            end=False
        )
    
    async def _handle_retrieve_context(self, snapshot: ConversationSnapshot, step: NextStep) -> OrchestratorResponse:
        """Consulta RAG + compone respuesta breve"""
        query = step.args.get("query") or snapshot.user_input
        filters = step.args.get("filters") or {}

        # Normalizar slots antes de llamar a RAG (consistencia)
        norm_slots = self._normalize_slots(snapshot.vertical, snapshot.slots)
        
        # Medir tiempo de RAG
        t0 = time.perf_counter()
        rag_results = await self.tools_client.retrieve_context(
            conversation_id=snapshot.conversation_id,
            query=query,
            slots=norm_slots,
            filters=filters,
            top_k=8
        )
        rag_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("rag_ms", rag_ms)

        # Heurística mínima con score de RAG (configurable por vertical)
        cfg = self.policy_engine.vertical_configs.get(snapshot.vertical, {})
        min_score = cfg.get("rag_min_score", 0.05)
        top_score = (rag_results[0].get("score") if rag_results else 0) or 0
        if not rag_results or top_score < min_score:
            # sin contexto útil → incrementa intentos para forzar ASK_HUMAN si persiste
            new_slots = dict(snapshot.slots)
            new_slots["_attempts_count"] = int(snapshot.attempts_count) + 1
            return OrchestratorResponse(
                assistant="No encontré información suficiente. ¿Podés darme un poco más de detalle?",
                slots=new_slots,
                tool_calls=[],
                context_used=[],
                next_action=NextAction.ANSWER,
                end=False
            )

        # señalamos que validamos con RAG (desbloquea EXECUTE_ACTION si hacía falta)
        new_slots = dict(snapshot.slots)
        new_slots["_validated_by_rag"] = True

        # Componer respuesta con LLM (JSON)
        sys = self._system_prompt(snapshot.vertical)
        ctx = "\n".join(r.get("text", "") for r in rag_results[:3])
        usr = f"""
Usuario dice: "{snapshot.user_input}"

Contexto (top 3):
{ctx}

Slots actuales: {json.dumps(new_slots, ensure_ascii=False)}

Con ese contexto, responde en 1–2 oraciones y propone el siguiente micro-paso útil (sin listar todo).
Devuelve JSON con "reply" y "updated_state".
""".strip()

        # Medir tiempo de LLM
        t0 = time.perf_counter()
        data = await self.llm_client.generate_json(sys, usr)
        llm_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("llm_ms", llm_ms)
        upd = self._filter_updated_state(snapshot.vertical, (data or {}).get("updated_state"))
        if upd:
            # Reset validación si cambian slots críticos
            new_slots = self._maybe_reset_validation(snapshot.slots, {**new_slots, **upd}, snapshot.vertical)
            new_slots.update(upd)

        reply = (data or {}).get("reply") or "Aquí tienes la información más relevante."
        # Normalizar slots después de merge
        new_slots = self._normalize_slots(snapshot.vertical, new_slots)
        return OrchestratorResponse(
            assistant=self._clip_reply(reply),
            slots=new_slots,
            tool_calls=[{"name": "retrieve_context", "arguments": {"query": query, "filters": filters}}],
            context_used=rag_results,
            next_action=NextAction.RETRIEVE_CONTEXT,
            end=False
        )
    
    async def _handle_execute_action(self, snapshot: ConversationSnapshot, step: NextStep) -> OrchestratorResponse:
        """Ejecuta la acción con idempotencia estable"""
        action_name = step.args.get("action_name") or "unknown_action"
        # Usar business_payload limpio para idempotencia estable (JSON-safe)
        business_payload = self._json_safe(self._business_payload(snapshot.vertical, snapshot.slots, snapshot.conversation_id))
        idem = stable_idempotency_key(snapshot.conversation_id, business_payload, snapshot.vertical)

        # Medir tiempo de acción
        t0 = time.perf_counter()
        result = await self.tools_client.execute_action(
            conversation_id=snapshot.conversation_id,
            action_name=action_name,
            payload=business_payload,
            idempotency_key=idem
        )
        action_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("action_ms", action_ms)

        status = result.get("status")
        summary = result.get("summary") or "Acción ejecutada"

        if status in ("success", "created", "ok"):
            text = f"¡Perfecto! {summary}"
            return OrchestratorResponse(
                assistant=self._clip_reply(text),
                slots=snapshot.slots,
                tool_calls=[{"name": action_name, "arguments": business_payload}],
                context_used=[],
                next_action=NextAction.EXECUTE_ACTION,
                end=True
            )

        logger.warning(f"execute_action fallo: {result}")
        # si falla, no cierres la conversación de una
        new_slots = dict(snapshot.slots)
        new_slots["_attempts_count"] = int(snapshot.attempts_count) + 1
        return OrchestratorResponse(
            assistant=self._clip_reply("No pude completar la acción. ¿Querés que te derive con un humano?"),
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.ASK_HUMAN,
            end=False
        )
    
    async def _handle_ask_human(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """Escalamiento a humano (el ticket se debería crear en otro servicio)"""
        msg = "Te conecto con un agente humano en un momento."
        # Circuit breaker suave: si ya estuvimos aquí, suavizar mensaje
        if snapshot.slots.get("_asked_human_once"):
            msg = "Ya escalé tu caso. En breve te escribe un agente 🙌"
        new_slots = dict(snapshot.slots)
        new_slots["_asked_human_once"] = True
        return OrchestratorResponse(
            assistant=msg,
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.ASK_HUMAN,
            end=True
        )

    async def _handle_answer(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """Respuesta general con LLM (JSON)"""
        sys = self._system_prompt(snapshot.vertical)
        usr = f"""
Usuario dice: "{snapshot.user_input}"
Slots actuales: {json.dumps(snapshot.slots, ensure_ascii=False)}

Responde útil en 1–2 oraciones y sugiere el siguiente paso.
Devuelve JSON con "reply" y "updated_state".
""".strip()

        # Medir tiempo de LLM
        t0 = time.perf_counter()
        data = await self.llm_client.generate_json(sys, usr)
        llm_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("llm_ms", llm_ms)
        new_slots = dict(snapshot.slots)
        upd = self._filter_updated_state(snapshot.vertical, (data or {}).get("updated_state"))
        if upd:
            # Reset validación si cambian slots críticos
            new_slots = self._maybe_reset_validation(snapshot.slots, {**new_slots, **upd}, snapshot.vertical)
            new_slots.update(upd)
        reply = (data or {}).get("reply") or "Entiendo. ¿Podés contarme un poco más para ayudarte mejor?"
        # Normalizar slots después de merge
        new_slots = self._normalize_slots(snapshot.vertical, new_slots)
        return OrchestratorResponse(
            assistant=self._clip_reply(reply),
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.ANSWER,
            end=False
        )
    
    async def close(self):
        await self.llm_client.close()
        await self.tools_client.close()


# Instancia global del servicio
orchestrator_service = OrchestratorService()
