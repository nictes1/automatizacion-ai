#!/usr/bin/env python3
"""
PulpoAI Shared Monitoring Client
Cliente de monitoreo compartido
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from .metrics import MetricsCollector
from .logger import StructuredLogger
from .exceptions import MonitoringError, MetricsError, LoggingError

logger = logging.getLogger(__name__)

class MonitoringClient:
    """Cliente de monitoreo"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics = MetricsCollector(service_name)
        self.logger = StructuredLogger(service_name)
        self.start_time = time.time()
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float, **kwargs):
        """Registrar request"""
        self.metrics.record_request(method, endpoint, status_code, duration)
        self.logger.log_request(method, endpoint, status_code, duration, **kwargs)
    
    def record_database_operation(self, operation: str, table: str, duration: float, **kwargs):
        """Registrar operación de base de datos"""
        self.metrics.record_db_query(operation, table, duration)
        self.logger.log_database_operation(operation, table, duration, **kwargs)
    
    def record_conversation(self, workspace_id: str, vertical: str, **kwargs):
        """Registrar conversación"""
        self.metrics.record_conversation(workspace_id, vertical)
        self.logger.log_conversation(workspace_id=workspace_id, action="created", **kwargs)
    
    def record_message(self, workspace_id: str, direction: str, **kwargs):
        """Registrar mensaje"""
        self.metrics.record_message(workspace_id, direction)
        self.logger.log_conversation(workspace_id=workspace_id, action="message", **kwargs)
    
    def record_action(self, workspace_id: str, action_type: str, status: str, **kwargs):
        """Registrar acción"""
        self.metrics.record_action(workspace_id, action_type, status)
        self.logger.log_action(action_type, workspace_id, status, **kwargs)
    
    def record_error(self, error_type: str, error_message: str, workspace_id: str = None, **kwargs):
        """Registrar error"""
        self.metrics.record_error(error_type, workspace_id)
        self.logger.log_error(error_type, error_message, workspace_id, **kwargs)
    
    def record_rag_search(self, query: str, workspace_id: str, vertical: str, results_count: int, duration: float, **kwargs):
        """Registrar búsqueda RAG"""
        self.metrics.record_rag_search(workspace_id, vertical, duration)
        self.logger.log_rag_search(query, workspace_id, results_count, duration, **kwargs)
    
    def record_document_ingestion(self, workspace_id: str, file_type: str, **kwargs):
        """Registrar ingesta de documento"""
        self.metrics.record_document_ingestion(workspace_id, file_type)
        self.logger.info("Document ingested", workspace_id=workspace_id, file_type=file_type, **kwargs)
    
    def record_embedding_generation(self, workspace_id: str, model: str, duration: float, **kwargs):
        """Registrar generación de embedding"""
        self.metrics.record_embedding_generation(workspace_id, model, duration)
        self.logger.log_embedding_generation(workspace_id, model, duration, **kwargs)
    
    def record_system_metric(self, metric_name: str, metric_value: float, workspace_id: str = None, **kwargs):
        """Registrar métrica del sistema"""
        self.logger.log_system_metric(metric_name, metric_value, workspace_id, **kwargs)
    
    def start_metrics_server(self, port: int = 8000):
        """Iniciar servidor de métricas"""
        self.metrics.start_metrics_server(port)
    
    def get_uptime(self) -> float:
        """Obtener tiempo de actividad"""
        return time.time() - self.start_time
    
    def get_service_info(self) -> Dict[str, Any]:
        """Obtener información del servicio"""
        return {
            "service_name": self.service_name,
            "uptime_seconds": self.get_uptime(),
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "status": "healthy"
        }

# Instancia global del cliente de monitoreo
monitoring_client = MonitoringClient("pulpoai")
