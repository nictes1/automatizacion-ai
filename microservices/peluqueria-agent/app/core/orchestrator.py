"""
Orquestador Principal - Cerebro Coordinador
Coordina el análisis de intención, integración MCP y generación de respuestas
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import asyncio

from .conversation_manager import ConversationManager
from .mcp_manager import MCPManager
from .response_generator import ResponseGenerator

logger = logging.getLogger(__name__)

class PeluqueriaOrchestrator:
    """Orquestador principal que coordina análisis, MCP y generación de respuestas"""
    
    def __init__(self):
        # Componentes principales
        self.conversation_manager = ConversationManager()
        self.mcp_manager = MCPManager()
        self.response_generator = ResponseGenerator()
        
        logger.info("✅ Orquestador Principal (LLM + MCP) inicializado")
    
    async def process_message(self, workspace_id: str, message: str, 
                            conversation_id: str = None, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Procesar mensaje con análisis completo de contexto y integración MCP
        
        Args:
            workspace_id: ID del workspace
            message: Mensaje del usuario
            conversation_id: ID de la conversación
            context: Contexto adicional
            
        Returns:
            Respuesta del agente con datos reales del MCP
        """
        try:
            logger.info(f"[ORCHESTRATOR] Procesando mensaje para workspace {workspace_id}")
            
            # 1. Obtener contexto completo de la conversación
            conversation_context = await self.conversation_manager.get_conversation_context(
                workspace_id, conversation_id or "default"
            )
            
            # 2. Analizar intención considerando TODO el contexto
            intent_analysis = await self.conversation_manager.analyze_intent_with_context(
                message, conversation_context, workspace_id
            )
            
            intent = intent_analysis.get("intent", "general_inquiry")
            entities = intent_analysis.get("entities", {})
            
            logger.info(f"[ORCHESTRATOR] Intención detectada: {intent}")
            logger.info(f"[ORCHESTRATOR] Entidades: {entities}")
            
            # 3. Ejecutar función MCP correspondiente
            mcp_result = await self.mcp_manager.execute_mcp_function(
                intent, entities, workspace_id
            )
            
            logger.info(f"[ORCHESTRATOR] Resultado MCP: {mcp_result.get('success', False)}")
            
            # 4. Generar respuesta usando LLM con datos reales del MCP
            response = await self.response_generator.generate_response(
                intent, entities, mcp_result, conversation_context, workspace_id
            )
            
            return {
                "assistant": response,
                "intent": intent,
                "entities": entities,
                "mcp_result": mcp_result,
                "context_understanding": intent_analysis.get("context_understanding", ""),
                "vertical": "peluqueria",
                "workspace_id": workspace_id,
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Error procesando mensaje: {e}")
            return {
                "assistant": "Disculpa, hubo un error procesando tu solicitud. ¿Podrías intentar de nuevo?",
                "error": str(e),
                "vertical": "peluqueria"
            }
