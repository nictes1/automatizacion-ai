"""
API Gateway - Router principal para microservicios por vertical
Enruta requests a microservicios específicos según el vertical del workspace
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import logging
import httpx
import asyncio
from typing import Dict, Any, Optional

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle del API Gateway"""
    logger.info("🚀 Starting API Gateway...")
    
    # Inicializar cliente HTTP
    app.state.http_client = httpx.AsyncClient(timeout=30.0)
    
    yield
    
    # Cerrar cliente HTTP
    await app.state.http_client.aclose()
    logger.info("🛑 Shutting down API Gateway...")

# Crear aplicación FastAPI
app = FastAPI(
    title="PulpoAI API Gateway",
    description="Router principal para microservicios por vertical",
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

# Configuración de microservicios por vertical
VERTICAL_SERVICES = {
    "peluqueria": {
        "url": "http://peluqueria-agent:8001",
        "name": "Peluquería Agent",
        "description": "Agente conversacional para negocios de peluquería"
    },
    "abogacia": {
        "url": "http://abogacia-agent:8002", 
        "name": "Abogacía Agent",
        "description": "Agente conversacional para bufetes de abogados"
    },
    "restaurante": {
        "url": "http://restaurante-agent:8003",
        "name": "Restaurante Agent", 
        "description": "Agente conversacional para restaurantes"
    }
}

# Cache de verticales por workspace (en producción usar Redis)
workspace_vertical_cache = {}

async def get_workspace_vertical(workspace_id: str) -> str:
    """
    Obtener vertical de un workspace
    
    Args:
        workspace_id: ID del workspace
        
    Returns:
        str: Vertical del workspace
    """
    # Verificar cache primero
    if workspace_id in workspace_vertical_cache:
        return workspace_vertical_cache[workspace_id]
    
    # En un sistema real, esto consultaría la base de datos
    # Por ahora, simulamos basado en el ID
    if "peluqueria" in workspace_id.lower():
        vertical = "peluqueria"
    elif "abogacia" in workspace_id.lower() or "abogado" in workspace_id.lower():
        vertical = "abogacia"
    elif "restaurante" in workspace_id.lower() or "restaurant" in workspace_id.lower():
        vertical = "restaurante"
    else:
        # Default a peluquería por ahora
        vertical = "peluqueria"
    
    # Guardar en cache
    workspace_vertical_cache[workspace_id] = vertical
    
    return vertical

async def call_vertical_service(service_url: str, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Llamar a un microservicio específico
    
    Args:
        service_url: URL del microservicio
        endpoint: Endpoint específico
        data: Datos a enviar
        
    Returns:
        Dict: Respuesta del microservicio
    """
    try:
        url = f"{service_url}/{endpoint}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data)
            response.raise_for_status()
            return response.json()
            
    except httpx.TimeoutException:
        logger.error(f"Timeout calling {service_url}/{endpoint}")
        raise HTTPException(status_code=504, detail="Service timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling {service_url}/{endpoint}: {e}")
        raise HTTPException(status_code=e.response.status_code, detail="Service error")
    except Exception as e:
        logger.error(f"Error calling {service_url}/{endpoint}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/")
async def root():
    """Endpoint raíz del API Gateway"""
    return {
        "service": "pulpo-ai-gateway",
        "version": "1.0.0",
        "status": "running",
        "description": "API Gateway para microservicios por vertical",
        "verticals": list(VERTICAL_SERVICES.keys()),
        "docs": "/docs"
    }

@app.get("/health")
async def health():
    """Health check del gateway"""
    return {
        "status": "healthy",
        "service": "pulpo-ai-gateway",
        "verticals_available": len(VERTICAL_SERVICES)
    }

@app.get("/verticals")
async def get_verticals():
    """Obtener verticales disponibles"""
    return {
        "verticals": VERTICAL_SERVICES,
        "total": len(VERTICAL_SERVICES)
    }

@app.get("/workspace/{workspace_id}/vertical")
async def get_workspace_vertical_endpoint(workspace_id: str):
    """Obtener vertical de un workspace"""
    try:
        vertical = await get_workspace_vertical(workspace_id)
        service_info = VERTICAL_SERVICES.get(vertical, {})
        
        return {
            "workspace_id": workspace_id,
            "vertical": vertical,
            "service": service_info
        }
    except Exception as e:
        logger.error(f"Error getting vertical for workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(
    request: Dict[str, Any]
):
    """
    Endpoint principal para chat - enruta al microservicio correcto
    
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
        
        # 1. Obtener vertical del workspace
        vertical = await get_workspace_vertical(workspace_id)
        
        # 2. Obtener configuración del servicio
        service_config = VERTICAL_SERVICES.get(vertical)
        if not service_config:
            raise HTTPException(
                status_code=404, 
                detail=f"Vertical '{vertical}' not supported"
            )
        
        # 3. Preparar datos para el microservicio
        data = {
            "workspace_id": workspace_id,
            "message": message,
            "conversation_id": conversation_id,
            "context": context or {}
        }
        
        # 4. Llamar al microservicio específico
        logger.info(f"Routing to {vertical} service: {service_config['url']}")
        response = await call_vertical_service(
            service_config["url"], 
            "chat", 
            data
        )
        
        # 5. Agregar metadatos del gateway
        response["gateway_info"] = {
            "vertical": vertical,
            "service_name": service_config["name"],
            "routed_at": "gateway"
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workspace/{workspace_id}/services")
async def get_workspace_services(workspace_id: str):
    """Obtener servicios disponibles para un workspace"""
    try:
        vertical = await get_workspace_vertical(workspace_id)
        service_config = VERTICAL_SERVICES.get(vertical)
        
        if not service_config:
            raise HTTPException(
                status_code=404,
                detail=f"Vertical '{vertical}' not supported"
            )
        
        # Llamar al microservicio para obtener servicios
        response = await call_vertical_service(
            service_config["url"],
            "services",
            {"workspace_id": workspace_id}
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting services for workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/workspace/{workspace_id}/prompts/{prompt_type}")
async def get_workspace_prompt(workspace_id: str, prompt_type: str):
    """Obtener prompt específico para un workspace"""
    try:
        vertical = await get_workspace_vertical(workspace_id)
        service_config = VERTICAL_SERVICES.get(vertical)
        
        if not service_config:
            raise HTTPException(
                status_code=404,
                detail=f"Vertical '{vertical}' not supported"
            )
        
        # Llamar al microservicio para obtener prompt
        response = await call_vertical_service(
            service_config["url"],
            f"prompts/{prompt_type}",
            {"workspace_id": workspace_id}
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting prompt for workspace {workspace_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,  # Puerto del gateway
        reload=True,
        log_level="info"
    )
