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
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import asyncio
import httpx
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncpg

# Import MCP client instead of tools directly
from services.mcp_client import get_mcp_client
from services.rate_limiter import RateLimiter, RateLimitType, TIER_CONFIGS
from services.tool_manifest import load_tool_manifest
from services.policy_engine import PolicyEngine as NewPolicyEngine, PolicyDecision, PlanAction
from services.tool_broker import get_tool_broker, ToolObservation
from services.state_reducer import get_state_reducer, apply_patch_to_snapshot

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
    CONFIRM_ACTION = "CONFIRM_ACTION"  # Nuevo: Confirmar antes de ejecutar
    EXECUTE_ACTION = "EXECUTE_ACTION"
    ANSWER = "ANSWER"
    ASK_HUMAN = "ASK_HUMAN"

class ConversationSnapshot(BaseModel):
    """Snapshot del estado actual de la conversación"""
    conversation_id: str
    vertical: str
    user_input: str
    workspace_id: str  # Workspace context para tools
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
# Configuración de Business Slots - Esquema Estructurado
# =========================

# Esquema de slots por intent (según recomendaciones ChatGPT)
SLOT_SCHEMAS = {
    "servicios": {
        "book_appointment": {
            "required": ["service_type", "preferred_date", "preferred_time", "client_name"],
            "optional": ["client_email", "client_phone", "staff_preference", "notes"],
            "hints": {
                "service_type": "corte, coloración, barba, brushing, etc.",
                "preferred_date": "aaaa-mm-dd o 'mañana', 'pasado mañana'",
                "preferred_time": "hh:mm formato 24h",
                "client_name": "solo nombre (ej: Juan, María)",
                "client_email": "email@dominio.com (opcional)",
                "staff_preference": "nombre del profesional preferido"
            },
            "validators": {
                "preferred_date": "fecha>=hoy",
                "preferred_time": "regex:^([01]\\d|2[0-3]):[0-5]\\d$",
                "client_email": "regex:^[\\w\\.-]+@[\\w\\.-]+\\.[a-zA-Z]{2,}$"
            },
            "dependencies": {
                "duration_minutes": "derive(service_type)"  # Se deriva del catálogo
            }
        }
    },
    "gastronomia": {
        "place_order": {
            "required": ["categoria", "items", "metodo_entrega"],
            "optional": ["direccion", "metodo_pago", "notas", "extras"],
            "hints": {
                "categoria": "entrada, plato principal, postre, bebida",
                "items": "lista de platos específicos",
                "metodo_entrega": "delivery, takeaway, mesa"
            }
        }
    },
    "inmobiliaria": {
        "schedule_visit": {
            "required": ["operation", "type", "zone"],
            "optional": ["price_range", "bedrooms", "bathrooms", "preferred_date"],
            "hints": {
                "operation": "compra, alquiler, venta",
                "type": "casa, apartamento, oficina",
                "zone": "barrio o zona específica"
            }
        }
    }
}

# Backward compatibility - slots planos para funciones existentes
BUSINESS_SLOTS = {
    "gastronomia": ["categoria", "items", "metodo_entrega", "direccion", "metodo_pago", "notas", "workspace_id", "conversation_id"],
    "inmobiliaria": ["operation", "type", "zone", "price_range", "bedrooms", "bathrooms", "property_id", "preferred_date", "contact_info", "workspace_id", "conversation_id"],
    "servicios": ["service_type", "preferred_date", "preferred_time", "staff_preference", "notes", "client_name", "client_email", "client_phone", "workspace_id", "conversation_id"],
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
# Validadores de Slots
# =========================

import re
from datetime import datetime, timedelta

class SlotValidator:
    """Validadores para slots según las recomendaciones de ChatGPT"""
    
    @staticmethod
    def validate_date(date_str: str) -> tuple[bool, str]:
        """Validar que la fecha no sea pasada"""
        if not date_str:
            return False, "Fecha requerida"
        
        try:
            # Parsear fecha en formato YYYY-MM-DD
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            
            if date_obj < today:
                return False, "No puedo agendar turnos para fechas pasadas"
            
            # Verificar que no sea más de 3 meses en el futuro
            max_date = today + timedelta(days=90)
            if date_obj > max_date:
                return False, "Solo agendo turnos hasta 3 meses adelante"
            
            return True, ""
        except ValueError:
            return False, "Formato de fecha inválido"
    
    @staticmethod
    def validate_time(time_str: str) -> tuple[bool, str]:
        """Validar que el horario esté dentro del horario de atención"""
        if not time_str:
            return False, "Horario requerido"
        
        try:
            # Parsear hora en formato HH:MM
            time_obj = datetime.strptime(time_str, "%H:%M").time()
            
            # Horario de atención: 9:00 a 18:00
            opening = datetime.strptime("09:00", "%H:%M").time()
            closing = datetime.strptime("18:00", "%H:%M").time()
            
            if time_obj < opening or time_obj > closing:
                return False, "Nuestro horario de atención es de 9:00 a 18:00"
            
            return True, ""
        except ValueError:
            return False, "Formato de hora inválido (usar HH:MM)"
    
    @staticmethod
    def validate_email(email_str: str) -> tuple[bool, str]:
        """Validar formato de email (opcional pero si se provee debe ser válido)"""
        if not email_str:
            return True, ""  # Email es opcional
        
        # Regex básico para email
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email_str):
            return True, ""
        else:
            return False, "Formato de email inválido"
    
    @staticmethod
    def validate_client_name(name_str: str) -> tuple[bool, str]:
        """Validar que el nombre no esté vacío y tenga formato apropiado"""
        if not name_str or not name_str.strip():
            return False, "Nombre requerido"
        
        # Verificar que tenga al menos 2 caracteres y solo letras/espacios
        name_clean = name_str.strip()
        if len(name_clean) < 2:
            return False, "El nombre debe tener al menos 2 caracteres"
        
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', name_clean):
            return False, "El nombre solo puede contener letras y espacios"
        
        return True, ""
    
    @staticmethod
    def validate_service_type(service_str: str) -> tuple[bool, str]:
        """Validar que el tipo de servicio sea válido"""
        if not service_str:
            return False, "Tipo de servicio requerido"
        
        # Lista de servicios válidos y sus variaciones
        service_mappings = {
            "corte de cabello": "Corte de Cabello",
            "corte de pelo": "Corte de Cabello", 
            "corte": "Corte de Cabello",
            "coloracion": "Coloración",
            "coloración": "Coloración",
            "tinte": "Coloración",
            "barba": "Barba",
            "brushing": "Brushing",
            "tratamiento": "Tratamiento",
            "permanente": "Permanente",
            "mechas": "Mechas"
        }
        
        # Normalizar entrada
        service_normalized = service_str.lower().strip()
        
        if service_normalized in service_mappings:
            return True, ""
        elif service_str in service_mappings.values():
            return True, ""  # Ya está en formato correcto
        else:
            valid_services = list(set(service_mappings.values()))
            return False, f"Servicio no disponible. Servicios válidos: {', '.join(valid_services)}"

# Mapeo de validadores por campo
SLOT_VALIDATORS = {
    "preferred_date": SlotValidator.validate_date,
    "preferred_time": SlotValidator.validate_time,
    "client_email": SlotValidator.validate_email,
    "client_name": SlotValidator.validate_client_name,
    "service_type": SlotValidator.validate_service_type,
}

# =========================
# Sistema de Memoria Conversacional
# =========================

from dataclasses import dataclass
from typing import Optional
import hashlib

@dataclass
class ConversationSummary:
    """Capa 2: Short-Term Memory - Resumen de conversaciones del día/semana"""
    conversation_id: str
    client_phone: str
    workspace_id: str
    summary_text: str
    key_facts: Dict[str, Any]  # Hechos clave extraídos
    last_interaction: datetime
    interaction_count: int
    created_at: datetime
    updated_at: datetime

@dataclass 
class ClientProfile:
    """Capa 3: Long-Term Memory - Perfil completo del cliente"""
    client_phone: str
    workspace_id: str
    name: Optional[str]
    email: Optional[str]
    preferences: Dict[str, Any]  # Servicios preferidos, horarios, etc.
    interaction_history: Dict[str, Any]  # Estadísticas de interacciones
    lead_score: int  # 0-100, para priorización
    tags: List[str]  # Etiquetas de negocio
    created_at: datetime
    updated_at: datetime

class ConversationalMemory:
    """Gestor del sistema de memoria conversacional de 3 capas"""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        # Importaciones locales para evitar problemas de dependencias
        import psycopg2
        from psycopg2.extras import RealDictCursor
        self.psycopg2 = psycopg2
        self.RealDictCursor = RealDictCursor
    
    def _get_client_phone(self, conversation_id: str) -> Optional[str]:
        """Extraer teléfono del cliente desde conversation_id o contexto"""
        # TODO: Implementar extracción real del teléfono
        # Por ahora, usar un hash del conversation_id como placeholder
        return hashlib.md5(conversation_id.encode()).hexdigest()[:12]
    
    async def load_working_memory(self, conversation_id: str, workspace_id: str) -> Dict[str, Any]:
        """
        Carga 1: Working Memory - Estado actual de la conversación
        Siempre se carga, es el estado base
        """
        # Esta es la funcionalidad existente (dialogue_states.slots)
        # No necesita cambios, ya está implementada
        return {}
    
    async def load_short_term_memory(self, conversation_id: str, workspace_id: str) -> Optional[ConversationSummary]:
        """
        Carga 2: Short-Term Memory - Conversaciones recientes del mismo cliente
        Se carga si última interacción < 8 horas
        """
        client_phone = self._get_client_phone(conversation_id)
        if not client_phone:
            return None
        
        try:
            # Buscar conversaciones recientes del mismo cliente
            conn = self.psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            
            # Buscar resumen más reciente del cliente en las últimas 8 horas
            cursor.execute("""
                SELECT * FROM pulpo.conversation_summaries 
                WHERE client_phone = %s 
                  AND workspace_id = %s 
                  AND last_interaction > NOW() - INTERVAL '8 hours'
                ORDER BY last_interaction DESC 
                LIMIT 1
            """, (client_phone, workspace_id))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result:
                return ConversationSummary(
                    conversation_id=result['conversation_id'],
                    client_phone=result['client_phone'],
                    workspace_id=result['workspace_id'],
                    summary_text=result['summary_text'],
                    key_facts=result['key_facts'],
                    last_interaction=result['last_interaction'],
                    interaction_count=result['interaction_count'],
                    created_at=result['created_at'],
                    updated_at=result['updated_at']
                )
            
        except Exception as e:
            logger.warning(f"[MEMORY] Error cargando short-term memory: {e}")
        
        return None
    
    async def load_long_term_memory(self, conversation_id: str, workspace_id: str) -> Optional[ClientProfile]:
        """
        Carga 3: Long-Term Memory - Perfil completo del cliente
        Se carga solo para clientes recurrentes (>3 interacciones)
        """
        client_phone = self._get_client_phone(conversation_id)
        if not client_phone:
            return None
        
        try:
            conn = self.psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=self.RealDictCursor)
            
            # Buscar perfil del cliente
            cursor.execute("""
                SELECT * FROM pulpo.client_profiles 
                WHERE client_phone = %s AND workspace_id = %s
            """, (client_phone, workspace_id))
            
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result and result['interaction_history'].get('total_interactions', 0) >= 3:
                return ClientProfile(
                    client_phone=result['client_phone'],
                    workspace_id=result['workspace_id'],
                    name=result['name'],
                    email=result['email'],
                    preferences=result['preferences'],
                    interaction_history=result['interaction_history'],
                    lead_score=result['lead_score'],
                    tags=result['tags'],
                    created_at=result['created_at'],
                    updated_at=result['updated_at']
                )
            
        except Exception as e:
            logger.warning(f"[MEMORY] Error cargando long-term memory: {e}")
        
        return None
    
    async def save_conversation_summary(self, conversation_id: str, workspace_id: str, 
                                      summary_text: str, key_facts: Dict[str, Any]) -> None:
        """Guardar resumen de conversación en short-term memory"""
        client_phone = self._get_client_phone(conversation_id)
        if not client_phone:
            return
        
        try:
            conn = self.psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            # Upsert conversation summary
            cursor.execute("""
                INSERT INTO pulpo.conversation_summaries 
                (conversation_id, client_phone, workspace_id, summary_text, key_facts, 
                 last_interaction, interaction_count, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), 1, NOW(), NOW())
                ON CONFLICT (client_phone, workspace_id) 
                DO UPDATE SET
                    conversation_id = EXCLUDED.conversation_id,
                    summary_text = EXCLUDED.summary_text,
                    key_facts = EXCLUDED.key_facts,
                    last_interaction = NOW(),
                    interaction_count = conversation_summaries.interaction_count + 1,
                    updated_at = NOW()
            """, (conversation_id, client_phone, workspace_id, summary_text, 
                  json.dumps(key_facts)))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"[MEMORY] Guardado resumen de conversación para {client_phone}")
            
        except Exception as e:
            logger.error(f"[MEMORY] Error guardando conversation summary: {e}")
    
    async def update_client_profile(self, conversation_id: str, workspace_id: str,
                                   name: Optional[str] = None, email: Optional[str] = None,
                                   preferences: Optional[Dict[str, Any]] = None) -> None:
        """Actualizar perfil del cliente en long-term memory"""
        client_phone = self._get_client_phone(conversation_id)
        if not client_phone:
            return
        
        try:
            conn = self.psycopg2.connect(self.db_url)
            cursor = conn.cursor()
            
            # Upsert client profile
            cursor.execute("""
                INSERT INTO pulpo.client_profiles 
                (client_phone, workspace_id, name, email, preferences, 
                 interaction_history, lead_score, tags, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, 0, %s, NOW(), NOW())
                ON CONFLICT (client_phone, workspace_id) 
                DO UPDATE SET
                    name = COALESCE(EXCLUDED.name, client_profiles.name),
                    email = COALESCE(EXCLUDED.email, client_profiles.email),
                    preferences = COALESCE(EXCLUDED.preferences, client_profiles.preferences),
                    interaction_history = jsonb_set(
                        client_profiles.interaction_history,
                        '{total_interactions}',
                        (COALESCE((client_profiles.interaction_history->>'total_interactions')::int, 0) + 1)::text::jsonb
                    ),
                    updated_at = NOW()
            """, (client_phone, workspace_id, name, email, 
                  json.dumps(preferences or {}), 
                  json.dumps({"total_interactions": 1}),
                  json.dumps([])))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            logger.info(f"[MEMORY] Actualizado perfil de cliente para {client_phone}")
            
        except Exception as e:
            logger.error(f"[MEMORY] Error actualizando client profile: {e}")

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
                "required_slots": ["service_type", "preferred_date", "preferred_time", "client_name"],
                "optional_slots": ["client_email", "client_phone", "staff_preference", "notes"],
                "max_attempts": 3,
                "needs_rag_before_action": False,  # muchas veces podés accionar directo
                "rag_min_score": 0.03
            }
        }
    
    async def enforce_policy(self, snapshot: ConversationSnapshot, orchestrator) -> NextStep:
        """
        Aplica políticas deterministas + intent detection para decidir el próximo paso.

        Args:
            snapshot: Estado actual de la conversación
            orchestrator: Referencia al orchestrator (para _detect_intent_with_llm)
        """
        cfg = self.vertical_configs.get(snapshot.vertical, {
            "required_slots": [],
            "optional_slots": [],
            "max_attempts": 3,
            "needs_rag_before_action": True
        })
        required_slots = cfg["required_slots"]
        max_attempts = cfg["max_attempts"]

        # 0) CONFIRM_ACTION: Si está esperando confirmación, manejar respuesta
        if snapshot.slots.get("_awaiting_confirmation"):
            logger.info(f"[POLICY] → CONFIRM_ACTION (respondiendo a confirmación)")
            return NextStep(
                next_action=NextAction.CONFIRM_ACTION,
                args={"action_name": self._get_action_name(snapshot.vertical)},
                reason="Cliente respondiendo a confirmación pendiente"
            )

        # 1) Saludo - SOLO si greeted=false Y no está en slots tampoco
        greeted_in_slots = snapshot.slots.get("greeted", False)
        if not snapshot.greeted and not greeted_in_slots:
            return NextStep(
                next_action=NextAction.GREET,
                args={"greeting_type": "initial"},
                reason="Usuario no ha sido saludado aún"
            )

        # 2) INTENT DETECTION con LLM (re-evaluar en CADA turno, NO cachear)
        # El usuario puede cambiar de intención durante la conversación
        # Ej: Turn 1 "¿cuánto sale?" (info_query) → Turn 5 "quiero turno mañana" (execute_action)
        intent_data = await orchestrator._detect_intent_with_llm(snapshot)
        user_intent = intent_data["intent"]
        intent_confidence = intent_data["confidence"]

        # Guardar en slots para telemetría (pero NO usar como cache)
        snapshot.slots["_intent"] = user_intent
        snapshot.slots["_intent_confidence"] = intent_confidence
        snapshot.slots["_intent_reason"] = intent_data["reason"]

        # IMPORTANTE: Normalizar slots ANTES de evaluar completitud
        # Esto convierte "mañana" → "2025-10-08", "10am" → "10:00", etc.
        snapshot.slots = orchestrator._normalize_slots(snapshot.vertical, snapshot.slots)
        
        # VALIDACIÓN: Si hay errores de validación, pedir corrección
        validation_errors = snapshot.slots.get("_validation_errors", [])
        if validation_errors:
            logger.info(f"[POLICY] Errores de validación detectados: {validation_errors}")
            return NextStep(
                next_action=NextAction.ANSWER,
                args={"validation_errors": validation_errors},
                reason=f"Corregir errores de validación: {', '.join(validation_errors)}"
            )

        # 3) PRIORIDAD: Si todos los slots requeridos están completos → EJECUTAR ACCIÓN
        # (evaluar ANTES de intent routing para evitar loops infinitos de RETRIEVE_CONTEXT)
        missing_slots = [s for s in required_slots if not snapshot.slots.get(s)]
        all_required_ready = len(missing_slots) == 0

        logger.info(f"[POLICY] Slots check - Required: {required_slots}, Missing: {missing_slots}, All ready: {all_required_ready}")
        logger.info(f"[POLICY] Current slots: {dict(snapshot.slots)}")

        if all_required_ready:
            needs_validation = cfg["needs_rag_before_action"]
            already_validated = snapshot.slots.get("_validated_by_rag", False)
            
            logger.info(f"[POLICY] Validation check - Needs: {needs_validation}, Already validated: {already_validated}")
            
            # 3.a) ¿Necesitamos validación antes de accionar? (Tool o RAG según vertical)
            if needs_validation and not already_validated:
                # Para servicios: usar tool, para otros: RAG
                tool_name, tool_args = self._decide_tool(snapshot, intent=user_intent)

                if tool_name:
                    # Usar tool (servicios)
                    logger.info(f"[POLICY] → RETRIEVE_CONTEXT (validar con tool: {tool_name})")
                    return NextStep(
                        next_action=NextAction.RETRIEVE_CONTEXT,
                        args={"tool_name": tool_name, "tool_args": tool_args, "use_tool": True},
                        reason=f"Validar con tool: {tool_name} antes de ejecutar"
                    )
                else:
                    # Usar RAG (gastronomía, inmobiliaria)
                    logger.info(f"[POLICY] → RETRIEVE_CONTEXT (validar con RAG)")
                    return NextStep(
                        next_action=NextAction.RETRIEVE_CONTEXT,
                        args={"query": self._build_query_from_slots(snapshot),
                              "filters": self._build_filters_from_slots(snapshot),
                              "use_tool": False},
                        reason="Validar con RAG antes de accionar"
                    )

            # 3.b) Si estamos listos y validados (o no hace falta validar), confirmar primero
            logger.info(f"[POLICY] → CONFIRM_ACTION (todos los slots listos, solicitar confirmación)")
            return NextStep(
                next_action=NextAction.CONFIRM_ACTION,
                args={"action_name": self._get_action_name(snapshot.vertical)},
                reason="Slots requeridos completos → solicitar confirmación antes de ejecutar"
            )

        # 4) ROUTING basado en intent detectado (solo si NO están todos los slots completos)

        # 4a) Si es consulta informacional → RETRIEVE_CONTEXT inmediatamente
        if user_intent == "info_query" and intent_confidence > 0.6:
            tool_name, tool_args = self._decide_tool(snapshot, intent=user_intent)

            if tool_name:
                # Usar tool (servicios)
                return NextStep(
                    next_action=NextAction.RETRIEVE_CONTEXT,
                    args={"tool_name": tool_name, "tool_args": tool_args, "use_tool": True},
                    reason=f"Intent: info_query (conf={intent_confidence:.2f}) → tool: {tool_name}"
                )
            elif self._has_slots_for_query(snapshot):
                # Usar RAG (gastronomía, inmobiliaria)
                return NextStep(
                    next_action=NextAction.RETRIEVE_CONTEXT,
                    args={"query": self._build_query_from_slots(snapshot),
                          "filters": self._build_filters_from_slots(snapshot),
                          "use_tool": False},
                    reason=f"Intent: info_query (conf={intent_confidence:.2f}) → RAG"
                )

        # 4b) Si faltan slots requeridos → SLOT_FILL (independiente del intent)
        # MEJORA: No condicionar a execute_action - el usuario puede dar info con cualquier intent
        if missing_slots and snapshot.attempts_count < max_attempts:
            # Verificar si el usuario quiere hacer una acción O ya está en proceso de slot filling
            user_wants_action = (user_intent == "execute_action" and intent_confidence > 0.6)
            already_in_process = snapshot.slots.get("service_type") or snapshot.slots.get("_attempts_count", 0) > 0
            
            if user_wants_action or already_in_process:
                # POLÍTICA ONE-SLOT-PER-TURN: Pedir slots en orden lógico
                next_slot = self._get_next_slot_to_ask(snapshot.vertical, missing_slots, snapshot.slots)
                return NextStep(
                    next_action=NextAction.SLOT_FILL,
                    args={"missing_slots": missing_slots, "ask_for": next_slot},
                    reason=f"Política one-slot-per-turn: pidiendo '{next_slot}' (faltan: {missing_slots})"
                )

        # 4) Si no hay requeridos, pero sí hay señales parciales → intentar obtener info (Tool o RAG)
        if self._has_slots_for_query(snapshot):
            tool_name, tool_args = self._decide_tool(snapshot, intent=user_intent)

            if tool_name:
                # Usar tool (servicios)
                return NextStep(
                    next_action=NextAction.RETRIEVE_CONTEXT,
                    args={"tool_name": tool_name, "tool_args": tool_args, "use_tool": True},
                    reason=f"Obtener info con tool: {tool_name}"
                )
            else:
                # Usar RAG (gastronomía, inmobiliaria)
                return NextStep(
                    next_action=NextAction.RETRIEVE_CONTEXT,
                    args={"query": self._build_query_from_slots(snapshot),
                          "filters": self._build_filters_from_slots(snapshot),
                          "use_tool": False},
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
        """Determina si hay suficiente información para hacer una consulta (tool o RAG)"""

        if snapshot.vertical == "gastronomia":
            return bool(snapshot.slots.get("categoria") or snapshot.slots.get("items"))

        if snapshot.vertical == "inmobiliaria":
            # pedir al menos operación + zona o tipo
            return bool(snapshot.slots.get("operation") and (snapshot.slots.get("type") or snapshot.slots.get("zone")))

        if snapshot.vertical == "servicios":
            # Si ya tiene slot de servicio, sí
            if snapshot.slots.get("service_type"):
                return True

            # Detectar queries informacionales en el user_input
            user_lower = snapshot.user_input.lower()

            # Keywords que indican consulta de información
            info_keywords = [
                "qué", "cuanto", "cuál", "precio", "costo", "servicio",
                "ofrec", "tien", "hay", "disponi", "horario", "promocion",
                "descuento", "paquete", "combo"
            ]

            # Si el usuario pregunta algo, podemos consultar
            return any(kw in user_lower for kw in info_keywords)

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

    def _decide_tool(self, snapshot: ConversationSnapshot, intent: str = "general_chat") -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Decide qué tool llamar basado en intent detectado, entidades mencionadas y vertical

        Args:
            snapshot: Estado de la conversación
            intent: Intent detectado (info_query, execute_action, modify_action, general_chat)

        Returns:
            (tool_name, tool_args) o (None, {}) si no aplica tool
        """
        import re

        if snapshot.vertical != "servicios":
            # Otros verticales usan RAG por ahora
            return (None, {})

        workspace_id = snapshot.workspace_id
        slots = snapshot.slots
        user_input_lower = snapshot.user_input.lower()

        # POLÍTICA TOOLS_FIRST: Detectar entidades que SIEMPRE requieren tools
        # (según recomendaciones ChatGPT - NUNCA inventar precios/servicios/horarios)
        asks_promotion = bool(re.search(r'\b(promocion|promo|descuento|oferta|rebaja)\b', user_input_lower))
        asks_package = bool(re.search(r'\b(paquete|combo|pack|conjunto)\b', user_input_lower))
        asks_hours = bool(re.search(r'\b(horario|abre|cierra|atiende?n?|abiert[oa]s?|cerrad[oa]s?|funcionan?)\b', user_input_lower))
        mentions_price = bool(re.search(r'\b(precio|cuanto|cuesta|vale|sale|costo|tarifa|valor)\b', user_input_lower))
        mentions_service = bool(re.search(r'\b(servicio|corte|color|tratamiento|permanente|depilacion|brushing|barba|coloracion|tinte|mechas)\b', user_input_lower))
        mentions_staff = bool(re.search(r'\b(profesional|peluquer[oa]|estilista|quien|quienes|atiende|trabaja|especialista)\b', user_input_lower))
        asks_availability = bool(re.search(r'\b(disponible|libre|turno|cita|agenda|horario|cuando|dia|fecha)\b', user_input_lower))
        
        # CRÍTICO: Si pregunta por servicios/precios/staff → SIEMPRE usar tool
        needs_tool_info = mentions_price or mentions_service or mentions_staff or asks_availability

        # === ROUTING BASADO EN INTENT ===

        if intent == "info_query":
            # POLÍTICA TOOLS_FIRST: Cliente pregunta información → SIEMPRE usar tools, NUNCA inventar

            # Prioridad 1: Promociones
            if asks_promotion:
                return ("get_active_promotions", {"workspace_id": workspace_id})

            # Prioridad 2: Paquetes
            if asks_package:
                return ("get_service_packages", {"workspace_id": workspace_id})

            # Prioridad 3: Horarios del negocio
            if asks_hours and not needs_tool_info:
                # Solo si pregunta SOLO por horarios (no "qué horario tengo para mi turno")
                return ("get_business_hours", {"workspace_id": workspace_id})

            # Prioridad 4: CRÍTICO - Cualquier consulta sobre servicios/precios/staff
            if needs_tool_info:
                return ("get_available_services", {"workspace_id": workspace_id})

            # Default para info_query: listar servicios (mejor que respuesta genérica)
            return ("get_available_services", {"workspace_id": workspace_id})

        elif intent == "execute_action":
            # Cliente quiere ejecutar acción (agendar, reservar, etc.)

            # Si tiene servicio + fecha → verificar disponibilidad específica
            if slots.get("service_type") and slots.get("preferred_date"):
                return ("check_service_availability", {
                    "workspace_id": workspace_id,
                    "service_name": slots["service_type"],
                    "date_str": slots["preferred_date"],
                    "time_str": slots.get("preferred_time")
                })

            # Si no tiene slots completos → mostrar opciones de servicios
            return ("get_available_services", {"workspace_id": workspace_id})

        elif intent == "modify_action":
            # Cliente quiere modificar/cancelar algo existente
            # Por ahora, listar servicios para contexto
            return ("get_available_services", {"workspace_id": workspace_id})

        else:
            # general_chat o intent desconocido
            # Fallback: listar servicios disponibles
            return ("get_available_services", {"workspace_id": workspace_id})

    def _format_tool_result(self, tool_result: Dict[str, Any]) -> str:
        """
        Formatea resultado de tool para el prompt del LLM

        Args:
            tool_result: Resultado del tool

        Returns:
            String formateado para incluir en el prompt
        """
        if not tool_result.get("success"):
            return f"[ERROR] {tool_result.get('error', 'Error desconocido')}"

        # get_available_services
        if "services" in tool_result:
            services = tool_result["services"]
            if not services:
                return "[INFO] No hay servicios disponibles en este momento."

            text = "[SERVICIOS DISPONIBLES]\n"
            for svc in services:
                # Soportar formato nuevo (con staff_options) y viejo (sin staff_options)
                if svc.get('staff_options') and len(svc['staff_options']) > 0:
                    # Formato con precios por staff
                    price_min = svc.get('price_min', 0)
                    price_max = svc.get('price_max', 0)
                    staff_count = svc.get('staff_count', 0)

                    if price_min == price_max:
                        text += f"• {svc['name']}: ${price_min} ARS\n"
                    else:
                        text += f"• {svc['name']}: desde ${price_min} hasta ${price_max} ARS ({staff_count} profesionales)\n"

                    # Listar profesionales
                    for staff in svc['staff_options'][:3]:  # Máximo 3
                        text += f"  - {staff['staff_name']}: ${staff['price']} ({staff['duration_minutes']} min)\n"
                else:
                    # Formato viejo (sin staff)
                    price = svc.get('price', svc.get('price_min', 0))
                    duration = svc.get('duration_minutes', 0)
                    text += f"• {svc['name']}: ${price} ({duration} minutos)\n"

                if svc.get('description'):
                    text += f"  {svc['description']}\n"
            return text.strip()

        # check_service_availability
        if "time_slots" in tool_result:
            service_info = tool_result.get("service_info", {})
            if tool_result["available"]:
                slots = tool_result["time_slots"]
                text = f"[DISPONIBILIDAD PARA {service_info.get('name', 'servicio')}]\n"
                text += f"Precio: ${service_info.get('price', 0)}\n"
                text += f"Duración: {service_info.get('duration_minutes', 0)} minutos\n"
                text += f"Horarios disponibles: {', '.join(slots[:8])}"  # Primeros 8
                if len(slots) > 8:
                    text += f" (y {len(slots)-8} más)"
                return text
            else:
                return f"[NO DISPONIBLE] {tool_result.get('reason', 'Sin disponibilidad en ese horario')}"

        # get_service_packages
        if "packages" in tool_result:
            packages = tool_result["packages"]
            if not packages:
                return "[INFO] No hay paquetes disponibles."

            text = "[PAQUETES DISPONIBLES]\n"
            for pkg in packages:
                text += f"• {pkg['name']}: ${pkg['package_price']}\n"
                text += f"  Incluye: {', '.join(pkg['services'])}\n"
                if pkg.get('savings'):
                    text += f"  Ahorrás: ${pkg['savings']}\n"
            return text.strip()

        # get_active_promotions
        if "promotions" in tool_result:
            promos = tool_result["promotions"]
            if not promos:
                return "[INFO] No hay promociones activas en este momento."

            text = "[PROMOCIONES ACTIVAS]\n"
            for promo in promos:
                text += f"• {promo['name']}: "
                if promo["discount_type"] == "percentage":
                    text += f"{promo['discount_value']}% OFF\n"
                elif promo["discount_type"] == "fixed_amount":
                    text += f"${promo['discount_value']} de descuento\n"
                else:
                    text += f"Servicio gratis\n"

                if promo.get('description'):
                    text += f"  {promo['description']}\n"
            return text.strip()

        # get_business_hours
        if "hours" in tool_result:
            hours = tool_result["hours"]
            text = "[HORARIOS DE ATENCIÓN]\n"
            day_names_es = {
                "monday": "Lunes", "tuesday": "Martes", "wednesday": "Miércoles",
                "thursday": "Jueves", "friday": "Viernes", "saturday": "Sábado", "sunday": "Domingo"
            }

            for day_en, day_es in day_names_es.items():
                if day_en in hours:
                    day_info = hours[day_en]
                    if day_info.get("open"):
                        blocks = day_info.get("blocks", [])
                        times = ", ".join([f"{b['open']}-{b['close']}" for b in blocks])
                        text += f"{day_es}: {times}\n"
                    else:
                        text += f"{day_es}: Cerrado\n"

            return text.strip()

        # Default: JSON dump
        return f"[TOOL RESULT]\n{json.dumps(tool_result, ensure_ascii=False, indent=2)}"

    def _get_action_name(self, vertical: str) -> str:
        actions = {
            "gastronomia": "crear_pedido",
            "inmobiliaria": "schedule_visit",
            "servicios": "schedule_appointment"  # Acción para agendamiento de turnos
        }
        return actions.get(vertical, "unknown_action")
    
    def _get_next_slot_to_ask(self, vertical: str, missing_slots: List[str], current_slots: Dict[str, Any]) -> str:
        """
        Implementa política ONE-SLOT-PER-TURN: decide qué slot pedir según orden lógico.
        
        Args:
            vertical: Vertical del negocio (servicios, gastronomia, etc.)
            missing_slots: Lista de slots que faltan
            current_slots: Slots actuales ya completados
            
        Returns:
            El próximo slot a pedir según prioridad lógica
        """
        # Orden de prioridad por vertical (según recomendaciones ChatGPT)
        priority_order = {
            "servicios": [
                "service_type",      # 1. Qué servicio quiere (crítico para todo lo demás)
                "preferred_date",    # 2. Cuándo (para chequear disponibilidad)
                "preferred_time",    # 3. A qué hora (específico)
                "client_name"        # 4. Nombre para confirmar
            ],
            "gastronomia": [
                "categoria",         # 1. Tipo de comida
                "items",            # 2. Platos específicos
                "metodo_entrega"    # 3. Cómo lo quiere
            ],
            "inmobiliaria": [
                "operation",        # 1. Compra/alquiler/venta
                "type",            # 2. Casa/apartamento
                "zone"             # 3. Zona/barrio
            ]
        }
        
        # Obtener orden para este vertical
        order = priority_order.get(vertical, missing_slots)
        
        # Encontrar el primer slot en el orden que esté faltando
        for slot in order:
            if slot in missing_slots:
                return slot
        
        # Fallback: si no encontramos nada en el orden, devolver el primero que falte
        return missing_slots[0] if missing_slots else ""

# =========================
# Clientes HTTP (LLM / Tools)
# =========================

class LLMClient:
    """Cliente para comunicación con el LLM (Ollama)"""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or os.getenv("OLLAMA_URL", "http://localhost:11434")
        # Usar modelo desde env o default a qwen2.5:14b (mejor para extracción)
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        # Timeout aumentado para modelos más grandes (10s)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

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
                "format": "json",
                "options": {
                    "temperature": 0.8,  # Más creatividad para respuestas variadas
                    "top_p": 0.9,
                    "repeat_penalty": 1.1  # Evitar repeticiones
                }
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

    def __init__(self, rag_url: str = None, actions_url: str = None):
        # Leer desde env vars con fallback a Docker networking
        self.rag_service_url = rag_url or os.getenv("RAG_URL", "http://rag:8007")
        self.actions_service_url = actions_url or os.getenv("ACTIONS_URL", "http://actions:8004")
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

    def __init__(self, enable_agent_loop: bool = False):
        """
        Args:
            enable_agent_loop: Si True, usa el nuevo loop de agente (Planner → Policy → Broker → Reducer)
                              Si False, usa el sistema anterior (Intent Detection + Decision Tree)
        """
        self.enable_agent_loop = enable_agent_loop
        self.policy_engine = PolicyEngine()
        self.llm_client = LLMClient()
        self.tools_client = ToolsClient()
        self._system_cache: Dict[str, str] = {}  # cache de prompts por vertical
        self.db_url = "postgresql://pulpo:pulpo@localhost:5432/pulpo"
        self.memory = ConversationalMemory(self.db_url)
        self.db_pool = None  # Pool de conexiones asyncpg
        self.database_url = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@postgres:5432/pulpo")
        
        # Rate Limiter para protección contra abuso
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
        self.rate_limiter = RateLimiter(redis_url)
        
        logger.info(f"[ORCHESTRATOR] Initialized with agent_loop={'enabled' if enable_agent_loop else 'disabled'}")

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
                    # asyncpg devuelve jsonb como dict, no necesita conversión
                    metadata = row["metadata"] if row["metadata"] else {}
                    messages.append({
                        "sender": row["sender"],
                        "content": row["content"],
                        "message_type": row["message_type"],
                        "metadata": metadata,
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
                metadata_raw = msg.get("metadata", {})

                # Si metadata es string JSON, parsearlo
                if isinstance(metadata_raw, str):
                    try:
                        metadata = json.loads(metadata_raw)
                    except:
                        metadata = {}
                else:
                    metadata = metadata_raw

                # Slots guardados en metadata (puede ser dict o string JSON)
                if "slots" in metadata:
                    slots_data = metadata["slots"]
                    if isinstance(slots_data, str):
                        try:
                            state["slots"] = json.loads(slots_data)
                        except:
                            state["slots"] = {}
                    elif isinstance(slots_data, dict):
                        state["slots"] = slots_data
                    else:
                        state["slots"] = {}

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

    # ---------- intent detection ----------

    async def _detect_intent_with_llm(self, snapshot: ConversationSnapshot) -> dict:
        """
        Detecta la intención del usuario usando LLM dedicado.
        Usa intents genéricos cross-vertical con ejemplos específicos por vertical.

        Returns:
            dict con keys: intent, confidence, reason
        """
        # Obtener ejemplos específicos de la vertical
        from services.vertical_manager import vertical_manager
        vertical_config = vertical_manager.get_vertical_config(snapshot.vertical)
        examples = vertical_config.intent_examples if vertical_config else []
        examples_text = "\n".join(f"- {ex}" for ex in examples) if examples else "No examples available"

        sys = f"""Eres un clasificador de intenciones para asistente conversacional.

TU TAREA: Clasificar la intención principal del mensaje del cliente.

INTENCIONES POSIBLES (genéricas, cross-vertical):

1. **info_query**: Cliente pregunta información
   - Precios, costos, tarifas
   - Productos/servicios disponibles
   - Horarios de atención
   - Características, detalles
   - Disponibilidad
   - Promociones/descuentos

2. **execute_action**: Cliente quiere realizar una acción
   - Agendar, reservar, pedir, comprar
   - Indica fecha/hora + intención de acción
   - Verbos de acción: "quiero", "necesito", "me gustaría"

3. **modify_action**: Cliente quiere cambiar/cancelar algo existente
   - Cancelar, reprogramar, modificar
   - Referencia a algo ya hecho ("mi turno", "mi pedido")

4. **general_chat**: Conversación general
   - Saludos, despedidas
   - Agradecimientos
   - Confirmaciones vagas
   - Preguntas sin contexto claro

REGLAS CRÍTICAS (aplicar en orden):

1. **execute_action** (PRIORIDAD ALTA):
   - Verbos de intención: "quiero", "necesito", "me gustaría", "voy a", "quería"
   - Acciones específicas: "turno", "cita", "reserva", "agendar", "pedir"
   - Ejemplos: "quiero turno", "necesito cita", "me gustaría agendar"
   - INCLUSO SIN fecha/hora → sigue siendo execute_action

2. **info_query**:
   - Preguntas explícitas: ¿cuánto?, ¿qué?, ¿cuál?, ¿cómo?, ¿dónde?
   - Consultas sin intención de acción: "que servicios tenes", "cuanto sale"
   - NO tiene verbos de intención

3. **modify_action**:
   - Referencias a algo existente: "mi turno", "mi pedido", "la reserva"
   - Verbos de cambio: "cancelar", "cambiar", "reprogramar"

4. **general_chat**:
   - Saludos: "hola", "buenos días"
   - Respuestas corteses: "muy bien", "gracias"
   - Sin intención clara

IMPORTANTE: "quiero turno" = execute_action (NO info_query)
Confidence: 0.9+ si es obvio, 0.7-0.8 si razonable, <0.6 si ambiguo

EJEMPLOS PARA VERTICAL "{snapshot.vertical}":
{examples_text}
"""

        usr = f"""
Mensaje del cliente: "{snapshot.user_input}"

Contexto de la conversación:
- Slots actuales: {json.dumps(snapshot.slots, ensure_ascii=False)}
- Vertical: {snapshot.vertical}
- Greeted: {snapshot.greeted}

Clasifica la intención. Devuelve JSON:
{{
  "intent": "info_query" | "execute_action" | "modify_action" | "general_chat",
  "confidence": 0.0-1.0,
  "reason": "explicación breve (máx 20 palabras)"
}}
""".strip()

        t0 = time.perf_counter()
        data = await self.llm_client.generate_json(sys, usr)
        intent_ms = int((time.perf_counter() - t0) * 1000)

        result = {
            "intent": data.get("intent", "general_chat") if data else "general_chat",
            "confidence": data.get("confidence", 0.5) if data else 0.5,
            "reason": data.get("reason", "No reason provided") if data else "LLM error",
            "ms": intent_ms
        }

        logger.info(f"[intent_detection] vertical={snapshot.vertical} intent={result['intent']} confidence={result['confidence']:.2f} reason={result['reason']} ({intent_ms}ms)")

        return result

    # ---------- prompts ----------

    def _system_prompt(self, vertical: str) -> str:
        if vertical in self._system_cache:
            return self._system_cache[vertical]

        base = """
Eres un asistente virtual inteligente para WhatsApp. Tu objetivo es ayudar al cliente de forma natural y eficiente, como lo haría un empleado experimentado del negocio.

PRINCIPIOS DE CONVERSACIÓN:
1. Sé NATURAL y HUMANO: No suenas como un formulario. Conversa de forma fluida.
2. ENTIENDE EL CONTEXTO: Lee toda la conversación para entender qué quiere el cliente.
3. SÉ EFICIENTE: Recolecta información de forma inteligente, no pidas dato por dato robóticamente.
4. CONFIRMA ANTES DE EJECUTAR: Resume el pedido/reserva antes de confirmar.
5. USA HERRAMIENTAS: Cuando necesites info del negocio (menú, disponibilidad), usa las tools disponibles.

FORMATO DE RESPUESTA (siempre JSON):
{
  "reply": "tu mensaje para el cliente (1-3 oraciones, natural y conversacional)",
  "updated_state": {
    "categoria": "...",
    "items": ["..."],
    // otros campos que descubriste en esta conversación
  },
  "tool_calls": [
    {"name": "search_menu", "arguments": {"query": "pizza"}}
  ],
  "end": false  // true solo cuando hayas completado la acción (pedido confirmado, turno agendado, etc)
}

IMPORTANTE:
- NO pidas información que ya sabes
- NO repitas preguntas
- SI el cliente da múltiple información junta, capturala toda
- Ejemplo: "quiero una pizza grande de muzzarella para delivery a Constitución 123" → Ya tenés: items=["pizza grande muzzarella"], metodo_entrega="delivery", direccion="Constitución 123"
""".strip()

        if vertical == "gastronomia":
            base += """

VERTICAL: GASTRONOMÍA
Tu rol: Tomar pedidos de comida como lo haría un empleado del local.

INFORMACIÓN NECESARIA PARA PEDIDO:
- ¿Qué quiere? (items: ej. "2 pizzas grandes", "hamburguesa completa")
- ¿Cómo lo quiere? (metodo_entrega: "delivery", "retiro", "comer aquí")
- Si es delivery: ¿Dónde? (direccion)
- Opcional: extras, forma de pago, notas especiales

TOOLS DISPONIBLES:
- search_menu: Buscar en el menú del local (precios, disponibilidad)
- create_order: Crear el pedido (solo cuando tengas TODO confirmado)

FLUJO CONVERSACIONAL:
1. Saluda y pregunta qué desea
2. Si no conocés el menú, usa search_menu para ayudar
3. Recolecta items + método de entrega (+ dirección si es delivery)
4. Resume el pedido y confirma
5. Ejecuta create_order
6. Confirma al cliente con tiempo estimado

EJEMPLO DE CONVERSACIÓN NATURAL:
Usuario: "hola quiero pedir"
Tú: "¡Hola! ¿Qué te gustaría pedir hoy?"
Usuario: "tienen pizzas?"
Tú: [usa search_menu] "Sí! Tenemos pizzas de muzzarella, napolitana, especial... ¿Cuál preferís?"
Usuario: "una grande de muzza para llevar"
Tú: "Perfecto! Una pizza grande de muzzarella para retiro. ¿En unos 25 minutos te viene bien?"
Usuario: "dale"
Tú: [ejecuta create_order] "¡Listo! Tu pedido está confirmado. Te esperamos en 25 minutos."
"""
        elif vertical == "inmobiliaria":
            base += """

VERTICAL: INMOBILIARIA
Tu rol: Agendar visitas a propiedades como lo haría un agente inmobiliario.

INFORMACIÓN NECESARIA:
- Operación (alquiler/venta)
- Tipo de propiedad (casa/depto/etc)
- Zona
- Rango de precio (opcional pero útil)
- Fecha preferida para la visita

TOOLS: list_properties, schedule_visit
"""
        elif vertical == "servicios":
            base += """

VERTICAL: SERVICIOS - Peluquería
Tu nombre: Sofía
Tu rol: Recepcionista virtual de una peluquería moderna y acogedora.

🎯 TU MISIÓN:
- Ayudar a los clientes a agendar turnos de forma natural y eficiente
- Extraer información necesaria de forma conversacional (no como formulario)
- Ser cálida, cercana y profesional - como una recepcionista experta

💬 TU ESTILO DE COMUNICACIÓN:
✓ Conversacional y cercano - como hablarías con un amigo
✓ Breve y directo - estamos en WhatsApp (máximo 2-3 líneas)
✓ Empático y servicial - el cliente es lo primero
✓ Natural y humano - usa pausas, expresiones coloquiales ("genial", "perfecto", "dale")
✓ Varía el largo de frases (unas cortas, otras un poco más largas)

❌ EVITA:
✗ Ser robótico o demasiado formal ("estimado cliente", "a la brevedad")
✗ Párrafos largos
✗ Repetir siempre la misma estructura
✗ Tecnicismos innecesarios

📋 INFORMACIÓN QUE NECESITAS PARA AGENDAR:
- service_type: Servicio deseado (ej: "Corte de Cabello", "Coloración", "Brushing")
- preferred_date: Fecha en formato YYYY-MM-DD (ej: "2025-10-07")
- preferred_time: Hora en formato HH:MM (ej: "15:00")
- client_name: Nombre del cliente
- client_email: Email del cliente
- client_phone: Teléfono (opcional)

🔧 CÓMO TRABAJAR:
1. Si el cliente ya dio información, reconócela y úsala (no preguntes de nuevo)
2. Pregunta solo por lo que falta
3. Si detectas intención de agendar, ayúdalo activamente
4. Cuando tengas TODO, resume y confirma antes de agendar

EJEMPLO DE CONVERSACIÓN NATURAL:
Usuario: "Hola, necesito cortarme el pelo mañana a las 3pm"
Tú: "¡Hola! Perfecto, te anoto para mañana a las 15hs para un corte. ¿Me pasás tu nombre y email?"
Usuario: "Soy Pablo, pablo@gmail.com"
Tú: "Genial Pablo! Confirmado tu turno para corte mañana 15hs. ¿Te mando la confirmación a pablo@gmail.com?"
Usuario: "Dale"
Tú: [ejecuta schedule_appointment] "¡Listo! Tu turno está confirmado. Te esperamos mañana a las 15hs 💈"

🚨 REGLAS CRÍTICAS - NO ALUCINES:
✓ NUNCA inventes precios, promociones ni información del negocio
✓ Si te preguntan por precios/servicios/horarios y NO tenés la info → Di "Déjame consultarlo" y NO inventes
✓ Cuando consultes precios, SIEMPRE menciona que varían por profesional
✓ Extrae TODA la información posible de cada mensaje del usuario
✓ updated_state debe contener los campos que descubriste (service_type, preferred_date, preferred_time, client_name, client_email, staff_preference si lo menciona)
✓ Solo marca end=true cuando hayas ejecutado schedule_appointment exitosamente

🔧 TOOLS DISPONIBLES (úsalos cuando el cliente consulte info):
- get_available_services: Lista servicios con precios por profesional
- check_availability: Verifica disponibilidad de horarios
- get_business_hours: Horarios de atención
- get_active_promotions: Promociones vigentes
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

        # Mapeo específico para servicios (appointments)
        if vertical == "servicios":
            # Mapear campos al formato esperado por Actions Service book_slot
            mapped_payload = {}

            # Mapeo directo - book_slot espera estos nombres exactos
            if "service_type" in payload:
                mapped_payload["service_type"] = payload["service_type"]

            if "preferred_date" in payload:
                mapped_payload["preferred_date"] = payload["preferred_date"]

            if "preferred_time" in payload:
                mapped_payload["preferred_time"] = payload["preferred_time"]

            if "client_name" in payload:
                mapped_payload["client_name"] = payload["client_name"]

            if "client_email" in payload:
                mapped_payload["client_email"] = payload["client_email"]

            if "client_phone" in payload:
                mapped_payload["client_phone"] = payload["client_phone"]

            if "notes" in payload:
                mapped_payload["notes"] = payload["notes"]

            # Agregar workspace_id y conversation_id que son requeridos
            if "workspace_id" in payload:
                mapped_payload["workspace_id"] = payload["workspace_id"]
            
            if "conversation_id" in payload:
                mapped_payload["conversation_id"] = payload["conversation_id"]

            return mapped_payload

        return payload

    def _filter_updated_state(self, vertical: str, upd: Dict[str, Any]) -> Dict[str, Any]:
        """Filtra claves desconocidas por vertical y valores vacíos para evitar que el LLM meta basura en slots"""
        allowed = set(BUSINESS_SLOTS.get(vertical, [])) | {"_validated_by_rag", "_attempts_count", "greeted", "extras"}
        # Filtrar también strings vacíos que pueden confundir la lógica de missing_slots
        return {k: v for k, v in (upd or {}).items() if k in allowed and v != ""}

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

    def _normalize_date(self, date_str: str) -> str:
        """Normaliza fechas relativas a formato ISO (YYYY-MM-DD)"""
        if not date_str or not isinstance(date_str, str):
            return date_str

        date_lower = date_str.lower().strip()
        today = datetime.now()

        # Fechas relativas comunes
        date_mapping = {
            "hoy": today,
            "mañana": today + timedelta(days=1),
            "pasado mañana": today + timedelta(days=2),
        }

        if date_lower in date_mapping:
            return date_mapping[date_lower].strftime("%Y-%m-%d")

        # Días de la semana (próxima ocurrencia)
        days_of_week = {
            "lunes": 0, "martes": 1, "miércoles": 2, "jueves": 3,
            "viernes": 4, "sábado": 5, "domingo": 6
        }

        if date_lower in days_of_week:
            target_day = days_of_week[date_lower]
            current_day = today.weekday()
            days_ahead = (target_day - current_day) % 7
            if days_ahead == 0:
                days_ahead = 7  # Si es hoy, ir a la próxima semana
            next_occurrence = today + timedelta(days=days_ahead)
            return next_occurrence.strftime("%Y-%m-%d")

        # Corregir fechas ISO con año incorrecto (pasado)
        # Patrón: YYYY-MM-DD
        iso_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', date_str)
        if iso_match:
            year, month, day = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
            # Si el año es pasado (< año actual), asumir año actual
            if year < today.year:
                return f"{today.year}-{month:02d}-{day:02d}"
            # Si es el año actual o futuro, devolver sin cambios
            return date_str

        # Si no se reconoce, devolver sin cambios
        return date_str

    def _normalize_time(self, time_str: str) -> str:
        """Normaliza horas a formato HH:MM"""
        if not time_str or not isinstance(time_str, str):
            return time_str

        time_lower = time_str.lower().strip()

        # "10am", "3pm", "10:30am"
        match = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', time_lower)
        if match:
            hour = int(match.group(1))
            minute = match.group(2) or "00"
            period = match.group(3)

            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            return f"{hour:02d}:{minute}"

        # "10 de la mañana", "3 de la tarde"
        match = re.match(r'^(\d{1,2})\s+de\s+la\s+(mañana|tarde|noche)$', time_lower)
        if match:
            hour = int(match.group(1))
            period = match.group(2)

            if period == "tarde" and hour != 12:
                hour += 12
            elif period == "noche" and hour < 12:
                hour += 12

            return f"{hour:02d}:00"

        # Si ya está en formato HH:MM o no se reconoce, devolver sin cambios
        return time_str

    def _normalize_slots(self, vertical: str, slots: Dict[str, Any]) -> Dict[str, Any]:
        """Normaliza slots por vertical (ej: items como lista, fechas a ISO)"""
        s = dict(slots)

        # Normalización para gastronomía
        if vertical == "gastronomia":
            raw = s.get("items")
            if raw is not None and not isinstance(raw, list):
                s["items"] = [str(raw)]

        # Normalización para servicios (fechas y horas)
        if vertical == "servicios":
            if "preferred_date" in s:
                s["preferred_date"] = self._normalize_date(s["preferred_date"])
            if "preferred_time" in s:
                s["preferred_time"] = self._normalize_time(s["preferred_time"])

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
    
    # ---------- memoria conversacional ----------
    
    async def _load_conversational_memory(self, snapshot: ConversationSnapshot) -> None:
        """
        Carga memoria conversacional de 3 capas según la arquitectura documentada
        """
        try:
            # Capa 2: Short-Term Memory (conversaciones recientes del mismo cliente)
            short_term = await self.memory.load_short_term_memory(
                snapshot.conversation_id, snapshot.workspace_id
            )
            
            if short_term:
                logger.info(f"[MEMORY] Cargada short-term memory: {short_term.interaction_count} interacciones previas")
                # Agregar contexto de conversaciones recientes a los slots
                snapshot.slots["_short_term_context"] = {
                    "summary": short_term.summary_text,
                    "key_facts": short_term.key_facts,
                    "interaction_count": short_term.interaction_count
                }
            
            # Capa 3: Long-Term Memory (perfil del cliente para recurrentes)
            long_term = await self.memory.load_long_term_memory(
                snapshot.conversation_id, snapshot.workspace_id
            )
            
            if long_term:
                logger.info(f"[MEMORY] Cargada long-term memory: cliente recurrente '{long_term.name}' con {long_term.interaction_history.get('total_interactions', 0)} interacciones")
                # Agregar perfil del cliente a los slots
                snapshot.slots["_client_profile"] = {
                    "name": long_term.name,
                    "email": long_term.email,
                    "preferences": long_term.preferences,
                    "lead_score": long_term.lead_score,
                    "total_interactions": long_term.interaction_history.get("total_interactions", 0)
                }
                
                # Si es cliente recurrente y ya tenemos su nombre, pre-llenar
                if long_term.name and not snapshot.slots.get("client_name"):
                    snapshot.slots["client_name"] = long_term.name
                    logger.info(f"[MEMORY] Pre-llenado client_name desde perfil: {long_term.name}")
                
                # Si tenemos email, pre-llenar
                if long_term.email and not snapshot.slots.get("client_email"):
                    snapshot.slots["client_email"] = long_term.email
                    logger.info(f"[MEMORY] Pre-llenado client_email desde perfil: {long_term.email}")
        
        except Exception as e:
            logger.warning(f"[MEMORY] Error cargando memoria conversacional: {e}")
    
    async def _save_conversational_memory(self, snapshot: ConversationSnapshot) -> None:
        """
        Guarda memoria conversacional al final de la conversación
        """
        try:
            # Generar resumen de la conversación actual
            summary_text = await self._generate_conversation_summary(snapshot)
            
            # Extraer hechos clave de los slots
            key_facts = {
                "service_type": snapshot.slots.get("service_type"),
                "preferred_date": snapshot.slots.get("preferred_date"),
                "preferred_time": snapshot.slots.get("preferred_time"),
                "client_name": snapshot.slots.get("client_name"),
                "client_email": snapshot.slots.get("client_email"),
                "last_action": snapshot.last_action
            }
            # Filtrar valores None
            key_facts = {k: v for k, v in key_facts.items() if v is not None}
            
            # Guardar en short-term memory
            await self.memory.save_conversation_summary(
                snapshot.conversation_id, snapshot.workspace_id, 
                summary_text, key_facts
            )
            
            # Actualizar long-term memory si tenemos información del cliente
            name = snapshot.slots.get("client_name")
            email = snapshot.slots.get("client_email")
            preferences = {}
            
            # Extraer preferencias de la conversación
            if snapshot.slots.get("service_type"):
                preferences["preferred_service"] = snapshot.slots["service_type"]
            if snapshot.slots.get("preferred_time"):
                preferences["preferred_time"] = snapshot.slots["preferred_time"]
            
            if name or email or preferences:
                await self.memory.update_client_profile(
                    snapshot.conversation_id, snapshot.workspace_id,
                    name=name, email=email, preferences=preferences
                )
        
        except Exception as e:
            logger.warning(f"[MEMORY] Error guardando memoria conversacional: {e}")
    
    async def _generate_conversation_summary(self, snapshot: ConversationSnapshot) -> str:
        """
        Genera un resumen conciso de la conversación usando LLM
        """
        try:
            sys = """Eres un asistente que genera resúmenes concisos de conversaciones.

TAREA: Crear un resumen de máximo 2-3 líneas de la conversación.

INCLUIR:
- Qué quería el cliente
- Qué información se recopiló
- Qué acción se completó (si aplica)

FORMATO: Texto plano, sin JSON, máximo 200 caracteres."""
            
            usr = f"""
Conversación:
- Slots recopilados: {json.dumps(snapshot.slots, ensure_ascii=False)}
- Última acción: {snapshot.last_action}
- Objetivo: {snapshot.objective}

Genera resumen conciso:"""
            
            data = await self.llm_client.generate_json(sys, usr)
            if data and data.get("reply"):
                return data["reply"][:200]  # Limitar tamaño
            else:
                # Fallback: resumen básico
                service = snapshot.slots.get("service_type", "servicio")
                name = snapshot.slots.get("client_name", "cliente")
                return f"Cliente {name} solicitó {service}. Información recopilada y procesada."
        
        except Exception as e:
            logger.warning(f"[MEMORY] Error generando resumen: {e}")
            return "Conversación completada con información del cliente."

    # ---------- extracción de slots ----------
    
    async def _extract_slots_from_current_message(self, snapshot: ConversationSnapshot) -> Dict[str, Any]:
        """
        Extrae slots del mensaje actual del usuario antes de tomar decisiones de policy.
        Esto permite que PolicyEngine vea el estado actualizado.
        """
        if not snapshot.user_input or not snapshot.user_input.strip():
            return {}
        
        # Obtener configuración de slots para este vertical
        cfg = self.policy_engine.vertical_configs.get(snapshot.vertical, {})
        required = cfg.get("required_slots", [])
        optional = cfg.get("optional_slots", [])
        all_slots = required + optional
        
        # Prompt simplificado para extracción rápida
        sys = f"""Eres un extractor de información para asistente conversacional.

VERTICAL: {snapshot.vertical}
CAMPOS POSIBLES: {', '.join(all_slots)}

EXTRAE información del mensaje del usuario. Devuelve JSON con los campos detectados.

REGLAS:
- Solo extrae información EXPLÍCITA del mensaje
- NO inventes información
- Nombres: cualquier cosa que parezca nombre propio
- Fechas: "mañana" → "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}"
- Horas: "10am" → "10:00", "3pm" → "15:00"
- Emails: cualquier texto con @

Ejemplos:
"soy Juan" → {{"client_name": "Juan"}}
"mañana a las 10am" → {{"preferred_date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "preferred_time": "10:00"}}
"corte de pelo" → {{"service_type": "Corte de Cabello"}}
"""
        
        usr = f'Mensaje: "{snapshot.user_input}"'
        
        try:
            data = await self.llm_client.generate_json(sys, usr)
            if data and isinstance(data, dict):
                # Filtrar solo campos válidos para este vertical
                raw_extracted = {k: v for k, v in data.items() if k in all_slots and v}
                
                # Validar cada slot extraído
                validated_slots = {}
                validation_errors = []
                
                for slot_name, slot_value in raw_extracted.items():
                    if slot_name in SLOT_VALIDATORS:
                        is_valid, error_msg = SLOT_VALIDATORS[slot_name](slot_value)
                        if is_valid:
                            validated_slots[slot_name] = slot_value
                        else:
                            validation_errors.append(f"{slot_name}: {error_msg}")
                            logger.warning(f"[VALIDATE] Slot inválido {slot_name}='{slot_value}': {error_msg}")
                    else:
                        # Si no hay validador, aceptar el valor
                        validated_slots[slot_name] = slot_value
                
                # Si hay errores de validación, agregar al contexto para que el LLM los maneje
                if validation_errors:
                    validated_slots["_validation_errors"] = validation_errors
                
                return validated_slots
        except Exception as e:
            logger.warning(f"[EXTRACT] Error extrayendo slots: {e}")
        
        return {}

    # ---------- bucle principal ----------

    async def decide(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """
        🧠 PUNTO DE ENTRADA PRINCIPAL: Decide qué arquitectura usar
        
        - Si enable_agent_loop=True → usa el nuevo loop de agente (Planner → Policy → Broker → Reducer)
        - Si enable_agent_loop=False → usa el sistema anterior (Intent Detection + Decision Tree)
        """
        if self.enable_agent_loop:
            logger.info(f"[DECIDE] Using NEW agent loop for conversation {snapshot.conversation_id}")
            return await self.decide_with_agent_loop(snapshot)
        else:
            logger.info(f"[DECIDE] Using LEGACY decision tree for conversation {snapshot.conversation_id}")
            return await self._decide_legacy(snapshot)
    
    async def _decide_legacy(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """
        🧠 NUEVA ARQUITECTURA: Intent Detection Universal + Smart Decision Tree
        Detecta intención en CADA mensaje y navega inteligentemente
        """
        start_time = time.time()
        ctx = REQUEST_CONTEXT.get()
        telemetry = {
            "conversation_id": snapshot.conversation_id,
            "vertical": snapshot.vertical,
            "attempts_count": snapshot.attempts_count,
            "request_id": (ctx.get("x-request-id") if ctx else None),
            "llm_ms": 0,
            "intent_detection_ms": 0,
            "decision_tree_ms": 0,
            "reply_len": 0
        }

        try:
            # 0. Log del snapshot recibido
            logger.info(f"[SNAPSHOT] conversation_id={snapshot.conversation_id}, greeted={snapshot.greeted}, slots={snapshot.slots}, user_input='{snapshot.user_input[:50]}'")

            # 0. Validar vertical
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

            # 2. 🧠 INTENT DETECTION UNIVERSAL - Detectar intención en CADA mensaje
            intent_start = time.time()
            intent_result = await self._universal_intent_detection(snapshot)
            telemetry["intent_detection_ms"] = int((time.time() - intent_start) * 1000)
            
            logger.info(f"[INTENT] Detectado: {intent_result['intent']} (confianza: {intent_result['confidence']:.2f})")
            logger.info(f"[SLOTS] Extraídos: {intent_result['extracted_slots']}")
            
            # 3. Actualizar snapshot con información extraída
            snapshot.slots.update(intent_result['extracted_slots'])
            
            # 4. 🌳 NAVEGAR ÁRBOL DE DECISIÓN basado en intención + contexto
            decision_start = time.time()
            response = await self._navigate_decision_tree(snapshot, intent_result)
            telemetry["decision_tree_ms"] = int((time.time() - decision_start) * 1000)
            
            logger.info(f"[DECISION_TREE] Acción final: {response.next_action}")

            # Completar telemetría
            telemetry["reply_len"] = len(response.assistant)
            telemetry["total_ms"] = int((time.time() - start_time) * 1000)
            
            logger.info(f"[telemetry] {snapshot.vertical}:{telemetry['request_id']} {telemetry}")
            
            return response

        except Exception as e:
            telemetry["error"] = str(e)
            telemetry["total_ms"] = int((time.time() - start_time) * 1000)
            logger.exception(f"[telemetry] {snapshot.vertical}:{telemetry['request_id']} {telemetry}")
            return OrchestratorResponse(
                assistant="Disculpá, tuve un problema técnico. ¿Podés repetir lo que necesitás?",
                slots=snapshot.slots,
                tool_calls=[],
                context_used=[],
                next_action=NextAction.ANSWER,
                end=False
            )

    async def decide_with_agent_loop(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """
        🤖 NUEVO LOOP DE AGENTE: Planner → Policy → Broker → Reducer → Response
        
        Este método implementa la nueva arquitectura de tool calling:
        1. Planner LLM decide qué tools ejecutar
        2. PolicyEngine valida permisos y argumentos  
        3. ToolBroker ejecuta tools con robustez
        4. StateReducer aplica resultados al estado
        5. Genera respuesta final con contexto actualizado
        """
        start_time = time.time()
        ctx = REQUEST_CONTEXT.get()
        request_id = ctx.get("x-request-id", f"req_{int(time.time() * 1000)}")
        
        telemetry = {
            "conversation_id": snapshot.conversation_id,
            "vertical": snapshot.vertical,
            "request_id": request_id,
            "planner_ms": 0,
            "policy_ms": 0,
            "broker_ms": 0,
            "reducer_ms": 0,
            "total_tools": 0,
            "successful_tools": 0
        }
        
        logger.info(f"[AGENT_LOOP] Starting for conversation {snapshot.conversation_id}")
        
        try:
            # 1. 🧠 PLANNER: LLM decide qué tools ejecutar
            planner_start = time.time()
            plan_actions = await self._planner_decide_tools(snapshot)
            telemetry["planner_ms"] = int((time.time() - planner_start) * 1000)
            telemetry["total_tools"] = len(plan_actions)
            
            logger.info(f"[PLANNER] Generated {len(plan_actions)} actions: {[a.tool for a in plan_actions]}")
            
            # 2. 🛡️ POLICY: Validar cada acción
            policy_start = time.time()
            validated_actions = []
            workspace_config = {"vertical": snapshot.vertical, "workspace_id": snapshot.workspace_id}
            
            # Cargar manifest de tools
            try:
                manifest = load_tool_manifest(snapshot.vertical)
                new_policy_engine = NewPolicyEngine()
            except Exception as e:
                logger.error(f"[POLICY] Error loading manifest: {e}")
                # Fallback al método anterior
                return await self.decide(snapshot)
            
            for action in plan_actions:
                policy_result = new_policy_engine.validate(action, dict(snapshot.slots), workspace_config, manifest)
                
                if policy_result.decision == PolicyDecision.ALLOW:
                    # Usar argumentos normalizados del policy
                    action.args = policy_result.normalized_args
                    validated_actions.append(action)
                    logger.info(f"[POLICY] ✅ {action.tool} allowed")
                else:
                    logger.warning(f"[POLICY] ❌ {action.tool} denied: {policy_result.reason}")
                    
                    # Si hay needs, agregar a validation_errors para que el LLM los maneje
                    if policy_result.needs:
                        current_errors = snapshot.slots.get("_validation_errors", [])
                        error_msg = f"Para usar {action.tool}: {', '.join(policy_result.needs)}"
                        if error_msg not in current_errors:
                            snapshot.slots["_validation_errors"] = current_errors + [error_msg]
            
            telemetry["policy_ms"] = int((time.time() - policy_start) * 1000)
            logger.info(f"[POLICY] Validated {len(validated_actions)}/{len(plan_actions)} actions")
            
            # 3. 🔧 BROKER: Ejecutar tools validados
            broker_start = time.time()
            observations = []
            
            if validated_actions:
                broker = get_tool_broker()
                mcp_client = await get_mcp_client()
                
                # Ejecutar tools (secuencialmente por ahora, paralelismo futuro)
                for action in validated_actions:
                    try:
                        # Buscar spec del tool en manifest
                        tool_spec = None
                        for tool in manifest.tools:
                            if tool.name == action.tool:
                                tool_spec = tool
                                break
                        
                        if not tool_spec:
                            logger.error(f"[BROKER] Tool spec not found: {action.tool}")
                            continue
                        
                        observation = await broker.execute(
                            tool=action.tool,
                            args=action.args,
                            workspace_id=snapshot.workspace_id,
                            conversation_id=snapshot.conversation_id,
                            request_id=request_id,
                            tool_spec=tool_spec,
                            mcp_client=mcp_client
                        )
                        
                        observations.append(observation)
                        
                        if observation.status.value == "success":
                            telemetry["successful_tools"] += 1
                            
                        logger.info(f"[BROKER] {action.tool} -> {observation.status}")
                        
                    except Exception as e:
                        logger.exception(f"[BROKER] Error executing {action.tool}: {e}")
            
            telemetry["broker_ms"] = int((time.time() - broker_start) * 1000)
            
            # 4. 🔄 REDUCER: Aplicar observaciones al estado
            reducer_start = time.time()
            new_state = dict(snapshot.slots)
            
            if observations:
                reducer = get_state_reducer()
                
                # Aplicar observaciones en batch
                patch = reducer.apply_multiple_observations(
                    observations, 
                    snapshot.slots, 
                    workspace_config, 
                    snapshot.conversation_id
                )
                
                # Aplicar patch al estado
                snapshot_dict = {
                    "slots": snapshot.slots,
                    "objective": snapshot.objective
                }
                updated_snapshot_dict = apply_patch_to_snapshot(snapshot_dict, patch)
                new_state = updated_snapshot_dict["slots"]
                
                logger.info(f"[REDUCER] Applied patch with {len(patch.slots_patch)} slot updates")
                
                # Invalidar caches si es necesario
                if patch.cache_invalidation_keys:
                    logger.info(f"[REDUCER] Cache invalidation: {patch.cache_invalidation_keys}")
            
            telemetry["reducer_ms"] = int((time.time() - reducer_start) * 1000)
            
            # 5. 📝 RESPONSE: Generar respuesta con contexto actualizado
            # Crear snapshot actualizado
            updated_snapshot = ConversationSnapshot(
                conversation_id=snapshot.conversation_id,
                vertical=snapshot.vertical,
                user_input=snapshot.user_input,
                workspace_id=snapshot.workspace_id,
                greeted=snapshot.greeted,
                slots=new_state,
                objective=snapshot.objective,
                last_action=snapshot.last_action,
                attempts_count=snapshot.attempts_count
            )
            
            # Generar contexto de observaciones para el LLM
            observation_context = ""
            if observations:
                reducer = get_state_reducer()
                observation_context = reducer.get_observation_context(snapshot.conversation_id)
            
            # Generar respuesta final usando el LLM con contexto enriquecido
            response = await self._generate_response_with_context(updated_snapshot, observation_context)
            
            # Completar telemetría
            telemetry["total_ms"] = int((time.time() - start_time) * 1000)
            logger.info(f"[AGENT_LOOP] Completed: {telemetry}")
            
            return response
            
        except Exception as e:
            telemetry["error"] = str(e)
            telemetry["total_ms"] = int((time.time() - start_time) * 1000)
            logger.exception(f"[AGENT_LOOP] Error: {telemetry}")
            
            # Fallback al método anterior en caso de error
            return await self.decide(snapshot)
    
    async def _planner_decide_tools(self, snapshot: ConversationSnapshot) -> List[PlanAction]:
        """
        🧠 PLANNER: LLM decide qué tools ejecutar basado en el estado conversacional
        """
        # Cargar manifest para obtener tools disponibles
        try:
            manifest = load_tool_manifest(snapshot.vertical)
        except Exception as e:
            logger.error(f"[PLANNER] Error loading manifest: {e}")
            return []
        
        # Generar descripción de tools disponibles para el LLM
        tools_description = []
        for tool in manifest.tools:
            args_desc = ", ".join([f"{k}: {v.get('description', 'N/A')}" for k, v in tool.args_schema.get('properties', {}).items()])
            tools_description.append(f"- {tool.name}: {tool.description} (args: {args_desc})")
        
        system_prompt = f"""Eres un planificador de herramientas especializado en {snapshot.vertical}.

HERRAMIENTAS DISPONIBLES:
{chr(10).join(tools_description)}

ESTADO ACTUAL:
- Usuario dice: "{snapshot.user_input}"
- Información recopilada: {dict(snapshot.slots)}
- Objetivo: {snapshot.objective}
- Ya saludado: {snapshot.greeted}

REGLAS:
1. Analiza qué necesita el usuario
2. Decide qué herramientas ejecutar para ayudarlo
3. Si el usuario pregunta información → usa tools de consulta (get_services, get_availability)
4. Si quiere agendar → primero verifica disponibilidad, luego agenda
5. Si falta información crítica → no ejecutes tools, el LLM preguntará
6. Ordena las herramientas por prioridad (consultas antes que acciones)

EJEMPLOS:

Usuario: "¿qué servicios tienen?"
→ [{{"tool": "get_services", "args": {{"workspace_id": "{snapshot.workspace_id}"}}}}]

Usuario: "quiero turno para corte mañana 3pm"
→ [
  {{"tool": "get_availability", "args": {{"workspace_id": "{snapshot.workspace_id}", "service_type": "Corte de Cabello", "preferred_date": "2025-10-10", "preferred_time": "15:00"}}}},
  {{"tool": "book_appointment", "args": {{"workspace_id": "{snapshot.workspace_id}", "service_type": "Corte de Cabello", "preferred_date": "2025-10-10", "preferred_time": "15:00", "client_name": "pendiente"}}}}
]

Usuario: "hola"
→ []  // Solo saludo, no necesita tools

Responde SOLO con array JSON de herramientas a ejecutar."""

        try:
            data = await self.llm_client.generate_json(system_prompt, "")
            
            if not data or not isinstance(data, list):
                logger.warning(f"[PLANNER] Invalid response: {data}")
                return []
            
            actions = []
            for item in data:
                if isinstance(item, dict) and "tool" in item:
                    action = PlanAction(
                        tool=item["tool"],
                        args=item.get("args", {}),
                        reasoning=item.get("reasoning", "")
                    )
                    actions.append(action)
            
            return actions
            
        except Exception as e:
            logger.error(f"[PLANNER] Error generating plan: {e}")
            return []
    
    async def _generate_response_with_context(self, snapshot: ConversationSnapshot, observation_context: str) -> OrchestratorResponse:
        """
        📝 Genera respuesta final con contexto de observaciones
        """
        # Construir prompt con contexto enriquecido
        slots_info = json.dumps(snapshot.slots, ensure_ascii=False) if snapshot.slots else "{}"
        
        system_prompt = f"""Eres un asistente conversacional especializado en {snapshot.vertical}.

MENSAJE DEL USUARIO: "{snapshot.user_input}"

ESTADO ACTUAL:
- Información recopilada: {slots_info}
- Objetivo: {snapshot.objective or 'Ayudar al cliente'}
- Ya saludado: {'Sí' if snapshot.greeted else 'No'}

{observation_context}

REGLAS:
❌ NO vuelvas a saludar si ya saludado = Sí
❌ NO preguntes información que ya está en los slots
❌ NO repitas información que acabas de obtener con herramientas
✓ USA los resultados de las herramientas para responder
✓ Si hay errores en _validation_errors, explícalos amablemente
✓ Sé conversacional y natural

RESPONDE EN JSON:
- "reply": Tu respuesta natural (1-3 oraciones)
- "updated_state": Slots que descubriste o actualizaste
- "end": true solo si completaste la acción principal"""

        try:
            data = await self.llm_client.generate_json(system_prompt, "")
            
            if not data:
                return OrchestratorResponse(
                    assistant="¿En qué más te puedo ayudar?",
                    slots=snapshot.slots,
                    tool_calls=[],
                    context_used=[],
                    next_action=NextAction.ANSWER,
                    end=False
                )
            
            # Extraer respuesta
            reply = data.get("reply", "¿En qué más te puedo ayudar?")
            updated_state = data.get("updated_state", {})
            end = data.get("end", False)
            
            # Aplicar updated_state
            new_slots = dict(snapshot.slots)
            if updated_state:
                # Filtrar solo slots válidos
                filtered_updates = self._filter_updated_state(snapshot.vertical, updated_state)
                new_slots.update(filtered_updates)
            
            return OrchestratorResponse(
                assistant=self._clip_reply(reply),
                slots=new_slots,
                tool_calls=[],  # Ya ejecutados por el broker
                context_used=[],
                next_action=NextAction.ANSWER,
                end=end
            )
            
        except Exception as e:
            logger.error(f"[RESPONSE] Error generating response: {e}")
            return OrchestratorResponse(
                assistant="¿En qué más te puedo ayudar?",
                slots=snapshot.slots,
                tool_calls=[],
                context_used=[],
                next_action=NextAction.ANSWER,
                end=False
            )
    
    # ---------- 🧠 NUEVA ARQUITECTURA: Intent Detection + Decision Tree ----------
    
    async def _universal_intent_detection(self, snapshot: ConversationSnapshot) -> Dict[str, Any]:
        """
        🧠 INTENT DETECTION UNIVERSAL con LLM
        Detecta intención + extrae TODOS los slots posibles en una sola pasada
        """
        # Obtener configuración del vertical
        cfg = self.policy_engine.vertical_configs.get(snapshot.vertical, {})
        required_slots = cfg.get("required_slots", [])
        optional_slots = cfg.get("optional_slots", [])
        all_slots = required_slots + optional_slots
        
        # Contexto conversacional
        conversation_context = self._build_conversation_context(snapshot)
        
        system_prompt = f"""Eres un detector de intenciones y extractor de información especializado en {snapshot.vertical}.

INTENCIONES POSIBLES:
- "greeting": Usuario saluda por primera vez
- "book_appointment": Usuario quiere agendar/reservar algo
- "info_query": Usuario pregunta información (precios, servicios, horarios)
- "confirm": Usuario confirma algo que se le preguntó
- "cancel": Usuario cancela o quiere cambiar algo
- "provide_info": Usuario proporciona información solicitada
- "general_chat": Conversación general, dudas, aclaraciones

SLOTS A EXTRAER (busca TODO lo que encuentres):
{', '.join(all_slots)}

REGLAS CRÍTICAS:
1. SIEMPRE extrae TODOS los datos que aparezcan en el mensaje
2. Si usuario dice "mañana" → calcular fecha exacta
3. Si dice "10am" → convertir a "10:00"
4. Si dice "corte" → expandir a "Corte de Cabello"
5. NO preguntes por datos que YA están en el contexto
6. Si el usuario da información completa de una vez, extraer TODO

CONTEXTO ACTUAL:
{conversation_context}

EJEMPLOS:

Usuario: "Hola, necesito turno para corte mañana a las 3pm, soy Juan"
→ {{
  "intent": "book_appointment",
  "confidence": 0.95,
  "extracted_slots": {{
    "service_type": "Corte de Cabello",
    "preferred_date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}",
    "preferred_time": "15:00",
    "client_name": "Juan"
  }},
  "reasoning": "Usuario quiere agendar con información completa"
}}

Usuario: "que servicios tenes?"
→ {{
  "intent": "info_query",
  "confidence": 0.9,
  "extracted_slots": {{}},
  "reasoning": "Consulta sobre servicios disponibles"
}}

Usuario: "soy María"
→ {{
  "intent": "provide_info",
  "confidence": 0.85,
  "extracted_slots": {{
    "client_name": "María"
  }},
  "reasoning": "Usuario proporciona nombre solicitado"
}}

Responde SOLO JSON válido."""

        user_prompt = f'Usuario dice: "{snapshot.user_input}"'
        
        try:
            data = await self.llm_client.generate_json(system_prompt, user_prompt)
            
            if data and isinstance(data, dict):
                # Validar estructura
                intent = data.get("intent", "general_chat")
                confidence = float(data.get("confidence", 0.5))
                extracted_slots = data.get("extracted_slots", {})
                reasoning = data.get("reasoning", "")
                
                # Validar slots extraídos
                validated_slots = {}
                for slot_name, slot_value in extracted_slots.items():
                    if slot_name in all_slots and slot_value:
                        # Aplicar validaciones si existen
                        if slot_name in SLOT_VALIDATORS:
                            is_valid, error_msg = SLOT_VALIDATORS[slot_name](str(slot_value))
                            if is_valid:
                                validated_slots[slot_name] = slot_value
                            else:
                                logger.warning(f"[INTENT] Slot inválido {slot_name}='{slot_value}': {error_msg}")
                        else:
                            validated_slots[slot_name] = slot_value
                
                logger.info(f"[INTENT] Detectado: {intent} | Slots: {validated_slots} | Razón: {reasoning}")
                
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "extracted_slots": validated_slots,
                    "reasoning": reasoning
                }
            
        except Exception as e:
            logger.error(f"[INTENT] Error en detección universal: {e}")
        
        # Fallback: detección básica
        return {
            "intent": "general_chat",
            "confidence": 0.3,
            "extracted_slots": {},
            "reasoning": "Fallback por error en LLM"
        }
    
    def _build_conversation_context(self, snapshot: ConversationSnapshot) -> str:
        """Construir contexto conversacional para intent detection"""
        context_parts = []
        
        # Estado del saludo
        if not snapshot.greeted:
            context_parts.append("- Primera interacción (no saludado)")
        else:
            context_parts.append("- Ya saludado")
        
        # Slots actuales
        if snapshot.slots:
            filled_slots = {k: v for k, v in snapshot.slots.items() if v and not k.startswith('_')}
            if filled_slots:
                context_parts.append(f"- Información ya recopilada: {filled_slots}")
        
        # Estado de confirmación
        if snapshot.slots.get("_awaiting_confirmation"):
            context_parts.append("- Esperando confirmación del usuario")
        
        # Intentos
        if snapshot.attempts_count > 0:
            context_parts.append(f"- Intentos previos: {snapshot.attempts_count}")
        
        return "\n".join(context_parts) if context_parts else "- Sin contexto previo"
    
    async def _navigate_decision_tree(self, snapshot: ConversationSnapshot, intent_result: Dict[str, Any]) -> OrchestratorResponse:
        """
        🌳 ÁRBOL DE DECISIÓN INTELIGENTE
        Navega basado en intención + contexto, evita preguntas redundantes
        """
        intent = intent_result["intent"]
        confidence = intent_result["confidence"]
        
        logger.info(f"[DECISION_TREE] Navegando: {intent} (confianza: {confidence:.2f})")
        
        # 🔄 ESTADO: Esperando confirmación
        if snapshot.slots.get("_awaiting_confirmation"):
            if intent == "confirm":
                return await self._handle_execute_action(snapshot, NextStep(NextAction.EXECUTE_ACTION, {}, "Confirmación recibida"))
            elif intent == "cancel":
                new_slots = dict(snapshot.slots)
                new_slots.pop("_awaiting_confirmation", None)
                snapshot.slots = new_slots
                return OrchestratorResponse(
                    assistant="Entendido, ¿qué te gustaría cambiar?",
                    slots=new_slots,
                    tool_calls=[],
                    context_used=[],
                    next_action=NextAction.ANSWER,
                    end=False
                )
            else:
                # Respuesta unclear, pedir aclaración
                return OrchestratorResponse(
                    assistant="¿Querés confirmar el turno o preferís cambiar algo? Decime 'sí' para confirmar o 'no' para modificar.",
                    slots=snapshot.slots,
                    tool_calls=[],
                    context_used=[],
                    next_action=NextAction.CONFIRM_ACTION,
                    end=False
                )
        
        # 👋 SALUDO: Primera interacción
        if not snapshot.greeted and intent == "greeting":
            return await self._handle_greet(snapshot)
        
        # 📋 RESERVA: Usuario quiere agendar
        if intent == "book_appointment" or (intent == "provide_info" and self._has_booking_context(snapshot)):
            return await self._handle_booking_flow(snapshot, intent_result)
        
        # ❓ CONSULTA: Usuario pregunta información
        if intent == "info_query":
            return await self._handle_info_query(snapshot, intent_result)
        
        # 📝 PROPORCIONAR INFO: Usuario da datos solicitados
        if intent == "provide_info":
            return await self._handle_provide_info(snapshot, intent_result)
        
        # 💬 CHAT GENERAL: Conversación general
        return await self._handle_general_chat(snapshot, intent_result)
    
    def _has_booking_context(self, snapshot: ConversationSnapshot) -> bool:
        """Verificar si hay contexto de reserva activa"""
        booking_indicators = ["service_type", "preferred_date", "preferred_time"]
        return any(snapshot.slots.get(slot) for slot in booking_indicators)
    
    async def _handle_booking_flow(self, snapshot: ConversationSnapshot, intent_result: Dict[str, Any]) -> OrchestratorResponse:
        """Manejar flujo de reserva inteligente"""
        cfg = self.policy_engine.vertical_configs.get(snapshot.vertical, {})
        required_slots = cfg.get("required_slots", [])
        
        # Verificar qué slots faltan
        missing_slots = [slot for slot in required_slots if not snapshot.slots.get(slot)]
        
        if not missing_slots:
            # Todos los slots completos → Confirmar
            logger.info(f"[BOOKING] Todos los slots completos, solicitando confirmación")
            return await self._handle_confirm_action(snapshot, NextStep(NextAction.CONFIRM_ACTION, {}, "Slots completos"))
        
        # Faltan slots → Pedir el siguiente inteligentemente
        next_slot = self._get_next_smart_slot(missing_slots, snapshot)
        logger.info(f"[BOOKING] Falta información, pidiendo: {next_slot}")
        
        return await self._handle_slot_fill(snapshot, NextStep(NextAction.SLOT_FILL, {"ask_for": next_slot}, f"Pidiendo {next_slot}"))
    
    def _get_next_smart_slot(self, missing_slots: List[str], snapshot: ConversationSnapshot) -> str:
        """Determinar el próximo slot a pedir de manera inteligente"""
        # Orden lógico por vertical
        priority_orders = {
            "servicios": ["service_type", "preferred_date", "preferred_time", "client_name", "client_email"],
            "gastronomia": ["categoria", "items", "metodo_entrega", "direccion"],
            "inmobiliaria": ["tipo_propiedad", "zona", "presupuesto", "contacto"]
        }
        
        order = priority_orders.get(snapshot.vertical, missing_slots)
        
        # Devolver el primero que falte según el orden
        for slot in order:
            if slot in missing_slots:
                return slot
        
        return missing_slots[0] if missing_slots else ""
    
    async def _handle_info_query(self, snapshot: ConversationSnapshot, intent_result: Dict[str, Any]) -> OrchestratorResponse:
        """Manejar consultas de información"""
        # Usar tools para obtener información real
        return await self._handle_retrieve_context(snapshot, NextStep(NextAction.RETRIEVE_CONTEXT, {"query": snapshot.user_input}, "Consulta de información"))
    
    async def _handle_provide_info(self, snapshot: ConversationSnapshot, intent_result: Dict[str, Any]) -> OrchestratorResponse:
        """Manejar cuando usuario proporciona información"""
        # La información ya se extrajo en intent_result, continuar con booking flow
        if self._has_booking_context(snapshot):
            return await self._handle_booking_flow(snapshot, intent_result)
        else:
            return OrchestratorResponse(
                assistant="Perfecto, ¿en qué más te puedo ayudar?",
                slots=snapshot.slots,
                tool_calls=[],
                context_used=[],
                next_action=NextAction.ANSWER,
                end=False
            )
    
    async def _handle_general_chat(self, snapshot: ConversationSnapshot, intent_result: Dict[str, Any]) -> OrchestratorResponse:
        """Manejar conversación general"""
        return await self._handle_answer(snapshot)
    
    # ---------- handlers ----------

    async def _handle_greet(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """Saludo natural usando LLM + extracción inteligente de slots"""
        sys = self._system_prompt(snapshot.vertical)

        # Obtener lista de campos posibles para este vertical
        cfg = self.policy_engine.vertical_configs.get(snapshot.vertical, {})
        required = cfg.get("required_slots", [])
        optional = cfg.get("optional_slots", [])

        usr = f"""
Usuario dice: "{snapshot.user_input}"

Contexto: Es el primer mensaje del usuario (greeted=false).

TAREAS:
1. Saluda de forma cordial y natural (según tu rol y estilo definido arriba)
2. CRÍTICO: Lee el mensaje COMPLETO y extrae CADA dato que aparezca - nombres, emails, servicios, fechas, horas
3. Si el usuario ya expresó una intención clara, reconócela en tu saludo
4. Si detectas que falta información importante, menciónalo naturalmente

CAMPOS QUE DEBES BUSCAR (extrae TODO lo que encuentres):
- Requeridos: {', '.join(required)}
- Opcionales: {', '.join(optional)}

IMPORTANTE - INTERPRETACIÓN DE FECHAS Y HORAS:
- Fechas relativas: "mañana" → "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "pasado mañana" → "{(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')}"
- Horas en español:
  * "10am" → "10:00"
  * "10 de la mañana" → "10:00"
  * "3pm" → "15:00"
  * "3 de la tarde" → "15:00"
  * "5:30pm" → "17:30"
  * "medio día" → "12:00"

EJEMPLOS CRÍTICOS - Extracción de TIEMPO:

Usuario: "necesito coloración mañana a las 10am"
→ {{"service_type": "Coloración", "preferred_date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "preferred_time": "10:00"}}

Usuario: "brushing a las 5pm"
→ {{"service_type": "Brushing", "preferred_time": "17:00"}}

Usuario: "corte mañana a las 2 de la tarde"
→ {{"service_type": "Corte de Cabello", "preferred_date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "preferred_time": "14:00"}}

EJEMPLO COMPLETO - Usuario da TODO:

Usuario: "Hola, soy María López, necesito coloración mañana a las 10am, mi mail es maria.lopez@hotmail.com"
updated_state CORRECTO:
{{
  "service_type": "Coloración",
  "preferred_date": "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}",
  "preferred_time": "10:00",
  "client_name": "María López",
  "client_email": "maria.lopez@hotmail.com"
}}

CONVERSIÓN DE HORAS (MEMORIZA):
- "10am" = "10:00"
- "3pm" = "15:00"
- "5pm" = "17:00"
- "2 de la tarde" = "14:00"
- "3 de la tarde" = "15:00"

EJEMPLOS DE SALUDOS VARIADOS (usa diferentes estilos):

Si usuario dice "hola":
- "¡Hola! ¿Cómo estás? ¿En qué puedo ayudarte?"
- "¡Hola! Bienvenido/a. ¿Qué necesitás hoy?"
- "¡Hola! ¿Todo bien? ¿En qué te puedo asistir?"
- "¡Hola! ¿Cómo andás? ¿Qué servicio te interesa?"

Si usuario pide servicio específico:
- "¡Perfecto! Te ayudo con [servicio]. ¿Para cuándo lo necesitás?"
- "¡Excelente elección! ¿Qué día te viene bien para [servicio]?"
- "¡Dale! [Servicio] es una de nuestras especialidades. ¿Cuándo querés venir?"

Si usuario da información completa:
- "¡Genial [nombre]! Ya tengo todo anotado. Te confirmo [detalles]..."
- "¡Perfecto [nombre]! Veo que querés [servicio] para [fecha]. Te chequeo disponibilidad..."

Devuelve JSON:
{{
  "reply": "tu saludo conversacional VARIADO (máximo 2-3 líneas, usa diferentes frases cada vez)",
  "updated_state": {{
    // Incluir TODOS los campos que detectaste
  }}
}}

REGLAS CRÍTICAS:
✓ VARÍA el saludo - NO uses siempre las mismas palabras
✓ Extrae TODOS los datos presentes (nombres, emails, servicios, fechas, horas)
✓ Lee el mensaje COMPLETO, no te detengas en la primera mitad
✓ Un nombre es cualquier cosa que parezca nombre propio (ej: "María López", "Juan Pérez")
✓ Un email es cualquier texto con @ (ej: "maria@gmail.com")
✗ NO inventar información que no está en el mensaje
✗ NO uses siempre "¡Hola! ¿Cómo estás? ¿En qué puedo ayudarte hoy?" - VARÍA
""".strip()

        # Medir tiempo de LLM
        t0 = time.perf_counter()
        data = await self.llm_client.generate_json(sys, usr)
        llm_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("llm_ms", llm_ms)

        new_slots = dict(snapshot.slots)
        new_slots["greeted"] = True

        # Si el LLM falla, usar fallback
        if not data:
            logger.warning(f"[GREET] ❌ LLM devolvió None/vacío, usando fallback")
            greeting = "¡Hola! ¿En qué puedo ayudarte hoy?"
        else:
            # Logging para debug
            logger.info(f"[GREET] 🔍 LLM response: {data}")
            
            # Usar reply del LLM si existe y no está vacío, sino fallback
            llm_reply = data.get("reply")
            if llm_reply and llm_reply.strip():  # Verificar que no esté vacío o solo espacios
                greeting = llm_reply
                logger.info(f"[GREET] ✅ Usando respuesta del LLM: '{llm_reply}'")
            else:
                logger.warning(f"[GREET] ⚠️ LLM devolvió reply vacío/None: '{llm_reply}', usando fallback")
                greeting = "¡Hola! ¿En qué puedo ayudarte hoy?"
            
            # Merge updated_state si existe
            upd = self._filter_updated_state(snapshot.vertical, data.get("updated_state") if data else {})
            if upd:
                new_slots.update(upd)
                logger.info(f"[GREET] ✅ Slots extraídos del primer mensaje: {upd}")

        return OrchestratorResponse(
            assistant=self._clip_reply(greeting),
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.GREET,
            end=False
        )
    
    async def _handle_slot_fill(self, snapshot: ConversationSnapshot, step: NextStep, inc_attempt: bool) -> OrchestratorResponse:
        """Pedir un slot puntual con LLM, validando JSON de salida"""
        ask_for = step.args.get("ask_for", "")
        missing_slots = step.args.get("missing_slots", [])

        # Obtener campos posibles para este vertical
        cfg = self.policy_engine.vertical_configs.get(snapshot.vertical, {})
        required = cfg.get("required_slots", [])
        optional = cfg.get("optional_slots", [])

        sys = self._system_prompt(snapshot.vertical)
        usr = f"""
Usuario dice: "{snapshot.user_input}"

Contexto:
- Slots actuales: {json.dumps(snapshot.slots, ensure_ascii=False)}
- Slots que faltan: {', '.join(missing_slots)}
- Estás pidiendo específicamente: {ask_for}

TAREAS:
1. CRÍTICO: Lee el mensaje COMPLETO y extrae CADA dato presente
   - Campos requeridos: {', '.join(required)}
   - Campos opcionales: {', '.join(optional)}
   - NO te limites a {ask_for} - extrae TODO

2. Genera respuesta natural:
   - Si usuario dio {ask_for}: reconócelo y agradece
   - Si usuario dio OTRO dato útil (aunque no sea {ask_for}): reconócelo igual
   - Si no dio nada útil: pide {ask_for} de nuevo

3. Si todavía falta info: pregunta por el siguiente campo faltante

EJEMPLOS DE EXTRACCIÓN:

Ejemplo A - Usuario responde con OTRO dato:
Preguntaste: preferred_time
Usuario dice: "Mi nombre es Pablo Martínez"
updated_state CORRECTO: {{"client_name": "Pablo Martínez"}}
reply: "Genial Pablo! ¿Y a qué hora te gustaría venir?"

Ejemplo B - Usuario da MÚLTIPLES datos:
Preguntaste: preferred_time
Usuario dice: "Soy Ana García, ana@gmail.com, a las 3pm estaría bien"
updated_state CORRECTO: {{"client_name": "Ana García", "client_email": "ana@gmail.com", "preferred_time": "15:00"}}
reply: "Perfecto Ana! Te anoto para las 3pm"

Ejemplo C - Usuario confirma sin dar info nueva:
Preguntaste: preferred_time
Usuario dice: "Sí, confirmá por favor"
updated_state CORRECTO: {{}} (vacío, no hay nueva info)
reply: "Para confirmar necesito saber a qué hora prefieres venir"

Devuelve JSON:
{{
  "reply": "tu respuesta conversacional (máximo 2-3 líneas)",
  "updated_state": {{
    // TODOS los campos que detectaste (puede ser más de uno)
  }}
}}

REGLAS CRÍTICAS:
✓ Lee el mensaje COMPLETO - nombres, emails, fechas, horas
✓ Extrae TODO, no solo {ask_for}
✓ Un email es cualquier texto con @
✓ Horarios: "3pm"/"3 de la tarde" → "15:00", "10am"/"10 de la mañana" → "10:00"
✗ NO inventar información
""".strip()

        # Medir tiempo de LLM
        t0 = time.perf_counter()
        data = await self.llm_client.generate_json(sys, usr)
        llm_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("llm_ms", llm_ms)
        
        # Logging para debug
        logger.info(f"[SLOT_FILL] 🔍 LLM response para '{snapshot.user_input}': {data}")
        
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
            logger.info(f"[SLOT_FILL] ✅ Slots extraídos: {upd}")

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
        """Consulta Tool o RAG según vertical + compone respuesta breve"""

        # Normalizar slots antes de continuar
        norm_slots = self._normalize_slots(snapshot.vertical, snapshot.slots)

        # Decidir si usar tool o RAG
        use_tool = step.args.get("use_tool", False)

        if use_tool:
            # ========== USAR TOOL (Servicios) ==========
            tool_name = step.args.get("tool_name")
            tool_args = step.args.get("tool_args", {})

            logger.info(f"[MCP] Llamando tool via MCP: {tool_name} con args: {tool_args}")

            # Medir tiempo de tool via MCP
            t0 = time.perf_counter()
            mcp_client = get_mcp_client()
            tool_result = await mcp_client.call_tool(tool_name, tool_args)
            tool_ms = int((time.perf_counter() - t0) * 1000)
            self._telemetry_add("rag_ms", tool_ms)  # Usamos mismo campo para stats

            # Formatear resultado para el LLM
            context_text = self.policy_engine._format_tool_result(tool_result)

            logger.info(f"[MCP] Resultado: success={tool_result.get('success')}, context_len={len(context_text)}")

        else:
            # ========== USAR RAG (Gastronomía, Inmobiliaria) ==========
            query = step.args.get("query") or snapshot.user_input
            filters = step.args.get("filters") or {}

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

            # Usar RAG results
            context_text = "\n".join(r.get("text", "") for r in rag_results[:3])

        # ========== GENERAR RESPUESTA CON LLM ==========

        # señalamos que validamos con contexto (desbloquea EXECUTE_ACTION si hacía falta)
        new_slots = dict(snapshot.slots)
        new_slots["_validated_by_rag"] = True

        # Componer respuesta con LLM (JSON)
        sys = self._system_prompt(snapshot.vertical)

        # Instrucciones específicas por vertical
        if snapshot.vertical == "servicios":
            context_instructions = """
INSTRUCCIONES CRÍTICAS:
1. USA EXACTAMENTE los datos del "Contexto del sistema" - NO inventes información
2. Si el contexto muestra precios y nombres de profesionales → MENCIÓNALOS ESPECÍFICAMENTE
3. Ejemplo correcto: "Tenemos corte con Carlos a $3500, Juan a $4500 y María a $6000"
4. Si el contexto está vacío o es un error → admítelo: "Déjame consultar eso"
5. Responde en 1-2 oraciones naturales y útiles
"""
        else:
            # Gastronomía e Inmobiliaria (RAG)
            context_instructions = """
Con ese contexto, responde en 1–2 oraciones y propone el siguiente micro-paso útil (sin listar todo).
Si el contexto tiene información específica (precios, detalles), menciónala.
"""

        usr = f"""
Usuario dice: "{snapshot.user_input}"

Contexto del sistema:
{context_text}

Slots actuales: {json.dumps(new_slots, ensure_ascii=False)}

{context_instructions}

IMPORTANTE - EXTRACCIÓN DE SLOTS:
- FECHA ACTUAL: Hoy es {datetime.now().strftime('%A %d de %B de %Y')} ({datetime.now().strftime('%Y-%m-%d')})
- AÑO ACTUAL: {datetime.now().year}
- SIEMPRE extrae datos mencionados por el usuario (nombres, fechas, horas, servicios)
- Fechas relativas: "mañana" → "{(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')}", "pasado mañana" → "{(datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d')}", "hoy" → "{datetime.now().strftime('%Y-%m-%d')}"
- Fechas absolutas: Si el usuario dice "8 de octubre", asume año {datetime.now().year} → "{datetime.now().year}-10-08"
- Horas: "10am"/"10 de la mañana" → "10:00", "3pm"/"3 de la tarde" → "15:00", "5:30pm" → "17:30"

Devuelve JSON con "reply" y "updated_state" (con TODOS los campos que detectaste).
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

        # Preparar tool_calls y context_used según el método usado
        if use_tool:
            tool_calls_list = [{"name": tool_name, "arguments": tool_args}]
            context_list = [{"text": context_text, "source": "tool"}]
        else:
            tool_calls_list = [{"name": "retrieve_context", "arguments": {"query": step.args.get("query", ""), "filters": step.args.get("filters", {})}}]
            context_list = rag_results if 'rag_results' in locals() else []

        return OrchestratorResponse(
            assistant=self._clip_reply(reply),
            slots=new_slots,
            tool_calls=tool_calls_list,
            context_used=context_list,
            next_action=NextAction.RETRIEVE_CONTEXT,
            end=False
        )
    
    async def _handle_confirm_action(self, snapshot: ConversationSnapshot, step: NextStep) -> OrchestratorResponse:
        """
        Mostrar resumen de la información recopilada y solicitar confirmación del cliente
        """
        action_name = step.args.get("action_name", "acción")
        
        # Detectar intención de confirmación usando IA (más flexible)
        confirmation_intent = await self._detect_confirmation_intent(snapshot.user_input)
        
        is_confirming = confirmation_intent == "confirm"
        is_canceling = confirmation_intent == "cancel"
        
        # Si ya está confirmando, proceder a ejecutar
        if is_confirming:
            logger.info(f"[CONFIRM] Cliente confirmó la acción con: '{snapshot.user_input}', procediendo a ejecutar")
            # Limpiar flag de confirmación y proceder
            new_slots = dict(snapshot.slots)
            new_slots.pop("_awaiting_confirmation", None)
            snapshot.slots = new_slots
            # Cambiar el next_action a EXECUTE_ACTION y delegar
            step.next_action = NextAction.EXECUTE_ACTION
            return await self._handle_execute_action(snapshot, step)
        
        # Si está cancelando, volver a slot filling
        if is_canceling:
            logger.info(f"[CONFIRM] Cliente canceló, volviendo a recopilar información")
            new_slots = dict(snapshot.slots)
            new_slots["_confirmation_cancelled"] = True
            new_slots.pop("_awaiting_confirmation", None)  # Limpiar flag
            return OrchestratorResponse(
                assistant="Entendido, ¿qué te gustaría cambiar?",
                slots=new_slots,
                tool_calls=[],
                context_used=[],
                next_action=NextAction.ANSWER,
                end=False
            )
        
        # Si no está claro, pedir aclaración
        if confirmation_intent == "unclear":
            logger.info(f"[CONFIRM] Respuesta unclear: '{snapshot.user_input}', pidiendo aclaración")
            return OrchestratorResponse(
                assistant="No estoy seguro si querés confirmar o cambiar algo. ¿Podés decirme 'sí' para confirmar o 'no' si querés modificar algo?",
                slots=snapshot.slots,  # Mantener estado
                tool_calls=[],
                context_used=[],
                next_action=NextAction.CONFIRM_ACTION,
                end=False
            )
        
        # Primera vez o respuesta ambigua: mostrar resumen y pedir confirmación
        summary = self._generate_appointment_summary(snapshot)
        
        confirmation_message = f"""
{summary}

¿Está todo correcto? Escribí "sí" para confirmar o "no" si querés cambiar algo.
        """.strip()
        
        # Marcar que ya se mostró la confirmación
        new_slots = dict(snapshot.slots)
        new_slots["_awaiting_confirmation"] = True
        
        logger.info(f"[CONFIRM] Mostrando resumen y solicitando confirmación")
        
        return OrchestratorResponse(
            assistant=self._clip_reply(confirmation_message),
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.CONFIRM_ACTION,
            end=False
        )
    
    def _generate_appointment_summary(self, snapshot: ConversationSnapshot) -> str:
        """
        Genera un resumen claro y profesional del turno a confirmar
        """
        # Extraer información de los slots
        service = snapshot.slots.get("service_type", "servicio")
        date = snapshot.slots.get("preferred_date", "fecha no especificada")
        time = snapshot.slots.get("preferred_time", "hora no especificada")
        name = snapshot.slots.get("client_name", "cliente")
        email = snapshot.slots.get("client_email")
        
        # Formatear fecha de manera amigable
        formatted_date = self._format_date_friendly(date)
        
        # Formatear hora de manera amigable  
        formatted_time = self._format_time_friendly(time)
        
        # Construir resumen
        summary_lines = [
            "📋 **RESUMEN DE TU TURNO**",
            "",
            f"👤 **Cliente:** {name}",
            f"✂️ **Servicio:** {service}",
            f"📅 **Fecha:** {formatted_date}",
            f"🕐 **Hora:** {formatted_time}"
        ]
        
        if email:
            summary_lines.append(f"📧 **Email:** {email}")
        
        return "\n".join(summary_lines)
    
    def _format_date_friendly(self, date_str: str) -> str:
        """Convierte fecha YYYY-MM-DD a formato amigable"""
        try:
            from datetime import datetime
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Nombres de días en español
            days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                     "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            
            day_name = days[date_obj.weekday()]
            month_name = months[date_obj.month - 1]
            
            return f"{day_name} {date_obj.day} de {month_name}"
        except:
            return date_str
    
    def _format_time_friendly(self, time_str: str) -> str:
        """Convierte hora HH:MM a formato amigable"""
        try:
            from datetime import datetime
            time_obj = datetime.strptime(time_str, "%H:%M")
            
            # Formato 12 horas con AM/PM en español
            hour = time_obj.hour
            minute = time_obj.minute
            
            if hour == 0:
                return f"12:{minute:02d} AM"
            elif hour < 12:
                return f"{hour}:{minute:02d} AM"
            elif hour == 12:
                return f"12:{minute:02d} PM"
            else:
                return f"{hour-12}:{minute:02d} PM"
        except:
            return time_str
    
    async def _detect_confirmation_intent(self, user_input: str) -> str:
        """
        Detectar intención de confirmación usando LLM
        Más flexible que palabras hardcodeadas
        
        Returns: "confirm", "cancel", "unclear"
        """
        system_prompt = """Eres un detector de intenciones especializado en confirmaciones.

El usuario está respondiendo a una pregunta de confirmación sobre un turno/cita.
Tu tarea es clasificar su respuesta en una de estas categorías:

CATEGORÍAS:
- "confirm": El usuario confirma/acepta (ej: "sí", "ok", "perfecto", "me parece bien", "dale", "está todo correcto")
- "cancel": El usuario cancela/rechaza/quiere cambiar (ej: "no", "cancelar", "quiero cambiar", "no está bien", "modificar")
- "unclear": No está claro o pide más información (ej: "¿qué hora dijiste?", "no entiendo", "¿cuánto cuesta?")

EJEMPLOS:
Usuario: "sí" → "confirm"
Usuario: "perfecto, confirmá" → "confirm" 
Usuario: "me parece bien así" → "confirm"
Usuario: "está todo correcto" → "confirm"
Usuario: "dale, agendá" → "confirm"
Usuario: "no, quiero cambiar la hora" → "cancel"
Usuario: "cancelar por favor" → "cancel"
Usuario: "no me convence" → "cancel"
Usuario: "¿a qué hora era?" → "unclear"
Usuario: "cuánto sale?" → "unclear"

Responde SOLO con la categoría: "confirm", "cancel" o "unclear"."""

        user_prompt = f'Usuario: "{user_input}"'
        
        try:
            # Usar el LLM para detectar intención
            response = await self.llm_client.generate_text(system_prompt, user_prompt)
            
            # Limpiar respuesta y validar
            intent = response.strip().lower().replace('"', '')
            
            if intent in ["confirm", "cancel", "unclear"]:
                logger.info(f"[CONFIRM_INTENT] '{user_input}' → {intent}")
                return intent
            else:
                logger.warning(f"[CONFIRM_INTENT] Respuesta inválida del LLM: '{response}', usando fallback")
                # Fallback a reglas simples
                return self._fallback_confirmation_detection(user_input)
                
        except Exception as e:
            logger.error(f"[CONFIRM_INTENT] Error en detección: {e}, usando fallback")
            return self._fallback_confirmation_detection(user_input)
    
    def _fallback_confirmation_detection(self, user_input: str) -> str:
        """
        Fallback con reglas simples si el LLM falla
        """
        user_lower = user_input.lower().strip()
        
        # Palabras de confirmación básicas
        if any(word in user_lower for word in ["si", "sí", "ok", "dale", "perfecto", "correcto"]):
            return "confirm"
        
        # Palabras de cancelación básicas  
        if any(word in user_lower for word in ["no", "cancel", "cambiar", "modificar"]):
            return "cancel"
        
        # Por defecto, unclear
        return "unclear"
    
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
            
            # MEMORIA: Guardar conversación exitosa en memoria conversacional
            try:
                await self._save_conversational_memory(snapshot)
                logger.info(f"[MEMORY] Memoria conversacional guardada para conversación exitosa")
            except Exception as e:
                logger.warning(f"[MEMORY] Error guardando memoria al completar acción: {e}")
            
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
    
    async def _handle_validation_errors(self, snapshot: ConversationSnapshot, validation_errors: List[str]) -> OrchestratorResponse:
        """
        Maneja errores de validación de slots de manera amigable
        """
        # Limpiar errores de validación de los slots para evitar loops
        new_slots = dict(snapshot.slots)
        if "_validation_errors" in new_slots:
            del new_slots["_validation_errors"]
        
        # Construir mensaje amigable basado en los errores
        error_messages = []
        for error in validation_errors:
            if "fecha" in error.lower() and "pasada" in error.lower():
                error_messages.append("No puedo agendar turnos para fechas pasadas. ¿Podrías darme una fecha desde hoy en adelante?")
            elif "horario" in error.lower() and "atención" in error.lower():
                error_messages.append("Nuestro horario de atención es de 9:00 a 18:00. ¿Te viene bien algún horario dentro de ese rango?")
            elif "email" in error.lower() and "inválido" in error.lower():
                error_messages.append("El formato del email no es válido. ¿Podrías escribirlo de nuevo? (ejemplo: nombre@dominio.com)")
            elif "nombre" in error.lower():
                error_messages.append("Necesito tu nombre para agendar el turno. ¿Cómo te llamás?")
            elif "servicio" in error.lower():
                error_messages.append("Ese servicio no está disponible. Te puedo ofrecer: Corte de Cabello, Coloración, Barba, Brushing, Tratamiento, Permanente o Mechas.")
            else:
                # Mensaje genérico para otros errores
                error_messages.append(error.split(": ", 1)[-1] if ": " in error else error)
        
        # Combinar mensajes de error de manera natural
        if len(error_messages) == 1:
            reply = error_messages[0]
        else:
            reply = "Hay algunos detalles que necesito corregir: " + " También, ".join(error_messages)
        
        logger.info(f"[VALIDATION] Manejando errores: {validation_errors} → '{reply}'")
        
        return OrchestratorResponse(
            assistant=self._clip_reply(reply),
            slots=new_slots,
            tool_calls=[],
            context_used=[],
            next_action=NextAction.ANSWER,
            end=False
        )

    async def _handle_answer(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """
        Handler inteligente principal: usa el LLM para entender contexto,
        recolectar información de forma natural y decidir próximos pasos
        """
        # Verificar si hay errores de validación que manejar
        validation_errors = snapshot.slots.get("_validation_errors", [])
        if validation_errors:
            return await self._handle_validation_errors(snapshot, validation_errors)
        
        sys = self._system_prompt(snapshot.vertical)

        # Construir contexto rico para el LLM
        slots_info = json.dumps(snapshot.slots, ensure_ascii=False) if snapshot.slots else "{}"

        usr = f"""
MENSAJE DEL USUARIO: "{snapshot.user_input}"

ESTADO ACTUAL DE LA CONVERSACIÓN:
- Información recolectada hasta ahora: {slots_info}
- Objetivo: {snapshot.objective or 'Ayudar al cliente con su consulta'}
- Ya saludado: {'Sí' if snapshot.greeted else 'No'}

REGLAS CRÍTICAS - LEE ESTO:
❌ NO vuelvas a saludar si ya saludado = Sí
❌ NO preguntes por información que ya tenés en los slots
❌ NO repitas preguntas (ej: si ya preguntaste "¿cómo estás?", NO vuelvas a preguntar)
❌ Si el usuario responde cortesías ("muy bien", "bien gracias", "y vos") → NO CONVERSES sobre eso, reconoce BREVEMENTE (1 palabra) y avanza inmediatamente al negocio
✓ USA la información de slots para continuar la conversación
✓ Si el usuario responde algo, reconócelo y avanzá al siguiente paso

RESPUESTAS CORTESES - CÓMO MANEJARLAS:
Usuario: "muy bien y vos"
✓ CORRECTO: "¡Perfecto! ¿En qué te puedo ayudar hoy?"
✗ INCORRECTO: "¡Hola! ¿Cómo estás? Espero que muy bien también. ¿En qué te puedo ayudar hoy?"

Usuario: "bien gracias"
✓ CORRECTO: "¡Genial! ¿Qué necesitás?"
✗ INCORRECTO: "¡Hola! ¿Cómo estás? ¿En qué te puedo ayudar?"

INSTRUCCIONES:
1. Analiza qué información nueva te da el usuario en este mensaje
2. Actualiza el estado con toda la info que puedas extraer
3. Decide si necesitas:
   - Pedir más información (¿qué falta para completar el objetivo?)
   - Buscar información del negocio (usa tools como search_menu)
   - Confirmar y ejecutar la acción (si ya tenés todo)
4. Responde de forma natural y conversacional

RESPONDE EN JSON con:
- "reply": Tu mensaje (natural, 1-3 oraciones)
- "updated_state": Slots/campos que descubriste o actualizaste
- "tool_calls": Array de tools a ejecutar (si necesitás buscar info)
- "end": true solo si completaste la acción principal (pedido confirmado, turno agendado, etc)
""".strip()

        # Medir tiempo de LLM
        t0 = time.perf_counter()
        data = await self.llm_client.generate_json(sys, usr)
        llm_ms = int((time.perf_counter() - t0) * 1000)
        self._telemetry_add("llm_ms", llm_ms)

        new_slots = dict(snapshot.slots)
        tool_calls = []
        end = False

        if data:
            # Logging para debug
            logger.info(f"[ANSWER] 🔍 LLM response: {data}")
            
            # Extraer updated_state
            upd = self._filter_updated_state(snapshot.vertical, data.get("updated_state", {}))
            if upd:
                new_slots = self._maybe_reset_validation(snapshot.slots, {**new_slots, **upd}, snapshot.vertical)
                new_slots.update(upd)

            # Extraer tool_calls
            tool_calls = data.get("tool_calls", [])

            # Extraer end
            end = data.get("end", False)

            # Usar reply del LLM si existe y no está vacío, sino fallback
            llm_reply = data.get("reply")
            if llm_reply and llm_reply.strip():
                reply = llm_reply
                logger.info(f"[ANSWER] ✅ Usando respuesta del LLM: '{llm_reply}'")
            else:
                logger.warning(f"[ANSWER] ⚠️ LLM devolvió reply vacío/None: '{llm_reply}', usando fallback")
                reply = "Entiendo. ¿Podés contarme un poco más?"
        else:
            logger.warning(f"[ANSWER] ❌ LLM devolvió None/vacío, usando fallback")
            reply = "Entiendo. ¿Podés contarme un poco más para ayudarte mejor?"

        # Normalizar slots después de merge
        new_slots = self._normalize_slots(snapshot.vertical, new_slots)

        return OrchestratorResponse(
            assistant=self._clip_reply(reply),
            slots=new_slots,
            tool_calls=tool_calls,
            context_used=[],
            next_action=NextAction.ANSWER,
            end=end
        )
    
    async def close(self):
        await self.llm_client.close()
        await self.tools_client.close()


# Instancia global del servicio
_orchestrator_instance: Optional[OrchestratorService] = None

def get_orchestrator_service(enable_agent_loop: bool = False) -> OrchestratorService:
    """
    Obtiene instancia singleton del orchestrator
    
    Args:
        enable_agent_loop: Si True, habilita el nuevo loop de agente
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorService(enable_agent_loop=enable_agent_loop)
    return _orchestrator_instance

# Mantener compatibilidad con código existente
orchestrator_service = get_orchestrator_service()
