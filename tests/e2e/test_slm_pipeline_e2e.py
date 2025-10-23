"""
Tests E2E del SLM Pipeline
Simula conversaciones completas desde el usuario hasta la respuesta
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

from services.orchestrator_slm_pipeline import OrchestratorSLMPipeline

@dataclass
class MockSnapshot:
    """Mock del ConversationSnapshot"""
    workspace_id: str
    conversation_id: str
    user_input: str
    vertical: str
    slots: dict
    
class DummyLLMClient:
    """Mock del LLM client para testing"""
    
    async def generate_json(self, system_prompt, user_prompt="", schema=None, temperature=0.2, max_tokens=400):
        """Simula respuestas del LLM"""
        # Detectar si es Extractor o Planner por el schema
        if schema and "intent" in str(schema):
            # Es Extractor
            if "horario" in user_prompt.lower() or "abre" in user_prompt.lower():
                return {
                    "intent": "info_hours",
                    "slots": {},
                    "confidence": 0.93
                }
            elif "precio" in user_prompt.lower() or "cuesta" in user_prompt.lower():
                return {
                    "intent": "info_prices",
                    "slots": {"service_type": "Corte de Cabello"},
                    "confidence": 0.92
                }
            elif "quiero" in user_prompt.lower() and "turno" in user_prompt.lower():
                return {
                    "intent": "book",
                    "slots": {
                        "service_type": "Corte de Cabello",
                        "preferred_date": "2025-10-16",
                        "preferred_time": "15:00"
                    },
                    "confidence": 0.95
                }
            else:
                return {
                    "intent": "greeting",
                    "slots": {},
                    "confidence": 0.90
                }
        
        else:
            # Es Planner
            import json
            try:
                user_data = json.loads(user_prompt)
                intent = user_data.get("current_input", {}).get("intent")
                slots = user_data.get("current_input", {}).get("slots", {})
                ws_id = user_data.get("context", {}).get("workspace_id", "WS-TEST")
                
                if intent == "info_hours":
                    return {
                        "plan_version": "v1",
                        "actions": [{"tool": "get_business_hours", "args": {"workspace_id": ws_id}}],
                        "needs_confirmation": False
                    }
                
                elif intent in ["info_prices", "info_services"]:
                    args = {"workspace_id": ws_id}
                    if slots.get("service_type"):
                        args["q"] = slots["service_type"]
                    return {
                        "plan_version": "v1",
                        "actions": [{"tool": "get_available_services", "args": args}],
                        "needs_confirmation": False
                    }
                
                elif intent == "book":
                    actions = []
                    missing = []
                    
                    if slots.get("service_type") and slots.get("preferred_date"):
                        actions.append({
                            "tool": "check_service_availability",
                            "args": {
                                "workspace_id": ws_id,
                                "service_type": slots["service_type"],
                                "date_str": slots["preferred_date"]
                            }
                        })
                        
                        if slots.get("preferred_time") and slots.get("client_name") and slots.get("client_email"):
                            actions.append({
                                "tool": "book_appointment",
                                "args": {
                                    "workspace_id": ws_id,
                                    "service_type": slots["service_type"],
                                    "preferred_date": slots["preferred_date"],
                                    "preferred_time": slots["preferred_time"],
                                    "client_name": slots["client_name"],
                                    "client_email": slots["client_email"]
                                }
                            })
                        else:
                            if not slots.get("preferred_time"):
                                missing.append("preferred_time")
                            if not slots.get("client_name"):
                                missing.append("client_name")
                            if not slots.get("client_email"):
                                missing.append("client_email")
                    
                    return {
                        "plan_version": "v1",
                        "actions": actions,
                        "needs_confirmation": bool(missing),
                        "missing_slots": missing
                    }
                
                else:
                    return {
                        "plan_version": "v1",
                        "actions": [],
                        "needs_confirmation": True
                    }
            except:
                return {
                    "plan_version": "v1",
                    "actions": [],
                    "needs_confirmation": True
                }

class MockToolBroker:
    """Mock del tool broker"""
    async def execute(self, *args, **kwargs):
        return {"success": True, "data": {}}

class MockPolicyEngine:
    """Mock del policy engine"""
    def validate_plan(self, snapshot, plan):
        return MagicMock(allowed=True, needs=[])

class MockStateReducer:
    """Mock del state reducer"""
    def apply(self, observations, snapshot):
        return {}

@pytest.fixture
def orchestrator():
    """Fixture del orchestrator con mocks"""
    llm_client = DummyLLMClient()
    tool_broker = MockToolBroker()
    policy_engine = MockPolicyEngine()
    state_reducer = MockStateReducer()
    
    return OrchestratorSLMPipeline(
        llm_client=llm_client,
        tool_broker=tool_broker,
        policy_engine=policy_engine,
        state_reducer=state_reducer,
        enable_slm_pipeline=True
    )

@pytest.mark.asyncio
async def test_e2e_info_hours(orchestrator):
    """Test E2E: consulta de horarios"""
    snapshot = MockSnapshot(
        workspace_id="WS-TEST",
        conversation_id="CONV-1",
        user_input="¿A qué hora abren?",
        vertical="servicios",
        slots={}
    )
    
    response = await orchestrator.decide(snapshot)
    
    assert response.assistant is not None
    assert len(response.assistant) > 0
    assert "horario" in response.assistant.lower() or "consulté" in response.assistant.lower()
    assert response.debug["intent"] == "info_hours"
    assert response.debug["t_total_ms"] < 2000  # < 2s

@pytest.mark.asyncio
async def test_e2e_info_prices(orchestrator):
    """Test E2E: consulta de precios"""
    snapshot = MockSnapshot(
        workspace_id="WS-TEST",
        conversation_id="CONV-2",
        user_input="¿Cuánto cuesta un corte?",
        vertical="servicios",
        slots={}
    )
    
    response = await orchestrator.decide(snapshot)
    
    assert response.assistant is not None
    assert response.debug["intent"] == "info_prices"
    assert response.debug["t_total_ms"] < 2000

@pytest.mark.asyncio
async def test_e2e_book_incomplete(orchestrator):
    """Test E2E: reserva incompleta (falta datos del cliente)"""
    snapshot = MockSnapshot(
        workspace_id="WS-TEST",
        conversation_id="CONV-3",
        user_input="Quiero turno para corte mañana a las 3pm",
        vertical="servicios",
        slots={}
    )
    
    response = await orchestrator.decide(snapshot)
    
    assert response.assistant is not None
    assert response.debug["intent"] == "book"
    
    # Debería pedir datos del cliente
    assert "nombre" in response.assistant.lower() or "email" in response.assistant.lower()
    assert response.next_action == "ask_missing_data"

@pytest.mark.asyncio
async def test_e2e_greeting(orchestrator):
    """Test E2E: saludo inicial"""
    snapshot = MockSnapshot(
        workspace_id="WS-TEST",
        conversation_id="CONV-4",
        user_input="Hola, buenos días",
        vertical="servicios",
        slots={}
    )
    
    response = await orchestrator.decide(snapshot)
    
    assert response.assistant is not None
    assert response.debug["intent"] == "greeting"
    assert "ayudo" in response.assistant.lower() or "hola" in response.assistant.lower()

@pytest.mark.asyncio
async def test_e2e_latency_budget(orchestrator):
    """Test E2E: verificar presupuesto de latencia"""
    snapshot = MockSnapshot(
        workspace_id="WS-TEST",
        conversation_id="CONV-5",
        user_input="¿Qué servicios tienen?",
        vertical="servicios",
        slots={}
    )
    
    response = await orchestrator.decide(snapshot)
    
    # Verificar presupuestos por etapa
    debug = response.debug
    
    assert debug["t_extract_ms"] < 300  # Objetivo: 150-250ms
    assert debug["t_plan_ms"] < 300     # Objetivo: 120-200ms
    assert debug["t_policy_ms"] < 50    # Objetivo: <10ms
    assert debug["t_nlg_ms"] < 200      # Objetivo: 80-150ms
    assert debug["t_total_ms"] < 1500   # Objetivo: <1500ms (p90)

@pytest.mark.asyncio
async def test_e2e_response_length(orchestrator):
    """Test E2E: verificar que respuestas sean cortas"""
    snapshot = MockSnapshot(
        workspace_id="WS-TEST",
        conversation_id="CONV-6",
        user_input="¿Cuánto sale un corte?",
        vertical="servicios",
        slots={}
    )
    
    response = await orchestrator.decide(snapshot)
    
    # Respuesta debería ser < 300 chars (idealmente <200)
    assert len(response.assistant) < 300
    
    # Debería tener máximo 3-4 oraciones
    sentences = response.assistant.count(".") + response.assistant.count("?") + response.assistant.count("!")
    assert sentences <= 4

if __name__ == "__main__":
    pytest.main([__file__, "-v"])




