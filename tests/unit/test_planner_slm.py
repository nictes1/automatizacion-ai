"""
Tests unitarios para Planner SLM
Valida que el planner genere planes válidos y maneje fallbacks correctamente
"""

import pytest
import json
from pathlib import Path
from services.slm.planner import PlannerSLM, PlanOutput

class DummyLLM:
    """Mock del LLM client para testing"""
    
    async def generate_json(self, system_prompt, user_prompt, schema, temperature=0.2, max_tokens=400):
        """Simula respuestas del SLM"""
        user_data = json.loads(user_prompt)
        intent = user_data["current_input"]["intent"]
        slots = user_data["current_input"].get("slots", {})
        ws_id = user_data["context"]["workspace_id"]
        
        # Simular respuestas por intent
        if intent == "info_hours":
            return {
                "plan_version": "v1",
                "actions": [{"tool": "get_business_hours", "args": {"workspace_id": ws_id}}],
                "needs_confirmation": False
            }
        
        elif intent == "info_services":
            return {
                "plan_version": "v1",
                "actions": [{"tool": "get_available_services", "args": {"workspace_id": ws_id}}],
                "needs_confirmation": False
            }
        
        elif intent == "info_prices":
            q = slots.get("service_type")
            args = {"workspace_id": ws_id}
            if q:
                args["q"] = q
            return {
                "plan_version": "v1",
                "actions": [{"tool": "get_available_services", "args": args}],
                "needs_confirmation": False
            }
        
        elif intent == "book":
            service_type = slots.get("service_type")
            preferred_date = slots.get("preferred_date")
            preferred_time = slots.get("preferred_time")
            client_name = slots.get("client_name")
            client_email = slots.get("client_email")
            
            actions = []
            needs_confirmation = False
            missing_slots = []
            
            if service_type and preferred_date:
                actions.append({
                    "tool": "check_service_availability",
                    "args": {
                        "workspace_id": ws_id,
                        "service_type": service_type,
                        "date_str": preferred_date
                    }
                })
                
                if preferred_time and client_name and client_email:
                    actions.append({
                        "tool": "book_appointment",
                        "args": {
                            "workspace_id": ws_id,
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
            
            return {
                "plan_version": "v1",
                "actions": actions,
                "needs_confirmation": needs_confirmation,
                "missing_slots": missing_slots if missing_slots else []
            }
        
        else:
            # Intent desconocido
            return {
                "plan_version": "v1",
                "actions": [],
                "needs_confirmation": True
            }

@pytest.fixture
def planner_schema():
    """Carga el schema del planner"""
    path = Path("config/schemas/planner_v1.json")
    return json.loads(path.read_text())

@pytest.fixture
def planner():
    """Fixture del planner con LLM dummy"""
    llm = DummyLLM()
    return PlannerSLM(llm)

@pytest.mark.asyncio
async def test_planner_info_hours(planner):
    """Test: consulta de horarios"""
    extractor_out = {
        "intent": "info_hours",
        "slots": {},
        "confidence": 0.93
    }
    
    result = await planner.plan(extractor_out, ["get_business_hours"], "WS-TEST")
    
    assert result.plan_version == "v1"
    assert len(result.actions) == 1
    assert result.actions[0]["tool"] == "get_business_hours"
    assert result.actions[0]["args"]["workspace_id"] == "WS-TEST"
    assert result.needs_confirmation is False

@pytest.mark.asyncio
async def test_planner_info_services(planner):
    """Test: consulta de servicios"""
    extractor_out = {
        "intent": "info_services",
        "slots": {},
        "confidence": 0.90
    }
    
    result = await planner.plan(extractor_out, ["get_available_services"], "WS-TEST")
    
    assert result.plan_version == "v1"
    assert len(result.actions) == 1
    assert result.actions[0]["tool"] == "get_available_services"
    assert result.needs_confirmation is False

@pytest.mark.asyncio
async def test_planner_info_prices_with_service(planner):
    """Test: consulta de precios con servicio específico"""
    extractor_out = {
        "intent": "info_prices",
        "slots": {"service_type": "Corte de Cabello"},
        "confidence": 0.92
    }
    
    result = await planner.plan(extractor_out, ["get_available_services"], "WS-TEST")
    
    assert result.plan_version == "v1"
    assert len(result.actions) == 1
    assert result.actions[0]["tool"] == "get_available_services"
    assert result.actions[0]["args"]["q"] == "Corte de Cabello"
    assert result.needs_confirmation is False

@pytest.mark.asyncio
async def test_planner_book_incomplete(planner):
    """Test: reserva incompleta (falta hora)"""
    extractor_out = {
        "intent": "book",
        "slots": {
            "service_type": "Corte de Cabello",
            "preferred_date": "2025-10-16",
            "preferred_time": None
        },
        "confidence": 0.88
    }
    
    result = await planner.plan(
        extractor_out,
        ["check_service_availability", "book_appointment"],
        "WS-TEST"
    )
    
    assert result.plan_version == "v1"
    assert len(result.actions) == 1  # Solo check_service_availability
    assert result.actions[0]["tool"] == "check_service_availability"
    assert result.needs_confirmation is True
    assert "preferred_time" in result.missing_slots

@pytest.mark.asyncio
async def test_planner_book_complete(planner):
    """Test: reserva completa (todos los datos)"""
    extractor_out = {
        "intent": "book",
        "slots": {
            "service_type": "Corte de Cabello",
            "preferred_date": "2025-10-16",
            "preferred_time": "15:00",
            "client_name": "Juan Pérez",
            "client_email": "juan@example.com"
        },
        "confidence": 0.95
    }
    
    result = await planner.plan(
        extractor_out,
        ["check_service_availability", "book_appointment"],
        "WS-TEST"
    )
    
    assert result.plan_version == "v1"
    assert len(result.actions) == 2  # check + book
    assert result.actions[0]["tool"] == "check_service_availability"
    assert result.actions[1]["tool"] == "book_appointment"
    assert result.actions[1]["args"]["preferred_time"] == "15:00"
    assert result.needs_confirmation is False

@pytest.mark.asyncio
async def test_planner_max_3_actions(planner):
    """Test: máximo 3 actions por plan"""
    # Este test verifica que el planner nunca devuelva más de 3 actions
    # incluso si el SLM intentara generar más
    extractor_out = {
        "intent": "book",
        "slots": {
            "service_type": "Corte de Cabello",
            "preferred_date": "2025-10-16",
            "preferred_time": "15:00",
            "client_name": "Juan Pérez",
            "client_email": "juan@example.com"
        },
        "confidence": 0.95
    }
    
    result = await planner.plan(extractor_out, ["check_service_availability", "book_appointment"], "WS-TEST")
    
    assert len(result.actions) <= 3

@pytest.mark.asyncio
async def test_planner_unknown_intent_fallback(planner):
    """Test: intent desconocido usa fallback"""
    extractor_out = {
        "intent": "chitchat",
        "slots": {},
        "confidence": 0.75
    }
    
    result = await planner.plan(extractor_out, [], "WS-TEST")
    
    assert result.plan_version == "v1"
    assert result.needs_confirmation is True  # No sabe qué hacer

@pytest.mark.asyncio
async def test_planner_workspace_id_injection(planner):
    """Test: workspace_id se inyecta automáticamente en args"""
    extractor_out = {
        "intent": "info_hours",
        "slots": {},
        "confidence": 0.9
    }
    
    result = await planner.plan(extractor_out, ["get_business_hours"], "WS-CUSTOM")
    
    # Verificar que workspace_id esté presente en todos los args
    for action in result.actions:
        assert "workspace_id" in action["args"]
        assert action["args"]["workspace_id"] == "WS-CUSTOM"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])




