#!/usr/bin/env python3
"""
PulpoAI Shared Monitoring Exceptions
Excepciones compartidas para monitoreo
"""

class MonitoringError(Exception):
    """Error base de monitoreo"""
    pass

class MetricsError(MonitoringError):
    """Error de métricas"""
    pass

class LoggingError(MonitoringError):
    """Error de logging"""
    pass

class PrometheusError(MetricsError):
    """Error de Prometheus"""
    pass

class StructuredLoggingError(LoggingError):
    """Error de logging estructurado"""
    pass
