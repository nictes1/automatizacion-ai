"""
Response Generator - Generación de respuestas con LLM
Genera respuestas naturales usando LLM basándose en datos reales del MCP
"""

import logging
from typing import Dict, Any, List
import httpx
import os

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """Generador de respuestas usando LLM"""
    
    def __init__(self):
        # Configuración de LLM
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.model_name = os.getenv("MODEL_NAME", "llama3.2:3b")
        
        logger.info("✅ Response Generator inicializado")
    
    async def generate_response(self, intent: str, entities: Dict[str, Any], 
                              mcp_result: Dict[str, Any], conversation_context: List[Dict[str, Any]],
                              workspace_id: str) -> str:
        """
        Generar respuesta natural usando LLM basándose en datos reales
        
        Args:
            intent: Intención del usuario
            entities: Entidades extraídas
            mcp_result: Resultado de la función MCP
            conversation_context: Contexto de la conversación
            workspace_id: ID del workspace
            
        Returns:
            str: Respuesta generada por LLM
        """
        try:
            # Construir prompt para generación de respuesta
            prompt = self._build_response_prompt(
                intent, entities, mcp_result, conversation_context, workspace_id
            )
            
            # Llamar al LLM para generar respuesta
            response = await self._call_llm(prompt)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            return "Disculpa, hubo un error procesando tu solicitud. ¿Podrías intentar de nuevo?"
    
    def _build_response_prompt(self, intent: str, entities: Dict[str, Any], 
                             mcp_result: Dict[str, Any], conversation_context: List[Dict[str, Any]],
                             workspace_id: str) -> str:
        """Construir prompt para generación de respuesta"""
        
        # Construir historial de conversación
        conversation_history = ""
        for msg in conversation_context[-5:]:  # Últimos 5 mensajes
            role = "Usuario" if msg["role"] == "user" else "Asistente"
            conversation_history += f"{role}: {msg['message']}\n"
        
        # Información del MCP
        mcp_info = ""
        if mcp_result.get("success"):
            mcp_data = mcp_result.get("data", {})
            mcp_info = f"Datos obtenidos del sistema: {mcp_data}"
        else:
            mcp_info = f"Error obteniendo datos: {mcp_result.get('error', 'Error desconocido')}"
        
        return f"""Eres un asistente de peluquería profesional y amigable. Genera una respuesta natural y útil basándote en la información disponible.

CONTEXTO DE LA CONVERSACIÓN:
{conversation_history}

INTENCIÓN DEL USUARIO: {intent}
ENTIDADES EXTRAÍDAS: {entities}
WORKSPACE: {workspace_id}

{mcp_info}

INSTRUCCIONES:
1. Sé amable, profesional y conversacional
2. Usa la información real obtenida del sistema (MCP)
3. Si hay datos específicos, úsalos en tu respuesta
4. Si hay errores, explica de manera amigable
5. Mantén el foco en servicios de peluquería
6. Haz preguntas específicas si es necesario
7. Usa un tono natural y cercano

GENERA UNA RESPUESTA NATURAL Y ÚTIL:"""
    
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
                            "temperature": 0.8,
                            "top_p": 0.9,
                            "max_tokens": 500
                        }
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("response", "")
                
        except Exception as e:
            logger.error(f"Error llamando LLM: {e}")
            return "Disculpa, no pude procesar tu solicitud en este momento."
    
    async def generate_follow_up_question(self, intent: str, entities: Dict[str, Any], 
                                        missing_info: List[str]) -> str:
        """
        Generar pregunta de seguimiento para obtener información faltante
        
        Args:
            intent: Intención del usuario
            entities: Entidades ya obtenidas
            missing_info: Información faltante
            
        Returns:
            str: Pregunta de seguimiento generada por LLM
        """
        try:
            prompt = f"""Eres un asistente de peluquería. Genera una pregunta natural para obtener información faltante.

INTENCIÓN: {intent}
INFORMACIÓN YA OBTENIDA: {entities}
INFORMACIÓN FALTANTE: {missing_info}

Genera una pregunta amigable y específica para obtener la información faltante:"""
            
            response = await self._call_llm(prompt)
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generando pregunta de seguimiento: {e}")
            return "¿Podrías proporcionarme más información?"
    
    async def generate_error_response(self, error_type: str, error_message: str) -> str:
        """
        Generar respuesta de error amigable
        
        Args:
            error_type: Tipo de error
            error_message: Mensaje de error
            
        Returns:
            str: Respuesta de error generada por LLM
        """
        try:
            prompt = f"""Eres un asistente de peluquería. Genera una respuesta amigable para un error del sistema.

TIPO DE ERROR: {error_type}
MENSAJE DE ERROR: {error_message}

Genera una respuesta que:
1. Sea amigable y no técnica
2. Explique el problema de manera simple
3. Ofrezca alternativas
4. Mantenga el tono profesional

RESPUESTA:"""
            
            response = await self._call_llm(prompt)
            return response.strip()
            
        except Exception as e:
            logger.error(f"Error generando respuesta de error: {e}")
            return "Disculpa, hubo un problema técnico. ¿Podrías intentar de nuevo?"
