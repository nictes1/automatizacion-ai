# tests/test_tool_broker_http.py
"""
Tests para ToolBroker - Casos HTTP críticos
"""

import pytest
import asyncio
import json
from unittest.mock import patch
from services.tool_broker import ToolBroker, ToolStatus
from tests.conftest import DummySession, TestableToolBroker, assert_tool_observation


class TestToolBrokerHTTP:
    """Tests para ejecución HTTP del ToolBroker"""
    
    @pytest.mark.asyncio
    async def test_429_retry_after_seconds(self):
        """Test: 429 con Retry-After en segundos → respeta la espera"""
        broker = TestableToolBroker(max_retries=1, base_backoff_ms=1)
        
        # 1º intento: 429 con Retry-After: 2; 2º intento: 200 OK
        session = DummySession([
            (429, {"error": "rate limited"}, {"Retry-After": "2"}),
            (200, {"success": True, "data": "ok"}, {})
        ])
        broker.set_test_session(session)
        
        spec = {
            "type": "http",
            "url": "https://api.test.com/endpoint",
            "method": "GET"
        }
        
        obs = await broker.execute(
            tool="get_test",
            args={"q": "test"},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "success", "get_test")
        assert obs.attempt == 2  # Hubo reintento
        assert obs.result["success"] is True
    
    @pytest.mark.asyncio
    async def test_429_retry_after_date(self, make_retry_after_date):
        """Test: 429 con Retry-After en fecha RFC-7231 → respeta la espera"""
        broker = TestableToolBroker(max_retries=1, base_backoff_ms=1)
        
        # Fecha 1 segundo en el futuro
        retry_date = make_retry_after_date(1)
        session = DummySession([
            (429, {"error": "rate limited"}, {"Retry-After": retry_date}),
            (200, {"success": True, "data": "ok"}, {})
        ])
        broker.set_test_session(session)
        
        spec = {
            "type": "http", 
            "url": "https://api.test.com/endpoint",
            "method": "GET"
        }
        
        obs = await broker.execute(
            tool="get_test",
            args={"q": "test"},
            workspace_id="ws1",
            conversation_id="conv1", 
            request_id="req2",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "success", "get_test")
        assert obs.attempt == 2
    
    @pytest.mark.asyncio
    async def test_408_timeout_retry(self):
        """Test: 408 timeout → reintenta con backoff"""
        broker = TestableToolBroker(max_retries=2, base_backoff_ms=1)
        
        session = DummySession([
            (408, {"error": "timeout"}, {}),
            (408, {"error": "timeout"}, {}),
            (200, {"success": True}, {})
        ])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/endpoint", "method": "GET"}
        
        obs = await broker.execute(
            tool="get_test",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req3", 
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "success", "get_test")
        assert obs.attempt == 3
    
    @pytest.mark.asyncio
    async def test_5xx_retry_4xx_no_retry(self):
        """Test: 5xx → retry; 4xx (≠429) → no retry (lógico)"""
        broker = TestableToolBroker(max_retries=2, base_backoff_ms=1)
        
        # Test 5xx → retry
        session = DummySession([
            (500, {"error": "server error"}, {}),
            (200, {"success": True}, {})
        ])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/endpoint", "method": "GET"}
        
        obs = await broker.execute(
            tool="get_test",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req4",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "success", "get_test")
        assert obs.attempt == 2
        
        # Test 4xx → no retry
        broker2 = TestableToolBroker(max_retries=5, base_backoff_ms=1)
        session2 = DummySession([
            (400, {"error": "bad request"}, {})
        ])
        broker2.set_test_session(session2)
        
        obs2 = await broker2.execute(
            tool="get_test",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req5",
            tool_spec=spec
        )
        
        assert_tool_observation(obs2, "failure", "get_test")
        assert obs2.attempt == 1  # Sin reintentos
        assert obs2.status_code == 400
    
    @pytest.mark.asyncio
    async def test_post_non_idempotent_no_retry(self):
        """Test: POST con retry_safe=False → no retry"""
        broker = TestableToolBroker(max_retries=5, base_backoff_ms=1)
        
        session = DummySession([
            (500, {"error": "server boom"}, {})
        ])
        broker.set_test_session(session)
        
        spec = {
            "type": "http",
            "url": "https://api.test.com/payment",
            "method": "POST",
            "retry_safe": False
        }
        
        obs = await broker.execute(
            tool="charge_payment",
            args={"amount": 100},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req6",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "failure", "charge_payment")
        assert obs.attempt == 1  # Sin reintentos por ser no-idempotente
        assert obs.status_code == 500
    
    @pytest.mark.asyncio
    async def test_idempotency_duplicate(self):
        """Test: mismo request_id → DUPLICATE desde cache"""
        broker = TestableToolBroker(max_retries=0)
        
        session = DummySession([
            (200, {"success": True, "data": "first"}, {}),
            (200, {"success": True, "data": "second"}, {})  # No debería usarse
        ])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/endpoint", "method": "GET"}
        
        # Primera ejecución
        obs1 = await broker.execute(
            tool="get_test",
            args={"q": "test"},
            workspace_id="ws1",
            conversation_id="conv1", 
            request_id="SAME_ID",
            tool_spec=spec
        )
        
        assert_tool_observation(obs1, "success", "get_test")
        assert obs1.from_cache is False
        assert obs1.result["data"] == "first"
        
        # Segunda con mismo request_id → duplicate desde cache
        obs2 = await broker.execute(
            tool="get_test",
            args={"q": "test"},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="SAME_ID",  # Mismo ID
            tool_spec=spec
        )
        
        assert_tool_observation(obs2, "duplicate", "get_test")
        assert obs2.from_cache is True
        # El resultado viene del cache, no del segundo request
        assert obs2.result["data"] == "first"
    
    @pytest.mark.asyncio
    async def test_request_body_too_large(self):
        """Test: request body > max_body_mb → 413"""
        broker = TestableToolBroker(max_retries=0, max_body_mb=0)  # Fuerza 0MB
        
        # No necesitamos session porque debería fallar antes de hacer request
        session = DummySession([])
        broker.set_test_session(session)
        
        # Args que generan JSON > 0MB
        big_args = {"data": "x" * (1024 * 1024)}  # ~1MB de datos
        
        spec = {
            "type": "http",
            "url": "https://api.test.com/endpoint", 
            "method": "POST"
        }
        
        obs = await broker.execute(
            tool="big_upload",
            args=big_args,
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req7",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "failure", "big_upload")
        assert obs.status_code == 413
        assert "too large" in obs.error.lower()
    
    @pytest.mark.asyncio
    async def test_response_content_length_too_large(self):
        """Test: response Content-Length > max_body_mb → 413"""
        broker = TestableToolBroker(max_retries=0, max_body_mb=1)  # 1MB límite
        
        # Response con Content-Length de 2MB
        large_content_length = str(2 * 1024 * 1024)
        session = DummySession([
            (200, {"data": "ok"}, {"Content-Length": large_content_length})
        ])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/endpoint", "method": "GET"}
        
        obs = await broker.execute(
            tool="get_large",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req8",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "failure", "get_large")
        assert obs.status_code == 413
        assert "too large" in obs.error.lower()
    
    @pytest.mark.asyncio
    async def test_headers_enrichment(self):
        """Test: headers estándar + autenticación declarativa"""
        broker = TestableToolBroker(max_retries=0)
        
        # Capturar headers enviados
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
            "method": "POST",
            "auth": {
                "type": "bearer",
                "token": "secret123"
            },
            "headers": {
                "X-Custom": "custom-value"
            }
        }
        
        obs = await broker.execute(
            tool="auth_test",
            args={"data": "test"},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req9",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "success", "auth_test")
        
        # Verificar headers estándar
        assert captured_headers["X-Workspace-Id"] == "ws1"
        assert captured_headers["X-Conversation-Id"] == "conv1"
        assert captured_headers["X-Request-Id"] == "req9"
        assert captured_headers["X-Tool-Name"] == "auth_test"
        assert captured_headers["X-Tool-Retry-Safe"] == "false"  # POST default
        assert captured_headers["User-Agent"] == "PulpoAI-ToolBroker/1.0"
        assert captured_headers["Content-Type"] == "application/json"
        
        # Verificar autenticación
        assert captured_headers["Authorization"] == "Bearer secret123"
        
        # Verificar header custom
        assert captured_headers["X-Custom"] == "custom-value"
    
    @pytest.mark.asyncio
    async def test_non_json_response(self):
        """Test: response no-JSON → maneja como texto"""
        broker = TestableToolBroker(max_retries=0)
        
        class TextResponse(DummySession):
            async def request(self, method, url, **kwargs):
                class TextResp:
                    def __init__(self):
                        self.status = 200
                        self.headers = {}
                    
                    async def json(self):
                        raise ValueError("Not JSON")
                    
                    async def text(self):
                        return "Plain text response"
                    
                    def get_encoding(self):
                        return "utf-8"
                
                class TextCtx:
                    def __init__(self):
                        self.resp = TextResp()
                    async def __aenter__(self):
                        return self.resp
                    async def __aexit__(self, *args):
                        return False
                
                return TextCtx()
        
        session = TextResponse([])
        broker.set_test_session(session)
        
        spec = {"type": "http", "url": "https://api.test.com/text", "method": "GET"}
        
        obs = await broker.execute(
            tool="get_text",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req10",
            tool_spec=spec
        )
        
        assert_tool_observation(obs, "success", "get_text")
        assert obs.result["_raw"] == "Plain text response"
