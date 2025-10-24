"""
Conversation Manager - Gestión de contexto de conversación
Lee toda la conversación para entender la intención completa
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
import os

logger = logging.getLogger(__name__)

class ConversationManager:
    """Gestor de contexto de conversación completo"""
    
    def __init__(self):
        # Configuración de LLM
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.model_name = os.getenv("MODEL_NAME", "llama3.2:3b")
        
        # Configuración de base de datos
        self.database_url = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@postgres:5432/pulpo")
        
        logger.info("✅ Conversation Manager inicializado")
    
    async def get_conversation_context(self, workspace_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Obtener contexto completo de la conversación
        
        Args:
            workspace_id: ID del workspace
            conversation_id: ID de la conversación
            
        Returns:
            List[Dict]: Lista de mensajes de la conversación
        """
        try:
            # En un sistema real, esto consultaría la base de datos
            # Por ahora simulamos el contexto
            context = [
                {
                    "role": "user",
                    "message": "Hola, quiero agendar un turno",
                    "timestamp": datetime.now().isoformat()
                },
                {
                    "role": "assistant", 
                    "message": "¡Hola! ¿Qué servicio te gustaría agendar?",
                    "timestamp": datetime.now().isoformat()
                }
            ]
            
            return context
            
        except Exception as e:
            logger.error(f"Error obteniendo contexto de conversación: {e}")
            return []
    
    async def analyze_intent_with_context(self, message: str, conversation_context: List[Dict[str, Any]], 
                                        workspace_id: str) -> Dict[str, Any]:
        """
        Analizar intención considerando TODO el contexto de la conversación
        
        Args:
            message: Mensaje actual del usuario
            conversation_context: Contexto completo de la conversación
            workspace_id: ID del workspace
            
        Returns:
            Dict: Análisis completo de intención y entidades
        """
        try:
            # Construir prompt con contexto completo
            prompt = self._build_context_analysis_prompt(message, conversation_context)
            
            # Llamar al LLM con contexto completo
            response = await self._call_llm(prompt)
            
            # Parsear respuesta del LLM
            try:
                import json
                result = json.loads(response)
                return {
                    "intent": result.get("intent", "general_inquiry"),
                    "entities": result.get("entities", {}),
                    "confidence": result.get("confidence", 0.8),
                    "context_understanding": result.get("context_understanding", ""),
                    "next_action": result.get("next_action", "continue_conversation")
                }
            except json.JSONDecodeError:
                # Fallback si el LLM no devuelve JSON válido
                return await self._fallback_intent_analysis(message, conversation_context)
                
        except Exception as e:
            logger.error(f"Error analizando intención con contexto: {e}")
            return {
                "intent": "general_inquiry",
                "entities": {},
                "confidence": 0.3,
                "context_understanding": "Error en análisis",
                "next_action": "continue_conversation"
            }
    
    def _build_context_analysis_prompt(self, message: str, conversation_context: List[Dict[str, Any]]) -> str:
        """Construir prompt para análisis con contexto completo"""
        
        # Construir historial de conversación
        conversation_history = ""
        for msg in conversation_context[-10:]:  # Últimos 10 mensajes
            role = "Usuario" if msg["role"] == "user" else "Asistente"
            conversation_history += f"{role}: {msg['message']}\n"
        
        return f"""Eres un asistente especializado en peluquería. Analiza la intención del usuario considerando TODO el contexto de la conversación.

CONTEXTO DE LA CONVERSACIÓN:
{conversation_history}

MENSAJE ACTUAL DEL USUARIO: "{message}"

INTENCIONES DISPONIBLES:
- greeting: Saludo inicial
- info_services: Consultar servicios disponibles
- info_prices: Consultar precios
- info_hours: Consultar horarios
- book_appointment: Agendar turno
- check_availability: Verificar disponibilidad
- cancel_appointment: Cancelar turno
- modify_appointment: Modificar turno
- general_inquiry: Consulta general

ENTIDADES A EXTRAER:
- service_type: Tipo de servicio
- preferred_date: Fecha preferida
- preferred_time: Hora preferida
- client_name: Nombre del cliente
- client_email: Email del cliente
- client_phone: Teléfono del cliente
- staff_preference: Profesional preferido
- notes: Notas adicionales

INSTRUCCIONES:
1. Considera TODO el contexto de la conversación, no solo el último mensaje
2. Identifica la intención principal del usuario
3. Extrae entidades relevantes
4. Determina qué acción tomar basándote en el contexto completo
5. Evalúa la confianza en tu análisis

Responde SOLO con un JSON válido:
{{
    "intent": "nombre_de_la_intencion",
    "entities": {{
        "slot_name": "valor_extraido"
    }},
    "confidence": 0.8,
    "context_understanding": "Explicación de cómo el contexto influye en la intención",
    "next_action": "accion_siguiente"
}}"""
    
    async def _call_llm(self, prompt: str) -> str:
        """Llamar al LLM"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9,
                            "max_tokens": 1000
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
                
        except Exception as e:
            logger.error(f"Error llamando LLM: {e}")
            return ""
    
    async def _fallback_intent_analysis(self, message: str, conversation_context: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback para análisis de intención"""
        message_lower = message.lower()
        
        # Análisis simple basado en palabras clave
        if any(word in message_lower for word in ["hola", "buenos días", "buenas tardes"]):
            return {
                "intent": "greeting",
                "entities": {},
                "confidence": 0.9,
                "context_understanding": "Saludo detectado",
                "next_action": "greet_user"
            }
        
        elif any(word in message_lower for word in ["servicios", "qué tienen", "qué ofrecen"]):
            return {
                "intent": "info_services",
                "entities": {},
                "confidence": 0.8,
                "context_understanding": "Consulta sobre servicios",
                "next_action": "get_services_info"
            }
        
        elif any(word in message_lower for word in ["precios", "cuánto cuesta", "costo"]):
            return {
                "intent": "info_prices",
                "entities": {},
                "confidence": 0.8,
                "context_understanding": "Consulta sobre precios",
                "next_action": "get_prices_info"
            }
        
        elif any(word in message_lower for word in ["turno", "cita", "agendar", "reservar"]):
            return {
                "intent": "book_appointment",
                "entities": {},
                "confidence": 0.8,
                "context_understanding": "Intención de agendar turno",
                "next_action": "collect_booking_info"
            }
        
        else:
            return {
                "intent": "general_inquiry",
                "entities": {},
                "confidence": 0.5,
                "context_understanding": "Consulta general",
                "next_action": "continue_conversation"
            }
