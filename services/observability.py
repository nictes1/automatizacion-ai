"""
Sistema de Observabilidad para PulpoAI
Métricas, logging estructurado y dashboards
"""

import time
import logging
import structlog
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
import json


# ==========================================
# MÉTRICAS PROMETHEUS
# ==========================================

# Registry para métricas
metrics_registry = CollectorRegistry()

# Contadores
tool_calls_total = Counter(
    'pulpo_tool_calls_total',
    'Total number of tool calls',
    ['tool', 'workspace', 'result', 'status_code'],
    registry=metrics_registry
)

orchestrator_requests_total = Counter(
    'pulpo_orchestrator_requests_total',
    'Total number of orchestrator requests',
    ['vertical', 'workspace', 'agent_loop_enabled', 'result'],
    registry=metrics_registry
)

circuit_breaker_state_changes = Counter(
    'pulpo_circuit_breaker_state_changes_total',
    'Circuit breaker state changes',
    ['workspace', 'tool', 'from_state', 'to_state'],
    registry=metrics_registry
)

rate_limit_hits = Counter(
    'pulpo_rate_limit_hits_total',
    'Rate limit hits',
    ['workspace', 'tool', 'retry_after'],
    registry=metrics_registry
)

# Histogramas (latencia)
tool_execution_duration = Histogram(
    'pulpo_tool_execution_duration_seconds',
    'Tool execution duration',
    ['tool', 'workspace', 'result'],
    registry=metrics_registry
)

orchestrator_duration = Histogram(
    'pulpo_orchestrator_duration_seconds',
    'Orchestrator request duration',
    ['vertical', 'workspace', 'agent_loop_enabled'],
    registry=metrics_registry
)

planner_duration = Histogram(
    'pulpo_planner_duration_seconds',
    'Planner decision duration',
    ['vertical', 'workspace'],
    registry=metrics_registry
)

policy_duration = Histogram(
    'pulpo_policy_duration_seconds',
    'Policy validation duration',
    ['vertical', 'workspace'],
    registry=metrics_registry
)

# Gauges (estado actual)
active_circuit_breakers = Gauge(
    'pulpo_active_circuit_breakers',
    'Number of active circuit breakers',
    ['workspace', 'tool', 'state'],
    registry=metrics_registry
)

cache_size = Gauge(
    'pulpo_cache_size',
    'Cache size',
    ['cache_type', 'workspace'],
    registry=metrics_registry
)

canary_traffic_percentage = Gauge(
    'pulpo_canary_traffic_percentage',
    'Percentage of traffic using agent loop',
    ['workspace'],
    registry=metrics_registry
)


# ==========================================
# LOGGING ESTRUCTURADO
# ==========================================

# Configurar structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("pulpo.observability")


# ==========================================
# MODELOS DE EVENTOS
# ==========================================

class EventType(Enum):
    """Tipos de eventos para observabilidad"""
    TOOL_CALL = "tool_call"
    TOOL_SUCCESS = "tool_success"
    TOOL_FAILURE = "tool_failure"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_CLOSE = "circuit_breaker_close"
    RATE_LIMIT_HIT = "rate_limit_hit"
    ORCHESTRATOR_REQUEST = "orchestrator_request"
    CANARY_DECISION = "canary_decision"
    POLICY_DECISION = "policy_decision"
    PLANNER_DECISION = "planner_decision"


@dataclass
class ObservabilityEvent:
    """Evento de observabilidad estructurado"""
    event_type: EventType
    timestamp: float
    workspace_id: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    tool: Optional[str] = None
    duration_ms: Optional[float] = None
    success: Optional[bool] = None
    error: Optional[str] = None
    status_code: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para logging"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        return data


# ==========================================
# OBSERVABILITY MANAGER
# ==========================================

class ObservabilityManager:
    """Gestor central de observabilidad"""
    
    def __init__(self):
        self.events_buffer: List[ObservabilityEvent] = []
        self.buffer_size = 1000
        self.flush_interval = 30  # segundos
    
    def emit_event(self, event: ObservabilityEvent):
        """Emite un evento de observabilidad"""
        # Agregar al buffer
        self.events_buffer.append(event)
        
        # Log estructurado
        logger.info("observability_event", **event.to_dict())
        
        # Emitir métricas Prometheus
        self._emit_prometheus_metrics(event)
        
        # Flush si buffer lleno
        if len(self.events_buffer) >= self.buffer_size:
            self._flush_events()
    
    def _emit_prometheus_metrics(self, event: ObservabilityEvent):
        """Emite métricas Prometheus basadas en el evento"""
        labels = {
            'workspace': event.workspace_id,
            'tool': event.tool or 'unknown',
            'result': 'success' if event.success else 'error' if event.success is not None else 'unknown',
            'status_code': str(event.status_code) if event.status_code else '0'
        }
        
        if event.event_type == EventType.TOOL_CALL:
            tool_calls_total.labels(**labels).inc()
            
            if event.duration_ms:
                tool_execution_duration.labels(
                    tool=event.tool or 'unknown',
                    workspace=event.workspace_id,
                    result='success' if event.success else 'error'
                ).observe(event.duration_ms / 1000.0)
        
        elif event.event_type == EventType.CIRCUIT_BREAKER_OPEN:
            circuit_breaker_state_changes.labels(
                workspace=event.workspace_id,
                tool=event.tool or 'unknown',
                from_state='closed',
                to_state='open'
            ).inc()
            
            active_circuit_breakers.labels(
                workspace=event.workspace_id,
                tool=event.tool or 'unknown',
                state='open'
            ).set(1)
        
        elif event.event_type == EventType.CIRCUIT_BREAKER_CLOSE:
            circuit_breaker_state_changes.labels(
                workspace=event.workspace_id,
                tool=event.tool or 'unknown',
                from_state='open',
                to_state='closed'
            ).inc()
            
            active_circuit_breakers.labels(
                workspace=event.workspace_id,
                tool=event.tool or 'unknown',
                state='open'
            ).set(0)
        
        elif event.event_type == EventType.RATE_LIMIT_HIT:
            rate_limit_hits.labels(
                workspace=event.workspace_id,
                tool=event.tool or 'unknown',
                retry_after=str(event.metadata.get('retry_after', 0)) if event.metadata else '0'
            ).inc()
    
    def _flush_events(self):
        """Envía eventos del buffer a sistema de análisis"""
        if not self.events_buffer:
            return
        
        # En producción, aquí enviarías a Elasticsearch, BigQuery, etc.
        logger.info("flushing_events", count=len(self.events_buffer))
        
        # Limpiar buffer
        self.events_buffer.clear()
    
    def get_metrics_prometheus(self) -> str:
        """Obtiene métricas en formato Prometheus"""
        return generate_latest(metrics_registry).decode('utf-8')
    
    def get_health_status(self) -> Dict[str, Any]:
        """Obtiene estado de salud del sistema"""
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "events_buffer_size": len(self.events_buffer),
            "metrics_registry_size": len(list(metrics_registry.collect())),
            "uptime_seconds": time.time() - self._start_time if hasattr(self, '_start_time') else 0
        }


# ==========================================
# HELPERS PARA USO EN COMPONENTES
# ==========================================

# Instancia global
observability_manager = ObservabilityManager()


def emit_tool_call_event(
    tool: str,
    workspace_id: str,
    conversation_id: str,
    success: bool,
    duration_ms: float,
    error: Optional[str] = None,
    status_code: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """Helper para emitir evento de tool call"""
    event = ObservabilityEvent(
        event_type=EventType.TOOL_CALL,
        timestamp=time.time(),
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        tool=tool,
        duration_ms=duration_ms,
        success=success,
        error=error,
        status_code=status_code,
        metadata=metadata
    )
    observability_manager.emit_event(event)


def emit_circuit_breaker_event(
    workspace_id: str,
    tool: str,
    from_state: str,
    to_state: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Helper para emitir evento de circuit breaker"""
    event_type = EventType.CIRCUIT_BREAKER_OPEN if to_state == 'open' else EventType.CIRCUIT_BREAKER_CLOSE
    
    event = ObservabilityEvent(
        event_type=event_type,
        timestamp=time.time(),
        workspace_id=workspace_id,
        tool=tool,
        metadata={
            'from_state': from_state,
            'to_state': to_state,
            **(metadata or {})
        }
    )
    observability_manager.emit_event(event)


def emit_rate_limit_event(
    workspace_id: str,
    tool: str,
    retry_after: int,
    metadata: Optional[Dict[str, Any]] = None
):
    """Helper para emitir evento de rate limit"""
    event = ObservabilityEvent(
        event_type=EventType.RATE_LIMIT_HIT,
        timestamp=time.time(),
        workspace_id=workspace_id,
        tool=tool,
        metadata={
            'retry_after': retry_after,
            **(metadata or {})
        }
    )
    observability_manager.emit_event(event)


def emit_orchestrator_event(
    workspace_id: str,
    conversation_id: str,
    vertical: str,
    agent_loop_enabled: bool,
    success: bool,
    duration_ms: float,
    metadata: Optional[Dict[str, Any]] = None
):
    """Helper para emitir evento de orchestrator"""
    event = ObservabilityEvent(
        event_type=EventType.ORCHESTRATOR_REQUEST,
        timestamp=time.time(),
        workspace_id=workspace_id,
        conversation_id=conversation_id,
        duration_ms=duration_ms,
        success=success,
        metadata={
            'vertical': vertical,
            'agent_loop_enabled': agent_loop_enabled,
            **(metadata or {})
        }
    )
    observability_manager.emit_event(event)
    
    # Métrica específica
    orchestrator_requests_total.labels(
        vertical=vertical,
        workspace=workspace_id,
        agent_loop_enabled=str(agent_loop_enabled),
        result='success' if success else 'error'
    ).inc()
    
    orchestrator_duration.labels(
        vertical=vertical,
        workspace=workspace_id,
        agent_loop_enabled=str(agent_loop_enabled)
    ).observe(duration_ms / 1000.0)


def emit_canary_decision_event(
    workspace_id: str,
    user_id: Optional[str],
    use_agent_loop: bool,
    strategy: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Helper para emitir evento de decisión canary"""
    event = ObservabilityEvent(
        event_type=EventType.CANARY_DECISION,
        timestamp=time.time(),
        workspace_id=workspace_id,
        user_id=user_id,
        success=use_agent_loop,
        metadata={
            'strategy': strategy,
            'use_agent_loop': use_agent_loop,
            **(metadata or {})
        }
    )
    observability_manager.emit_event(event)


# ==========================================
# DASHBOARD DATA PROVIDER
# ==========================================

class DashboardDataProvider:
    """Proveedor de datos para dashboards"""
    
    def get_system_overview(self) -> Dict[str, Any]:
        """Obtiene overview del sistema para dashboard"""
        return {
            "timestamp": time.time(),
            "health": observability_manager.get_health_status(),
            "active_circuit_breakers": self._get_active_circuit_breakers(),
            "top_tools": self._get_top_tools(),
            "error_rates": self._get_error_rates(),
            "latency_p95": self._get_latency_p95()
        }
    
    def _get_active_circuit_breakers(self) -> List[Dict[str, Any]]:
        """Obtiene circuit breakers activos"""
        # En producción, esto vendría de métricas reales
        return []
    
    def _get_top_tools(self) -> List[Dict[str, Any]]:
        """Obtiene tools más utilizados"""
        # En producción, esto vendría de métricas reales
        return [
            {"tool": "get_services", "calls": 150, "success_rate": 0.98},
            {"tool": "book_appointment", "calls": 45, "success_rate": 0.95},
            {"tool": "get_availability", "calls": 80, "success_rate": 0.99}
        ]
    
    def _get_error_rates(self) -> Dict[str, float]:
        """Obtiene tasas de error por workspace"""
        # En producción, esto vendría de métricas reales
        return {
            "workspace_1": 0.02,
            "workspace_2": 0.01,
            "workspace_3": 0.03
        }
    
    def _get_latency_p95(self) -> Dict[str, float]:
        """Obtiene latencia P95 por workspace"""
        # En producción, esto vendría de métricas reales
        return {
            "workspace_1": 1200.0,
            "workspace_2": 800.0,
            "workspace_3": 1500.0
        }


# Instancia global
dashboard_provider = DashboardDataProvider()


# ==========================================
# FUNCIÓN PARA EXPORTAR MÉTRICAS PROMETHEUS
# ==========================================

def get_metrics_prometheus() -> str:
    """
    Exporta todas las métricas en formato Prometheus
    """
    from prometheus_client import generate_latest
    return generate_latest(metrics_registry).decode('utf-8')
