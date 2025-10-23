"""
Orchestrator con SLM Pipeline
Integra Extractor → Planner → Policy → Broker → Reducer → NLG
"""

import json
import time
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from services.slm.extractor import ExtractorSLM
from services.slm.planner import PlannerSLM
from services.response.simple_nlg import build_user_message, _build_missing_prompt

logger = logging.getLogger(__name__)

@dataclass
class OrchestratorResponse:
    """Respuesta del orchestrator"""
    assistant: str
    slots: Dict[str, Any]
    tool_calls: List[Dict[str, Any]]
    context_used: List[str]
    next_action: str
    end: bool
    debug: Optional[Dict[str, Any]] = None

class OrchestratorSLMPipeline:
    """
    Orchestrator basado en SLM Pipeline
    
    Pipeline:
    1. Extractor SLM → intent + slots
    2. Planner SLM → tools a ejecutar
    3. Policy → validación
    4. Tool Broker → ejecución
    5. State Reducer → actualización
    6. NLG → respuesta determinística
    """
    
    def __init__(self, llm_client, tool_broker, policy_engine, state_reducer, enable_slm_pipeline: bool = True):
        self.enable_slm_pipeline = enable_slm_pipeline
        self.llm_client = llm_client
        self.tool_broker = tool_broker
        self.policy_engine = policy_engine
        self.state_reducer = state_reducer
        
        # Cargar schemas
        self.extractor_schema = self._load_schema("config/schemas/extractor_v1.json")
        self.planner_schema = self._load_schema("config/schemas/planner_v1.json")
        
        # Inicializar SLMs
        self.extractor_slm = ExtractorSLM(llm_client, schema_path="config/schemas/extractor_v1.json")
        self.planner_slm = PlannerSLM(llm_client, schema_path="config/schemas/planner_v1.json")
        
        logger.info("[ORCHESTRATOR_SLM] Inicializado con SLM pipeline")
    
    def _load_schema(self, path: str) -> Dict[str, Any]:
        """Carga schema JSON"""
        try:
            return json.loads(Path(path).read_text())
        except Exception as e:
            logger.error(f"[ORCHESTRATOR_SLM] Error cargando schema {path}: {e}")
            return {}
    
    async def decide(self, snapshot) -> OrchestratorResponse:
        """
        Punto de entrada principal
        
        Args:
            snapshot: ConversationSnapshot con estado actual
            
        Returns:
            OrchestratorResponse con respuesta para el usuario
        """
        if not self.enable_slm_pipeline:
            logger.warning("[ORCHESTRATOR_SLM] Pipeline deshabilitado, usando legacy")
            return await self._decide_legacy(snapshot)
        
        return await self._decide_with_slm_pipeline(snapshot)
    
    async def _decide_with_slm_pipeline(self, snapshot) -> OrchestratorResponse:
        """Pipeline SLM completo"""
        t0 = time.time()
        
        workspace_id = snapshot.workspace_id
        user_text = snapshot.user_input
        conversation_id = snapshot.conversation_id
        
        try:
            # 1) EXTRACTION (150-250ms)
            t_extract_start = time.time()
            
            tenant_context = {
                "workspace_id": workspace_id,
                "available_services": snapshot.slots.get("_available_services_cache", [])
            }
            
            extract = await self.extractor_slm.extract(user_text, tenant_context)
            
            intent = extract.intent
            slots = extract.slots
            confidence = extract.confidence
            
            t_extract = int((time.time() - t_extract_start) * 1000)
            logger.info(f"[EXTRACT] intent={intent}, confidence={confidence:.2f}, slots={len(slots)}, time={t_extract}ms")
            
            # 2) PLANNING (120-200ms)
            t_plan_start = time.time()
            
            # Obtener tools disponibles del manifest
            from services.tool_manifest import load_tool_manifest
            try:
                manifest = load_tool_manifest(snapshot.vertical)
                allowed_tools = [t.name for t in manifest.tools]
            except:
                allowed_tools = []
                logger.warning("[PLANNER] No se pudo cargar manifest, usando lista vacía")
            
            plan = await self.planner_slm.plan(
                extractor_out=extract.to_dict(),
                manifest_tools=allowed_tools,
                workspace_id=workspace_id
            )
            
            t_plan = int((time.time() - t_plan_start) * 1000)
            logger.info(f"[PLANNER] actions={len(plan.actions)}, needs_confirmation={plan.needs_confirmation}, time={t_plan}ms")
            
            # Merge slots del extractor con snapshot
            updated_slots = dict(snapshot.slots)
            for key, value in slots.items():
                if value is not None:
                    updated_slots[key] = value
            
            # 3) POLICY VALIDATION (<10ms)
            t_policy_start = time.time()
            
            if plan.needs_confirmation and plan.missing_slots:
                # Faltan datos obligatorios
                missing_msg = _build_missing_prompt(intent, plan.missing_slots, updated_slots)
                
                t_total = int((time.time() - t0) * 1000)
                
                return OrchestratorResponse(
                    assistant=missing_msg,
                    slots=updated_slots,
                    tool_calls=[],
                    context_used=[],
                    next_action="ask_missing_data",
                    end=False,
                    debug={
                        "intent": intent,
                        "missing_slots": plan.missing_slots,
                        "t_extract_ms": t_extract,
                        "t_plan_ms": t_plan,
                        "t_total_ms": t_total
                    }
                )
            
            t_policy = int((time.time() - t_policy_start) * 1000)
            
            # 4) TOOL EXECUTION (100-500ms)
            t_broker_start = time.time()
            
            observations = []
            tool_calls_log = []
            
            for idx, action in enumerate(plan.actions):
                tool_name = action["tool"]
                tool_args = action.get("args", {})
                
                # Asegurar workspace_id en args
                if "workspace_id" not in tool_args:
                    tool_args["workspace_id"] = workspace_id
                
                try:
                    # Ejecutar tool
                    # Nota: aquí deberías usar tu tool_broker real
                    # Por ahora simulamos la estructura
                    observation = await self._execute_tool_safe(
                        tool_name, tool_args, workspace_id, conversation_id
                    )
                    
                    observations.append(observation)
                    tool_calls_log.append({
                        "tool": tool_name,
                        "args": self._redact_pii(tool_args),
                        "success": observation.get("success", False)
                    })
                    
                except Exception as e:
                    logger.error(f"[BROKER] Error ejecutando {tool_name}: {e}")
                    observations.append({
                        "tool": tool_name,
                        "success": False,
                        "error": str(e)
                    })
            
            t_broker = int((time.time() - t_broker_start) * 1000)
            logger.info(f"[BROKER] executed={len(observations)}, time={t_broker}ms")
            
            # 5) STATE REDUCTION (<20ms)
            t_reduce_start = time.time()
            
            # Aplicar observaciones al estado
            patch = self._apply_observations_to_state(observations, updated_slots)
            
            # Merge patch con slots
            for key, value in patch.items():
                updated_slots[key] = value
            
            t_reduce = int((time.time() - t_reduce_start) * 1000)
            
            # 6) RESPONSE GENERATION (80-150ms)
            t_nlg_start = time.time()
            
            response_text = build_user_message(
                intent=intent,
                extract=extract.to_dict(),
                plan=plan.to_dict(),
                patch={"slots_patch": patch},
                observations=observations
            )
            
            t_nlg = int((time.time() - t_nlg_start) * 1000)
            t_total = int((time.time() - t0) * 1000)
            
            logger.info(f"[PIPELINE] Total: {t_total}ms (extract={t_extract}ms, plan={t_plan}ms, policy={t_policy}ms, broker={t_broker}ms, reduce={t_reduce}ms, nlg={t_nlg}ms)")
            
            return OrchestratorResponse(
                assistant=response_text,
                slots=updated_slots,
                tool_calls=tool_calls_log,
                context_used=["slm_pipeline"],
                next_action="answer",
                end=(intent in ["cancel", "chitchat"]),
                debug={
                    "intent": intent,
                    "confidence": confidence,
                    "t_extract_ms": t_extract,
                    "t_plan_ms": t_plan,
                    "t_policy_ms": t_policy,
                    "t_broker_ms": t_broker,
                    "t_reduce_ms": t_reduce,
                    "t_nlg_ms": t_nlg,
                    "t_total_ms": t_total
                }
            )
        
        except Exception as e:
            logger.exception(f"[ORCHESTRATOR_SLM] Error en pipeline: {e}")
            
            return OrchestratorResponse(
                assistant="Hubo un problema. ¿Podés intentar de nuevo?",
                slots=snapshot.slots,
                tool_calls=[],
                context_used=[],
                next_action="error",
                end=False,
                debug={"error": str(e)}
            )
    
    async def _execute_tool_safe(self, tool_name: str, args: Dict[str, Any], workspace_id: str, conversation_id: str) -> Dict[str, Any]:
        """
        Ejecuta un tool de forma segura
        Wrapper temporal - reemplazar con tu tool_broker real
        """
        try:
            # Aquí deberías usar tu tool_broker existente
            # Por ahora retornamos estructura simulada
            
            # Importar tools de servicios
            from services import servicios_tools
            
            if hasattr(servicios_tools, tool_name):
                tool_func = getattr(servicios_tools, tool_name)
                result = await tool_func(**args)
                
                return {
                    "tool": tool_name,
                    "success": result.get("success", False),
                    "data": result.get("data"),
                    "error": result.get("error")
                }
            else:
                return {
                    "tool": tool_name,
                    "success": False,
                    "error": f"Tool {tool_name} not found"
                }
        
        except Exception as e:
            logger.error(f"[TOOL_EXECUTE] Error: {e}")
            return {
                "tool": tool_name,
                "success": False,
                "error": str(e)
            }
    
    def _apply_observations_to_state(self, observations: List[Dict[str, Any]], current_slots: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica observaciones de tools al estado
        Wrapper temporal - reemplazar con tu state_reducer real
        """
        patch = {}
        
        for obs in observations:
            tool = obs.get("tool")
            success = obs.get("success", False)
            data = obs.get("data", {})
            
            if not success:
                continue
            
            # Mapear resultados de tools a slots
            if tool == "get_available_services":
                patch["_available_services"] = data
            
            elif tool == "get_business_hours":
                patch["_business_hours"] = data
            
            elif tool == "check_service_availability":
                patch["_availability_checked"] = True
                patch["_available_slots"] = data.get("available_slots", [])
            
            elif tool == "book_appointment":
                if data.get("booking_id"):
                    patch["booking_id"] = data["booking_id"]
                    patch["_booking_confirmed"] = True
            
            elif tool == "cancel_appointment":
                patch["_cancelled"] = True
        
        return patch
    
    def _redact_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redacta PII de logs"""
        redacted = data.copy()
        
        pii_fields = ["client_name", "client_email", "client_phone"]
        for field in pii_fields:
            if field in redacted:
                redacted[field] = "***"
        
        return redacted
    
    async def _decide_legacy(self, snapshot):
        """Fallback a método legacy (placeholder)"""
        logger.warning("[ORCHESTRATOR_SLM] Using legacy decision method")
        return OrchestratorResponse(
            assistant="Sistema en mantenimiento. Intenta en unos minutos.",
            slots=snapshot.slots,
            tool_calls=[],
            context_used=["legacy"],
            next_action="wait",
            end=False
        )




