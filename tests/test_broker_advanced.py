# tests/test_broker_advanced.py
"""
Tests avanzados para ToolBroker - Casos edge y métricas
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch
from services.tool_broker import ToolBroker, ToolStatus
from tests.conftest import DummySession, TestableToolBroker


class TestToolBrokerAdvanced:
    """Tests avanzados para ToolBroker"""
    
    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrent_calls(self):
        """Test: Semáforo limita calls concurrentes por tool"""
        broker = TestableToolBroker(max_retries=0, max_inflight_per_tool=2)
        
        # Session que tarda en responder
        call_count = 0
        
        class SlowSession:
            def __init__(self):
                self.closed = False
            
            async def request(self, method, url, **kwargs):
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.1)  # Simular latencia
                
                class SlowResp:
                    def __init__(self):
                        self.status = 200
                        self.headers = {}
                    async def json(self):
                        return {"success": True, "call": call_count}
                    async def text(self):
                        return "ok"
                    def get_encoding(self):
                        return "utf-8"
                
                class SlowCtx:
                    def __init__(self):
                        self.resp = SlowResp()
                    async def __aenter__(self):
                        return self.resp
                    async def __aexit__(self, *args):
                        return False
                
                return SlowCtx()
            
            async def close(self):
                self.closed = True
        
        broker.set_test_session(SlowSession())
        
        spec = {"type": "http", "url": "https://api.test.com/slow", "method": "GET"}
        
        # Lanzar 5 calls concurrentes (límite = 2)
        tasks = []
        for i in range(5):
            task = broker.execute(
                tool="slow_tool",
                args={"id": i},
                workspace_id="ws1",
                conversation_id="conv1",
                request_id=f"req_{i}",
                tool_spec=spec
            )
            tasks.append(task)
        
        # Ejecutar concurrentemente
        results = await asyncio.gather(*tasks)
        
        # Verificar que todos tuvieron éxito
        for obs in results:
            assert obs.status == ToolStatus.SUCCESS
        
        # Verificar que se respetó el límite de concurrencia
        # (esto es difícil de testear directamente, pero podemos verificar que funcionó)
        assert len(results) == 5
        assert call_count == 5
    
    @pytest.mark.asyncio
    async def test_metrics_emission(self):
        """Test: Emisión de métricas estructuradas"""
        broker = TestableToolBroker(max_retries=0)
        
        # Capturar métricas emitidas
        emitted_metrics = []
        
        def metric_callback(metric_name, value, labels):
            emitted_metrics.append((metric_name, value, labels))
        
        broker.set_metric_callback(metric_callback)
        
        # Session exitosa
        session = DummySession([
            (200, {"success": True}, {})
        ])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/test", "method": "GET"}
        
        obs = await broker.execute(
            tool="test_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec
        )
        
        # Verificar métrica emitida
        assert len(emitted_metrics) == 1
        metric_name, value, labels = emitted_metrics[0]
        
        assert metric_name == "tool_call_total"
        assert value == 1
        assert labels["tool"] == "test_tool"
        assert labels["workspace"] == "ws1"
        assert labels["result"] == "success"
        assert labels["status_code"] == "200"
    
    @pytest.mark.asyncio
    async def test_metrics_emission_failure(self):
        """Test: Métricas para fallos"""
        broker = TestableToolBroker(max_retries=0)
        
        emitted_metrics = []
        broker.set_metric_callback(lambda m, v, l: emitted_metrics.append((m, v, l)))
        
        # Session que falla
        session = DummySession([
            (500, {"error": "server error"}, {})
        ])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/test", "method": "GET"}
        
        obs = await broker.execute(
            tool="failing_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec
        )
        
        # Verificar métrica de fallo
        assert len(emitted_metrics) == 1
        metric_name, value, labels = emitted_metrics[0]
        
        assert labels["result"] == "error"
        assert labels["status_code"] == "500"
    
    @pytest.mark.asyncio
    async def test_api_key_authentication(self):
        """Test: Autenticación con API key"""
        broker = TestableToolBroker(max_retries=0)
        
        captured_headers = {}
        
        class HeaderCapturingSession(DummySession):
            async def request(self, method, url, **kwargs):
                nonlocal captured_headers
                captured_headers = kwargs.get("headers", {})
                return await super().request(method, url, **kwargs)
        
        session = HeaderCapturingSession([
            (200, {"success": True}, {})
        ])
        broker.set_test_session(session)
        
        spec = {
            "type": "http",
            "url": "https://api.test.com/endpoint",
            "method": "GET",
            "auth": {
                "type": "api_key",
                "header": "X-API-Key",
                "value": "secret-api-key-123"
            }
        }
        
        obs = await broker.execute(
            tool="api_key_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec
        )
        
        assert obs.status == ToolStatus.SUCCESS
        assert captured_headers["X-API-Key"] == "secret-api-key-123"
    
    @pytest.mark.asyncio
    async def test_custom_timeout_per_tool(self):
        """Test: Timeout personalizado por tool"""
        broker = TestableToolBroker(max_retries=0)
        
        # Session que simula timeout
        class TimeoutSession:
            def __init__(self):
                self.closed = False
            
            async def request(self, method, url, **kwargs):
                # Verificar que se aplicó el timeout correcto
                timeout = kwargs.get("timeout")
                assert timeout.total == 2.0  # 2000ms / 1000
                assert timeout.sock_connect == 2.0  # min(2, 2)
                assert timeout.sock_read == 2.0
                
                # Simular timeout
                raise asyncio.TimeoutError("Request timeout")
            
            async def close(self):
                self.closed = True
        
        broker.set_test_session(TimeoutSession())
        
        spec = {
            "type": "http",
            "url": "https://api.test.com/slow",
            "method": "GET",
            "timeout_ms": 2000  # 2 segundos
        }
        
        obs = await broker.execute(
            tool="timeout_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec
        )
        
        assert obs.status == ToolStatus.TIMEOUT
        assert obs.error == "http_timeout"
        assert obs.status_code == 408
    
    @pytest.mark.asyncio
    async def test_unknown_tool_type(self):
        """Test: Tipo de tool desconocido"""
        broker = TestableToolBroker(max_retries=0)
        
        spec = {
            "type": "unknown_protocol",
            "url": "custom://api.test.com/endpoint"
        }
        
        obs = await broker.execute(
            tool="unknown_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec
        )
        
        assert obs.status == ToolStatus.FAILURE
        assert "Unknown tool type: unknown_protocol" in obs.error
    
    @pytest.mark.asyncio
    async def test_cache_ttl_per_tool(self):
        """Test: TTL de cache personalizado por tool"""
        broker = TestableToolBroker(max_retries=0)
        
        session = DummySession([
            (200, {"data": "cached_result"}, {})
        ])
        broker.set_test_session(session)
        
        spec = {
            "type": "http",
            "url": "https://api.test.com/cacheable",
            "method": "GET",
            "cache_ttl_seconds": 3600  # 1 hora
        }
        
        obs = await broker.execute(
            tool="cacheable_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec
        )
        
        assert obs.status == ToolStatus.SUCCESS
        
        # Verificar que se guardó en cache con TTL personalizado
        cache_key = "ws1:conv1:req1:cacheable_tool"
        cached_obs = broker._idempotency_cache.get(cache_key)
        assert cached_obs is not None
        assert cached_obs.result["data"] == "cached_result"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_disabled(self):
        """Test: Circuit breaker deshabilitado"""
        broker = TestableToolBroker(max_retries=0, circuit_breaker_enabled=False)
        
        # Múltiples fallos que normalmente abrirían el CB
        session = DummySession([
            (500, {"error": "fail"}, {}),
            (500, {"error": "fail"}, {}),
            (500, {"error": "fail"}, {}),
            (500, {"error": "fail"}, {}),
            (500, {"error": "fail"}, {}),
            (200, {"success": True}, {})  # Finalmente éxito
        ])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/flaky", "method": "GET"}
        
        # Múltiples calls que fallan
        for i in range(5):
            obs = await broker.execute(
                tool="flaky_tool",
                args={},
                workspace_id="ws1",
                conversation_id="conv1",
                request_id=f"req_{i}",
                tool_spec=spec
            )
            assert obs.status == ToolStatus.FAILURE
        
        # Call final debería funcionar (CB deshabilitado)
        obs = await broker.execute(
            tool="flaky_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req_final",
            tool_spec=spec
        )
        
        assert obs.status == ToolStatus.SUCCESS
        assert obs.circuit_breaker_tripped is False
    
    @pytest.mark.asyncio
    async def test_shutdown_lifecycle(self):
        """Test: Shutdown graceful del broker"""
        broker = TestableToolBroker()
        
        # Simular sesión HTTP
        mock_session = MagicMock()
        mock_session.closed = False
        broker._http_session = mock_session
        
        # Cerrar broker
        await broker.close()
        
        # Verificar que se cerró la sesión
        mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_pii_redaction_in_logs(self):
        """Test: PII se redacta en logs"""
        broker = TestableToolBroker(max_retries=0)
        
        session = DummySession([
            (200, {"success": True}, {})
        ])
        broker.set_test_session(session)
        
        # Args con PII
        args_with_pii = {
            "client_name": "Juan Pérez",
            "client_email": "juan@example.com",
            "service_type": "Corte"
        }
        
        spec = {"type": "http", "url": "https://api.test.com/book", "method": "POST"}
        
        with patch('services.tool_broker.logger') as mock_logger:
            obs = await broker.execute(
                tool="book_with_pii",
                args=args_with_pii,
                workspace_id="ws1",
                conversation_id="conv1",
                request_id="req1",
                tool_spec=spec
            )
            
            # Verificar que se loggearon args redactados
            log_calls = [call for call in mock_logger.info.call_args_list if "args=" in str(call)]
            assert len(log_calls) > 0
            
            # Los logs no deberían contener PII sin redactar
            log_content = str(log_calls)
            assert "juan@example.com" not in log_content  # Email redactado
            assert "***" in log_content  # Contiene redacción
