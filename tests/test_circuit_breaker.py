# tests/test_circuit_breaker.py
"""
Tests para Circuit Breaker - Transiciones de estado críticas
"""

import pytest
import time
from services.tool_broker import CircuitBreaker, CircuitBreakerState


class TestCircuitBreaker:
    """Tests para comportamiento del Circuit Breaker"""
    
    def test_cb_closed_to_open_transition(self):
        """Test: CLOSED → OPEN en N fallos"""
        cb = CircuitBreaker(failure_threshold=3, window_seconds=60, cooldown_seconds=30)
        ws, tool = "workspace1", "get_services"
        
        # Estado inicial: CLOSED
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is False
        assert reason == ""
        
        # 2 fallos → sigue CLOSED
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is False
        
        # 3º fallo → OPEN
        cb.record_failure(ws, tool)
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is True
        assert "Circuit breaker OPEN" in reason
        assert "30s" in reason  # Menciona cooldown
    
    def test_cb_open_to_half_open_after_cooldown(self):
        """Test: OPEN → HALF_OPEN después del cooldown"""
        cb = CircuitBreaker(failure_threshold=2, window_seconds=60, cooldown_seconds=0)  # Sin cooldown
        ws, tool = "workspace1", "get_services"
        
        # Provocar OPEN
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is True
        
        # Con cooldown=0, inmediatamente pasa a HALF_OPEN
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is False  # HALF_OPEN permite requests
    
    def test_cb_half_open_success_to_closed(self):
        """Test: HALF_OPEN + éxito → CLOSED"""
        cb = CircuitBreaker(failure_threshold=2, window_seconds=60, cooldown_seconds=0, half_open_max_calls=1)
        ws, tool = "workspace1", "get_services"
        
        # Provocar OPEN → HALF_OPEN
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        cb.is_open(ws, tool)  # Transición a HALF_OPEN
        
        # Éxito en HALF_OPEN → CLOSED
        cb.record_success(ws, tool)
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is False
        assert reason == ""
    
    def test_cb_half_open_failure_to_open(self):
        """Test: HALF_OPEN + fallo → vuelve a OPEN"""
        cb = CircuitBreaker(failure_threshold=2, window_seconds=60, cooldown_seconds=0)
        ws, tool = "workspace1", "get_services"
        
        # Provocar OPEN → HALF_OPEN
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        cb.is_open(ws, tool)  # Transición a HALF_OPEN
        
        # Fallo en HALF_OPEN → vuelve a OPEN
        cb.record_failure(ws, tool)
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is True
        assert "Circuit breaker OPEN" in reason
    
    def test_cb_half_open_max_calls_limit(self):
        """Test: HALF_OPEN respeta max_calls"""
        cb = CircuitBreaker(failure_threshold=2, window_seconds=60, cooldown_seconds=0, half_open_max_calls=1)
        ws, tool = "workspace1", "get_services"
        
        # Provocar OPEN → HALF_OPEN
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        
        # Primera consulta en HALF_OPEN → permite
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is False
        
        # Segunda consulta → bloquea (max_calls=1)
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is True
        assert "max 1 test calls" in reason
    
    def test_cb_sliding_window_old_failures_ignored(self):
        """Test: Fallos fuera de la ventana se ignoran"""
        cb = CircuitBreaker(failure_threshold=3, window_seconds=1)  # Ventana de 1 segundo
        ws, tool = "workspace1", "get_services"
        
        # 2 fallos
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        
        # Esperar que pasen fuera de la ventana
        time.sleep(1.1)
        
        # Nuevo fallo → debería ser solo 1 en la ventana actual
        cb.record_failure(ws, tool)
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is False  # No alcanza el threshold de 3
    
    def test_cb_workspace_tool_isolation(self):
        """Test: CB aislado por (workspace_id, tool)"""
        cb = CircuitBreaker(failure_threshold=2, window_seconds=60, cooldown_seconds=0)
        
        # Workspace1 tool1 → OPEN
        cb.record_failure("ws1", "tool1")
        cb.record_failure("ws1", "tool1")
        is_open, _ = cb.is_open("ws1", "tool1")
        assert is_open is True
        
        # Workspace1 tool2 → sigue CLOSED
        is_open, _ = cb.is_open("ws1", "tool2")
        assert is_open is False
        
        # Workspace2 tool1 → sigue CLOSED
        is_open, _ = cb.is_open("ws2", "tool1")
        assert is_open is False
    
    def test_cb_force_half_open_admin_function(self):
        """Test: force_half_open para testing/admin"""
        cb = CircuitBreaker(failure_threshold=2, window_seconds=60, cooldown_seconds=30)
        ws, tool = "workspace1", "get_services"
        
        # Provocar OPEN
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is True
        
        # Forzar HALF_OPEN (sin esperar cooldown)
        cb.force_half_open(ws, tool)
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is False  # Permite request de test
    
    def test_cb_success_in_closed_prunes_old_failures(self):
        """Test: Éxito en CLOSED limpia fallos viejos"""
        cb = CircuitBreaker(failure_threshold=3, window_seconds=1)
        ws, tool = "workspace1", "get_services"
        
        # 2 fallos
        cb.record_failure(ws, tool)
        cb.record_failure(ws, tool)
        
        # Esperar que salgan de la ventana
        time.sleep(1.1)
        
        # Éxito → debería limpiar fallos viejos
        cb.record_success(ws, tool)
        
        # Verificar que los fallos se limpiaron
        # (esto es interno, pero podemos verificar que no se abre con 1 fallo nuevo)
        cb.record_failure(ws, tool)
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is False  # Solo 1 fallo en ventana actual
    
    def test_cb_multiple_rapid_failures(self):
        """Test: Múltiples fallos rápidos"""
        cb = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=0)
        ws, tool = "workspace1", "batch_process"
        
        # 10 fallos rápidos
        for i in range(10):
            cb.record_failure(ws, tool)
        
        # Debería estar OPEN
        is_open, reason = cb.is_open(ws, tool)
        assert is_open is True
        assert "10 failures" in reason
    
    def test_cb_recovery_scenario(self):
        """Test: Escenario completo de recovery"""
        cb = CircuitBreaker(failure_threshold=3, window_seconds=60, cooldown_seconds=0, half_open_max_calls=2)
        ws, tool = "workspace1", "flaky_service"
        
        # 1. Fallos → OPEN
        for _ in range(3):
            cb.record_failure(ws, tool)
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is True
        
        # 2. OPEN → HALF_OPEN (cooldown=0)
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is False  # Primera call de test
        
        # 3. Fallo en test → vuelve a OPEN
        cb.record_failure(ws, tool)
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is True
        
        # 4. OPEN → HALF_OPEN otra vez
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is False
        
        # 5. Éxito en test → CLOSED
        cb.record_success(ws, tool)
        is_open, _ = cb.is_open(ws, tool)
        assert is_open is False
        
        # 6. Verificar que está realmente CLOSED (permite múltiples calls)
        for _ in range(5):
            is_open, _ = cb.is_open(ws, tool)
            assert is_open is False
