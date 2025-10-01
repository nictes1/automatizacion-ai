#!/usr/bin/env python3
"""
Sistema de Debounce para n8n
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
    should_process: bool

class N8NDebounceSystem:
    """Sistema de debounce optimizado para n8n"""
    
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
    
    def normalize_twilio_payload(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalizar payload de Twilio para n8n"""
        try:
            # Extraer información del payload
            body = payload.get('Body', '')
            from_number = payload.get('From', '').replace('whatsapp:', '')
            message_sid = payload.get('MessageSid', '')
            
            # En n8n, el workspace_id puede venir de diferentes formas:
            # 1. Como parámetro en el webhook
            # 2. Como configuración del nodo
            # 3. Como parte del payload
            workspace_id = (
                payload.get('WorkspaceId') or 
                payload.get('workspace_id') or 
                payload.get('workspace') or
                "default-workspace"  # fallback
            )
            
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
    
    def add_message(self, workspace_id: str, user_phone: str, text: str, 
                   wa_message_sid: str, raw_payload: Dict[str, Any] = None) -> DebounceResult:
        """
        Agregar mensaje al buffer de debounce
        
        Returns:
            DebounceResult con trigger=True si debe procesarse inmediatamente
        """
        try:
            if not self.redis_client:
                logger.error("Redis no disponible")
                return DebounceResult(
                    False, "", [], "", workspace_id, user_phone, False
                )
            
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
                user_phone=user_phone,
                should_process=should_trigger
            )
            
        except Exception as e:
            logger.error(f"Error en add_message: {e}")
            return DebounceResult(
                False, "", [], "", workspace_id, user_phone, False
            )
    
    def flush_expired(self) -> List[DebounceResult]:
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
                                    user_phone=user_phone,
                                    should_process=True
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
    
    def get_buffer_stats(self) -> Dict[str, Any]:
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

# Funciones para n8n
def n8n_normalize_twilio(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función para n8n: normalizar payload de Twilio
    Usar en un nodo Function de n8n
    """
    debounce_system = N8NDebounceSystem()
    normalized = debounce_system.normalize_twilio_payload(payload)
    
    if normalized:
        return [{"json": normalized}]
    else:
        return [{"json": {"error": "Payload inválido"}}]

def n8n_add_message(workspace_id: str, user_phone: str, text: str, 
                   wa_sid: str, raw_payload: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Función para n8n: agregar mensaje al debounce
    Usar en un nodo Function de n8n
    """
    debounce_system = N8NDebounceSystem()
    result = debounce_system.add_message(workspace_id, user_phone, text, wa_sid, raw_payload)
    
    return {
        "trigger": result.trigger,
        "should_process": result.should_process,
        "message_count": len(result.messages),
        "aggregated_text": result.aggregated_text,
        "workspace_id": result.workspace_id,
        "user_phone": result.user_phone
    }

def n8n_flush_expired() -> List[Dict[str, Any]]:
    """
    Función para n8n: procesar buffers expirados
    Usar en un nodo Function de n8n (ejecutar cada 5 segundos)
    """
    debounce_system = N8NDebounceSystem()
    results = debounce_system.flush_expired()
    
    if results:
        return [{"json": {
            "trigger": True,
            "workspace_id": result.workspace_id,
            "user_phone": result.user_phone,
            "aggregated_text": result.aggregated_text,
            "message_count": len(result.messages),
            "messages": [
                {
                    "text": msg.text,
                    "wa_sid": msg.wa_message_sid,
                    "timestamp": msg.timestamp
                }
                for msg in result.messages
            ]
        }} for result in results]
    else:
        return [{"json": {"trigger": False}}]

# Función de conveniencia
def create_debounce_system(redis_url: str = "redis://localhost:6379", 
                          debounce_seconds: int = 10) -> N8NDebounceSystem:
    """Crear sistema de debounce para n8n"""
    return N8NDebounceSystem(redis_url, debounce_seconds)

# Ejemplo de uso para n8n
def example_n8n_usage():
    """Ejemplo de uso en n8n"""
    
    # En n8n, usarías estas funciones en nodos Function:
    
    # 1. Normalizar Twilio (nodo Function)
    twilio_payload = {
        'Body': 'Hola, quiero hacer un pedido',
        'From': 'whatsapp:+5491123456789',
        'MessageSid': 'SM1234567890',
        'WorkspaceId': 'workspace-001'
    }
    
    normalized = n8n_normalize_twilio(twilio_payload)
    print("Normalizado:", normalized)
    
    # 2. Agregar mensaje (nodo Function)
    if normalized and normalized[0].get("json"):
        data = normalized[0]["json"]
        result = n8n_add_message(
            data["workspace_id"],
            data["user_phone"],
            data["text"],
            data["wa_sid"],
            data["raw"]
        )
        print("Resultado debounce:", result)
    
    # 3. Flush expirados (nodo Function en cron cada 5s)
    expired = n8n_flush_expired()
    print("Expirados:", expired)

if __name__ == "__main__":
    example_n8n_usage()

