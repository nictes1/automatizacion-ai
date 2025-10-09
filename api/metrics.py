"""
API de Métricas para PulpoAI
Endpoints para Prometheus, health checks y dashboards
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Dict, Any
import time

from services.observability import (
    observability_manager, 
    dashboard_provider,
    get_metrics_prometheus
)
from config.canary_config import get_canary_manager


router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics():
    """
    Endpoint de métricas para Prometheus
    """
    try:
        metrics = observability_manager.get_metrics_prometheus()
        return PlainTextResponse(content=metrics, media_type="text/plain")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating metrics: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    try:
        health_status = observability_manager.get_health_status()
        
        # Verificar estado general
        is_healthy = (
            health_status["status"] == "healthy" and
            health_status["events_buffer_size"] < 1000 and
            health_status["uptime_seconds"] > 0
        )
        
        status_code = 200 if is_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if is_healthy else "unhealthy",
                "timestamp": time.time(),
                "details": health_status
            }
        )
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": time.time(),
                "error": str(e)
            }
        )


@router.get("/dashboard/overview")
async def dashboard_overview():
    """
    Datos para dashboard principal
    """
    try:
        overview = dashboard_provider.get_system_overview()
        return JSONResponse(content=overview)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating dashboard data: {str(e)}")


@router.get("/canary/status")
async def canary_status():
    """
    Estado del canary deployment
    """
    try:
        canary_manager = get_canary_manager()
        status = canary_manager.get_canary_status()
        return JSONResponse(content=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting canary status: {str(e)}")


@router.post("/canary/config")
async def update_canary_config(config: Dict[str, Any]):
    """
    Actualizar configuración canary
    """
    try:
        canary_manager = get_canary_manager()
        canary_manager.update_config(config)
        
        return JSONResponse(content={
            "status": "success",
            "message": "Canary configuration updated",
            "new_config": canary_manager.get_canary_status()
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error updating canary config: {str(e)}")


@router.get("/tools/performance")
async def tools_performance():
    """
    Performance de tools individuales
    """
    try:
        # En producción, esto vendría de métricas reales
        performance_data = {
            "timestamp": time.time(),
            "tools": [
                {
                    "name": "get_services",
                    "total_calls": 150,
                    "success_rate": 0.98,
                    "avg_latency_ms": 250,
                    "p95_latency_ms": 500,
                    "p99_latency_ms": 800,
                    "error_rate": 0.02,
                    "circuit_breaker_state": "closed"
                },
                {
                    "name": "book_appointment",
                    "total_calls": 45,
                    "success_rate": 0.95,
                    "avg_latency_ms": 1200,
                    "p95_latency_ms": 2000,
                    "p99_latency_ms": 3000,
                    "error_rate": 0.05,
                    "circuit_breaker_state": "closed"
                },
                {
                    "name": "get_availability",
                    "total_calls": 80,
                    "success_rate": 0.99,
                    "avg_latency_ms": 180,
                    "p95_latency_ms": 350,
                    "p99_latency_ms": 600,
                    "error_rate": 0.01,
                    "circuit_breaker_state": "closed"
                }
            ]
        }
        
        return JSONResponse(content=performance_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting tools performance: {str(e)}")


@router.get("/workspaces/summary")
async def workspaces_summary():
    """
    Resumen por workspace
    """
    try:
        # En producción, esto vendría de métricas reales
        summary_data = {
            "timestamp": time.time(),
            "workspaces": [
                {
                    "workspace_id": "workspace_1",
                    "total_requests": 500,
                    "success_rate": 0.97,
                    "avg_latency_ms": 800,
                    "p95_latency_ms": 1500,
                    "error_rate": 0.03,
                    "canary_traffic_percentage": 0.1,
                    "active_circuit_breakers": 0
                },
                {
                    "workspace_id": "workspace_2",
                    "total_requests": 300,
                    "success_rate": 0.99,
                    "avg_latency_ms": 600,
                    "p95_latency_ms": 1200,
                    "error_rate": 0.01,
                    "canary_traffic_percentage": 0.0,
                    "active_circuit_breakers": 0
                },
                {
                    "workspace_id": "workspace_3",
                    "total_requests": 200,
                    "success_rate": 0.95,
                    "avg_latency_ms": 1000,
                    "p95_latency_ms": 2000,
                    "error_rate": 0.05,
                    "canary_traffic_percentage": 0.0,
                    "active_circuit_breakers": 1
                }
            ]
        }
        
        return JSONResponse(content=summary_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting workspaces summary: {str(e)}")


@router.get("/alerts/active")
async def active_alerts():
    """
    Alertas activas del sistema
    """
    try:
        # En producción, esto vendría de un sistema de alertas real
        alerts = []
        
        # Simular algunas alertas
        current_time = time.time()
        
        # Alerta de circuit breaker abierto
        alerts.append({
            "id": "cb_workspace_3_get_availability",
            "type": "circuit_breaker_open",
            "severity": "warning",
            "message": "Circuit breaker OPEN for get_availability in workspace_3",
            "workspace_id": "workspace_3",
            "tool": "get_availability",
            "timestamp": current_time - 300,  # 5 minutos atrás
            "acknowledged": False
        })
        
        # Alerta de alta latencia
        alerts.append({
            "id": "high_latency_workspace_1",
            "type": "high_latency",
            "severity": "info",
            "message": "P95 latency above threshold for workspace_1",
            "workspace_id": "workspace_1",
            "threshold": 1000,
            "current_value": 1500,
            "timestamp": current_time - 600,  # 10 minutos atrás
            "acknowledged": True
        })
        
        return JSONResponse(content={
            "timestamp": current_time,
            "total_alerts": len(alerts),
            "unacknowledged": len([a for a in alerts if not a["acknowledged"]]),
            "alerts": alerts
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting active alerts: {str(e)}")


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """
    Reconocer una alerta
    """
    try:
        # En producción, esto actualizaría el estado en la base de datos
        return JSONResponse(content={
            "status": "success",
            "message": f"Alert {alert_id} acknowledged",
            "timestamp": time.time()
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error acknowledging alert: {str(e)}")


@router.get("/slo/status")
async def slo_status():
    """
    Estado de SLOs (Service Level Objectives)
    """
    try:
        # En producción, esto calcularía SLOs reales
        slo_data = {
            "timestamp": time.time(),
            "slo_period": "24h",
            "objectives": [
                {
                    "name": "availability",
                    "target": 0.999,  # 99.9%
                    "current": 0.998,
                    "status": "breach",
                    "description": "Service availability"
                },
                {
                    "name": "latency_p95",
                    "target": 1000,  # 1 segundo
                    "current": 1200,
                    "status": "breach",
                    "description": "P95 response time"
                },
                {
                    "name": "error_rate",
                    "target": 0.01,  # 1%
                    "current": 0.02,
                    "status": "breach",
                    "description": "Error rate"
                }
            ]
        }
        
        return JSONResponse(content=slo_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting SLO status: {str(e)}")
