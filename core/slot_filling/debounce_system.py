#!/usr/bin/env python3
"""
Sistema de Debounce para mensajes de WhatsApp
Acumula mensajes durante 10 segundos y procesa el agregado
"""

import json
import asyncio
import redis
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import uuid

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class DebounceMessage:
    """Mensaje individual en el buffer de debounce"""
    timestamp: float
    text: str
    wa_message_sid: str
    raw_payload: Dict[str, Any] = None

@dataclass
class DebounceResult:
    """Resultado del debounce"""
    trigger: bool
    key: str
    messages: List[DebounceMessage]
    aggregated_text: str
    workspace_id: str
    user_phone: str

class DebounceSystem:
    """Sistema de debounce para mensajes de WhatsApp"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379", debounce_seconds: int = 10):
        self.redis_url = redis_url
        self.debounce_seconds = debounce_seconds
        self.redis_client = None
        self._connect_redis()
    
    def _connect_redis(self):
        """Conectar a Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.redis_client.ping()
            logger.info("✅ Redis conectado para debounce")
        except Exception as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            self.redis_client = None
    
    def _get_debounce_key(self, workspace_id: str, user_phone: str) -> str:
        """Generar clave de debounce"""
        return f"debounce:{workspace_id}:{user_phone}"
    
    async def add_message(self, workspace_id: str, user_phone: str, text: str, 
                         wa_message_sid: str, raw_payload: Dict[str, Any] = None) -> DebounceResult:
        """
        Agregar mensaje al buffer de debounce
        
        Returns:
            DebounceResult con trigger=True si debe procesarse inmediatamente
        """
        try:
            if not self.redis_client:
                logger.error("Redis no disponible")
                return DebounceResult(False, "", [], "", workspace_id, user_phone)
            
            key = self._get_debounce_key(workspace_id, user_phone)
            now = datetime.now().timestamp()
            
            # Crear mensaje
            message = DebounceMessage(
                timestamp=now,
                text=text,
                wa_message_sid=wa_message_sid,
                raw_payload=raw_payload
            )
            
            # Obtener buffer existente
            existing_data = self.redis_client.get(key)
            if existing_data:
                messages = json.loads(existing_data)
            else:
                messages = []
            
            # Agregar nuevo mensaje
            messages.append({
                'timestamp': message.timestamp,
                'text': message.text,
                'wa_message_sid': message.wa_message_sid,
                'raw_payload': message.raw_payload
            })
            
            # Guardar con TTL
            self.redis_client.setex(key, self.debounce_seconds, json.dumps(messages))
            
            # Convertir a objetos DebounceMessage
            debounce_messages = [
                DebounceMessage(
                    timestamp=msg['timestamp'],
                    text=msg['text'],
                    wa_message_sid=msg['wa_message_sid'],
                    raw_payload=msg.get('raw_payload')
                )
                for msg in messages
            ]
            
            # Agregar texto
            aggregated_text = " ".join([msg.text for msg in debounce_messages])
            
            # Heurística: si es el primer mensaje, no disparar inmediatamente
            # Solo disparar si hay múltiples mensajes y el último fue hace tiempo
            should_trigger = len(messages) > 1 and (
                now - messages[-2]['timestamp'] >= self.debounce_seconds
            )
            
            logger.info(f"Debounce: {len(messages)} mensajes, trigger={should_trigger}")
            
            return DebounceResult(
                trigger=should_trigger,
                key=key,
                messages=debounce_messages,
                aggregated_text=aggregated_text,
                workspace_id=workspace_id,
                user_phone=user_phone
            )
            
        except Exception as e:
            logger.error(f"Error en add_message: {e}")
            return DebounceResult(False, "", [], "", workspace_id, user_phone)
    
    async def flush_expired(self) -> List[DebounceResult]:
        """
        Buscar y procesar buffers expirados
        Se ejecuta periódicamente (cada 5 segundos)
        """
        try:
            if not self.redis_client:
                return []
            
            # Buscar todas las claves de debounce
            pattern = "debounce:*"
            keys = self.redis_client.keys(pattern)
            
            results = []
            now = datetime.now().timestamp()
            
            for key in keys:
                try:
                    # Verificar TTL
                    ttl = self.redis_client.ttl(key)
                    
                    # Si TTL <= 0, el buffer expiró
                    if ttl <= 0:
                        # Obtener datos
                        data = self.redis_client.get(key)
                        if data:
                            messages_data = json.loads(data)
                            
                            # Extraer workspace_id y user_phone de la clave
                            key_parts = key.decode('utf-8').split(':')
                            if len(key_parts) >= 3:
                                workspace_id = key_parts[1]
                                user_phone = key_parts[2]
                                
                                # Convertir a objetos DebounceMessage
                                messages = [
                                    DebounceMessage(
                                        timestamp=msg['timestamp'],
                                        text=msg['text'],
                                        wa_message_sid=msg['wa_message_sid'],
                                        raw_payload=msg.get('raw_payload')
                                    )
                                    for msg in messages_data
                                ]
                                
                                # Agregar texto
                                aggregated_text = " ".join([msg.text for msg in messages])
                                
                                results.append(DebounceResult(
                                    trigger=True,
                                    key=key.decode('utf-8'),
                                    messages=messages,
                                    aggregated_text=aggregated_text,
                                    workspace_id=workspace_id,
                                    user_phone=user_phone
                                ))
                            
                            # Eliminar clave expirada
                            self.redis_client.delete(key)
                            
                except Exception as e:
                    logger.error(f"Error procesando clave {key}: {e}")
                    continue
            
            if results:
                logger.info(f"Flush: {len(results)} buffers expirados procesados")
            
            return results
            
        except Exception as e:
            logger.error(f"Error en flush_expired: {e}")
            return []
    
    async def get_pending_messages(self, workspace_id: str, user_phone: str) -> Optional[List[DebounceMessage]]:
        """Obtener mensajes pendientes sin procesar"""
        try:
            if not self.redis_client:
                return None
            
            key = self._get_debounce_key(workspace_id, user_phone)
            data = self.redis_client.get(key)
            
            if data:
                messages_data = json.loads(data)
                return [
                    DebounceMessage(
                        timestamp=msg['timestamp'],
                        text=msg['text'],
                        wa_message_sid=msg['wa_message_sid'],
                        raw_payload=msg.get('raw_payload')
                    )
                    for msg in messages_data
                ]
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo mensajes pendientes: {e}")
            return None
    
    async def clear_buffer(self, workspace_id: str, user_phone: str) -> bool:
        """Limpiar buffer específico"""
        try:
            if not self.redis_client:
                return False
            
            key = self._get_debounce_key(workspace_id, user_phone)
            result = self.redis_client.delete(key)
            return result > 0
            
        except Exception as e:
            logger.error(f"Error limpiando buffer: {e}")
            return False
    
    async def get_buffer_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de buffers activos"""
        try:
            if not self.redis_client:
                return {"error": "Redis no disponible"}
            
            pattern = "debounce:*"
            keys = self.redis_client.keys(pattern)
            
            stats = {
                "total_buffers": len(keys),
                "buffers": []
            }
            
            for key in keys:
                try:
                    ttl = self.redis_client.ttl(key)
                    data = self.redis_client.get(key)
                    
                    if data:
                        messages = json.loads(data)
                        key_str = key.decode('utf-8')
                        key_parts = key_str.split(':')
                        
                        stats["buffers"].append({
                            "key": key_str,
                            "workspace_id": key_parts[1] if len(key_parts) > 1 else "unknown",
                            "user_phone": key_parts[2] if len(key_parts) > 2 else "unknown",
                            "message_count": len(messages),
                            "ttl_seconds": ttl,
                            "last_message": max([msg['timestamp'] for msg in messages]) if messages else 0
                        })
                        
                except Exception as e:
                    logger.error(f"Error procesando estadísticas para {key}: {e}")
                    continue
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"error": str(e)}

class DebounceManager:
    """Manager para el sistema de debounce con procesamiento automático"""
    
    def __init__(self, debounce_system: DebounceSystem, message_processor=None):
        self.debounce_system = debounce_system
        self.message_processor = message_processor
        self.is_running = False
        self.flush_task = None
    
    async def start_flush_loop(self, interval_seconds: int = 5):
        """Iniciar loop de flush automático"""
        self.is_running = True
        logger.info(f"🔄 Iniciando loop de flush cada {interval_seconds}s")
        
        while self.is_running:
            try:
                # Procesar buffers expirados
                expired_results = await self.debounce_system.flush_expired()
                
                # Procesar cada resultado
                for result in expired_results:
                    if self.message_processor:
                        await self.message_processor(result)
                
                # Esperar antes del siguiente ciclo
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error en flush loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    async def stop_flush_loop(self):
        """Detener loop de flush"""
        self.is_running = False
        if self.flush_task:
            self.flush_task.cancel()
        logger.info("⏹️ Loop de flush detenido")
    
    async def process_message(self, workspace_id: str, user_phone: str, text: str, 
                            wa_message_sid: str, raw_payload: Dict[str, Any] = None) -> DebounceResult:
        """Procesar mensaje con debounce"""
        # Agregar mensaje al buffer
        result = await self.debounce_system.add_message(
            workspace_id, user_phone, text, wa_message_sid, raw_payload
        )
        
        # Si debe disparar inmediatamente, procesar
        if result.trigger and self.message_processor:
            await self.message_processor(result)
        
        return result

# Función de conveniencia para crear el sistema
def create_debounce_system(redis_url: str = "redis://localhost:6379", 
                          debounce_seconds: int = 10) -> DebounceSystem:
    """Crear sistema de debounce"""
    return DebounceSystem(redis_url, debounce_seconds)

def create_debounce_manager(debounce_system: DebounceSystem, 
                          message_processor=None) -> DebounceManager:
    """Crear manager de debounce"""
    return DebounceManager(debounce_system, message_processor)

# Ejemplo de uso
async def example_usage():
    """Ejemplo de uso del sistema de debounce"""
    
    # Crear sistema
    debounce_system = create_debounce_system()
    
    # Crear manager
    async def message_processor(result: DebounceResult):
        print(f"📨 Procesando {len(result.messages)} mensajes:")
        print(f"   Workspace: {result.workspace_id}")
        print(f"   Usuario: {result.user_phone}")
        print(f"   Texto agregado: {result.aggregated_text}")
        print(f"   Mensajes: {[msg.text for msg in result.messages]}")
    
    manager = create_debounce_manager(debounce_system, message_processor)
    
    # Simular mensajes
    workspace_id = "test-workspace"
    user_phone = "+5491123456789"
    
    # Mensaje 1
    result1 = await manager.process_message(
        workspace_id, user_phone, "Hola", "msg1"
    )
    print(f"Mensaje 1 - Trigger: {result1.trigger}")
    
    # Mensaje 2 (dentro de la ventana)
    await asyncio.sleep(2)
    result2 = await manager.process_message(
        workspace_id, user_phone, "quiero hacer un pedido", "msg2"
    )
    print(f"Mensaje 2 - Trigger: {result2.trigger}")
    
    # Mensaje 3 (dentro de la ventana)
    await asyncio.sleep(3)
    result3 = await manager.process_message(
        workspace_id, user_phone, "de pizzas", "msg3"
    )
    print(f"Mensaje 3 - Trigger: {result3.trigger}")
    
    # Esperar a que expire
    print("Esperando 12 segundos para que expire...")
    await asyncio.sleep(12)
    
    # Flush manual
    expired = await debounce_system.flush_expired()
    print(f"Buffers expirados: {len(expired)}")

if __name__ == "__main__":
    asyncio.run(example_usage())
