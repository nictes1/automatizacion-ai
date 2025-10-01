"""
Ejemplo de lifespan de FastAPI para cierre correcto de AsyncClients
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from .orchestrator_service import orchestrator_service, RequestContext, ConversationSnapshot, OrchestratorResponse
import logging

# Configuración de logging en el entrypoint (evita conflictos con otros servicios)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orchestrator")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager para el ciclo de vida de la aplicación FastAPI
    - Startup: inicialización de recursos
    - Shutdown: limpieza de conexiones
    """
    # Startup
    logger.info("Starting Orchestrator API...")
    yield
    # Shutdown
    logger.info("Shutting down Orchestrator API...")
    await orchestrator_service.close()

# Uso en tu aplicación FastAPI
app = FastAPI(lifespan=lifespan)

# Ejemplo de endpoint
@app.post("/orchestrator/decide", response_model=OrchestratorResponse)
async def decide_endpoint(request: Request, snapshot: ConversationSnapshot):
    """
    Endpoint que usa RequestContext para propagar headers
    FastAPI valida y serializa automáticamente la respuesta
    """
    with RequestContext({
        "authorization": request.headers.get("authorization"),
        "x-workspace-id": request.headers.get("x-workspace-id"),
        "x-request-id": request.headers.get("x-request-id")
    }):
        return await orchestrator_service.decide(snapshot)
