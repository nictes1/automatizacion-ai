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

class DecideResponse(BaseModel):
    assistant: str
    next_action: str
    tool_calls: list = []
    slots: Dict[str, Any] = {}
    objective: str = ""
    end: bool = False

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
        
        # Crear snapshot
        snapshot = ConversationSnapshot(
            conversation_id=request.conversation_id,
            vertical=request.vertical,
            user_input=request.user_input,
            greeted=request.greeted,
            slots=request.slots,
            objective=request.objective,
            last_action=request.last_action,
            attempts_count=request.attempts_count
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

# Startup/shutdown
@app.on_event("startup")
async def startup():
    logger.info("Orchestrator Service starting up...")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Orchestrator Service shutting down...")
    await orchestrator_service.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
