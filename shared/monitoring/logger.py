#!/usr/bin/env python3
"""
PulpoAI Shared Structured Logger
Logger estructurado compartido
"""

import os
import json
import logging
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import structlog
from structlog.stdlib import LoggerFactory

class StructuredLogger:
    """Logger estructurado"""
    
    def __init__(self, service_name: str, log_level: str = "INFO"):
        self.service_name = service_name
        self.log_level = log_level
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """Configurar logger estructurado"""
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
            logger_factory=LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configurar logging
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=getattr(logging, self.log_level.upper())
        )
        
        return structlog.get_logger(self.service_name)
    
    def info(self, message: str, **kwargs):
        """Log de información"""
        self.logger.info(message, service=self.service_name, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log de advertencia"""
        self.logger.warning(message, service=self.service_name, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log de error"""
        self.logger.error(message, service=self.service_name, **kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log de debug"""
        self.logger.debug(message, service=self.service_name, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log crítico"""
        self.logger.critical(message, service=self.service_name, **kwargs)
    
    def log_request(self, method: str, endpoint: str, status_code: int, duration: float, **kwargs):
        """Log de request"""
        self.info(
            "Request processed",
            method=method,
            endpoint=endpoint,
            status_code=status_code,
            duration=duration,
            **kwargs
        )
    
    def log_database_operation(self, operation: str, table: str, duration: float, **kwargs):
        """Log de operación de base de datos"""
        self.info(
            "Database operation",
            operation=operation,
            table=table,
            duration=duration,
            **kwargs
        )
    
    def log_conversation(self, conversation_id: str, workspace_id: str, action: str, **kwargs):
        """Log de conversación"""
        self.info(
            "Conversation event",
            conversation_id=conversation_id,
            workspace_id=workspace_id,
            action=action,
            **kwargs
        )
    
    def log_action(self, action_type: str, workspace_id: str, status: str, **kwargs):
        """Log de acción"""
        self.info(
            "Action executed",
            action_type=action_type,
            workspace_id=workspace_id,
            status=status,
            **kwargs
        )
    
    def log_rag_search(self, query: str, workspace_id: str, results_count: int, duration: float, **kwargs):
        """Log de búsqueda RAG"""
        self.info(
            "RAG search",
            query=query,
            workspace_id=workspace_id,
            results_count=results_count,
            duration=duration,
            **kwargs
        )
    
    def log_embedding_generation(self, workspace_id: str, model: str, duration: float, **kwargs):
        """Log de generación de embedding"""
        self.info(
            "Embedding generated",
            workspace_id=workspace_id,
            model=model,
            duration=duration,
            **kwargs
        )
    
    def log_error(self, error_type: str, error_message: str, workspace_id: str = None, **kwargs):
        """Log de error"""
        self.error(
            "Error occurred",
            error_type=error_type,
            error_message=error_message,
            workspace_id=workspace_id,
            **kwargs
        )
    
    def log_system_metric(self, metric_name: str, metric_value: float, workspace_id: str = None, **kwargs):
        """Log de métrica del sistema"""
        self.info(
            "System metric",
            metric_name=metric_name,
            metric_value=metric_value,
            workspace_id=workspace_id,
            **kwargs
        )

# Instancia global del logger
structured_logger = StructuredLogger("pulpoai")
