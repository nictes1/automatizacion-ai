#!/usr/bin/env python3
"""
Sistema de monitoreo y métricas para PulpoAI
Proporciona métricas de rendimiento, salud del sistema y alertas
"""

import time
import psutil
import logging
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import aiohttp
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """Métricas del sistema"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_usage_percent: float = 0.0
    gpu_memory_used_mb: float = 0.0
    gpu_utilization_percent: float = 0.0

@dataclass
class ServiceMetrics:
    """Métricas de servicios"""
    timestamp: datetime = field(default_factory=datetime.now)
    service_name: str = ""
    status: str = "unknown"
    response_time_ms: float = 0.0
    error_count: int = 0
    request_count: int = 0

@dataclass
class RAGMetrics:
    """Métricas específicas del RAG"""
    timestamp: datetime = field(default_factory=datetime.now)
    total_documents: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    cache_hit_rate: float = 0.0
    avg_ingest_time_ms: float = 0.0
    avg_search_time_ms: float = 0.0
    embeddings_generated_today: int = 0

class SystemMonitor:
    """
    Monitor del sistema PulpoAI
    Recopila métricas de rendimiento y salud
    """
    
    def __init__(self):
        self.metrics_history: List[SystemMetrics] = []
        self.service_metrics: Dict[str, List[ServiceMetrics]] = {}
        self.rag_metrics_history: List[RAGMetrics] = []
        self.max_history_size = 1000
        
    def get_system_metrics(self) -> SystemMetrics:
        """Obtener métricas actuales del sistema"""
        try:
            # Métricas básicas del sistema
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Métricas de GPU (si está disponible)
            gpu_memory = 0.0
            gpu_util = 0.0
            
            try:
                import subprocess
                result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,utilization.gpu', '--format=csv,noheader,nounits'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gpu_data = result.stdout.strip().split(', ')
                    gpu_memory = float(gpu_data[0])
                    gpu_util = float(gpu_data[1])
            except:
                pass  # GPU no disponible
            
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                disk_usage_percent=disk.percent,
                gpu_memory_used_mb=gpu_memory,
                gpu_utilization_percent=gpu_util
            )
            
            # Agregar a historial
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history.pop(0)
                
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo métricas del sistema: {e}")
            return SystemMetrics()
    
    async def check_service_health(self, service_name: str, url: str) -> ServiceMetrics:
        """Verificar salud de un servicio"""
        start_time = time.time()
        status = "healthy"
        error_count = 0
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as response:
                    if response.status == 200:
                        status = "healthy"
                    else:
                        status = "unhealthy"
                        error_count = 1
        except Exception as e:
            status = "unhealthy"
            error_count = 1
            logger.warning(f"⚠️ Servicio {service_name} no responde: {e}")
        
        response_time = (time.time() - start_time) * 1000
        
        metrics = ServiceMetrics(
            service_name=service_name,
            status=status,
            response_time_ms=response_time,
            error_count=error_count,
            request_count=1
        )
        
        # Agregar a historial del servicio
        if service_name not in self.service_metrics:
            self.service_metrics[service_name] = []
        
        self.service_metrics[service_name].append(metrics)
        if len(self.service_metrics[service_name]) > self.max_history_size:
            self.service_metrics[service_name].pop(0)
            
        return metrics
    
    async def check_all_services(self) -> Dict[str, ServiceMetrics]:
        """Verificar salud de todos los servicios"""
        services = {
            "postgres": "http://localhost:5432",
            "redis": "http://localhost:6379",
            "weaviate": "http://localhost:8080/v1/meta",
            "ollama": "http://localhost:11434/api/tags",
            "worker-rag": "http://localhost:8002/health",
            "n8n": "http://localhost:5678"
        }
        
        results = {}
        tasks = []
        
        for service_name, url in services.items():
            task = self.check_service_health(service_name, url)
            tasks.append((service_name, task))
        
        for service_name, task in tasks:
            try:
                metrics = await task
                results[service_name] = metrics
            except Exception as e:
                logger.error(f"❌ Error verificando {service_name}: {e}")
                results[service_name] = ServiceMetrics(
                    service_name=service_name,
                    status="error",
                    error_count=1
                )
        
        return results
    
    def get_rag_metrics(self) -> RAGMetrics:
        """Obtener métricas específicas del RAG"""
        try:
            # Aquí se integrarían con la base de datos para obtener métricas reales
            # Por ahora, métricas de ejemplo
            metrics = RAGMetrics(
                total_documents=0,  # Se obtendría de la DB
                total_chunks=0,     # Se obtendría de la DB
                total_embeddings=0, # Se obtendría de la DB
                cache_hit_rate=0.0, # Se calcularía del caché
                avg_ingest_time_ms=0.0,  # Se calcularía del historial
                avg_search_time_ms=0.0,  # Se calcularía del historial
                embeddings_generated_today=0  # Se contaría del día
            )
            
            self.rag_metrics_history.append(metrics)
            if len(self.rag_metrics_history) > self.max_history_size:
                self.rag_metrics_history.pop(0)
                
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Error obteniendo métricas RAG: {e}")
            return RAGMetrics()
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Obtener resumen de salud del sistema"""
        try:
            # Métricas del sistema
            system_metrics = self.get_system_metrics()
            
            # Verificar servicios (esto sería async en producción)
            service_status = {}
            for service_name in ["postgres", "redis", "weaviate", "ollama", "worker-rag", "n8n"]:
                if service_name in self.service_metrics:
                    latest = self.service_metrics[service_name][-1] if self.service_metrics[service_name] else None
                    service_status[service_name] = {
                        "status": latest.status if latest else "unknown",
                        "last_check": latest.timestamp.isoformat() if latest else None
                    }
                else:
                    service_status[service_name] = {"status": "unknown", "last_check": None}
            
            # Métricas RAG
            rag_metrics = self.get_rag_metrics()
            
            # Calcular salud general
            healthy_services = sum(1 for s in service_status.values() if s["status"] == "healthy")
            total_services = len(service_status)
            overall_health = "healthy" if healthy_services == total_services else "degraded"
            
            if system_metrics.cpu_percent > 80 or system_metrics.memory_percent > 90:
                overall_health = "critical"
            
            return {
                "overall_health": overall_health,
                "timestamp": datetime.now().isoformat(),
                "system_metrics": {
                    "cpu_percent": system_metrics.cpu_percent,
                    "memory_percent": system_metrics.memory_percent,
                    "memory_used_mb": system_metrics.memory_used_mb,
                    "disk_usage_percent": system_metrics.disk_usage_percent,
                    "gpu_memory_used_mb": system_metrics.gpu_memory_used_mb,
                    "gpu_utilization_percent": system_metrics.gpu_utilization_percent
                },
                "services": service_status,
                "rag_metrics": {
                    "total_documents": rag_metrics.total_documents,
                    "total_chunks": rag_metrics.total_chunks,
                    "total_embeddings": rag_metrics.total_embeddings,
                    "cache_hit_rate": rag_metrics.cache_hit_rate,
                    "avg_ingest_time_ms": rag_metrics.avg_ingest_time_ms,
                    "avg_search_time_ms": rag_metrics.avg_search_time_ms
                },
                "alerts": self._generate_alerts(system_metrics, service_status)
            }
            
        except Exception as e:
            logger.error(f"❌ Error generando resumen de salud: {e}")
            return {"error": str(e)}
    
    def _generate_alerts(self, system_metrics: SystemMetrics, service_status: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generar alertas basadas en métricas"""
        alerts = []
        
        # Alertas de sistema
        if system_metrics.cpu_percent > 80:
            alerts.append({
                "level": "warning",
                "message": f"CPU usage high: {system_metrics.cpu_percent:.1f}%"
            })
        
        if system_metrics.memory_percent > 90:
            alerts.append({
                "level": "critical",
                "message": f"Memory usage critical: {system_metrics.memory_percent:.1f}%"
            })
        
        if system_metrics.disk_usage_percent > 85:
            alerts.append({
                "level": "warning",
                "message": f"Disk usage high: {system_metrics.disk_usage_percent:.1f}%"
            })
        
        # Alertas de servicios
        for service_name, status in service_status.items():
            if status["status"] == "unhealthy":
                alerts.append({
                    "level": "critical",
                    "message": f"Service {service_name} is unhealthy"
                })
        
        return alerts
    
    def export_metrics(self, filepath: str = None) -> str:
        """Exportar métricas a archivo JSON"""
        if not filepath:
            filepath = f"metrics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            export_data = {
                "export_timestamp": datetime.now().isoformat(),
                "system_metrics": [
                    {
                        "timestamp": m.timestamp.isoformat(),
                        "cpu_percent": m.cpu_percent,
                        "memory_percent": m.memory_percent,
                        "memory_used_mb": m.memory_used_mb,
                        "disk_usage_percent": m.disk_usage_percent,
                        "gpu_memory_used_mb": m.gpu_memory_used_mb,
                        "gpu_utilization_percent": m.gpu_utilization_percent
                    }
                    for m in self.metrics_history
                ],
                "service_metrics": {
                    service_name: [
                        {
                            "timestamp": m.timestamp.isoformat(),
                            "status": m.status,
                            "response_time_ms": m.response_time_ms,
                            "error_count": m.error_count,
                            "request_count": m.request_count
                        }
                        for m in metrics_list
                    ]
                    for service_name, metrics_list in self.service_metrics.items()
                },
                "rag_metrics": [
                    {
                        "timestamp": m.timestamp.isoformat(),
                        "total_documents": m.total_documents,
                        "total_chunks": m.total_chunks,
                        "total_embeddings": m.total_embeddings,
                        "cache_hit_rate": m.cache_hit_rate,
                        "avg_ingest_time_ms": m.avg_ingest_time_ms,
                        "avg_search_time_ms": m.avg_search_time_ms
                    }
                    for m in self.rag_metrics_history
                ]
            }
            
            with open(filepath, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"✅ Métricas exportadas a {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Error exportando métricas: {e}")
            return ""

# Instancia global del monitor
system_monitor = SystemMonitor()

# Funciones de conveniencia
def get_system_health() -> Dict[str, Any]:
    """Obtener resumen de salud del sistema"""
    return system_monitor.get_health_summary()

def get_system_metrics() -> SystemMetrics:
    """Obtener métricas actuales del sistema"""
    return system_monitor.get_system_metrics()

async def check_services() -> Dict[str, ServiceMetrics]:
    """Verificar salud de todos los servicios"""
    return await system_monitor.check_all_services()

