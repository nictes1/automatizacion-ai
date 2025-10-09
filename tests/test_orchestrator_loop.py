# tests/test_orchestrator_loop.py
"""
Tests para Orchestrator - Loop completo del agente
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from services.orchestrator_service import OrchestratorService, ConversationSnapshot, get_orchestrator_service
from services.policy_engine import PlanAction, PolicyDecision, PolicyResult
from services.tool_broker import ToolObservation, ToolStatus
from services.state_reducer import ConversationStatePatch
from tests.conftest import DummySession, DummyMCPClient
import time


class TestOrchestratorLoop:
    """Tests para el loop completo del agente"""
    
    @pytest.mark.asyncio
    async def test_orchestrator_feature_flag_legacy(self):
        """Test: Feature flag usa sistema legacy"""
        orchestrator = OrchestratorService(enable_agent_loop=False)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1",
            vertical="servicios", 
            user_input="hola",
            workspace_id="ws1",
            greeted=False,
            slots={},
            objective="Ayudar al cliente"
        )
        
        # Mock del método legacy
        with patch.object(orchestrator, '_decide_legacy') as mock_legacy:
            mock_legacy.return_value = MagicMock(assistant="¡Hola!")
            
            response = await orchestrator.decide(snapshot)
            
            # Verificar que se llamó al método legacy
            mock_legacy.assert_called_once_with(snapshot)
            assert response.assistant == "¡Hola!"
    
    @pytest.mark.asyncio
    async def test_orchestrator_feature_flag_agent_loop(self):
        """Test: Feature flag usa nuevo loop de agente"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1",
            vertical="servicios",
            user_input="¿qué servicios tienen?",
            workspace_id="ws1", 
            greeted=True,
            slots={},
            objective="Ayudar al cliente"
        )
        
        # Mock del método de agente
        with patch.object(orchestrator, 'decide_with_agent_loop') as mock_agent:
            mock_agent.return_value = MagicMock(assistant="Tenemos corte, color y brushing")
            
            response = await orchestrator.decide(snapshot)
            
            # Verificar que se llamó al método de agente
            mock_agent.assert_called_once_with(snapshot)
            assert "corte" in response.assistant.lower()
    
    @pytest.mark.asyncio
    async def test_agent_loop_planner_to_response_flow(self):
        """Test: Flujo completo Planner → Policy → Broker → Reducer → Response"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1",
            vertical="servicios",
            user_input="¿qué servicios tienen?",
            workspace_id="ws1",
            greeted=True,
            slots={},
            objective="Consultar servicios"
        )
        
        # Mock de componentes
        mock_plan_actions = [
            PlanAction(
                tool="get_services",
                args={"workspace_id": "ws1"},
                reasoning="Usuario pregunta por servicios"
            )
        ]
        
        mock_policy_result = PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="Tool permitido",
            normalized_args={"workspace_id": "ws1"}
        )
        
        mock_observation = ToolObservation(
            tool="get_services",
            args={"workspace_id": "ws1"},
            status=ToolStatus.SUCCESS,
            result={"services": [{"name": "Corte", "price": 25}]},
            timestamp=time.time()
        )
        
        mock_patch = ConversationStatePatch(
            slots_patch={"_available_services": ["Corte"]},
            slots_to_remove=[],
            cache_invalidation_keys=[],
            change_reasons=["Tool executed successfully"]
        )
        
        # Aplicar mocks
        with patch.object(orchestrator, '_planner_decide_tools', return_value=mock_plan_actions), \
             patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch('services.orchestrator_service.get_tool_broker') as mock_broker_fn, \
             patch('services.orchestrator_service.get_mcp_client') as mock_mcp_fn, \
             patch('services.orchestrator_service.get_state_reducer') as mock_reducer_fn, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            # Configurar mocks
            mock_manifest.return_value = MagicMock(tools=[MagicMock(name="get_services")])
            mock_policy = MagicMock()
            mock_policy.validate.return_value = mock_policy_result
            mock_policy_cls.return_value = mock_policy
            
            mock_broker = AsyncMock()
            mock_broker.execute.return_value = mock_observation
            mock_broker_fn.return_value = mock_broker
            
            mock_mcp_fn.return_value = MagicMock()
            
            mock_reducer = MagicMock()
            mock_reducer.apply_multiple_observations.return_value = mock_patch
            mock_reducer_fn.return_value = mock_reducer
            
            mock_response.return_value = MagicMock(
                assistant="Tenemos estos servicios: Corte ($25)",
                slots={"_available_services": ["Corte"]},
                end=False
            )
            
            # Ejecutar
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar flujo completo
            assert "servicios" in response.assistant.lower()
            assert response.slots["_available_services"] == ["Corte"]
            
            # Verificar llamadas
            mock_policy.validate.assert_called_once()
            mock_broker.execute.assert_called_once()
            mock_reducer.apply_multiple_observations.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agent_loop_policy_denial(self):
        """Test: PolicyEngine deniega tool → agrega validation_errors"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1",
            vertical="servicios",
            user_input="quiero cancelar mi turno",
            workspace_id="ws1",
            greeted=True,
            slots={},
            objective="Cancelar turno"
        )
        
        mock_plan_actions = [
            PlanAction(
                tool="cancel_appointment",
                args={},
                reasoning="Usuario quiere cancelar"
            )
        ]
        
        mock_policy_result = PolicyResult(
            decision=PolicyDecision.DENY,
            reason="Tier insuficiente",
            needs=["tier PRO", "booking_id"],
            why="Necesitas tier PRO para cancelar turnos"
        )
        
        with patch.object(orchestrator, '_planner_decide_tools', return_value=mock_plan_actions), \
             patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            # Configurar mocks
            mock_manifest.return_value = MagicMock(tools=[])
            mock_policy = MagicMock()
            mock_policy.validate.return_value = mock_policy_result
            mock_policy_cls.return_value = mock_policy
            
            mock_response.return_value = MagicMock(
                assistant="Para cancelar turnos necesitas tier PRO",
                slots={"_validation_errors": ["Para usar cancel_appointment: tier PRO, booking_id"]},
                end=False
            )
            
            # Ejecutar
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar que se agregó validation_error
            assert "tier PRO" in response.assistant
            assert len(response.slots["_validation_errors"]) > 0
    
    @pytest.mark.asyncio
    async def test_agent_loop_tool_failure_handling(self):
        """Test: Manejo de fallos de tools"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1", 
            vertical="servicios",
            user_input="¿qué servicios tienen?",
            workspace_id="ws1",
            greeted=True,
            slots={},
            objective="Consultar servicios"
        )
        
        mock_plan_actions = [
            PlanAction(tool="get_services", args={"workspace_id": "ws1"})
        ]
        
        mock_policy_result = PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason="Permitido",
            normalized_args={"workspace_id": "ws1"}
        )
        
        # Tool que falla
        mock_observation = ToolObservation(
            tool="get_services",
            args={"workspace_id": "ws1"},
            status=ToolStatus.FAILURE,
            error="Database connection timeout",
            timestamp=time.time()
        )
        
        mock_patch = ConversationStatePatch(
            slots_patch={
                "_tool_get_services_success": False,
                "_tool_get_services_error": "Database connection timeout"
            },
            slots_to_remove=[],
            cache_invalidation_keys=[],
            change_reasons=["Tool failed"]
        )
        
        with patch.object(orchestrator, '_planner_decide_tools', return_value=mock_plan_actions), \
             patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch('services.orchestrator_service.get_tool_broker') as mock_broker_fn, \
             patch('services.orchestrator_service.get_mcp_client') as mock_mcp_fn, \
             patch('services.orchestrator_service.get_state_reducer') as mock_reducer_fn, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            # Configurar mocks
            mock_manifest.return_value = MagicMock(tools=[MagicMock(name="get_services")])
            mock_policy = MagicMock()
            mock_policy.validate.return_value = mock_policy_result
            mock_policy_cls.return_value = mock_policy
            
            mock_broker = AsyncMock()
            mock_broker.execute.return_value = mock_observation
            mock_broker_fn.return_value = mock_broker
            
            mock_mcp_fn.return_value = MagicMock()
            
            mock_reducer = MagicMock()
            mock_reducer.apply_multiple_observations.return_value = mock_patch
            mock_reducer_fn.return_value = mock_reducer
            
            mock_response.return_value = MagicMock(
                assistant="Disculpá, hay un problema técnico con el servicio",
                slots={"_tool_get_services_error": "Database connection timeout"},
                end=False
            )
            
            # Ejecutar
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar manejo del error
            assert "problema técnico" in response.assistant.lower()
            assert response.slots["_tool_get_services_error"] == "Database connection timeout"
    
    @pytest.mark.asyncio
    async def test_agent_loop_multiple_tools_sequential(self):
        """Test: Múltiples tools ejecutados secuencialmente"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1",
            vertical="servicios", 
            user_input="quiero turno para corte mañana 3pm",
            workspace_id="ws1",
            greeted=True,
            slots={"client_name": "Juan"},
            objective="Agendar turno"
        )
        
        mock_plan_actions = [
            PlanAction(tool="get_availability", args={"service_type": "Corte", "date": "2025-10-10"}),
            PlanAction(tool="book_appointment", args={"service_type": "Corte", "date": "2025-10-10", "time": "15:00"})
        ]
        
        mock_policy_results = [
            PolicyResult(decision=PolicyDecision.ALLOW, reason="OK", normalized_args={"service_type": "Corte", "date": "2025-10-10"}),
            PolicyResult(decision=PolicyDecision.ALLOW, reason="OK", normalized_args={"service_type": "Corte", "date": "2025-10-10", "time": "15:00"})
        ]
        
        mock_observations = [
            ToolObservation(
                tool="get_availability",
                status=ToolStatus.SUCCESS,
                result={"available_slots": ["15:00", "16:00"]},
                timestamp=time.time()
            ),
            ToolObservation(
                tool="book_appointment", 
                status=ToolStatus.SUCCESS,
                result={"booking_id": "B123", "confirmation_code": "CONF456"},
                timestamp=time.time()
            )
        ]
        
        mock_patch = ConversationStatePatch(
            slots_patch={
                "_available_times": ["15:00", "16:00"],
                "booking_id": "B123",
                "confirmation_code": "CONF456"
            },
            slots_to_remove=[],
            cache_invalidation_keys=[],
            change_reasons=["Tools executed successfully"]
        )
        
        with patch.object(orchestrator, '_planner_decide_tools', return_value=mock_plan_actions), \
             patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch('services.orchestrator_service.get_tool_broker') as mock_broker_fn, \
             patch('services.orchestrator_service.get_mcp_client') as mock_mcp_fn, \
             patch('services.orchestrator_service.get_state_reducer') as mock_reducer_fn, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            # Configurar mocks
            mock_manifest.return_value = MagicMock(tools=[
                MagicMock(name="get_availability"),
                MagicMock(name="book_appointment")
            ])
            
            mock_policy = MagicMock()
            mock_policy.validate.side_effect = mock_policy_results
            mock_policy_cls.return_value = mock_policy
            
            mock_broker = AsyncMock()
            mock_broker.execute.side_effect = mock_observations
            mock_broker_fn.return_value = mock_broker
            
            mock_mcp_fn.return_value = MagicMock()
            
            mock_reducer = MagicMock()
            mock_reducer.apply_multiple_observations.return_value = mock_patch
            mock_reducer_fn.return_value = mock_reducer
            
            mock_response.return_value = MagicMock(
                assistant="¡Perfecto! Tu turno está confirmado para mañana a las 15:00. Código: CONF456",
                slots={
                    "booking_id": "B123",
                    "confirmation_code": "CONF456",
                    "_available_times": ["15:00", "16:00"]
                },
                end=True
            )
            
            # Ejecutar
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar ejecución de ambos tools
            assert mock_broker.execute.call_count == 2
            assert "confirmado" in response.assistant.lower()
            assert response.slots["booking_id"] == "B123"
            assert response.end is True
    
    @pytest.mark.asyncio
    async def test_agent_loop_fallback_on_error(self):
        """Test: Fallback al sistema legacy en caso de error"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1",
            vertical="servicios",
            user_input="hola",
            workspace_id="ws1",
            greeted=False,
            slots={},
            objective="Saludar"
        )
        
        # Mock que falla en planner
        with patch.object(orchestrator, '_planner_decide_tools', side_effect=Exception("Planner error")), \
             patch.object(orchestrator, 'decide', wraps=orchestrator.decide) as mock_decide, \
             patch.object(orchestrator, '_decide_legacy') as mock_legacy:
            
            mock_legacy.return_value = MagicMock(assistant="¡Hola! (fallback)")
            
            # Ejecutar
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar fallback
            assert "fallback" in response.assistant
            mock_legacy.assert_called_once_with(snapshot)
    
    def test_get_orchestrator_service_singleton(self):
        """Test: Singleton del orchestrator service"""
        # Primera llamada
        orch1 = get_orchestrator_service(enable_agent_loop=True)
        
        # Segunda llamada debería devolver la misma instancia
        orch2 = get_orchestrator_service(enable_agent_loop=False)  # Flag ignorado
        
        assert orch1 is orch2
        assert orch1.enable_agent_loop is True  # Configuración de la primera llamada
    
    @pytest.mark.asyncio
    async def test_planner_decide_tools_integration(self):
        """Test: Integración del planner con manifest real"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="conv1",
            vertical="servicios",
            user_input="¿qué servicios tienen y cuánto cuestan?",
            workspace_id="ws1",
            greeted=True,
            slots={},
            objective="Consultar servicios y precios"
        )
        
        # Mock del LLM response
        mock_llm_response = [
            {
                "tool": "get_services",
                "args": {"workspace_id": "ws1"},
                "reasoning": "Usuario pregunta por servicios y precios"
            }
        ]
        
        with patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch.object(orchestrator.llm_client, 'generate_json', return_value=mock_llm_response):
            
            # Configurar manifest mock
            mock_tool = MagicMock()
            mock_tool.name = "get_services"
            mock_tool.description = "Obtiene lista de servicios disponibles"
            mock_tool.args_schema = {"properties": {"workspace_id": {"description": "ID del workspace"}}}
            
            mock_manifest.return_value = MagicMock(tools=[mock_tool])
            
            # Ejecutar
            actions = await orchestrator._planner_decide_tools(snapshot)
            
            # Verificar resultado
            assert len(actions) == 1
            assert actions[0].tool == "get_services"
            assert actions[0].args == {"workspace_id": "ws1"}
            assert "servicios y precios" in actions[0].reasoning
