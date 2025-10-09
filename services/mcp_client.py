"""
MCP Client para el Orchestrator
Cliente para consumir tools via Model Context Protocol
"""

import httpx
import logging
import os
from typing import Dict, List, Any, Optional
import json

logger = logging.getLogger(__name__)

# MCP Server URL from environment or default to localhost
MCP_SERVER_URL = os.getenv("MCP_URL", "http://localhost:8010")

class MCPClient:
    """Cliente MCP para comunicarse con el servidor de tools"""

    def __init__(self, base_url: str = "http://localhost:8010"):
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    async def close(self):
        """Cierra el cliente HTTP"""
        await self.client.aclose()

    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        Lista todos los tools disponibles

        Returns:
            [
                {
                    "name": "get_available_services",
                    "description": "...",
                    "input_schema": {...}
                },
                ...
            ]
        """
        # Usar cache si está disponible
        if self._tools_cache is not None:
            return self._tools_cache

        try:
            response = await self.client.post(f"{self.base_url}/mcp/tools/list")
            response.raise_for_status()
            data = response.json()

            tools = data.get("tools", [])
            self._tools_cache = tools  # Cache

            logger.info(f"📋 MCP Client: {len(tools)} tools disponibles")
            return tools

        except Exception as e:
            logger.error(f"❌ Error listando tools via MCP: {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Llama a un tool específico

        Args:
            tool_name: Nombre del tool (ej: "get_available_services")
            arguments: Argumentos del tool (ej: {"workspace_id": "..."})

        Returns:
            Resultado del tool parseado como dict

        Example:
            result = await client.call_tool("get_available_services", {
                "workspace_id": "550e8400-e29b-41d4-a716-446655440000"
            })
            # result = {"success": True, "services": [...]}
        """
        try:
            logger.info(f"🔧 MCP Client: Llamando tool '{tool_name}' con args: {arguments}")

            response = await self.client.post(
                f"{self.base_url}/mcp/tools/call",
                json={
                    "name": tool_name,
                    "arguments": arguments
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

            # MCP response format:
            # {
            #   "content": [{"type": "text", "text": "{...}"}],
            #   "is_error": false
            # }

            is_error = data.get("is_error", False)
            content = data.get("content", [])

            if is_error:
                error_text = content[0].get("text", "Unknown error") if content else "Unknown error"
                logger.error(f"❌ MCP Tool error: {error_text}")
                return json.loads(error_text) if error_text.startswith("{") else {"success": False, "error": error_text}

            if not content:
                logger.warning(f"⚠️  MCP Tool returned empty content")
                return {"success": False, "error": "Empty response from MCP server"}

            # Parse el texto JSON del content
            result_text = content[0].get("text", "{}")
            result = json.loads(result_text)

            logger.info(f"✅ MCP Client: Tool '{tool_name}' completado, success={result.get('success')}")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error llamando MCP tool '{tool_name}': {e.response.status_code}")
            return {
                "success": False,
                "error": f"HTTP {e.response.status_code}: {e.response.text}"
            }
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error parseando respuesta JSON de MCP: {e}")
            return {
                "success": False,
                "error": f"Invalid JSON response: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Error inesperado llamando MCP tool '{tool_name}': {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_tool_schema(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el schema de un tool específico

        Returns:
            {
                "name": "...",
                "description": "...",
                "input_schema": {...}
            }
        """
        tools = await self.list_tools()
        for tool in tools:
            if tool.get("name") == tool_name:
                return tool
        return None

# =========================
# Global MCP Client Instance
# =========================

# Singleton instance
_mcp_client: Optional[MCPClient] = None

def get_mcp_client(base_url: str = None) -> MCPClient:
    """
    Obtiene o crea la instancia global del MCP client

    Usage:
        client = get_mcp_client()
        result = await client.call_tool("get_available_services", {...})
    """
    global _mcp_client
    if _mcp_client is None:
        url = base_url or MCP_SERVER_URL
        _mcp_client = MCPClient(base_url=url)
    return _mcp_client

async def close_mcp_client():
    """Cierra el MCP client global"""
    global _mcp_client
    if _mcp_client is not None:
        await _mcp_client.close()
        _mcp_client = None
