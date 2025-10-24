"""
MCP Manager - Integración con MCP para datos reales
Se comunica con el MCP para obtener información real de cada peluquería
"""

import logging
from typing import Dict, Any, Optional
import httpx
import os

logger = logging.getLogger(__name__)

class MCPManager:
    """Gestor de integración con MCP para datos reales"""
    
    def __init__(self):
        # Configuración de MCP
        self.mcp_url = os.getenv("MCP_URL", "http://mcp:8010")
        
        # Mapeo de intenciones a funciones MCP
        self.intent_to_mcp_function = {
            "info_services": "get_services",
            "info_prices": "get_prices", 
            "info_hours": "get_business_hours",
            "book_appointment": "book_appointment",
            "check_availability": "check_availability",
            "cancel_appointment": "cancel_appointment",
            "modify_appointment": "modify_appointment"
        }
        
        logger.info("✅ MCP Manager inicializado")
    
    async def execute_mcp_function(self, intent: str, entities: Dict[str, Any], 
                                  workspace_id: str) -> Dict[str, Any]:
        """
        Ejecutar función MCP basada en intención
        
        Args:
            intent: Intención del usuario
            entities: Entidades extraídas
            workspace_id: ID del workspace
            
        Returns:
            Dict: Resultado de la función MCP
        """
        try:
            # Obtener función MCP correspondiente
            mcp_function = self.intent_to_mcp_function.get(intent)
            
            if not mcp_function:
                return {
                    "success": False,
                    "error": f"No hay función MCP para la intención: {intent}",
                    "data": None
                }
            
            # Construir parámetros para la función MCP
            params = self._build_mcp_params(intent, entities, workspace_id)
            
            # Llamar a la función MCP
            result = await self._call_mcp_function(mcp_function, params)
            
            return result
            
        except Exception as e:
            logger.error(f"Error ejecutando función MCP: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    def _build_mcp_params(self, intent: str, entities: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Construir parámetros para función MCP"""
        base_params = {
            "workspace_id": workspace_id
        }
        
        if intent == "info_services":
            return base_params
        
        elif intent == "info_prices":
            return base_params
        
        elif intent == "info_hours":
            return base_params
        
        elif intent == "book_appointment":
            return {
                **base_params,
                "service_type": entities.get("service_type"),
                "preferred_date": entities.get("preferred_date"),
                "preferred_time": entities.get("preferred_time"),
                "client_name": entities.get("client_name", "Cliente"),
                "client_email": entities.get("client_email"),
                "client_phone": entities.get("client_phone"),
                "staff_preference": entities.get("staff_preference"),
                "notes": entities.get("notes")
            }
        
        elif intent == "check_availability":
            return {
                **base_params,
                "service_type": entities.get("service_type"),
                "date": entities.get("preferred_date"),
                "time": entities.get("preferred_time")
            }
        
        elif intent == "cancel_appointment":
            return {
                **base_params,
                "appointment_id": entities.get("appointment_id"),
                "client_phone": entities.get("client_phone")
            }
        
        elif intent == "modify_appointment":
            return {
                **base_params,
                "appointment_id": entities.get("appointment_id"),
                "new_date": entities.get("preferred_date"),
                "new_time": entities.get("preferred_time"),
                "client_phone": entities.get("client_phone")
            }
        
        return base_params
    
    async def _call_mcp_function(self, function_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Llamar a función MCP específica"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_url}/api/{function_name}",
                    json=params
                )
                response.raise_for_status()
                
                result = response.json()
                return {
                    "success": True,
                    "data": result,
                    "function_called": function_name
                }
                
        except httpx.TimeoutException:
            logger.error(f"Timeout llamando función MCP {function_name}")
            return {
                "success": False,
                "error": "Timeout en servicio MCP",
                "data": None
            }
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error llamando función MCP {function_name}: {e}")
            return {
                "success": False,
                "error": f"Error HTTP: {e.response.status_code}",
                "data": None
            }
        except Exception as e:
            logger.error(f"Error llamando función MCP {function_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    async def get_services_info(self, workspace_id: str) -> Dict[str, Any]:
        """Obtener información de servicios desde MCP"""
        return await self._call_mcp_function("get_services", {"workspace_id": workspace_id})
    
    async def get_prices_info(self, workspace_id: str) -> Dict[str, Any]:
        """Obtener información de precios desde MCP"""
        return await self._call_mcp_function("get_prices", {"workspace_id": workspace_id})
    
    async def get_business_hours(self, workspace_id: str) -> Dict[str, Any]:
        """Obtener horarios de atención desde MCP"""
        return await self._call_mcp_function("get_business_hours", {"workspace_id": workspace_id})
    
    async def book_appointment(self, workspace_id: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Agendar turno usando MCP"""
        params = self._build_mcp_params("book_appointment", entities, workspace_id)
        return await self._call_mcp_function("book_appointment", params)
    
    async def check_availability(self, workspace_id: str, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Verificar disponibilidad usando MCP"""
        params = self._build_mcp_params("check_availability", entities, workspace_id)
        return await self._call_mcp_function("check_availability", params)
