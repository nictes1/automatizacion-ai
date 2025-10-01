"""
Mini test de humo para verificar serialización de OrchestratorResponse
"""

import pytest
import json
from unittest.mock import AsyncMock, patch
from services.orchestrator_service import (
    OrchestratorService, 
    ConversationSnapshot, 
    OrchestratorResponse,
    NextAction
)


@pytest.mark.asyncio
async def test_orchestrator_response_serialization():
    """
    Test que verifica que OrchestratorResponse se serializa correctamente
    con next_action como Enum
    """
    # Crear un snapshot de prueba
    snapshot = ConversationSnapshot(
        conversation_id="test-123",
        vertical="gastronomia",
        user_input="Quiero pedir empanadas",
        greeted=False,
        slots={},
        objective="completar_pedido",
        attempts_count=0
    )
    
    # Mock del servicio para retornar respuesta controlada
    with patch.object(OrchestratorService, 'decide') as mock_decide:
        # Configurar mock para retornar respuesta con NextAction.GREET
        mock_response = OrchestratorResponse(
            assistant="¡Hola! ¿En qué puedo ayudarte?",
            slots={"greeted": True},
            tool_calls=[],
            context_used=[],
            next_action=NextAction.GREET,
            end=False
        )
        mock_decide.return_value = mock_response
        
        # Crear instancia del servicio
        service = OrchestratorService()
        
        # Llamar al método
        response = await service.decide(snapshot)
        
        # Verificar que es una instancia de OrchestratorResponse
        assert isinstance(response, OrchestratorResponse)
        
        # Verificar que next_action es el Enum correcto
        assert response.next_action == NextAction.GREET
        
        # Verificar serialización a JSON
        json_str = response.model_dump_json()
        json_data = json.loads(json_str)
        
        # Verificar que next_action se serializa como string
        assert json_data["next_action"] == "GREET"
        
        # Verificar que el JSON completo es válido
        assert json_data["assistant"] == "¡Hola! ¿En qué puedo ayudarte?"
        assert json_data["slots"] == {"greeted": True}
        assert json_data["tool_calls"] == []
        assert json_data["context_used"] == []
        assert json_data["end"] is False
        
        print("✅ Serialización correcta:")
        print(f"   next_action: {json_data['next_action']}")
        print(f"   JSON válido: {len(json_str)} caracteres")


@pytest.mark.asyncio
async def test_all_next_action_values_serialize():
    """
    Test que verifica que todos los valores de NextAction se serializan correctamente
    """
    test_cases = [
        NextAction.GREET,
        NextAction.SLOT_FILL,
        NextAction.RETRIEVE_CONTEXT,
        NextAction.EXECUTE_ACTION,
        NextAction.ANSWER,
        NextAction.ASK_HUMAN
    ]
    
    for action in test_cases:
        response = OrchestratorResponse(
            assistant="Test message",
            slots={},
            tool_calls=[],
            context_used=[],
            next_action=action,
            end=False
        )
        
        # Serializar a JSON
        json_str = response.model_dump_json()
        json_data = json.loads(json_str)
        
        # Verificar que el Enum se serializa como su valor
        assert json_data["next_action"] == action.value
        
        print(f"✅ {action.name} → {action.value}")


if __name__ == "__main__":
    # Ejecutar tests básicos
    import asyncio
    
    async def run_tests():
        print("🧪 Ejecutando tests de serialización...")
        await test_orchestrator_response_serialization()
        await test_all_next_action_values_serialize()
        print("🎉 Todos los tests pasaron!")
    
    asyncio.run(run_tests())
