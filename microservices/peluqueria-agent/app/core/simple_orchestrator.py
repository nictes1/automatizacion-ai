"""
Simple Orchestrator - Versión simplificada que funciona
Para testing rápido sin LLM
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import httpx
import os

logger = logging.getLogger(__name__)

class SimplePeluqueriaOrchestrator:
    """Orquestador simplificado para testing"""
    
    def __init__(self):
        # Configuración de MCP
        self.mcp_url = os.getenv("MCP_URL", "http://localhost:8010")
        
        logger.info("✅ Simple Orchestrator inicializado")
    
    async def process_message(self, workspace_id: str, message: str, 
                            conversation_id: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Procesar mensaje de manera simplificada
        
        Args:
            workspace_id: ID del workspace
            message: Mensaje del usuario
            conversation_id: ID de la conversación
            context: Contexto adicional
            
        Returns:
            Respuesta del agente
        """
        try:
            logger.info(f"[SIMPLE-ORCHESTRATOR] Procesando mensaje para workspace {workspace_id}")
            
            # 1. Detectar intención simple
            intent = self._detect_simple_intent(message)
            logger.info(f"[SIMPLE-ORCHESTRATOR] Intención detectada: {intent}")
            
            # 2. Ejecutar función MCP correspondiente
            mcp_result = await self._call_mcp_simple(intent, workspace_id)
            logger.info(f"[SIMPLE-ORCHESTRATOR] Resultado MCP: {mcp_result.get('success', False)}")
            
            # 3. Generar respuesta simple
            response = self._generate_simple_response(intent, mcp_result)
            
            return {
                "assistant": response,
                "intent": intent,
                "mcp_result": mcp_result,
                "vertical": "peluqueria",
                "workspace_id": workspace_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[SIMPLE-ORCHESTRATOR] Error procesando mensaje: {e}")
            return {
                "assistant": "Disculpa, hubo un error procesando tu solicitud. ¿Podrías intentar de nuevo?",
                "error": str(e),
                "vertical": "peluqueria"
            }
    
    def _detect_simple_intent(self, message: str) -> str:
        """Detectar intención de manera simple"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["hola", "buenos días", "buenas tardes"]):
            return "greeting"
        elif any(word in message_lower for word in ["servicios", "qué tienen", "qué ofrecen"]):
            return "info_services"
        elif any(word in message_lower for word in ["precios", "cuánto cuesta", "costo"]):
            return "info_prices"
        elif any(word in message_lower for word in ["horarios", "cuándo", "disponible"]):
            return "info_hours"
        elif any(word in message_lower for word in ["turno", "cita", "agendar", "reservar"]):
            return "book_appointment"
        else:
            return "general_inquiry"
    
    async def _call_mcp_simple(self, intent: str, workspace_id: str) -> Dict[str, Any]:
        """Llamar a MCP de manera simple"""
        try:
            # Mapear intención a función MCP
            mcp_function = {
                "greeting": "get_services",
                "info_services": "get_services",
                "info_prices": "get_prices",
                "info_hours": "get_business_hours",
                "book_appointment": "book_appointment"
            }.get(intent, "get_services")
            
            # Llamar a MCP
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.mcp_url}/api/{mcp_function}",
                    json={"workspace_id": workspace_id}
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "success": True,
                    "data": result,
                    "function_called": mcp_function
                }
                
        except Exception as e:
            logger.error(f"Error llamando MCP: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": None
            }
    
    def _generate_simple_response(self, intent: str, mcp_result: Dict[str, Any]) -> str:
        """Generar respuesta simple"""
        
        if not mcp_result.get("success", False):
            return "Disculpa, no pude obtener la información. ¿Podrías intentar de nuevo?"
        
        data = mcp_result.get("data", {})
        
        if intent == "greeting":
            return "¡Hola! Bienvenido a nuestra peluquería. ¿En qué puedo ayudarte hoy?"
        
        elif intent == "info_services":
            services = data.get("services", [])
            if services:
                services_text = "\n".join([f"• {s.get('name', 'Servicio')}: ${s.get('price_min', 0)}-${s.get('price_max', 0)}" for s in services])
                return f"¡Aquí tienes nuestros servicios!\n\n{services_text}\n\n¿Te gustaría agendar alguno?"
            else:
                return "No pude obtener la información de servicios. ¿Podrías intentar de nuevo?"
        
        elif intent == "info_prices":
            prices = data.get("prices", [])
            if prices:
                prices_text = "\n".join([f"• {p.get('name', 'Servicio')}: ${p.get('price_min', 0)}-${p.get('price_max', 0)}" for p in prices])
                return f"¡Aquí tienes nuestros precios!\n\n{prices_text}\n\n¿Te gustaría agendar alguno?"
            else:
                return "No pude obtener la información de precios. ¿Podrías intentar de nuevo?"
        
        elif intent == "info_hours":
            hours = data.get("open", "09:00")
            close = data.get("close", "19:00")
            days = data.get("days", "Lun-Sáb")
            return f"Nuestros horarios de atención son:\n\n{days}: {hours} - {close}\n\n¿Te gustaría agendar un turno?"
        
        elif intent == "book_appointment":
            return "¡Perfecto! Te ayudo a agendar tu turno. ¿Qué servicio te gustaría?"
        
        else:
            return "¿En qué más puedo ayudarte? Puedo ayudarte con información sobre nuestros servicios, precios, horarios o agendar turnos."
