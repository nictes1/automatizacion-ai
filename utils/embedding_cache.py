"""
Cache de embeddings con TTL
"""
import os
import time
import logging
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)

class EmbeddingCache:
    """Cache simple de embeddings con TTL"""
    
    def __init__(self, ttl_seconds: int = 120):
        self.ttl = ttl_seconds
        self.max_entries = int(os.getenv("EMB_CACHE_MAX", "5000"))
        self.store: dict = {}  # (workspace_id, query) -> (embedding, expires_at)
        self.hits = 0
        self.misses = 0
    
    def get(self, workspace_id: str, query: str) -> Optional[list]:
        """Obtiene un embedding del cache si no ha expirado"""
        key = (workspace_id, query)
        cached = self.store.get(key)
        
        if cached is None:
            self.misses += 1
            logger.debug(f"Cache miss for workspace {workspace_id}")
            # Exponer métrica de miss
            try:
                from services.metrics import emb_cache_miss
                emb_cache_miss.labels(workspace_id).inc()
            except ImportError:
                pass  # Métricas no disponibles
            return None
        
        embedding, expires_at = cached
        if time.time() > expires_at:
            # Expirado, remover del cache
            del self.store[key]
            self.misses += 1
            logger.debug(f"Cache expired for workspace {workspace_id}")
            # Exponer métrica de miss
            try:
                from services.metrics import emb_cache_miss
                emb_cache_miss.labels(workspace_id).inc()
            except ImportError:
                pass  # Métricas no disponibles
            return None
        
        self.hits += 1
        logger.debug(f"Cache hit for workspace {workspace_id}")
        # Exponer métrica de hit
        try:
            from services.metrics import emb_cache_hits
            emb_cache_hits.labels(workspace_id).inc()
        except ImportError:
            pass  # Métricas no disponibles
        return embedding
    
    def set(self, workspace_id: str, query: str, embedding: list):
        """Guarda un embedding en el cache"""
        key = (workspace_id, query)
        expires_at = time.time() + self.ttl
        
        # Límite de tamaño del cache
        if len(self.store) >= self.max_entries:
            # Elimina el primer elemento (FIFO simple)
            self.store.pop(next(iter(self.store)))
        
        self.store[key] = (embedding, expires_at)
    
    def clear(self):
        """Limpia el cache"""
        self.store.clear()
        self.hits = 0
        self.misses = 0
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas del cache"""
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "size": len(self.store)
        }

# Cache global
embedding_cache = EmbeddingCache(ttl_seconds=120)
