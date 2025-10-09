"""
Configuración de Canary Deployment para PulpoAI
Feature flags y configuración de rollout gradual
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class CanaryStrategy(Enum):
    """Estrategias de canary deployment"""
    PERCENTAGE = "percentage"      # Porcentaje de tráfico
    WORKSPACE = "workspace"       # Por workspace específico
    USER_ID = "user_id"          # Por user ID
    GEOGRAPHIC = "geographic"     # Por región geográfica


@dataclass
class CanaryConfig:
    """Configuración de canary deployment"""
    enabled: bool = False
    strategy: CanaryStrategy = CanaryStrategy.PERCENTAGE
    percentage: float = 0.0  # 0.0 - 1.0
    workspace_whitelist: list = None
    workspace_blacklist: list = None
    user_id_whitelist: list = None
    geographic_regions: list = None
    rollback_threshold: float = 0.05  # 5% error rate para rollback
    min_requests: int = 100  # Mínimo de requests para evaluar
    evaluation_window_minutes: int = 10  # Ventana de evaluación


class CanaryManager:
    """Gestor de canary deployment con feature flags"""
    
    def __init__(self):
        self.config = self._load_config()
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "error_rate": 0.0,
            "avg_latency_ms": 0.0,
            "p95_latency_ms": 0.0,
            "p99_latency_ms": 0.0
        }
    
    def _load_config(self) -> CanaryConfig:
        """Carga configuración desde variables de entorno"""
        return CanaryConfig(
            enabled=os.getenv("CANARY_ENABLED", "false").lower() == "true",
            strategy=CanaryStrategy(os.getenv("CANARY_STRATEGY", "percentage")),
            percentage=float(os.getenv("CANARY_PERCENTAGE", "0.0")),
            workspace_whitelist=self._parse_list(os.getenv("CANARY_WORKSPACE_WHITELIST", "")),
            workspace_blacklist=self._parse_list(os.getenv("CANARY_WORKSPACE_BLACKLIST", "")),
            user_id_whitelist=self._parse_list(os.getenv("CANARY_USER_WHITELIST", "")),
            geographic_regions=self._parse_list(os.getenv("CANARY_GEOGRAPHIC_REGIONS", "")),
            rollback_threshold=float(os.getenv("CANARY_ROLLBACK_THRESHOLD", "0.05")),
            min_requests=int(os.getenv("CANARY_MIN_REQUESTS", "100")),
            evaluation_window_minutes=int(os.getenv("CANARY_EVAL_WINDOW", "10"))
        )
    
    def _parse_list(self, value: str) -> list:
        """Parsea string separado por comas en lista"""
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]
    
    def should_use_agent_loop(
        self, 
        workspace_id: str, 
        user_id: Optional[str] = None,
        geographic_region: Optional[str] = None
    ) -> bool:
        """
        Determina si usar el nuevo loop de agente basado en configuración canary
        
        Args:
            workspace_id: ID del workspace
            user_id: ID del usuario (opcional)
            geographic_region: Región geográfica (opcional)
            
        Returns:
            True si debe usar el nuevo loop de agente
        """
        if not self.config.enabled:
            return False
        
        # Verificar blacklist primero
        if workspace_id in (self.config.workspace_blacklist or []):
            return False
        
        # Verificar whitelist
        if self.config.workspace_whitelist and workspace_id not in self.config.workspace_whitelist:
            return False
        
        # Aplicar estrategia específica
        if self.config.strategy == CanaryStrategy.PERCENTAGE:
            return self._percentage_based_decision(workspace_id)
        
        elif self.config.strategy == CanaryStrategy.WORKSPACE:
            return workspace_id in (self.config.workspace_whitelist or [])
        
        elif self.config.strategy == CanaryStrategy.USER_ID:
            return user_id in (self.config.user_id_whitelist or []) if user_id else False
        
        elif self.config.strategy == CanaryStrategy.GEOGRAPHIC:
            return geographic_region in (self.config.geographic_regions or []) if geographic_region else False
        
        return False
    
    def _percentage_based_decision(self, workspace_id: str) -> bool:
        """Decisión basada en porcentaje usando hash determinístico"""
        import hashlib
        
        # Hash determinístico basado en workspace_id
        hash_input = f"canary_{workspace_id}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        
        # Normalizar a 0-1
        normalized = (hash_value % 10000) / 10000.0
        
        return normalized < self.config.percentage
    
    def record_request_metrics(
        self,
        success: bool,
        latency_ms: float,
        workspace_id: str,
        user_id: Optional[str] = None
    ):
        """Registra métricas de request para evaluación canary"""
        self.metrics["total_requests"] += 1
        
        if success:
            self.metrics["successful_requests"] += 1
        else:
            self.metrics["failed_requests"] += 1
        
        # Actualizar error rate
        if self.metrics["total_requests"] > 0:
            self.metrics["error_rate"] = (
                self.metrics["failed_requests"] / self.metrics["total_requests"]
            )
        
        # Actualizar latencia (simplificado - en producción usar percentiles reales)
        if self.metrics["total_requests"] == 1:
            self.metrics["avg_latency_ms"] = latency_ms
        else:
            # Promedio móvil simple
            alpha = 0.1  # Factor de suavizado
            self.metrics["avg_latency_ms"] = (
                alpha * latency_ms + (1 - alpha) * self.metrics["avg_latency_ms"]
            )
    
    def should_rollback(self) -> bool:
        """
        Determina si se debe hacer rollback basado en métricas
        
        Returns:
            True si se debe hacer rollback
        """
        if self.metrics["total_requests"] < self.config.min_requests:
            return False
        
        # Rollback si error rate excede threshold
        if self.metrics["error_rate"] > self.config.rollback_threshold:
            return True
        
        # Rollback si latencia promedio excede threshold (ej: 5 segundos)
        if self.metrics["avg_latency_ms"] > 5000:
            return True
        
        return False
    
    def get_canary_status(self) -> Dict[str, Any]:
        """Obtiene estado actual del canary deployment"""
        return {
            "enabled": self.config.enabled,
            "strategy": self.config.strategy.value,
            "percentage": self.config.percentage,
            "metrics": self.metrics.copy(),
            "should_rollback": self.should_rollback(),
            "config": {
                "rollback_threshold": self.config.rollback_threshold,
                "min_requests": self.config.min_requests,
                "evaluation_window_minutes": self.config.evaluation_window_minutes
            }
        }
    
    def update_config(self, new_config: Dict[str, Any]):
        """Actualiza configuración canary dinámicamente"""
        if "enabled" in new_config:
            self.config.enabled = bool(new_config["enabled"])
        
        if "percentage" in new_config:
            self.config.percentage = max(0.0, min(1.0, float(new_config["percentage"])))
        
        if "strategy" in new_config:
            self.config.strategy = CanaryStrategy(new_config["strategy"])
        
        if "workspace_whitelist" in new_config:
            self.config.workspace_whitelist = new_config["workspace_whitelist"]
        
        if "rollback_threshold" in new_config:
            self.config.rollback_threshold = float(new_config["rollback_threshold"])


# Instancia global del canary manager
canary_manager = CanaryManager()


def get_canary_manager() -> CanaryManager:
    """Obtiene instancia singleton del canary manager"""
    return canary_manager


# Helper functions para uso en el orchestrator
def should_use_agent_loop(workspace_id: str, user_id: Optional[str] = None) -> bool:
    """Helper para determinar si usar agent loop"""
    return canary_manager.should_use_agent_loop(workspace_id, user_id)


def record_canary_metrics(success: bool, latency_ms: float, workspace_id: str, user_id: Optional[str] = None):
    """Helper para registrar métricas canary"""
    canary_manager.record_request_metrics(success, latency_ms, workspace_id, user_id)
