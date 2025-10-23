"""
Planner SLM - Decisión de Tools (NO genera texto)
Usa SLM pequeño con few-shot para decidir qué tools ejecutar basándose en intent + slots
"""

from __future__ import annotations
import json
import logging
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from jsonschema import Draft7Validator, ValidationError

logger = logging.getLogger(__name__)

# Tools permitidos en el vertical de servicios
ALLOWED_TOOLS = {
    "get_available_services",
    "get_business_hours",
    "check_service_availability",
    "book_appointment",
    "cancel_appointment",
    "find_appointment_by_phone",
    "get_service_packages",
    "get_active_promotions",
}

# Sistema: el Planner NO genera texto libre, solo JSON estructurado
PLANNER_SYSTEM = """Eres un planificador de acciones para un agente de reservas de servicios.

TU SALIDA DEBE SER **SOLO JSON VÁLIDO** que cumpla el schema pulpo.planner.v1.

REGLAS CRÍTICAS:
1. NO generes texto para el usuario
2. NO expliques nada en prosa
3. SOLO decide qué tools ejecutar
4. Máximo 3 tools por plan
5. Usa nombres EXACTOS de tools
6. Si faltan datos obligatorios → needs_confirmation=true

Responde SOLO con el JSON del plan."""

# Few-shot examples por intent
PLANNER_FEWSHOT = [
    # 1) Info de servicios general
    {
        "input": {
            "intent": "info_services",
            "slots": {},
            "confidence": 0.9
        },
        "plan": {
            "plan_version": "v1",
            "actions": [
                {"tool": "get_available_services", "args": {"workspace_id": "__WS__"}}
            ],
            "needs_confirmation": False
        }
    },
    
    # 2) Info de precios con servicio específico
    {
        "input": {
            "intent": "info_prices",
            "slots": {"service_type": "Corte de Cabello"},
            "confidence": 0.92
        },
        "plan": {
            "plan_version": "v1",
            "actions": [
                {"tool": "get_available_services", "args": {"workspace_id": "__WS__", "q": "Corte de Cabello"}}
            ],
            "needs_confirmation": False
        }
    },
    
    # 3) Info de horarios
    {
        "input": {
            "intent": "info_hours",
            "slots": {},
            "confidence": 0.93
        },
        "plan": {
            "plan_version": "v1",
            "actions": [
                {"tool": "get_business_hours", "args": {"workspace_id": "__WS__"}}
            ],
            "needs_confirmation": False
        }
    },
    
    # 4) Reserva con servicio+fecha pero sin hora (pedir hora)
    {
        "input": {
            "intent": "book",
            "slots": {
                "service_type": "Corte de Cabello",
                "preferred_date": "2025-10-16",
                "preferred_time": None
            },
            "confidence": 0.88
        },
        "plan": {
            "plan_version": "v1",
            "actions": [
                {"tool": "check_service_availability", "args": {
                    "workspace_id": "__WS__",
                    "service_type": "Corte de Cabello",
                    "date_str": "2025-10-16"
                }}
            ],
            "needs_confirmation": True,
            "missing_slots": ["preferred_time"]
        }
    },
    
    # 5) Reserva completa con servicio+fecha+hora (verificar y reservar)
    {
        "input": {
            "intent": "book",
            "slots": {
                "service_type": "Corte de Cabello",
                "preferred_date": "2025-10-16",
                "preferred_time": "15:00",
                "client_name": "Juan Pérez",
                "client_email": "juan@example.com"
            },
            "confidence": 0.95
        },
        "plan": {
            "plan_version": "v1",
            "actions": [
                {"tool": "check_service_availability", "args": {
                    "workspace_id": "__WS__",
                    "service_type": "Corte de Cabello",
                    "date_str": "2025-10-16"
                }},
                {"tool": "book_appointment", "args": {
                    "workspace_id": "__WS__",
                    "service_type": "Corte de Cabello",
                    "preferred_date": "2025-10-16",
                    "preferred_time": "15:00",
                    "client_name": "Juan Pérez",
                    "client_email": "juan@example.com"
                }}
            ],
            "needs_confirmation": False
        }
    },
    
    # 6) Cancelación
    {
        "input": {
            "intent": "cancel",
            "slots": {"booking_id": "BOOK-123"},
            "confidence": 0.90
        },
        "plan": {
            "plan_version": "v1",
            "actions": [
                {"tool": "cancel_appointment", "args": {
                    "workspace_id": "__WS__",
                    "booking_id": "BOOK-123"
                }}
            ],
            "needs_confirmation": False
        }
    }
]

@dataclass
class PlanOutput:
    """Salida del Planner validada"""
    plan_version: str
    actions: List[Dict[str, Any]]
    needs_confirmation: bool
    missing_slots: Optional[List[str]] = None
    confidence: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "plan_version": self.plan_version,
            "actions": self.actions,
            "needs_confirmation": self.needs_confirmation
        }
        if self.missing_slots:
            result["missing_slots"] = self.missing_slots
        if self.confidence is not None:
            result["confidence"] = self.confidence
        return result

class PlannerSLM:
    """
    Planner basado en SLM con few-shot
    
    Características:
    - Decide qué tools ejecutar (NO genera texto)
    - Usa schema JSON para constrain output
    - Few-shot examples por intent
    - Fallback determinístico si SLM falla
    - Latencia objetivo: 120-200ms
    """
    
    def __init__(self, llm_client, schema_path: str = "config/schemas/planner_v1.json"):
        self.llm_client = llm_client
        
        # Cargar schema JSON
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
        
        self.validator = Draft7Validator(self.schema)
        
        logger.info(f"[PLANNER] Inicializado con schema v1")
    
    async def plan(self,
                   extractor_out: Dict[str, Any],
                   manifest_tools: List[str],
                   workspace_id: str) -> PlanOutput:
        """
        Genera plan de tools basándose en el output del Extractor
        
        Args:
            extractor_out: Output del Extractor {intent, slots, confidence}
            manifest_tools: Lista de tools disponibles en el manifest
            workspace_id: ID del workspace
            
        Returns:
            PlanOutput validado contra schema
        """
        # Construir prompt con few-shot
        user_prompt = self._build_user_prompt(extractor_out, manifest_tools, workspace_id)
        
        try:
            # Llamar al SLM con constrained decoding
            raw_plan = await self.llm_client.generate_json(
                system_prompt=PLANNER_SYSTEM,
                user_prompt=user_prompt,
                schema=self.schema,
                temperature=0.2,  # Bajo para consistencia
                max_tokens=400
            )
            
            # Sanitizar y validar
            plan_dict = self._coerce_and_sanitize(raw_plan, workspace_id)
            
            # Validar contra schema
            is_valid, error = self._validate(plan_dict)
            
            if is_valid:
                logger.info(f"[PLANNER] Plan generado: {len(plan_dict['actions'])} actions, needs_confirmation={plan_dict['needs_confirmation']}")
                return self._dict_to_output(plan_dict)
            else:
                logger.warning(f"[PLANNER] Schema validation failed: {error}, usando fallback")
                return self._fallback_plan(extractor_out, workspace_id)
            
        except Exception as e:
            logger.error(f"[PLANNER] Error generando plan: {e}")
            return self._fallback_plan(extractor_out, workspace_id)
    
    def _build_user_prompt(self, extractor_out: Dict[str, Any], manifest_tools: List[str], workspace_id: str) -> str:
        """Construye prompt con few-shot examples"""
        
        # Filtrar tools permitidos
        allowed_manifest_tools = [t for t in manifest_tools if t in ALLOWED_TOOLS]
        
        # Preparar few-shot examples
        fs_examples = []
        for ex in PLANNER_FEWSHOT:
            # Reemplazar __WS__ con workspace_id real
            plan_json = json.dumps(ex["plan"]).replace("__WS__", workspace_id)
            fs_examples.append({
                "input": ex["input"],
                "plan": json.loads(plan_json)
            })
        
        # Construir payload
        payload = {
            "context": {
                "workspace_id": workspace_id,
                "allowed_tools": allowed_manifest_tools,
                "rules": [
                    "Máximo 3 acciones por plan",
                    "Usa get_available_services para consultas de servicios/precios",
                    "Usa get_business_hours para consultas de horarios",
                    "ANTES de book_appointment SIEMPRE usa check_service_availability",
                    "Si faltan slots obligatorios para book_appointment, marca needs_confirmation=true",
                    "Solo usa tools que están en allowed_tools"
                ]
            },
            "fewshot_examples": fs_examples,
            "current_input": extractor_out
        }
        
        return json.dumps(payload, ensure_ascii=False, indent=2)
    
    def _coerce_and_sanitize(self, plan: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Sanitiza y normaliza el plan del SLM"""
        plan = dict(plan or {})
        
        # Asegurar campos obligatorios
        plan.setdefault("plan_version", "v1")
        plan.setdefault("actions", [])
        plan.setdefault("needs_confirmation", False)
        
        # Filtrar y limpiar actions
        actions: List[Dict[str, Any]] = []
        for action in plan.get("actions", [])[:3]:  # Máximo 3
            tool = action.get("tool")
            args = action.get("args", {}) or {}
            
            # Filtrar tools no permitidos
            if tool not in ALLOWED_TOOLS:
                logger.warning(f"[PLANNER] Tool '{tool}' no permitido, ignorado")
                continue
            
            # Asegurar que workspace_id esté en args
            if "workspace_id" not in args:
                args["workspace_id"] = workspace_id
            
            clean_action = {"tool": tool, "args": args}
            
            # Agregar reasoning si existe (opcional)
            if "reasoning" in action:
                clean_action["reasoning"] = action["reasoning"][:150]
            
            actions.append(clean_action)
        
        plan["actions"] = actions
        
        return plan
    
    def _validate(self, plan: Dict[str, Any]) -> Tuple[bool, str]:
        """Valida plan contra schema JSON"""
        try:
            self.validator.validate(plan)
            return True, ""
        except ValidationError as e:
            return False, str(e.message)
    
    def _fallback_plan(self, extractor_out: Dict[str, Any], workspace_id: str) -> PlanOutput:
        """Genera plan usando reglas determinísticas de fallback"""
        logger.warning("[PLANNER] Usando fallback determinístico")
        
        intent = extractor_out.get("intent", "other")
        slots = extractor_out.get("slots", {}) or {}
        
        service_type = slots.get("service_type")
        preferred_date = slots.get("preferred_date")
        preferred_time = slots.get("preferred_time")
        client_name = slots.get("client_name")
        client_email = slots.get("client_email")
        booking_id = slots.get("booking_id")
        
        actions = []
        needs_confirmation = False
        missing_slots = []
        
        # Fallback por intent
        if intent == "info_services":
            actions = [{"tool": "get_available_services", "args": {"workspace_id": workspace_id}}]
            
        elif intent == "info_prices":
            args = {"workspace_id": workspace_id}
            if service_type:
                args["q"] = service_type
            actions = [{"tool": "get_available_services", "args": args}]
            
        elif intent == "info_hours":
            actions = [{"tool": "get_business_hours", "args": {"workspace_id": workspace_id}}]
            
        elif intent == "book":
            if service_type and preferred_date:
                # Verificar disponibilidad
                actions.append({
                    "tool": "check_service_availability",
                    "args": {
                        "workspace_id": workspace_id,
                        "service_type": service_type,
                        "date_str": preferred_date
                    }
                })
                
                # Si tenemos todo, intentar reservar
                if preferred_time and client_name and client_email:
                    actions.append({
                        "tool": "book_appointment",
                        "args": {
                            "workspace_id": workspace_id,
                            "service_type": service_type,
                            "preferred_date": preferred_date,
                            "preferred_time": preferred_time,
                            "client_name": client_name,
                            "client_email": client_email
                        }
                    })
                else:
                    needs_confirmation = True
                    if not preferred_time:
                        missing_slots.append("preferred_time")
                    if not client_name:
                        missing_slots.append("client_name")
                    if not client_email:
                        missing_slots.append("client_email")
            else:
                needs_confirmation = True
                if not service_type:
                    missing_slots.append("service_type")
                if not preferred_date:
                    missing_slots.append("preferred_date")
        
        elif intent == "cancel":
            if booking_id:
                actions = [{
                    "tool": "cancel_appointment",
                    "args": {"workspace_id": workspace_id, "booking_id": booking_id}
                }]
            else:
                needs_confirmation = True
                missing_slots.append("booking_id")
        
        else:
            # Intent desconocido o chitchat → no hacer nada
            needs_confirmation = True
        
        return PlanOutput(
            plan_version="v1",
            actions=actions[:3],  # Máximo 3
            needs_confirmation=needs_confirmation,
            missing_slots=missing_slots if missing_slots else None,
            confidence=0.5  # Baja confidence para fallback
        )
    
    def _dict_to_output(self, plan_dict: Dict[str, Any]) -> PlanOutput:
        """Convierte dict a PlanOutput"""
        return PlanOutput(
            plan_version=plan_dict["plan_version"],
            actions=plan_dict["actions"],
            needs_confirmation=plan_dict["needs_confirmation"],
            missing_slots=plan_dict.get("missing_slots"),
            confidence=plan_dict.get("confidence")
        )




