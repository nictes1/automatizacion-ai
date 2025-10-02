#!/usr/bin/env python3
"""
PulpoAI Shared Metrics Collector
Recolector de métricas compartido
"""

import os
import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server
from prometheus_client.core import CollectorRegistry

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Recolector de métricas"""
    
    def __init__(self, service_name: str, registry: Optional[CollectorRegistry] = None):
        self.service_name = service_name
        self.registry = registry or CollectorRegistry()
        
        # Métricas de requests
        self.requests_total = Counter(
            f'{service_name}_requests_total',
            'Total number of requests',
            ['method', 'endpoint', 'status_code'],
            registry=self.registry
        )
        
        self.request_duration = Histogram(
            f'{service_name}_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint'],
            registry=self.registry
        )
        
        # Métricas de base de datos
        self.db_queries_total = Counter(
            f'{service_name}_db_queries_total',
            'Total number of database queries',
            ['operation', 'table'],
            registry=self.registry
        )
        
        self.db_query_duration = Histogram(
            f'{service_name}_db_query_duration_seconds',
            'Database query duration in seconds',
            ['operation', 'table'],
            registry=self.registry
        )
        
        # Métricas de negocio
        self.conversations_total = Counter(
            f'{service_name}_conversations_total',
            'Total number of conversations',
            ['workspace_id', 'vertical'],
            registry=self.registry
        )
        
        self.messages_total = Counter(
            f'{service_name}_messages_total',
            'Total number of messages',
            ['workspace_id', 'direction'],
            registry=self.registry
        )
        
        self.actions_executed_total = Counter(
            f'{service_name}_actions_executed_total',
            'Total number of actions executed',
            ['workspace_id', 'action_type', 'status'],
            registry=self.registry
        )
        
        # Métricas de sistema
        self.active_connections = Gauge(
            f'{service_name}_active_connections',
            'Number of active connections',
            registry=self.registry
        )
        
        self.memory_usage = Gauge(
            f'{service_name}_memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )
        
        # Métricas de errores
        self.errors_total = Counter(
            f'{service_name}_errors_total',
            'Total number of errors',
            ['error_type', 'workspace_id'],
            registry=self.registry
        )
        
        # Métricas de RAG
        self.rag_searches_total = Counter(
            f'{service_name}_rag_searches_total',
            'Total number of RAG searches',
            ['workspace_id', 'vertical'],
            registry=self.registry
        )
        
        self.rag_search_duration = Histogram(
            f'{service_name}_rag_search_duration_seconds',
            'RAG search duration in seconds',
            ['workspace_id'],
            registry=self.registry
        )
        
        self.documents_ingested_total = Counter(
            f'{service_name}_documents_ingested_total',
            'Total number of documents ingested',
            ['workspace_id', 'file_type'],
            registry=self.registry
        )
        
        # Métricas de embeddings
        self.embeddings_generated_total = Counter(
            f'{service_name}_embeddings_generated_total',
            'Total number of embeddings generated',
            ['workspace_id', 'model'],
            registry=self.registry
        )
        
        self.embedding_generation_duration = Histogram(
            f'{service_name}_embedding_generation_duration_seconds',
            'Embedding generation duration in seconds',
            ['workspace_id', 'model'],
            registry=self.registry
        )
    
    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Registrar request"""
        self.requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        self.request_duration.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)
    
    def record_db_query(self, operation: str, table: str, duration: float):
        """Registrar consulta de base de datos"""
        self.db_queries_total.labels(
            operation=operation,
            table=table
        ).inc()
        
        self.db_query_duration.labels(
            operation=operation,
            table=table
        ).observe(duration)
    
    def record_conversation(self, workspace_id: str, vertical: str):
        """Registrar conversación"""
        self.conversations_total.labels(
            workspace_id=workspace_id,
            vertical=vertical
        ).inc()
    
    def record_message(self, workspace_id: str, direction: str):
        """Registrar mensaje"""
        self.messages_total.labels(
            workspace_id=workspace_id,
            direction=direction
        ).inc()
    
    def record_action(self, workspace_id: str, action_type: str, status: str):
        """Registrar acción"""
        self.actions_executed_total.labels(
            workspace_id=workspace_id,
            action_type=action_type,
            status=status
        ).inc()
    
    def record_error(self, error_type: str, workspace_id: str = None):
        """Registrar error"""
        self.errors_total.labels(
            error_type=error_type,
            workspace_id=workspace_id or "unknown"
        ).inc()
    
    def record_rag_search(self, workspace_id: str, vertical: str, duration: float):
        """Registrar búsqueda RAG"""
        self.rag_searches_total.labels(
            workspace_id=workspace_id,
            vertical=vertical
        ).inc()
        
        self.rag_search_duration.labels(
            workspace_id=workspace_id
        ).observe(duration)
    
    def record_document_ingestion(self, workspace_id: str, file_type: str):
        """Registrar ingesta de documento"""
        self.documents_ingested_total.labels(
            workspace_id=workspace_id,
            file_type=file_type
        ).inc()
    
    def record_embedding_generation(self, workspace_id: str, model: str, duration: float):
        """Registrar generación de embedding"""
        self.embeddings_generated_total.labels(
            workspace_id=workspace_id,
            model=model
        ).inc()
        
        self.embedding_generation_duration.labels(
            workspace_id=workspace_id,
            model=model
        ).observe(duration)
    
    def set_active_connections(self, count: int):
        """Establecer número de conexiones activas"""
        self.active_connections.set(count)
    
    def set_memory_usage(self, bytes_used: int):
        """Establecer uso de memoria"""
        self.memory_usage.set(bytes_used)
    
    def start_metrics_server(self, port: int = 8000):
        """Iniciar servidor de métricas"""
        try:
            start_http_server(port, registry=self.registry)
            logger.info(f"Metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")
            raise MetricsError(f"Failed to start metrics server: {e}")

# Instancia global del recolector de métricas
metrics_collector = MetricsCollector("pulpoai")
