#!/usr/bin/env python3
"""
Sistema de caché para embeddings
Optimiza el rendimiento evitando regenerar embeddings duplicados
"""

import hashlib
import json
import logging
import redis
import pickle
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CacheConfig:
    """Configuración del sistema de caché"""
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    cache_ttl: int = 86400  # 24 horas
    max_cache_size: int = 10000  # Máximo 10k embeddings en caché
    enable_compression: bool = True

class EmbeddingCache:
    """
    Sistema de caché para embeddings usando Redis
    Evita regenerar embeddings para textos idénticos
    """
    
    def __init__(self, config: CacheConfig = None):
        self.config = config or CacheConfig()
        self.redis_client = None
        self._connect()
        
    def _connect(self):
        """Conectar a Redis"""
        try:
            self.redis_client = redis.from_url(self.config.redis_url)
            self.redis_client.ping()
            logger.info("✅ Caché de embeddings conectado a Redis")
        except Exception as e:
            logger.error(f"❌ Error conectando a Redis: {e}")
            self.redis_client = None
    
    def _generate_cache_key(self, text: str, model: str) -> str:
        """Generar clave de caché única para un texto y modelo"""
        # Crear hash del texto + modelo
        content = f"{model}:{text}"
        hash_obj = hashlib.sha256(content.encode('utf-8'))
        return f"embedding:{hash_obj.hexdigest()}"
    
    def _serialize_embedding(self, embedding: List[float]) -> bytes:
        """Serializar embedding para almacenamiento"""
        if self.config.enable_compression:
            return pickle.dumps(embedding, protocol=pickle.HIGHEST_PROTOCOL)
        return json.dumps(embedding).encode('utf-8')
    
    def _deserialize_embedding(self, data: bytes) -> List[float]:
        """Deserializar embedding desde almacenamiento"""
        if self.config.enable_compression:
            return pickle.loads(data)
        return json.loads(data.decode('utf-8'))
    
    def get_embedding(self, text: str, model: str) -> Optional[List[float]]:
        """
        Obtener embedding desde caché
        Retorna None si no está en caché
        """
        if not self.redis_client:
            return None
            
        try:
            cache_key = self._generate_cache_key(text, model)
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                embedding = self._deserialize_embedding(cached_data)
                logger.debug(f"✅ Embedding encontrado en caché para: {text[:50]}...")
                return embedding
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo embedding del caché: {e}")
            
        return None
    
    def set_embedding(self, text: str, model: str, embedding: List[float]) -> bool:
        """
        Almacenar embedding en caché
        Retorna True si se almacenó correctamente
        """
        if not self.redis_client:
            return False
            
        try:
            cache_key = self._generate_cache_key(text, model)
            serialized_data = self._serialize_embedding(embedding)
            
            # Almacenar con TTL
            self.redis_client.setex(
                cache_key, 
                self.config.cache_ttl, 
                serialized_data
            )
            
            logger.debug(f"✅ Embedding almacenado en caché para: {text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error almacenando embedding en caché: {e}")
            return False
    
    def get_embeddings_batch(self, texts: List[str], model: str) -> Dict[str, Optional[List[float]]]:
        """
        Obtener múltiples embeddings desde caché
        Retorna diccionario con texto -> embedding (None si no está en caché)
        """
        if not self.redis_client:
            return {text: None for text in texts}
            
        try:
            # Generar todas las claves
            cache_keys = [self._generate_cache_key(text, model) for text in texts]
            
            # Obtener todos los valores de una vez
            cached_data = self.redis_client.mget(cache_keys)
            
            # Procesar resultados
            results = {}
            for text, data in zip(texts, cached_data):
                if data:
                    embedding = self._deserialize_embedding(data)
                    results[text] = embedding
                    logger.debug(f"✅ Embedding encontrado en caché para: {text[:50]}...")
                else:
                    results[text] = None
                    
            return results
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo embeddings batch del caché: {e}")
            return {text: None for text in texts}
    
    def set_embeddings_batch(self, embeddings_dict: Dict[str, List[float]], model: str) -> int:
        """
        Almacenar múltiples embeddings en caché
        Retorna número de embeddings almacenados
        """
        if not self.redis_client:
            return 0
            
        try:
            # Preparar datos para almacenamiento
            pipe = self.redis_client.pipeline()
            stored_count = 0
            
            for text, embedding in embeddings_dict.items():
                cache_key = self._generate_cache_key(text, model)
                serialized_data = self._serialize_embedding(embedding)
                
                pipe.setex(cache_key, self.config.cache_ttl, serialized_data)
                stored_count += 1
                
            # Ejecutar todas las operaciones
            pipe.execute()
            
            logger.info(f"✅ {stored_count} embeddings almacenados en caché")
            return stored_count
            
        except Exception as e:
            logger.error(f"❌ Error almacenando embeddings batch en caché: {e}")
            return 0
    
    def clear_cache(self, model: str = None) -> int:
        """
        Limpiar caché de embeddings
        Si se especifica modelo, solo limpia ese modelo
        Retorna número de claves eliminadas
        """
        if not self.redis_client:
            return 0
            
        try:
            if model:
                pattern = f"embedding:*{model}*"
            else:
                pattern = "embedding:*"
                
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted_count = self.redis_client.delete(*keys)
                logger.info(f"✅ {deleted_count} embeddings eliminados del caché")
                return deleted_count
            else:
                logger.info("✅ No hay embeddings en caché para eliminar")
                return 0
                
        except Exception as e:
            logger.error(f"❌ Error limpiando caché: {e}")
            return 0
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas del caché
        """
        if not self.redis_client:
            return {"error": "Redis no conectado"}
            
        try:
            # Contar embeddings en caché
            embedding_keys = self.redis_client.keys("embedding:*")
            total_embeddings = len(embedding_keys)
            
            # Obtener información de memoria
            info = self.redis_client.info('memory')
            memory_used = info.get('used_memory_human', 'N/A')
            
            # Obtener TTL promedio
            ttls = []
            for key in embedding_keys[:100]:  # Muestra de 100 claves
                ttl = self.redis_client.ttl(key)
                if ttl > 0:
                    ttls.append(ttl)
            
            avg_ttl = sum(ttls) / len(ttls) if ttls else 0
            
            return {
                "total_embeddings": total_embeddings,
                "memory_used": memory_used,
                "average_ttl_seconds": avg_ttl,
                "cache_enabled": True,
                "compression_enabled": self.config.enable_compression
            }
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo estadísticas del caché: {e}")
            return {"error": str(e)}
    
    def is_healthy(self) -> bool:
        """Verificar si el caché está funcionando"""
        if not self.redis_client:
            return False
            
        try:
            self.redis_client.ping()
            return True
        except:
            return False

# Instancia global del caché
embedding_cache = EmbeddingCache()

# Funciones de conveniencia
def get_cached_embedding(text: str, model: str) -> Optional[List[float]]:
    """Obtener embedding desde caché"""
    return embedding_cache.get_embedding(text, model)

def set_cached_embedding(text: str, model: str, embedding: List[float]) -> bool:
    """Almacenar embedding en caché"""
    return embedding_cache.set_embedding(text, model, embedding)

def get_cache_stats() -> Dict[str, Any]:
    """Obtener estadísticas del caché"""
    return embedding_cache.get_cache_stats()

