"""
API Router para Orchestrator Service
Integrado con n8n para procesamiento de mensajes WhatsApp
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import os
import time
import hashlib

from services.orchestrator_integration import OrchestratorServiceIntegrated
from services.orchestrator_service import orchestrator_service, ConversationSnapshot

logger = logging.getLogger(__name__)

router = APIRouter()

# ========================================
# Feature Flag: SLM Pipeline
# ========================================
ENABLE_SLM_PIPELINE = os.getenv("ENABLE_SLM_PIPELINE", "false").lower() == "true"
SLM_CANARY_PERCENT = int(os.getenv("SLM_CANARY_PERCENT", "0"))

logger.info(f"[ORCHESTRATOR] SLM Pipeline: enabled={ENABLE_SLM_PIPELINE}, canary={SLM_CANARY_PERCENT}%")

# ========================================
# Modelos Pydantic
# ========================================

# ========================================
# Modelos según contrato n8n real
# ========================================

class UserMessageModel(BaseModel):
    """Mensaje del usuario desde n8n"""
    text: str
    message_id: str
    from_: str = Field(alias="from")  # Phone number
    to: str
    waid: str
    timestamp_iso: str
    locale: str = "es-AR"

class ContextModel(BaseModel):
    """Contexto de negocio desde n8n"""
    platform: str = "twilio"
    channel: str = "whatsapp"
    business_name: str
    vertical: str = "servicios"

class StateModel(BaseModel):
    """Estado de conversación desde n8n"""
    fsm_state: Optional[str] = None
    slots: Dict[str, Any] = {}
    last_k_observations: list = []

class DecideRequest(BaseModel):
    """
    Request de n8n para decidir próximo paso en conversación
    
    Formato real que viene desde n8n:
    1. Webhook Inbound recibe de Twilio
    2. Normalize Input extrae campos
    3. Resolve Channel busca workspace_id
    4. Load State carga slots/fsm_state
    5. Function Node prepara este JSON
    6. HTTP Request llama a /orchestrator/decide
    """
    user_message: UserMessageModel
    context: ContextModel
    state: StateModel
    
    class Config:
        populate_by_name = True


class AssistantResponseModel(BaseModel):
    """Respuesta del asistente para n8n"""
    text: str
    suggested_replies: list = []


class PatchModel(BaseModel):
    """Patch de estado para n8n"""
    slots: Dict[str, Any] = {}
    slots_to_remove: list = []
    cache_invalidation_keys: list = []


class TelemetryModel(BaseModel):
    """Telemetría detallada para observabilidad"""
    route: str
    extractor_ms: int = 0
    planner_ms: int = 0
    policy_ms: int = 0
    broker_ms: int = 0
    reducer_ms: int = 0
    nlg_ms: int = 0
    total_ms: int = 0
    intent: Optional[str] = None
    confidence: Optional[float] = None


class DecideResponse(BaseModel):
    """
    Response que n8n procesa:
    1. Lee assistant.text para enviar via Twilio
    2. Ejecuta tool_calls (si n8n lo maneja)
    3. Aplica patch.slots al estado
    4. Persiste en DB
    5. Logea telemetry para métricas
    """
    assistant: AssistantResponseModel
    tool_calls: list = []
    patch: PatchModel
    telemetry: TelemetryModel


class PersistMessageRequest(BaseModel):
    workspace_id: str
    conversation_id: str
    message_text: str
    metadata: Dict[str, Any] = {}


class PersistMessageResponse(BaseModel):
    message_id: str
    success: bool = True


# ========================================
# Helper Functions
# ========================================

def _decide_route(conversation_id: str) -> str:
    """
    Decide si usar SLM Pipeline o Legacy basado en feature flag + canary
    
    Canary deployment por hash de conversation_id:
    - SLM_CANARY_PERCENT=10 → 10% de conversaciones van a SLM
    - SLM_CANARY_PERCENT=0 → 100% SLM (0 = todo)
    - SLM_CANARY_PERCENT=100 → 100% Legacy
    - ENABLE_SLM_PIPELINE=false → 100% Legacy
    """
    if not ENABLE_SLM_PIPELINE:
        return "legacy"
    
    canary_percent = SLM_CANARY_PERCENT
    
    # canary_percent=0 significa 100% SLM
    if canary_percent == 0:
        return "slm_pipeline"
    
    # canary_percent=100 significa 100% Legacy
    if canary_percent >= 100:
        return "legacy"
    
    # Hash de conversation_id para routing determinístico
    # Misma conversación siempre va al mismo route
    bucket = int(hashlib.md5(conversation_id.encode()).hexdigest(), 16) % 100
    
    # Si bucket < canary_percent → SLM
    # Ej: canary=10, bucket=[0-9] → SLM, bucket=[10-99] → Legacy
    return "slm_pipeline" if bucket < canary_percent else "legacy"


async def _decide_with_slm_pipeline(
    request: DecideRequest,
    workspace_id: str,
    conversation_id: str,
    channel: str
) -> DecideResponse:
    """
    Ejecuta decisión con SLM Pipeline
    
    TODO: Implementar una vez que tengamos orchestrator_slm_pipeline configurado
    """
    # TODO: Implementar
    logger.warning(f"[SLM_PIPELINE] Not yet implemented, falling back to legacy")
    return await _decide_with_legacy(request, workspace_id, conversation_id)


async def _decide_with_legacy(
    request: DecideRequest,
    workspace_id: str,
    conversation_id: str
) -> DecideResponse:
    """
    Ejecuta decisión con Orchestrator Legacy
    
    Convierte DecideRequest (n8n) → ConversationSnapshot (Legacy) → DecideResponse (n8n)
    """
    # Crear snapshot para legacy
    snapshot = ConversationSnapshot(
        conversation_id=conversation_id,
        vertical=request.context.vertical,
        user_input=request.user_message.text,
        workspace_id=workspace_id,
        greeted=False,  # Legacy no usa este campo actualmente
        slots=request.state.slots,
        objective="",  # Legacy infiere objective
        last_action=None,
        attempts_count=0
    )
    
    # Llamar a legacy orchestrator
    response = await orchestrator_service.decide(snapshot)
    
    # Convertir response legacy → DecideResponse (n8n)
    return DecideResponse(
        assistant=AssistantResponseModel(
            text=response.assistant,
            suggested_replies=[]
        ),
        tool_calls=response.tool_calls or [],
        patch=PatchModel(
            slots=response.slots or {},
            slots_to_remove=[],
            cache_invalidation_keys=[]
        ),
        telemetry=TelemetryModel(
            route="legacy",
            intent=None,  # Legacy no retorna intent explícito
            confidence=None
        )
    )


# ========================================
# Endpoint principal
# ========================================

@router.post("/decide", response_model=DecideResponse)
async def decide(
    request: DecideRequest,
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_channel: Optional[str] = Header(None, alias="X-Channel"),
    x_conversation_id: Optional[str] = Header(None, alias="X-Conversation-Id"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    """
    Decide el próximo paso en la conversación (n8n → Orchestrator)
    
    Flow completo:
    1. Twilio recibe WhatsApp → webhook a n8n
    2. n8n normaliza (Normalize Input node)
    3. n8n resuelve workspace (Resolve Channel node)
    4. n8n carga estado (Load State node)
    5. n8n prepara JSON (Function Node)
    6. n8n llama a /orchestrator/decide (HTTP Request node) ← ESTAMOS ACÁ
    7. Orchestrator decide con SLM Pipeline o Legacy (según feature flag + canary)
    8. Retorna JSON con assistant.text + tool_calls + patch
    9. n8n ejecuta tool_calls (si los hay)
    10. n8n envía assistant.text via Twilio
    11. n8n persiste patch.slots en DB
    
    Contrato:
    - Request: user_message + context + state
    - Response: assistant + tool_calls + patch + telemetry
    """
    t0 = time.time()
    
    try:
        # Usar headers si existen, sino inferir de request
        workspace_id = x_workspace_id or "550e8400-e29b-41d4-a716-446655440003"
        conversation_id = x_conversation_id or f"wa-{request.user_message.waid}"
        channel = x_channel or "whatsapp"
        
        logger.info(
            f"[DECIDE] workspace={workspace_id} conv={conversation_id} "
            f"from={request.user_message.from_} text_len={len(request.user_message.text)}"
        )
        
        # ========================================
        # ROUTING: SLM Pipeline vs Legacy (con canary por hash)
        # ========================================
        
        route = _decide_route(conversation_id)
        
        logger.info(f"[ROUTING] route={route} workspace={workspace_id} conv={conversation_id}")
        
        # ========================================
        # EJECUTAR según route
        # ========================================
        
        if route == "slm_pipeline":
            # SLM Pipeline
            response = await _decide_with_slm_pipeline(
                request=request,
                workspace_id=workspace_id,
                conversation_id=conversation_id,
                channel=channel
            )
        else:
            # Legacy
            response = await _decide_with_legacy(
                request=request,
                workspace_id=workspace_id,
                conversation_id=conversation_id
            )
        
        # Agregar telemetría total
        t_total = int((time.time() - t0) * 1000)
        response.telemetry.total_ms = t_total
        
        logger.info(
            f"[DECIDE_DONE] route={route} workspace={workspace_id} "
            f"intent={response.telemetry.intent} total_ms={t_total}"
        )
        
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[DECIDE_ERROR] workspace={workspace_id} error={e}")
        
        # Respuesta de fallback para n8n
        return DecideResponse(
            assistant=AssistantResponseModel(
                text="Disculpá, tuve un problema técnico. ¿Podés intentar de nuevo en un momento?"
            ),
            tool_calls=[],
            patch=PatchModel(slots={}),
            telemetry=TelemetryModel(
                route="error",
                total_ms=int((time.time() - t0) * 1000)
            )
        )


@router.post("/persist_message", response_model=PersistMessageResponse)
async def persist_message(
    request: PersistMessageRequest,
    x_workspace_id: Optional[str] = Header(None)
):
    """
    Persiste un mensaje de respuesta del asistente en la base de datos
    """
    try:
        import psycopg2
        import os
        import json

        # Normalizar metadata: convertir last_action a minúsculas
        metadata = dict(request.metadata)
        if 'last_action' in metadata and metadata['last_action']:
            metadata['last_action'] = metadata['last_action'].lower()

        # Conectar a PostgreSQL
        conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@postgres:5432/pulpo"))
        cur = conn.cursor()

        # Llamar a la función persist_outbound
        cur.execute(
            """
            SELECT pulpo.persist_outbound(
                %s::uuid,
                %s::uuid,
                %s,
                'text',
                'ai',
                %s::jsonb
            ) AS message_id
            """,
            (
                request.workspace_id,
                request.conversation_id,
                request.message_text,
                json.dumps(metadata)
            )
        )

        result = cur.fetchone()
        message_id = str(result[0]) if result else None

        conn.commit()
        cur.close()
        conn.close()

        if not message_id:
            raise HTTPException(status_code=500, detail="Failed to persist message")

        return PersistMessageResponse(message_id=message_id, success=True)

    except Exception as e:
        logger.exception(f"Error persisting message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
