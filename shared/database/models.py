#!/usr/bin/env python3
"""
PulpoAI Shared Database Models
Modelos de datos compartidos para PulpoAI
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

class Vertical(str, Enum):
    """Verticales de negocio"""
    GASTRONOMIA = "gastronomia"
    INMOBILIARIA = "inmobiliaria"
    SERVICIOS = "servicios"
    OTRO = "otro"

class PlanTier(str, Enum):
    """Niveles de plan"""
    BASIC = "agent_basic"
    PRO = "agent_pro"
    PREMIUM = "agent_premium"
    CUSTOM = "agent_custom"

class ConversationStatus(str, Enum):
    """Estados de conversación"""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"
    HANDOFF = "handoff"

class MessageDirection(str, Enum):
    """Dirección de mensaje"""
    INBOUND = "inbound"
    OUTBOUND = "outbound"

class NextAction(str, Enum):
    """Próximas acciones"""
    ANSWER = "answer"
    TOOL_CALL = "tool_call"
    HANDOFF = "handoff"
    WAIT = "wait"

@dataclass
class Workspace:
    """Modelo de workspace"""
    id: str
    name: str
    plan_tier: PlanTier
    vertical: Vertical
    settings_json: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class User:
    """Modelo de usuario"""
    id: str
    email: str
    name: str
    created_at: datetime

@dataclass
class WorkspaceMember:
    """Modelo de miembro de workspace"""
    id: str
    workspace_id: str
    user_id: str
    role: str
    created_at: datetime

@dataclass
class Channel:
    """Modelo de canal"""
    id: str
    workspace_id: str
    type: str
    provider: str
    business_phone_id: str
    display_phone: str
    status: str
    settings_json: Dict[str, Any]
    created_at: datetime

@dataclass
class Contact:
    """Modelo de contacto"""
    id: str
    workspace_id: str
    user_phone: str
    attributes_json: Dict[str, Any]
    last_seen_at: Optional[datetime]
    created_at: datetime

@dataclass
class Conversation:
    """Modelo de conversación"""
    id: str
    workspace_id: str
    channel_id: str
    contact_id: str
    status: ConversationStatus
    last_message_at: Optional[datetime]
    total_messages: int
    unread_count: int
    created_at: datetime
    updated_at: datetime

@dataclass
class Message:
    """Modelo de mensaje"""
    id: str
    conversation_id: str
    workspace_id: str
    direction: MessageDirection
    text: str
    wa_message_sid: Optional[str]
    intent: Optional[str]
    slots_extracted: Optional[Dict[str, Any]]
    tool_calls: Optional[Dict[str, Any]]
    tool_results: Optional[Dict[str, Any]]
    created_at: datetime

@dataclass
class DialogueState:
    """Modelo de estado de diálogo"""
    id: str
    workspace_id: str
    conversation_id: str
    fsm_state: str
    intent: Optional[str]
    slots: Dict[str, Any]
    next_action: NextAction
    meta: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class DialogueStateHistory:
    """Modelo de historial de estado de diálogo"""
    id: str
    workspace_id: str
    conversation_id: str
    event: str
    payload: Dict[str, Any]
    previous_state: Optional[Dict[str, Any]]
    new_state: Optional[Dict[str, Any]]
    created_at: datetime

@dataclass
class DialogueSlot:
    """Modelo de slot de diálogo"""
    id: str
    workspace_id: str
    conversation_id: str
    slot_name: str
    slot_value: Dict[str, Any]
    slot_type: str
    created_at: datetime
    updated_at: datetime

@dataclass
class Document:
    """Modelo de documento"""
    id: str
    workspace_id: str
    title: str
    content: str
    metadata: Dict[str, Any]
    file_path: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    created_at: datetime
    updated_at: datetime

@dataclass
class DocumentChunk:
    """Modelo de chunk de documento"""
    id: str
    document_id: str
    workspace_id: str
    chunk_index: int
    content: str
    embedding: Optional[List[float]]
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class BusinessAction:
    """Modelo de acción de negocio"""
    id: str
    workspace_id: str
    conversation_id: str
    action_type: str
    action_data: Dict[str, Any]
    status: str
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime

@dataclass
class Order:
    """Modelo de pedido"""
    id: str
    workspace_id: str
    conversation_id: str
    items: List[Dict[str, Any]]
    extras: List[Dict[str, Any]]
    total: Optional[float]
    metodo_entrega: Optional[str]
    direccion: Optional[str]
    metodo_pago: Optional[str]
    status: str
    eta_minutes: Optional[int]
    created_at: datetime
    updated_at: datetime

@dataclass
class Property:
    """Modelo de propiedad"""
    id: str
    workspace_id: str
    operation: Optional[str]
    type: Optional[str]
    zone: Optional[str]
    address: Optional[str]
    price: Optional[float]
    bedrooms: Optional[int]
    bathrooms: Optional[int]
    surface_m2: Optional[float]
    description: Optional[str]
    features: Dict[str, Any]
    images: List[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    is_available: bool
    created_at: datetime
    updated_at: datetime

@dataclass
class Appointment:
    """Modelo de cita"""
    id: str
    workspace_id: str
    conversation_id: str
    appointment_type: str
    scheduled_at: datetime
    duration_minutes: int
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

@dataclass
class SystemMetric:
    """Modelo de métrica del sistema"""
    id: str
    workspace_id: Optional[str]
    metric_name: str
    metric_value: float
    metric_unit: Optional[str]
    tags: Dict[str, Any]
    recorded_at: datetime

@dataclass
class ErrorLog:
    """Modelo de log de error"""
    id: str
    workspace_id: Optional[str]
    service_name: str
    error_type: str
    error_message: str
    stack_trace: Optional[str]
    context: Dict[str, Any]
    created_at: datetime
