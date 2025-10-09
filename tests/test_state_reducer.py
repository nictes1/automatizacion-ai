# tests/test_state_reducer.py
"""
Tests para StateReducer - Aplicación de observaciones al estado
"""

import pytest
from services.state_reducer import StateReducer, ConversationStatePatch, StateChangeType
from services.tool_broker import ToolObservation, ToolStatus
from tests.conftest import assert_no_mutation
import time


class TestStateReducer:
    """Tests para StateReducer"""
    
    def test_reducer_success_book_appointment(self):
        """Test: SUCCESS para book_appointment extrae slots relevantes"""
        reducer = StateReducer()
        
        current_state = {
            "client_name": "Juan",
            "service_type": "Corte"
        }
        
        observation = ToolObservation(
            tool="book_appointment",
            args={"client_name": "Juan", "service_type": "Corte"},
            status=ToolStatus.SUCCESS,
            result={
                "booking_id": "B123",
                "confirmation_code": "CONF456", 
                "appointment_date": "2025-10-10",
                "appointment_time": "15:00"
            },
            execution_time_ms=250,
            timestamp=time.time()
        )
        
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        conversation_id = "conv1"
        
        patch = reducer.apply_observation(observation, current_state, workspace_config, conversation_id)
        
        # Verificar slots extraídos
        assert patch.slots_patch["booking_id"] == "B123"
        assert patch.slots_patch["confirmation_code"] == "CONF456"
        assert patch.slots_patch["confirmed_date"] == "2025-10-10"
        assert patch.slots_patch["confirmed_time"] == "15:00"
        
        # Verificar flags de éxito
        assert patch.slots_patch["_tool_book_appointment_success"] is True
        assert "_tool_book_appointment_last_run" in patch.slots_patch
        
        # Verificar metadata
        assert StateChangeType.TOOL_SUCCESS.value in [r for r in patch.change_reasons if "book_appointment executed successfully" in r]
        assert patch.confidence_score == 1.0
        assert len(patch.last_k_observations) == 1
    
    def test_reducer_success_get_services(self):
        """Test: SUCCESS para get_services extrae lista de servicios"""
        reducer = StateReducer()
        
        observation = ToolObservation(
            tool="get_services",
            args={"workspace_id": "ws1"},
            status=ToolStatus.SUCCESS,
            result={
                "services": [
                    {"name": "Corte de Cabello", "price": 25, "duration": 30},
                    {"name": "Color", "price": 50, "duration": 60},
                    {"name": "Brushing", "price": 20, "duration": 20}
                ]
            },
            execution_time_ms=150,
            timestamp=time.time()
        )
        
        current_state = {}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        patch = reducer.apply_observation(observation, current_state, workspace_config, "conv1")
        
        # Verificar servicios extraídos
        expected_services = ["Corte de Cabello", "Color", "Brushing"]
        assert patch.slots_patch["_available_services"] == expected_services
        
        # Verificar precios extraídos
        expected_prices = {
            "Corte de Cabello": 25,
            "Color": 50,
            "Brushing": 20
        }
        assert patch.slots_patch["_service_prices"] == expected_prices
        
        # Verificar cache invalidation
        assert "services_cache" in patch.cache_invalidation_keys
    
    def test_reducer_success_get_availability(self):
        """Test: SUCCESS para get_availability extrae horarios disponibles"""
        reducer = StateReducer()
        
        observation = ToolObservation(
            tool="get_availability",
            args={"service_type": "Corte", "date": "2025-10-10"},
            status=ToolStatus.SUCCESS,
            result={
                "available_slots": ["10:00", "11:00", "14:00", "15:00"],
                "next_available": "2025-10-10 10:00"
            },
            execution_time_ms=200,
            timestamp=time.time()
        )
        
        current_state = {"service_type": "Corte"}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        patch = reducer.apply_observation(observation, current_state, workspace_config, "conv1")
        
        # Verificar slots de disponibilidad
        assert patch.slots_patch["_available_times"] == ["10:00", "11:00", "14:00", "15:00"]
        assert patch.slots_patch["_next_available"] == "2025-10-10 10:00"
        
        # Verificar cache invalidation
        assert "availability_cache" in patch.cache_invalidation_keys
    
    def test_reducer_failure_propagation(self):
        """Test: FAILURE propaga error al estado"""
        reducer = StateReducer()
        
        observation = ToolObservation(
            tool="book_appointment",
            args={"client_name": "Juan"},
            status=ToolStatus.FAILURE,
            error="Missing required field: service_type",
            execution_time_ms=50,
            timestamp=time.time()
        )
        
        current_state = {"client_name": "Juan"}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        patch = reducer.apply_observation(observation, current_state, workspace_config, "conv1")
        
        # Verificar flags de error
        assert patch.slots_patch["_tool_book_appointment_success"] is False
        assert patch.slots_patch["_tool_book_appointment_error"] == "Missing required field: service_type"
        
        # Verificar validation_errors para tool crítico
        expected_error = "Error ejecutando book_appointment: Missing required field: service_type"
        assert patch.slots_patch["_validation_errors"] == [expected_error]
        
        # Verificar confianza reducida
        assert patch.confidence_score < 1.0
    
    def test_reducer_circuit_open(self):
        """Test: CIRCUIT_OPEN agrega mensaje informativo"""
        reducer = StateReducer()
        
        observation = ToolObservation(
            tool="get_services",
            args={"workspace_id": "ws1"},
            status=ToolStatus.CIRCUIT_OPEN,
            error="Circuit breaker OPEN (5 failures in 60s)",
            execution_time_ms=0,
            circuit_breaker_tripped=True,
            timestamp=time.time()
        )
        
        current_state = {}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        patch = reducer.apply_observation(observation, current_state, workspace_config, "conv1")
        
        # Verificar flags de circuit breaker
        assert patch.slots_patch["_tool_get_services_circuit_open"] is True
        
        # Verificar mensaje informativo
        expected_msg = "Servicio get_services temporalmente no disponible"
        assert patch.slots_patch["_validation_errors"] == [expected_msg]
    
    def test_reducer_duplicate_no_changes(self):
        """Test: DUPLICATE no hace cambios, solo logging"""
        reducer = StateReducer()
        
        observation = ToolObservation(
            tool="get_services",
            args={"workspace_id": "ws1"},
            status=ToolStatus.DUPLICATE,
            from_cache=True,
            timestamp=time.time()
        )
        
        current_state = {"existing": "data"}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        patch = reducer.apply_observation(observation, current_state, workspace_config, "conv1")
        
        # No debería haber cambios en slots
        assert len(patch.slots_patch) == 0
        assert len(patch.slots_to_remove) == 0
        
        # Solo razón de cambio
        assert any("Duplicate call" in reason for reason in patch.change_reasons)
    
    def test_reducer_multiple_observations_batch(self):
        """Test: Aplicar múltiples observaciones en batch"""
        reducer = StateReducer()
        
        obs1 = ToolObservation(
            tool="get_services",
            args={"workspace_id": "ws1"},
            status=ToolStatus.SUCCESS,
            result={"services": [{"name": "Corte", "price": 25}]},
            timestamp=time.time()
        )
        
        obs2 = ToolObservation(
            tool="get_availability",
            args={"service_type": "Corte", "date": "2025-10-10"},
            status=ToolStatus.SUCCESS,
            result={"available_slots": ["10:00", "11:00"]},
            timestamp=time.time()
        )
        
        current_state = {}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        patch = reducer.apply_multiple_observations(
            [obs1, obs2], current_state, workspace_config, "conv1"
        )
        
        # Verificar que se aplicaron ambas observaciones
        assert patch.slots_patch["_available_services"] == ["Corte"]
        assert patch.slots_patch["_available_times"] == ["10:00", "11:00"]
        assert patch.slots_patch["_service_prices"] == {"Corte": 25}
        
        # Verificar flags de ambos tools
        assert patch.slots_patch["_tool_get_services_success"] is True
        assert patch.slots_patch["_tool_get_availability_success"] is True
        
        # Verificar historial
        assert len(patch.last_k_observations) == 2
    
    def test_reducer_lru_history_maintenance(self):
        """Test: Historial LRU mantiene solo K observaciones"""
        reducer = StateReducer(max_observations=3)  # Límite de 3
        
        current_state = {}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        conversation_id = "conv1"
        
        # Agregar 5 observaciones
        for i in range(5):
            obs = ToolObservation(
                tool=f"tool_{i}",
                args={},
                status=ToolStatus.SUCCESS,
                result={"data": i},
                timestamp=time.time()
            )
            reducer.apply_observation(obs, current_state, workspace_config, conversation_id)
        
        # Verificar que solo mantiene las últimas 3
        history = reducer._get_history(conversation_id)
        assert len(history) == 3
        
        # Verificar que son las más recientes (tool_2, tool_3, tool_4)
        tools = [obs.tool for obs in history]
        assert tools == ["tool_2", "tool_3", "tool_4"]
    
    def test_reducer_observation_context_generation(self):
        """Test: Generación de contexto para LLM"""
        reducer = StateReducer()
        
        # Agregar algunas observaciones
        observations = [
            ToolObservation(
                tool="get_services",
                status=ToolStatus.SUCCESS,
                result={"services": [{"name": "Corte"}]},
                timestamp=time.time()
            ),
            ToolObservation(
                tool="book_appointment",
                status=ToolStatus.FAILURE,
                error="Missing client_name",
                timestamp=time.time()
            ),
            ToolObservation(
                tool="get_availability",
                status=ToolStatus.RATE_LIMITED,
                timestamp=time.time()
            )
        ]
        
        current_state = {}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        conversation_id = "conv1"
        
        # Aplicar observaciones
        for obs in observations:
            reducer.apply_observation(obs, current_state, workspace_config, conversation_id)
        
        # Generar contexto
        context = reducer.get_observation_context(conversation_id, max_tokens=500)
        
        assert "HERRAMIENTAS EJECUTADAS RECIENTEMENTE:" in context
        assert "✅ get_services:" in context
        assert "❌ book_appointment:" in context
        assert "⏳ get_availability:" in context
    
    def test_reducer_immutability(self):
        """Test: StateReducer no muta el estado original"""
        reducer = StateReducer()
        
        original_state = {"client_name": "Juan", "existing": "data"}
        
        observation = ToolObservation(
            tool="get_services",
            args={},
            status=ToolStatus.SUCCESS,
            result={"services": [{"name": "Corte"}]},
            timestamp=time.time()
        )
        
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        patch = reducer.apply_observation(observation, original_state, workspace_config, "conv1")
        
        # Verificar que el estado original no se mutó
        assert_no_mutation(original_state, {"client_name": "Juan", "existing": "data"})
        assert original_state == {"client_name": "Juan", "existing": "data"}
        
        # Verificar que el patch contiene los cambios
        assert "_available_services" in patch.slots_patch
        assert patch.slots_patch["_available_services"] == ["Corte"]
    
    def test_reducer_confidence_calculation(self):
        """Test: Cálculo de confianza según diferentes escenarios"""
        reducer = StateReducer()
        
        current_state = {}
        workspace_config = {"vertical": "servicios", "workspace_id": "ws1"}
        
        # Éxito → confianza alta
        success_obs = ToolObservation(
            tool="get_services",
            status=ToolStatus.SUCCESS,
            result={"services": []},
            execution_time_ms=100,
            timestamp=time.time()
        )
        patch = reducer.apply_observation(success_obs, current_state, workspace_config, "conv1")
        assert patch.confidence_score == 1.0
        
        # Fallo → confianza baja
        failure_obs = ToolObservation(
            tool="get_services",
            status=ToolStatus.FAILURE,
            error="Error",
            timestamp=time.time()
        )
        patch = reducer.apply_observation(failure_obs, current_state, workspace_config, "conv1")
        assert patch.confidence_score < 1.0
        
        # Timeout muy alto → confianza reducida
        slow_obs = ToolObservation(
            tool="get_services",
            status=ToolStatus.SUCCESS,
            result={"services": []},
            execution_time_ms=15000,  # 15s
            timestamp=time.time()
        )
        patch = reducer.apply_observation(slow_obs, current_state, workspace_config, "conv1")
        assert patch.confidence_score < 1.0
