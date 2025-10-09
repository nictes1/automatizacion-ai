"""
MCP Server para Tools de Servicios (Peluquería)
Expone los tools via Model Context Protocol para que el orchestrator los consuma
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Import our tools
from services.servicios_tools import (
    SERVICIOS_TOOLS,
    execute_tool,
    get_available_services,
    check_service_availability,
    get_service_packages,
    get_active_promotions,
    get_business_hours
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# MCP Protocol Models
# =========================

class ToolParameter(BaseModel):
    """Schema para un parámetro de tool"""
    type: str
    description: Optional[str] = None
    required: bool = False
    enum: Optional[List[str]] = None

class ToolDefinition(BaseModel):
    """Definición de un tool en formato MCP"""
    name: str
    description: str
    inputSchema: Dict[str, Any] = Field(alias="input_schema")

class ListToolsResponse(BaseModel):
    """Respuesta a tools/list"""
    tools: List[ToolDefinition]

class CallToolRequest(BaseModel):
    """Request para llamar a un tool"""
    name: str
    arguments: Dict[str, Any] = {}

class CallToolResponse(BaseModel):
    """Respuesta de un tool"""
    content: List[Dict[str, Any]]
    isError: bool = Field(default=False, alias="is_error")

# =========================
# MCP Server Application
# =========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle handler"""
    logger.info("🚀 MCP Server starting up...")
    yield
    logger.info("🛑 MCP Server shutting down...")

app = FastAPI(
    title="PulpoAI MCP Server - Servicios",
    description="Model Context Protocol server para tools de servicios (peluquería)",
    version="1.0.0",
    lifespan=lifespan
)

# =========================
# MCP Endpoints
# =========================

@app.get("/")
async def root():
    """Root endpoint con info del server"""
    return {
        "name": "pulpoai-servicios-mcp",
        "version": "1.0.0",
        "protocol": "mcp",
        "capabilities": {
            "tools": True
        }
    }

@app.post("/mcp/tools/list", response_model=ListToolsResponse)
async def list_tools():
    """
    Lista todos los tools disponibles (MCP standard)
    Endpoint: POST /mcp/tools/list
    """
    tools = []

    for tool_name, tool_config in SERVICIOS_TOOLS.items():
        # Convertir a schema JSON para MCP
        parameters = tool_config.get("parameters", {})

        properties = {}
        required = []

        for param_name, param_config in parameters.items():
            properties[param_name] = {
                "type": param_config.get("type", "string"),
                "description": param_config.get("description", "")
            }

            if param_config.get("required", False):
                required.append(param_name)

        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required
        }

        tools.append(ToolDefinition(
            name=tool_name,
            description=tool_config.get("description", ""),
            input_schema=input_schema
        ))

    logger.info(f"📋 Listando {len(tools)} tools disponibles")
    return ListToolsResponse(tools=tools)

@app.post("/mcp/tools/call", response_model=CallToolResponse)
async def call_tool(request: CallToolRequest):
    """
    Ejecuta un tool específico (MCP standard)
    Endpoint: POST /mcp/tools/call

    Body:
    {
        "name": "get_available_services",
        "arguments": {"workspace_id": "..."}
    }
    """
    tool_name = request.name
    arguments = request.arguments

    logger.info(f"🔧 Llamando tool: {tool_name} con args: {arguments}")

    # Verificar que el tool existe
    if tool_name not in SERVICIOS_TOOLS:
        logger.error(f"❌ Tool no encontrado: {tool_name}")
        return CallToolResponse(
            content=[{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Tool '{tool_name}' no encontrado"
                })
            }],
            is_error=True
        )

    try:
        # Ejecutar el tool
        result = await execute_tool(tool_name, **arguments)

        # Formatear respuesta en formato MCP
        success = result.get("success", False)

        response = CallToolResponse(
            content=[{
                "type": "text",
                "text": json.dumps(result, ensure_ascii=False)
            }],
            is_error=not success
        )

        logger.info(f"✅ Tool ejecutado: {tool_name}, success={success}")
        return response

    except Exception as e:
        logger.error(f"❌ Error ejecutando tool {tool_name}: {e}")
        return CallToolResponse(
            content=[{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": str(e)
                })
            }],
            is_error=True
        )

# =========================
# Helper Endpoints (No-MCP, para debugging)
# =========================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mcp-servicios"}

@app.get("/tools")
async def get_tools_simple():
    """Lista tools en formato simple (no-MCP)"""
    return {
        "tools": list(SERVICIOS_TOOLS.keys()),
        "count": len(SERVICIOS_TOOLS)
    }

@app.post("/tools/{tool_name}")
async def call_tool_simple(tool_name: str, arguments: Dict[str, Any]):
    """Llama a un tool directamente (no-MCP, para testing)"""
    if tool_name not in SERVICIOS_TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' no encontrado")

    try:
        result = await execute_tool(tool_name, **arguments)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# Main
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8010,
        log_level="info"
    )
