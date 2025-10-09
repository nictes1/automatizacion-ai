"""
FastAPI application para el Orchestrator Service
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import asyncio
from services.orchestrator_service import orchestrator_service, ConversationSnapshot, OrchestratorResponse

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PulpoAI Orchestrator Service",
    description="Servicio de orquestación para conversaciones de WhatsApp",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic
class DecideRequest(BaseModel):
    conversation_id: str
    vertical: str
    user_input: str
    greeted: bool = False
    slots: Dict[str, Any] = {}
    objective: str = ""
    last_action: Optional[str] = None
    attempts_count: int = 0
    current_state: Optional[Dict[str, Any]] = None  # Alternativa para pasar estado completo
    platform: Optional[str] = None  # whatsapp, telegram, web, etc

class DecideResponse(BaseModel):
    assistant: str
    next_action: str
    tool_calls: list = []
    slots: Dict[str, Any] = {}
    objective: str = ""
    end: bool = False

class PersistMessageRequest(BaseModel):
    workspace_id: str
    conversation_id: str
    message_text: str
    metadata: Dict[str, Any] = {}

class PersistMessageResponse(BaseModel):
    message_id: str
    success: bool

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "orchestrator"}

# Endpoint principal
@app.post("/orchestrator/decide", response_model=DecideResponse)
async def decide(
    request: DecideRequest,
    x_workspace_id: Optional[str] = Header(None),
    x_request_id: Optional[str] = Header(None)
):
    """
    Decide el próximo paso en la conversación
    """
    try:
        # Preparar contexto de request
        headers = {}
        if x_workspace_id:
            headers["x-workspace-id"] = x_workspace_id
        if x_request_id:
            headers["x-request-id"] = x_request_id

        # Merge current_state si existe (prioridad sobre campos individuales)
        greeted = request.greeted
        slots = dict(request.slots)
        objective = request.objective
        last_action = request.last_action
        attempts_count = request.attempts_count

        if request.current_state:
            # current_state puede tener: greeted, slots, objective, last_action, attempts_count
            greeted = request.current_state.get("greeted", greeted)
            if "slots" in request.current_state:
                slots.update(request.current_state["slots"])
            objective = request.current_state.get("objective", objective)
            last_action = request.current_state.get("last_action", last_action)
            attempts_count = request.current_state.get("attempts_count", attempts_count)

        # Crear snapshot
        snapshot = ConversationSnapshot(
            conversation_id=request.conversation_id,
            vertical=request.vertical,
            user_input=request.user_input,
            workspace_id=x_workspace_id or "550e8400-e29b-41d4-a716-446655440000",  # Default workspace
            greeted=greeted,
            slots=slots,
            objective=objective,
            last_action=last_action,
            attempts_count=attempts_count
        )
        
        # Usar context manager para headers
        with orchestrator_service.set_request_context(headers):
            response = await orchestrator_service.decide(snapshot)
        
        # Convertir respuesta
        return DecideResponse(
            assistant=response.assistant,
            next_action=response.next_action.value,
            tool_calls=response.tool_calls,
            slots=response.slots,
            objective=request.objective,  # Mantener el objetivo original
            end=response.end
        )
        
    except Exception as e:
        logger.error(f"Error en decide: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/orchestrator/persist_message", response_model=PersistMessageResponse)
async def persist_message(
    request: PersistMessageRequest,
    x_workspace_id: Optional[str] = Header(None)
):
    """
    Persiste un mensaje del asistente en la base de datos usando la función SQL persist_outbound
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        import os
        import json

        # Usar workspace_id del header o del request body
        workspace_id = x_workspace_id or request.workspace_id

        # Conectar a la base de datos
        conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@postgres:5432/pulpo"))

        try:
            with conn.cursor() as cur:
                # Llamar a la función SQL persist_outbound
                cur.execute("""
                    SELECT pulpo.persist_outbound(
                        %s::uuid,
                        %s::uuid,
                        %s,
                        'text',
                        'assistant',
                        %s::jsonb
                    ) AS message_id
                """, (
                    workspace_id,
                    request.conversation_id,
                    request.message_text,
                    json.dumps(request.metadata)
                ))

                result = cur.fetchone()
                message_id = str(result[0])
                conn.commit()

                return PersistMessageResponse(
                    message_id=message_id,
                    success=True
                )
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error persistiendo mensaje: {e}")
        raise HTTPException(status_code=500, detail=f"Error persistiendo mensaje: {str(e)}")

# Startup/shutdown
@app.on_event("startup")
async def startup():
    logger.info("Orchestrator Service starting up...")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Orchestrator Service shutting down...")
    await orchestrator_service.close()
    # Close MCP client
    from services.mcp_client import close_mcp_client
    await close_mcp_client()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
