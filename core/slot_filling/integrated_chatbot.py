#!/usr/bin/env python3
"""
Sistema integrado de chatbot con Slot Filling + RAG + Debounce
Implementa el patrón completo de diálogo orientado a tareas
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path

# Importar componentes del sistema
from slot_filling_system import SlotFillingSystem, Workspace, Conversation, Message, MessageDirection
from debounce_system import DebounceSystem, DebounceManager, DebounceResult
from smart_document_processor import SmartDocumentProcessor

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IntegratedChatbot:
    """Sistema integrado de chatbot con todas las funcionalidades"""
    
    def __init__(self, rag_system=None, redis_url: str = "redis://localhost:6379"):
        # Componentes del sistema
        self.slot_filling_system = SlotFillingSystem(rag_system)
        self.debounce_system = DebounceSystem(redis_url)
        self.debounce_manager = DebounceManager(self.debounce_system, self._process_debounced_message)
        self.rag_system = rag_system
        
        # Estado del sistema
        self.is_running = False
        self.workspaces: Dict[str, Workspace] = {}
        self.conversations: Dict[str, Conversation] = {}
        
        # Cargar configuración
        self._load_workspaces()
    
    def _load_workspaces(self):
        """Cargar workspaces desde configuración"""
        # En producción, esto vendría de la base de datos
        self.workspaces = {
            "550e8400-e29b-41d4-a716-446655440000": Workspace(
                id="550e8400-e29b-41d4-a716-446655440000",
                name="La Nonna",
                vertical="gastronomia",
                plan="premium",
                rag_index="la-nonna-menu",
                twilio_from="+5491123456789"
            ),
            "550e8400-e29b-41d4-a716-446655440001": Workspace(
                id="550e8400-e29b-41d4-a716-446655440001",
                name="Inmobiliaria Central",
                vertical="inmobiliaria",
                plan="basic",
                rag_index="central-properties",
                twilio_from="+5491123456790"
            )
        }
        logger.info(f"✅ {len(self.workspaces)} workspaces cargados")
    
    async def start(self):
        """Iniciar el sistema completo"""
        try:
            self.is_running = True
            
            # Iniciar loop de debounce
            self.debounce_manager.is_running = True
            asyncio.create_task(self.debounce_manager.start_flush_loop())
            
            logger.info("🚀 Sistema integrado iniciado")
            
        except Exception as e:
            logger.error(f"❌ Error iniciando sistema: {e}")
            raise
    
    async def stop(self):
        """Detener el sistema"""
        try:
            self.is_running = False
            await self.debounce_manager.stop_flush_loop()
            logger.info("⏹️ Sistema integrado detenido")
            
        except Exception as e:
            logger.error(f"❌ Error deteniendo sistema: {e}")
    
    async def _process_debounced_message(self, result: DebounceResult):
        """Procesar mensaje después del debounce"""
        try:
            logger.info(f"📨 Procesando mensaje debounced: {result.workspace_id} - {result.user_phone}")
            
            # Obtener workspace
            workspace = self.workspaces.get(result.workspace_id)
            if not workspace:
                logger.error(f"Workspace no encontrado: {result.workspace_id}")
                return
            
            # Obtener o crear conversación
            conversation = await self._get_or_create_conversation(
                result.workspace_id, result.user_phone
            )
            
            # Crear mensaje
            message = Message(
                id=str(uuid.uuid4()),
                conversation_id=conversation.id,
                workspace_id=result.workspace_id,
                direction=MessageDirection.INBOUND,
                text=result.aggregated_text,
                wa_message_sid=result.messages[-1].wa_message_sid if result.messages else None,
                created_at=datetime.now()
            )
            
            # Procesar con slot filling
            response_text, new_state = await self.slot_filling_system.process_message(
                workspace, conversation, message, result.aggregated_text
            )
            
            # Actualizar conversación
            conversation.state = new_state
            conversation.last_message_at = datetime.now()
            conversation.total_messages += 1
            
            # Crear mensaje de respuesta
            response_message = Message(
                id=str(uuid.uuid4()),
                conversation_id=conversation.id,
                workspace_id=result.workspace_id,
                direction=MessageDirection.OUTBOUND,
                text=response_text,
                created_at=datetime.now()
            )
            
            # Enviar respuesta (simulado)
            await self._send_response(workspace, result.user_phone, response_text)
            
            # Guardar en base de datos (simulado)
            await self._save_conversation(conversation)
            await self._save_message(message)
            await self._save_message(response_message)
            
            logger.info(f"✅ Mensaje procesado y respuesta enviada")
            
        except Exception as e:
            logger.error(f"❌ Error procesando mensaje debounced: {e}")
    
    async def _get_or_create_conversation(self, workspace_id: str, user_phone: str) -> Conversation:
        """Obtener o crear conversación"""
        conversation_key = f"{workspace_id}:{user_phone}"
        
        if conversation_key in self.conversations:
            return self.conversations[conversation_key]
        
        # Crear nueva conversación
        conversation = Conversation(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            user_phone=user_phone,
            state={
                'current_state': 'START',
                'slots': {},
                'last_updated': datetime.now().isoformat()
            },
            last_message_at=datetime.now(),
            total_messages=0,
            unread_count=0
        )
        
        self.conversations[conversation_key] = conversation
        return conversation
    
    async def _send_response(self, workspace: Workspace, user_phone: str, text: str):
        """Enviar respuesta (simulado - en producción sería Twilio)"""
        logger.info(f"📤 Enviando respuesta a {user_phone}: {text}")
        # Aquí iría la integración con Twilio
        # await twilio_client.messages.create(
        #     from_=f"whatsapp:{workspace.twilio_from}",
        #     to=f"whatsapp:{user_phone}",
        #     body=text
        # )
    
    async def _save_conversation(self, conversation: Conversation):
        """Guardar conversación en base de datos (simulado)"""
        logger.debug(f"💾 Guardando conversación: {conversation.id}")
        # Aquí iría la persistencia en PostgreSQL
    
    async def _save_message(self, message: Message):
        """Guardar mensaje en base de datos (simulado)"""
        logger.debug(f"💾 Guardando mensaje: {message.id}")
        # Aquí iría la persistencia en PostgreSQL
    
    async def handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Manejar webhook de Twilio"""
        try:
            # Normalizar payload de Twilio
            normalized = self._normalize_twilio_payload(payload)
            
            if not normalized:
                return {"error": "Payload inválido"}
            
            # Agregar mensaje al debounce
            result = await self.debounce_manager.process_message(
                normalized['workspace_id'],
                normalized['user_phone'],
                normalized['text'],
                normalized['wa_sid'],
                normalized.get('raw')
            )
            
            return {
                "status": "received",
                "trigger": result.trigger,
                "message_count": len(result.messages)
            }
            
        except Exception as e:
            logger.error(f"❌ Error manejando webhook: {e}")
            return {"error": str(e)}
    
    def _normalize_twilio_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalizar payload de Twilio"""
        try:
            # Extraer información del payload
            body = payload.get('Body', '')
            from_number = payload.get('From', '').replace('whatsapp:', '')
            message_sid = payload.get('MessageSid', '')
            
            # En producción, el workspace_id vendría de la configuración de Twilio
            # o se determinaría por el número de teléfono
            workspace_id = payload.get('WorkspaceId') or "550e8400-e29b-41d4-a716-446655440000"
            
            if not all([body, from_number, message_sid]):
                return None
            
            return {
                'workspace_id': workspace_id,
                'user_phone': from_number,
                'text': body.strip(),
                'wa_sid': message_sid,
                'raw': payload
            }
            
        except Exception as e:
            logger.error(f"Error normalizando payload: {e}")
            return None
    
    async def get_conversation_state(self, workspace_id: str, user_phone: str) -> Optional[Dict[str, Any]]:
        """Obtener estado de conversación"""
        conversation_key = f"{workspace_id}:{user_phone}"
        conversation = self.conversations.get(conversation_key)
        
        if conversation:
            return {
                'conversation_id': conversation.id,
                'current_state': conversation.state.get('current_state'),
                'slots': conversation.state.get('slots', {}),
                'total_messages': conversation.total_messages,
                'last_message_at': conversation.last_message_at.isoformat() if conversation.last_message_at else None
            }
        
        return None
    
    async def get_debounce_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del debounce"""
        return await self.debounce_system.get_buffer_stats()
    
    async def test_conversation_flow(self, workspace_id: str, user_phone: str, messages: List[str]):
        """Probar flujo de conversación completo"""
        logger.info(f"🧪 Iniciando prueba de conversación: {workspace_id} - {user_phone}")
        
        for i, message_text in enumerate(messages):
            logger.info(f"📨 Mensaje {i+1}: {message_text}")
            
            # Simular webhook
            payload = {
                'Body': message_text,
                'From': f'whatsapp:{user_phone}',
                'MessageSid': f'test_msg_{i+1}',
                'WorkspaceId': workspace_id
            }
            
            result = await self.handle_webhook(payload)
            logger.info(f"📤 Resultado: {result}")
            
            # Esperar un poco entre mensajes
            await asyncio.sleep(1)
        
        # Mostrar estado final
        state = await self.get_conversation_state(workspace_id, user_phone)
        logger.info(f"📊 Estado final: {json.dumps(state, indent=2, default=str)}")

# Función de conveniencia
def create_integrated_chatbot(rag_system=None, redis_url: str = "redis://localhost:6379") -> IntegratedChatbot:
    """Crear sistema integrado de chatbot"""
    return IntegratedChatbot(rag_system, redis_url)

# Ejemplo de uso
async def example_conversation():
    """Ejemplo de conversación completa"""
    
    # Crear sistema (sin RAG para el ejemplo)
    chatbot = create_integrated_chatbot()
    
    try:
        # Iniciar sistema
        await chatbot.start()
        
        # Simular conversación de gastronomía
        workspace_id = "550e8400-e29b-41d4-a716-446655440000"  # La Nonna
        user_phone = "+5491123456789"
        
        messages = [
            "Hola",
            "quiero hacer un pedido",
            "de pizzas",
            "una margherita",
            "retiro",
            "efectivo"
        ]
        
        await chatbot.test_conversation_flow(workspace_id, user_phone, messages)
        
        # Esperar un poco para que se procese el debounce
        await asyncio.sleep(15)
        
        # Mostrar estadísticas
        stats = await chatbot.get_debounce_stats()
        logger.info(f"📊 Estadísticas debounce: {json.dumps(stats, indent=2)}")
        
    finally:
        # Detener sistema
        await chatbot.stop()

if __name__ == "__main__":
    asyncio.run(example_conversation())
