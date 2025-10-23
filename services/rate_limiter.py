#!/usr/bin/env python3
"""
Sistema de Rate Limiting para PulpoAI
Protección contra abuso en producción SaaS con múltiples niveles
"""

import asyncio
import json
import time
import hashlib
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class RateLimitType(Enum):
    """Tipos de rate limiting"""
    PER_PHONE = "per_phone"           # Por número de teléfono
    PER_WORKSPACE = "per_workspace"   # Por workspace
    PER_IP = "per_ip"                 # Por IP (si disponible)
    GLOBAL = "global"                 # Global del sistema

@dataclass
class RateLimit:
    """Configuración de un rate limit"""
    requests: int      # Número de requests permitidos
    window_seconds: int # Ventana de tiempo en segundos
    burst_requests: int = None  # Requests adicionales en burst (opcional)
    
    def __post_init__(self):
        if self.burst_requests is None:
            self.burst_requests = max(1, self.requests // 4)  # 25% adicional para burst

@dataclass
class RateLimitResult:
    """Resultado de verificación de rate limit"""
    allowed: bool
    limit_type: RateLimitType
    requests_remaining: int
    reset_time: int  # Unix timestamp cuando se resetea
    retry_after: Optional[int] = None  # Segundos para retry si blocked

class RateLimiter:
    """
    Rate Limiter distribuido usando Redis con sliding window
    Implementa múltiples niveles de protección para SaaS
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/1"):
        self.redis_url = redis_url
        self.redis_client = None
        
        # Configuraciones por defecto para diferentes niveles
        self.default_limits = {
            RateLimitType.PER_PHONE: [
                RateLimit(requests=10, window_seconds=60),      # 10 req/min por teléfono
                RateLimit(requests=50, window_seconds=3600),    # 50 req/hora por teléfono
                RateLimit(requests=200, window_seconds=86400),  # 200 req/día por teléfono
            ],
            RateLimitType.PER_WORKSPACE: [
                RateLimit(requests=100, window_seconds=60),     # 100 req/min por workspace
                RateLimit(requests=1000, window_seconds=3600),  # 1000 req/hora por workspace
                RateLimit(requests=5000, window_seconds=86400), # 5000 req/día por workspace
            ],
            RateLimitType.PER_IP: [
                RateLimit(requests=20, window_seconds=60),      # 20 req/min por IP
                RateLimit(requests=100, window_seconds=3600),   # 100 req/hora por IP
            ],
            RateLimitType.GLOBAL: [
                RateLimit(requests=1000, window_seconds=60),    # 1000 req/min global
                RateLimit(requests=10000, window_seconds=3600), # 10k req/hora global
            ]
        }
    
    async def _get_redis(self):
        """Obtener cliente Redis con lazy loading"""
        if self.redis_client is None:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(self.redis_url)
                await self.redis_client.ping()
                logger.info("[RATE_LIMIT] Conectado a Redis exitosamente")
            except Exception as e:
                logger.error(f"[RATE_LIMIT] Error conectando a Redis: {e}")
                # Fallback a rate limiting en memoria (solo para desarrollo)
                self.redis_client = InMemoryRedis()
        return self.redis_client
    
    def _get_key(self, limit_type: RateLimitType, identifier: str, window_seconds: int) -> str:
        """Generar clave Redis para rate limiting"""
        current_window = int(time.time()) // window_seconds
        key_base = f"rate_limit:{limit_type.value}:{identifier}:{window_seconds}"
        return f"{key_base}:{current_window}"
    
    async def check_rate_limit(
        self, 
        phone: str,
        workspace_id: str,
        ip_address: Optional[str] = None,
        custom_limits: Optional[Dict[RateLimitType, List[RateLimit]]] = None
    ) -> Tuple[bool, List[RateLimitResult]]:
        """
        Verificar rate limits en múltiples niveles
        
        Returns:
            (allowed, results) - allowed=True si pasa todos los checks
        """
        redis = await self._get_redis()
        limits_config = custom_limits or self.default_limits
        results = []
        
        # Identificadores para cada tipo
        identifiers = {
            RateLimitType.PER_PHONE: phone,
            RateLimitType.PER_WORKSPACE: workspace_id,
            RateLimitType.PER_IP: ip_address,
            RateLimitType.GLOBAL: "global"
        }
        
        overall_allowed = True
        
        for limit_type, identifier in identifiers.items():
            if identifier is None:
                continue  # Skip si no hay identificador (ej: IP)
                
            if limit_type not in limits_config:
                continue  # Skip si no hay configuración para este tipo
            
            # Verificar cada ventana de tiempo para este tipo
            for rate_limit in limits_config[limit_type]:
                result = await self._check_single_limit(
                    redis, limit_type, identifier, rate_limit
                )
                results.append(result)
                
                if not result.allowed:
                    overall_allowed = False
                    logger.warning(
                        f"[RATE_LIMIT] Bloqueado {limit_type.value}:{identifier} "
                        f"- {rate_limit.requests}/{rate_limit.window_seconds}s"
                    )
        
        return overall_allowed, results
    
    async def _check_single_limit(
        self,
        redis,
        limit_type: RateLimitType,
        identifier: str,
        rate_limit: RateLimit
    ) -> RateLimitResult:
        """Verificar un rate limit específico usando sliding window"""
        
        current_time = int(time.time())
        window_start = current_time - rate_limit.window_seconds
        key = f"rate_limit:{limit_type.value}:{identifier}"
        
        try:
            # Usar pipeline para atomicidad
            pipe = redis.pipeline()
            
            # Limpiar requests antiguos
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Contar requests actuales
            pipe.zcard(key)
            
            # Agregar request actual
            pipe.zadd(key, {str(current_time): current_time})
            
            # Establecer TTL
            pipe.expire(key, rate_limit.window_seconds + 60)
            
            results = await pipe.execute()
            current_count = results[1]  # Resultado del zcard
            
            # Verificar límites
            allowed = current_count <= rate_limit.requests
            requests_remaining = max(0, rate_limit.requests - current_count)
            reset_time = current_time + rate_limit.window_seconds
            
            retry_after = None
            if not allowed:
                # Calcular cuándo se liberará el próximo slot
                oldest_requests = await redis.zrange(key, 0, 0, withscores=True)
                if oldest_requests:
                    oldest_time = int(oldest_requests[0][1])
                    retry_after = max(1, oldest_time + rate_limit.window_seconds - current_time)
            
            return RateLimitResult(
                allowed=allowed,
                limit_type=limit_type,
                requests_remaining=requests_remaining,
                reset_time=reset_time,
                retry_after=retry_after
            )
            
        except Exception as e:
            logger.error(f"[RATE_LIMIT] Error verificando límite: {e}")
            # En caso de error, permitir (fail-open)
            return RateLimitResult(
                allowed=True,
                limit_type=limit_type,
                requests_remaining=rate_limit.requests,
                reset_time=current_time + rate_limit.window_seconds
            )
    
    async def increment_counter(
        self,
        phone: str,
        workspace_id: str,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Incrementar contadores después de procesar request exitoso
        (Ya se incrementó en check_rate_limit, pero útil para métricas)
        """
        # Los contadores ya se incrementaron en check_rate_limit
        # Este método puede usarse para métricas adicionales
        pass
    
    def get_rate_limit_headers(self, results: List[RateLimitResult]) -> Dict[str, str]:
        """
        Generar headers HTTP estándar para rate limiting
        """
        if not results:
            return {}
        
        # Usar el límite más restrictivo
        most_restrictive = min(results, key=lambda r: r.requests_remaining)
        
        headers = {
            "X-RateLimit-Limit": str(most_restrictive.requests_remaining + 1),
            "X-RateLimit-Remaining": str(most_restrictive.requests_remaining),
            "X-RateLimit-Reset": str(most_restrictive.reset_time)
        }
        
        if most_restrictive.retry_after:
            headers["Retry-After"] = str(most_restrictive.retry_after)
        
        return headers

class InMemoryRedis:
    """
    Fallback en memoria para desarrollo/testing
    NO usar en producción - no es distribuido
    """
    
    def __init__(self):
        self.data = {}
        self.expiry = {}
    
    async def ping(self):
        return True
    
    def pipeline(self):
        return InMemoryPipeline(self)
    
    async def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        if key not in self.data:
            return 0
        
        original_len = len(self.data[key])
        self.data[key] = {k: v for k, v in self.data[key].items() if not (min_score <= v <= max_score)}
        return original_len - len(self.data[key])
    
    async def zcard(self, key: str):
        return len(self.data.get(key, {}))
    
    async def zadd(self, key: str, mapping: Dict[str, float]):
        if key not in self.data:
            self.data[key] = {}
        self.data[key].update(mapping)
        return len(mapping)
    
    async def expire(self, key: str, seconds: int):
        self.expiry[key] = time.time() + seconds
        return True
    
    async def zrange(self, key: str, start: int, end: int, withscores: bool = False):
        if key not in self.data:
            return []
        
        items = sorted(self.data[key].items(), key=lambda x: x[1])
        if withscores:
            return [(k, v) for k, v in items[start:end+1]]
        else:
            return [k for k, v in items[start:end+1]]

class InMemoryPipeline:
    """Pipeline para InMemoryRedis"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.commands = []
    
    def zremrangebyscore(self, key: str, min_score: float, max_score: float):
        self.commands.append(('zremrangebyscore', key, min_score, max_score))
        return self
    
    def zcard(self, key: str):
        self.commands.append(('zcard', key))
        return self
    
    def zadd(self, key: str, mapping: Dict[str, float]):
        self.commands.append(('zadd', key, mapping))
        return self
    
    def expire(self, key: str, seconds: int):
        self.commands.append(('expire', key, seconds))
        return self
    
    async def execute(self):
        results = []
        for cmd in self.commands:
            method_name = cmd[0]
            args = cmd[1:]
            method = getattr(self.redis, method_name)
            result = await method(*args)
            results.append(result)
        return results

# Configuraciones predefinidas para diferentes tiers de SaaS
TIER_CONFIGS = {
    "free": {
        RateLimitType.PER_PHONE: [
            RateLimit(requests=5, window_seconds=60),       # 5 req/min
            RateLimit(requests=20, window_seconds=3600),    # 20 req/hora
            RateLimit(requests=50, window_seconds=86400),   # 50 req/día
        ],
        RateLimitType.PER_WORKSPACE: [
            RateLimit(requests=20, window_seconds=60),      # 20 req/min
            RateLimit(requests=100, window_seconds=3600),   # 100 req/hora
            RateLimit(requests=500, window_seconds=86400),  # 500 req/día
        ]
    },
    "pro": {
        RateLimitType.PER_PHONE: [
            RateLimit(requests=15, window_seconds=60),      # 15 req/min
            RateLimit(requests=100, window_seconds=3600),   # 100 req/hora
            RateLimit(requests=500, window_seconds=86400),  # 500 req/día
        ],
        RateLimitType.PER_WORKSPACE: [
            RateLimit(requests=100, window_seconds=60),     # 100 req/min
            RateLimit(requests=2000, window_seconds=3600),  # 2k req/hora
            RateLimit(requests=10000, window_seconds=86400), # 10k req/día
        ]
    },
    "enterprise": {
        RateLimitType.PER_PHONE: [
            RateLimit(requests=30, window_seconds=60),      # 30 req/min
            RateLimit(requests=500, window_seconds=3600),   # 500 req/hora
            RateLimit(requests=2000, window_seconds=86400), # 2k req/día
        ],
        RateLimitType.PER_WORKSPACE: [
            RateLimit(requests=500, window_seconds=60),     # 500 req/min
            RateLimit(requests=10000, window_seconds=3600), # 10k req/hora
            RateLimit(requests=50000, window_seconds=86400), # 50k req/día
        ]
    }
}

