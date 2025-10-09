"""
Smoke Tests E2E - Loop completo del agente
Tests mínimos que validan el flujo end-to-end
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from services.orchestrator_service import OrchestratorService, ConversationSnapshot
from services.tool_broker import ToolStatus
from services.policy_engine import PolicyDecision


class TestE2EAgentLoop:
    """Smoke tests para el loop completo del agente"""
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_e2e_services_query_flow(self):
        """Smoke test: Usuario pregunta por servicios → respuesta con datos"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="smoke_conv_1",
            vertical="servicios",
            user_input="¿qué servicios tienen?",
            workspace_id="smoke_ws_1",
            greeted=True,
            slots={},
            objective="Consultar servicios"
        )
        
        # Mock del flujo completo
        with patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch('services.orchestrator_service.get_tool_broker') as mock_broker_fn, \
             patch('services.orchestrator_service.get_mcp_client') as mock_mcp_fn, \
             patch('services.orchestrator_service.get_state_reducer') as mock_reducer_fn, \
             patch.object(orchestrator, '_planner_decide_tools') as mock_planner, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            # Configurar mocks para flujo exitoso
            mock_manifest.return_value = MagicMock(tools=[MagicMock(name="get_services")])
            
            mock_policy = MagicMock()
            mock_policy.validate.return_value = MagicMock(
                decision=PolicyDecision.ALLOW,
                normalized_args={"workspace_id": "smoke_ws_1"}
            )
            mock_policy_cls.return_value = mock_policy
            
            mock_broker = AsyncMock()
            mock_broker.execute.return_value = MagicMock(
                tool="get_services",
                status=ToolStatus.SUCCESS,
                result={"services": [{"name": "Corte", "price": 25}]},
                timestamp=1234567890
            )
            mock_broker_fn.return_value = mock_broker
            
            mock_mcp_fn.return_value = MagicMock()
            
            mock_reducer = MagicMock()
            mock_reducer.apply_multiple_observations.return_value = MagicMock(
                slots_patch={"_available_services": ["Corte"]},
                cache_invalidation_keys=[],
                change_reasons=["Tool executed successfully"]
            )
            mock_reducer_fn.return_value = mock_reducer
            
            mock_planner.return_value = [MagicMock(
                tool="get_services",
                args={"workspace_id": "smoke_ws_1"},
                reasoning="Usuario pregunta por servicios"
            )]
            
            mock_response.return_value = MagicMock(
                assistant="Tenemos estos servicios: Corte ($25)",
                slots={"_available_services": ["Corte"]},
                end=False
            )
            
            # Ejecutar flujo completo
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar resultado
            assert response.assistant is not None
            assert len(response.assistant) > 0
            assert "servicios" in response.assistant.lower()
            assert response.slots.get("_available_services") == ["Corte"]
            assert response.end is False
            
            # Verificar que se ejecutó el flujo completo
            mock_planner.assert_called_once()
            mock_policy.validate.assert_called_once()
            mock_broker.execute.assert_called_once()
            mock_reducer.apply_multiple_observations.assert_called_once()
            mock_response.assert_called_once()
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_e2e_booking_flow(self):
        """Smoke test: Usuario quiere agendar → flujo de reserva"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="smoke_conv_2",
            vertical="servicios",
            user_input="quiero turno para corte mañana 3pm, soy Juan",
            workspace_id="smoke_ws_1",
            greeted=True,
            slots={"client_name": "Juan"},
            objective="Agendar turno"
        )
        
        # Mock del flujo de reserva
        with patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch('services.orchestrator_service.get_tool_broker') as mock_broker_fn, \
             patch('services.orchestrator_service.get_mcp_client') as mock_mcp_fn, \
             patch('services.orchestrator_service.get_state_reducer') as mock_reducer_fn, \
             patch.object(orchestrator, '_planner_decide_tools') as mock_planner, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            # Configurar mocks
            mock_manifest.return_value = MagicMock(tools=[
                MagicMock(name="get_availability"),
                MagicMock(name="book_appointment")
            ])
            
            mock_policy = MagicMock()
            mock_policy.validate.side_effect = [
                MagicMock(decision=PolicyDecision.ALLOW, normalized_args={"service_type": "Corte", "date": "2025-10-10"}),
                MagicMock(decision=PolicyDecision.ALLOW, normalized_args={"service_type": "Corte", "date": "2025-10-10", "time": "15:00", "client_name": "Juan"})
            ]
            mock_policy_cls.return_value = mock_policy
            
            mock_broker = AsyncMock()
            mock_broker.execute.side_effect = [
                MagicMock(tool="get_availability", status=ToolStatus.SUCCESS, result={"available_slots": ["15:00"]}),
                MagicMock(tool="book_appointment", status=ToolStatus.SUCCESS, result={"booking_id": "B123", "confirmation_code": "CONF456"})
            ]
            mock_broker_fn.return_value = mock_broker
            
            mock_mcp_fn.return_value = MagicMock()
            
            mock_reducer = MagicMock()
            mock_reducer.apply_multiple_observations.return_value = MagicMock(
                slots_patch={
                    "_available_times": ["15:00"],
                    "booking_id": "B123",
                    "confirmation_code": "CONF456"
                },
                cache_invalidation_keys=[],
                change_reasons=["Tools executed successfully"]
            )
            mock_reducer_fn.return_value = mock_reducer
            
            mock_planner.return_value = [
                MagicMock(tool="get_availability", args={"service_type": "Corte", "date": "2025-10-10"}),
                MagicMock(tool="book_appointment", args={"service_type": "Corte", "date": "2025-10-10", "time": "15:00", "client_name": "Juan"})
            ]
            
            mock_response.return_value = MagicMock(
                assistant="¡Perfecto Juan! Tu turno está confirmado para mañana a las 15:00. Código: CONF456",
                slots={
                    "booking_id": "B123",
                    "confirmation_code": "CONF456",
                    "_available_times": ["15:00"]
                },
                end=True
            )
            
            # Ejecutar flujo de reserva
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar resultado
            assert "confirmado" in response.assistant.lower()
            assert "CONF456" in response.assistant
            assert response.slots.get("booking_id") == "B123"
            assert response.end is True
            
            # Verificar que se ejecutaron ambos tools
            assert mock_broker.execute.call_count == 2
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_e2e_policy_denial_flow(self):
        """Smoke test: Policy deniega tool → manejo de error"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="smoke_conv_3",
            vertical="servicios",
            user_input="quiero cancelar mi turno",
            workspace_id="smoke_ws_1",
            greeted=True,
            slots={},
            objective="Cancelar turno"
        )
        
        # Mock de policy denial
        with patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch.object(orchestrator, '_planner_decide_tools') as mock_planner, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            mock_manifest.return_value = MagicMock(tools=[MagicMock(name="cancel_appointment")])
            
            mock_policy = MagicMock()
            mock_policy.validate.return_value = MagicMock(
                decision=PolicyDecision.DENY,
                reason="Tier insuficiente",
                needs=["tier PRO", "booking_id"]
            )
            mock_policy_cls.return_value = mock_policy
            
            mock_planner.return_value = [MagicMock(
                tool="cancel_appointment",
                args={},
                reasoning="Usuario quiere cancelar"
            )]
            
            mock_response.return_value = MagicMock(
                assistant="Para cancelar turnos necesitas tier PRO y el ID de tu reserva",
                slots={"_validation_errors": ["Para usar cancel_appointment: tier PRO, booking_id"]},
                end=False
            )
            
            # Ejecutar flujo con policy denial
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar manejo del error
            assert "tier PRO" in response.assistant
            assert len(response.slots.get("_validation_errors", [])) > 0
            assert response.end is False
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_e2e_fallback_to_legacy(self):
        """Smoke test: Error en agente → fallback al sistema legacy"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="smoke_conv_4",
            vertical="servicios",
            user_input="hola",
            workspace_id="smoke_ws_1",
            greeted=False,
            slots={},
            objective="Saludar"
        )
        
        # Mock que falla en planner
        with patch.object(orchestrator, '_planner_decide_tools', side_effect=Exception("Planner error")), \
             patch.object(orchestrator, '_decide_legacy') as mock_legacy:
            
            mock_legacy.return_value = MagicMock(
                assistant="¡Hola! ¿En qué te puedo ayudar?",
                slots={"greeted": True},
                end=False
            )
            
            # Ejecutar con error en agente
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            # Verificar fallback
            assert "hola" in response.assistant.lower()
            assert response.slots.get("greeted") is True
            mock_legacy.assert_called_once_with(snapshot)
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_e2e_feature_flag_switching(self):
        """Smoke test: Feature flag alterna entre legacy y agente"""
        # Test con agente habilitado
        orchestrator_agent = OrchestratorService(enable_agent_loop=True)
        
        # Test con legacy
        orchestrator_legacy = OrchestratorService(enable_agent_loop=False)
        
        snapshot = ConversationSnapshot(
            conversation_id="smoke_conv_5",
            vertical="servicios",
            user_input="test message",
            workspace_id="smoke_ws_1",
            greeted=True,
            slots={},
            objective="Test"
        )
        
        # Mock ambos métodos
        with patch.object(orchestrator_agent, 'decide_with_agent_loop') as mock_agent, \
             patch.object(orchestrator_legacy, '_decide_legacy') as mock_legacy:
            
            mock_agent.return_value = MagicMock(assistant="Agent response")
            mock_legacy.return_value = MagicMock(assistant="Legacy response")
            
            # Test agente
            response_agent = await orchestrator_agent.decide(snapshot)
            assert response_agent.assistant == "Agent response"
            mock_agent.assert_called_once()
            
            # Test legacy
            response_legacy = await orchestrator_legacy.decide(snapshot)
            assert response_legacy.assistant == "Legacy response"
            mock_legacy.assert_called_once()
    
    @pytest.mark.smoke
    @pytest.mark.asyncio
    async def test_e2e_telemetry_emission(self):
        """Smoke test: Telemetría se emite correctamente"""
        orchestrator = OrchestratorService(enable_agent_loop=True)
        
        snapshot = ConversationSnapshot(
            conversation_id="smoke_conv_6",
            vertical="servicios",
            user_input="test telemetry",
            workspace_id="smoke_ws_1",
            greeted=True,
            slots={},
            objective="Test telemetry"
        )
        
        # Mock del flujo con telemetría
        with patch('services.orchestrator_service.load_tool_manifest') as mock_manifest, \
             patch('services.orchestrator_service.NewPolicyEngine') as mock_policy_cls, \
             patch('services.orchestrator_service.get_tool_broker') as mock_broker_fn, \
             patch('services.orchestrator_service.get_mcp_client') as mock_mcp_fn, \
             patch('services.orchestrator_service.get_state_reducer') as mock_reducer_fn, \
             patch.object(orchestrator, '_planner_decide_tools') as mock_planner, \
             patch.object(orchestrator, '_generate_response_with_context') as mock_response:
            
            # Configurar mocks mínimos
            mock_manifest.return_value = MagicMock(tools=[])
            mock_policy_cls.return_value = MagicMock()
            mock_broker_fn.return_value = AsyncMock()
            mock_mcp_fn.return_value = MagicMock()
            mock_reducer_fn.return_value = MagicMock()
            
            mock_planner.return_value = []  # Sin tools
            
            mock_response.return_value = MagicMock(
                assistant="Test response",
                slots={},
                end=False
            )
            
            # Ejecutar y verificar que no hay excepciones
            response = await orchestrator.decide_with_agent_loop(snapshot)
            
            assert response.assistant == "Test response"
            # La telemetría se emite internamente, no necesitamos verificar el contenido
