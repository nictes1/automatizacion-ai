"""
PulpoAI - Sistema de Agentes Conversacionales
Aplicación principal FastAPI
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging

# Importar routers
from api.metrics import router as metrics_router

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle de la aplicación"""
    # Startup
    logger.info("🚀 Starting PulpoAI application...")
    
    # Aquí podrías inicializar conexiones a BD, Redis, etc.
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down PulpoAI application...")
    
    # Aquí podrías cerrar conexiones, limpiar recursos, etc.


# Crear aplicación FastAPI
app = FastAPI(
    title="PulpoAI - Sistema de Agentes Conversacionales",
    description="Sistema inteligente de agentes conversacionales con tool calling",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Incluir routers
app.include_router(metrics_router)


@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "message": "PulpoAI - Sistema de Agentes Conversacionales",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "metrics": "/metrics/prometheus",
        "health": "/metrics/health"
    }


@app.get("/health")
async def health():
    """Health check simple"""
    return {"status": "healthy", "service": "pulpo-ai"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
