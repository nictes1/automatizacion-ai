"""
Integración del SLM Pipeline con Orchestrator existente
Incluye feature flags, canary deployment y telemetría
"""

import os
import random
import logging
import time
from typing import Optional
from dataclasses import dataclass

from services.orchestrator_slm_pipeline import OrchestratorSLMPipeline, OrchestratorResponse
from services.tool_broker import get_tool_broker
from services.policy_engine import PolicyEngine
from services.state_reducer import StateReducer

logger = logging.getLogger(__name__)

class OrchestratorServiceIntegrated:
    """
    Orchestrator con integración SLM Pipeline
    
    Features:
    - Feature flag: ENABLE_SLM_PIPELINE
    - Canary deployment: SLM_CANARY_PERCENT (0-100%)
    - Fallback automático a legacy
    - Telemetría completa
    """
    
    def __init__(self, llm_json_client, enable_agent_loop: bool = True):
        # Legacy flag (mantener compatibilidad)
        self.enable_agent_loop = enable_agent_loop
        
        # SLM Pipeline flags
        self.enable_slm_pipeline = os.getenv("ENABLE_SLM_PIPELINE", "false").lower() == "true"
        self.slm_canary_percent = int(os.getenv("SLM_CANARY_PERCENT", "0"))
        
        logger.info(f"[ORCHESTRATOR] SLM Pipeline: enabled={self.enable_slm_pipeline}, canary={self.slm_canary_percent}%")
        
        # Core infrastructure
        self.tool_broker = get_tool_broker()
        self.policy_engine = PolicyEngine()
        self.state_reducer = StateReducer()
        
        # Instancia SLM Pipeline
        self.slm_pipeline = OrchestratorSLMPipeline(
            llm_client=llm_json_client,
            tool_broker=self.tool_broker,
            policy_engine=self.policy_engine,
            state_reducer=self.state_reducer,
            enable_slm_pipeline=self.enable_slm_pipeline
        )
        
        # Métricas
        self.metrics = {
            "slm_requests": 0,
            "legacy_requests": 0,
            "slm_errors": 0,
            "legacy_errors": 0
        }
    
    async def decide(self, snapshot) -> OrchestratorResponse:
        """
        Punto de entrada principal con routing inteligente
        
        Routing:
        1. Si ENABLE_SLM_PIPELINE=false → legacy
        2. Si canary_percent > 0 → random routing
        3. Si canary_percent = 0 → 100% SLM
        """
        t0 = time.time()
        route = "legacy"
        
        try:
            # 1) Decidir routing
            if self.enable_slm_pipeline:
                if self.slm_canary_percent == 0:
                    # 100% SLM
                    route = "slm_pipeline"
                elif self.slm_canary_percent > 0:
                    # Canary: random routing
                    r = random.randint(1, 100)
                    if r <= self.slm_canary_percent:
                        route = "slm_pipeline"
            
            # 2) Ejecutar según route
            if route == "slm_pipeline":
                logger.info(f"[ROUTING] route=slm_pipeline canary={self.slm_canary_percent}% workspace={snapshot.workspace_id}")
                self.metrics["slm_requests"] += 1
                
                try:
                    response = await self.slm_pipeline.decide(snapshot)
                    
                    # Telemetría
                    t_total = int((time.time() - t0) * 1000)
                    self._log_telemetry(route, response, t_total, snapshot)
                    
                    return response
                    
                except Exception as e:
                    logger.error(f"[SLM_PIPELINE] Error: {e}, falling back to legacy")
                    self.metrics["slm_errors"] += 1
                    route = "legacy_fallback"
            
            # 3) Legacy (o fallback)
            logger.info(f"[ROUTING] route={route} workspace={snapshot.workspace_id}")
            self.metrics["legacy_requests"] += 1
            
            try:
                response = await self._decide_legacy(snapshot)
                
                t_total = int((time.time() - t0) * 1000)
                self._log_telemetry(route, response, t_total, snapshot)
                
                return response
                
            except Exception as e:
                logger.error(f"[LEGACY] Error: {e}")
                self.metrics["legacy_errors"] += 1
                raise
        
        except Exception as e:
            logger.exception(f"[ORCHESTRATOR] Fatal error: {e}")
            
            # Respuesta de emergencia
            return OrchestratorResponse(
                assistant="Disculpá, tuve un problema técnico. ¿Podés intentar de nuevo en un momento?",
                slots=snapshot.slots if hasattr(snapshot, 'slots') else {},
                tool_calls=[],
                context_used=[],
                next_action="error",
                end=False,
                debug={"error": str(e), "route": route}
            )
    
    def _log_telemetry(self, route: str, response: OrchestratorResponse, t_total: int, snapshot):
        """Log telemetría estructurada"""
        debug = response.debug or {}
        
        # Extraer métricas por etapa
        t_extract = debug.get("t_extract_ms", 0)
        t_plan = debug.get("t_plan_ms", 0)
        t_policy = debug.get("t_policy_ms", 0)
        t_broker = debug.get("t_broker_ms", 0)
        t_reduce = debug.get("t_reduce_ms", 0)
        t_nlg = debug.get("t_nlg_ms", 0)
        
        intent = debug.get("intent", "unknown")
        confidence = debug.get("confidence", 0.0)
        actions_count = len(response.tool_calls)
        
        # Log estructurado
        logger.info(
            f"TELEMETRY "
            f"route={route} "
            f"workspace={snapshot.workspace_id} "
            f"intent={intent} "
            f"confidence={confidence:.2f} "
            f"actions={actions_count} "
            f"t_extract_ms={t_extract} "
            f"t_plan_ms={t_plan} "
            f"t_policy_ms={t_policy} "
            f"t_broker_ms={t_broker} "
            f"t_reduce_ms={t_reduce} "
            f"t_nlg_ms={t_nlg} "
            f"t_total_ms={t_total}"
        )
        
        # Alertas si excede thresholds
        if t_total > 2000:
            logger.warning(f"[ALERT] High latency: {t_total}ms > 2000ms")
        
        if route == "slm_pipeline" and confidence < 0.7:
            logger.warning(f"[ALERT] Low confidence: {confidence:.2f} < 0.7")
    
    async def _decide_legacy(self, snapshot) -> OrchestratorResponse:
        """
        Método legacy (placeholder)
        Reemplazar con tu implementación actual
        """
        logger.warning("[LEGACY] Using legacy decision method")
        
        # Aquí iría tu lógica actual del orchestrator
        # Por ahora retorno respuesta genérica
        return OrchestratorResponse(
            assistant="Te ayudo con turnos, precios y horarios. ¿Qué necesitás?",
            slots=snapshot.slots if hasattr(snapshot, 'slots') else {},
            tool_calls=[],
            context_used=["legacy"],
            next_action="answer",
            end=False,
            debug={"route": "legacy"}
        )
    
    def get_metrics(self) -> dict:
        """Obtiene métricas del orchestrator"""
        total = self.metrics["slm_requests"] + self.metrics["legacy_requests"]
        
        return {
            **self.metrics,
            "total_requests": total,
            "slm_percentage": (self.metrics["slm_requests"] / total * 100) if total > 0 else 0,
            "slm_error_rate": (self.metrics["slm_errors"] / self.metrics["slm_requests"] * 100) if self.metrics["slm_requests"] > 0 else 0,
            "legacy_error_rate": (self.metrics["legacy_errors"] / self.metrics["legacy_requests"] * 100) if self.metrics["legacy_requests"] > 0 else 0
        }




