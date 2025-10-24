"""
Microservicio Peluquería Agent
Agente conversacional específico para negocios de peluquería
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import os
import sys
from typing import Dict, Any

# Importar orquestador simple
from app.core.simple_orchestrator import SimplePeluqueriaOrchestrator

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle del microservicio"""
    logger.info("🚀 Starting Peluquería Agent (Modular Architecture)...")
    
    # Inicializar orquestador simple
    app.state.orchestrator = SimplePeluqueriaOrchestrator()
    
    yield
    
    logger.info("🛑 Shutting down Peluquería Agent...")

# Crear aplicación FastAPI
app = FastAPI(
    title="Peluquería Agent",
    description="Agente conversacional para negocios de peluquería",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Endpoint raíz del microservicio"""
    return {
        "service": "peluqueria-agent",
        "version": "1.0.0",
        "status": "running",
        "vertical": "peluqueria",
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "peluqueria-agent",
        "vertical": "peluqueria"
    }

@app.post("/chat")
async def chat(request: Dict[str, Any]):
    """
    Endpoint principal para procesar mensajes de peluquería
    
    Args:
        request: Dict con workspace_id, message, conversation_id, context
    """
    try:
        # Extraer parámetros del request
        workspace_id = request.get("workspace_id")
        message = request.get("message")
        conversation_id = request.get("conversation_id")
        context = request.get("context", {})
        
        if not workspace_id or not message:
            raise HTTPException(
                status_code=400,
                detail="workspace_id and message are required"
            )
        
        orchestrator = app.state.orchestrator
        
        # Procesar mensaje con orchestrator específico de peluquería
        response = await orchestrator.process_message(
            workspace_id=workspace_id,
            message=message,
            conversation_id=conversation_id,
            context=context
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error procesando mensaje de peluquería: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# @app.get("/services")
# async def get_services():
#     """Obtener servicios disponibles de peluquería"""
#     try:
#         tools = app.state.tools
#         services = await tools.get_available_services()
#         return {"services": services}
#     except Exception as e:
#         logger.error(f"Error obteniendo servicios: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/prompts/{prompt_type}")
# async def get_prompt(prompt_type: str):
#     """Obtener prompts específicos de peluquería"""
#     try:
#         prompts = app.state.prompts
#         prompt = prompts.get_prompt(prompt_type)
#         return {"prompt": prompt}
#     except Exception as e:
#         logger.error(f"Error obteniendo prompt: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,  # Puerto específico para peluquería
        reload=True,
        log_level="info"
    )
