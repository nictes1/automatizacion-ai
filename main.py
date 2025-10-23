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
import os
import sys
import httpx
import asyncpg

# Importar routers
from api.metrics import router as metrics_router

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def validate_dependencies():
    """
    Valida que todas las dependencias críticas estén disponibles al startup.
    FAIL-FAST: Si alguna dependencia falla, la aplicación no arranca.
    """
    errors = []

    # 1. Validar PostgreSQL
    database_url = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@postgres:5432/pulpo")
    try:
        logger.info("🔍 Validando conexión a PostgreSQL...")
        conn = await asyncpg.connect(database_url)
        await conn.execute("SELECT 1")
        await conn.close()
        logger.info("✅ PostgreSQL disponible")
    except Exception as e:
        error_msg = f"❌ PostgreSQL no disponible: {e}"
        logger.error(error_msg)
        errors.append(error_msg)

    # 2. Validar Redis
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/1")
    try:
        logger.info("🔍 Validando conexión a Redis...")
        import redis.asyncio as aioredis
        redis_client = await aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await redis_client.ping()
        await redis_client.close()
        logger.info("✅ Redis disponible")
    except Exception as e:
        error_msg = f"❌ Redis no disponible: {e}"
        logger.error(error_msg)
        errors.append(error_msg)

    # 3. Validar MCP Server (CRÍTICO)
    mcp_url = os.getenv("MCP_URL", "http://mcp:8010")
    try:
        logger.info("🔍 Validando MCP Server...")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{mcp_url}/health")
            response.raise_for_status()
        logger.info("✅ MCP Server disponible")
    except Exception as e:
        error_msg = f"❌ MCP Server no disponible en {mcp_url}: {e}"
        logger.error(error_msg)
        errors.append(error_msg)

    # 4. Validar Ollama
    ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
    try:
        logger.info("🔍 Validando Ollama...")
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ollama_url}/api/tags")
            response.raise_for_status()
        logger.info("✅ Ollama disponible")
    except Exception as e:
        error_msg = f"⚠️  Ollama no disponible: {e} (continuando, pero LLM no funcionará)"
        logger.warning(error_msg)
        # Ollama no es bloqueante, solo warning

    # Si hay errores críticos, terminar el proceso
    if errors:
        logger.error("=" * 80)
        logger.error("🚨 FAIL-FAST: Dependencias críticas no disponibles")
        for error in errors:
            logger.error(f"  • {error}")
        logger.error("=" * 80)
        logger.error("💡 Solución: Verificar que todos los servicios estén levantados:")
        logger.error("   docker-compose ps")
        logger.error("   docker-compose logs postgres redis mcp")
        sys.exit(1)

    logger.info("✅ Todas las dependencias críticas están disponibles")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle de la aplicación"""
    # Startup
    logger.info("🚀 Starting PulpoAI application...")

    # Validar dependencias (FAIL-FAST)
    await validate_dependencies()

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

# Incluir orchestrator endpoints (FAIL-FAST: no catch ImportError)
from api.orchestrator import router as orchestrator_router
app.include_router(orchestrator_router, prefix="/orchestrator", tags=["orchestrator"])


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
