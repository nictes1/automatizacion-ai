# tests/test_tool_broker_mcp.py
"""
Tests para ToolBroker - Casos MCP
"""

import pytest
from services.tool_broker import ToolBroker, ToolStatus
from tests.conftest import DummyMCPClient, TestableToolBroker, assert_tool_observation


class TestToolBrokerMCP:
    """Tests para ejecución MCP del ToolBroker"""
    
    @pytest.mark.asyncio
    async def test_mcp_success_structured_response(self):
        """Test: MCP con respuesta estructurada {"success": true, "data": ...}"""
        broker = TestableToolBroker(max_retries=0)
        
        mcp_client = DummyMCPClient({
            "get_services": {
                "success": True,
                "data": {
                    "services": [
                        {"name": "Corte", "price": 25},
                        {"name": "Color", "price": 50}
                    ]
                }
            }
        })
        
        spec = {"type": "mcp"}
        
        obs = await broker.execute(
            tool="get_services",
            args={"workspace_id": "ws1"},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req1",
            tool_spec=spec,
            mcp_client=mcp_client
        )
        
        assert_tool_observation(obs, "success", "get_services")
        assert obs.status_code is None  # MCP no tiene status codes HTTP
        assert len(obs.result["services"]) == 2
        assert obs.result["services"][0]["name"] == "Corte"
        
        # Verificar que se llamó al MCP client
        assert len(mcp_client.call_history) == 1
        assert mcp_client.call_history[0] == ("get_services", {"workspace_id": "ws1"})
    
    @pytest.mark.asyncio
    async def test_mcp_success_legacy_response(self):
        """Test: MCP con respuesta legacy (sin estructura success/data)"""
        broker = TestableToolBroker(max_retries=0)
        
        mcp_client = DummyMCPClient({
            "get_availability": {
                "available_slots": ["10:00", "11:00", "14:00"],
                "date": "2025-10-10"
            }
        })
        
        spec = {"type": "mcp"}
        
        obs = await broker.execute(
            tool="get_availability",
            args={"date": "2025-10-10"},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req2",
            tool_spec=spec,
            mcp_client=mcp_client
        )
        
        assert_tool_observation(obs, "success", "get_availability")
        assert obs.result["available_slots"] == ["10:00", "11:00", "14:00"]
        assert obs.result["date"] == "2025-10-10"
    
    @pytest.mark.asyncio
    async def test_mcp_structured_failure(self):
        """Test: MCP con respuesta estructurada de error {"success": false, "error": ...}"""
        broker = TestableToolBroker(max_retries=0)
        
        mcp_client = DummyMCPClient({
            "book_appointment": {
                "success": False,
                "error": "No availability for requested time",
                "data": None
            }
        })
        
        spec = {"type": "mcp"}
        
        obs = await broker.execute(
            tool="book_appointment",
            args={"time": "25:00"},  # Hora inválida
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req3",
            tool_spec=spec,
            mcp_client=mcp_client
        )
        
        assert_tool_observation(obs, "failure", "book_appointment")
        assert obs.error == "No availability for requested time"
        assert obs.result == {}  # data era None
    
    @pytest.mark.asyncio
    async def test_mcp_exception_error(self):
        """Test: MCP que lanza excepción"""
        broker = TestableToolBroker(max_retries=0)
        
        mcp_client = DummyMCPClient({
            "failing_tool": RuntimeError("Connection timeout to external service")
        })
        
        spec = {"type": "mcp"}
        
        obs = await broker.execute(
            tool="failing_tool",
            args={"param": "value"},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req4",
            tool_spec=spec,
            mcp_client=mcp_client
        )
        
        assert_tool_observation(obs, "failure", "failing_tool")
        assert "mcp_error" in obs.error
        assert "Connection timeout" in obs.error
    
    @pytest.mark.asyncio
    async def test_mcp_no_client_provided(self):
        """Test: MCP sin cliente → error"""
        broker = TestableToolBroker(max_retries=0)
        
        spec = {"type": "mcp"}
        
        obs = await broker.execute(
            tool="some_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req5",
            tool_spec=spec,
            mcp_client=None  # Sin cliente
        )
        
        assert_tool_observation(obs, "failure", "some_tool")
        assert "MCP client not provided" in obs.error
        assert obs.status_code is None
    
    @pytest.mark.asyncio
    async def test_mcp_retry_safe_behavior(self):
        """Test: MCP con retry_safe=True por defecto"""
        broker = TestableToolBroker(max_retries=2, base_backoff_ms=1)
        
        # Cliente que falla 2 veces, luego éxito
        call_count = 0
        
        class FailingMCPClient:
            async def call_tool(self, tool, args):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    raise RuntimeError(f"Temporary failure {call_count}")
                return {"success": True, "data": {"attempt": call_count}}
        
        spec = {"type": "mcp", "retry_safe": True}
        
        obs = await broker.execute(
            tool="flaky_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req6",
            tool_spec=spec,
            mcp_client=FailingMCPClient()
        )
        
        assert_tool_observation(obs, "success", "flaky_tool")
        assert obs.attempt == 3  # Falló 2 veces, éxito en el 3º
        assert obs.result["attempt"] == 3
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_mcp_retry_safe_false(self):
        """Test: MCP con retry_safe=False → no retry"""
        broker = TestableToolBroker(max_retries=5, base_backoff_ms=1)
        
        call_count = 0
        
        class FailingMCPClient:
            async def call_tool(self, tool, args):
                nonlocal call_count
                call_count += 1
                raise RuntimeError("Always fails")
        
        spec = {"type": "mcp", "retry_safe": False}
        
        obs = await broker.execute(
            tool="non_idempotent_tool",
            args={},
            workspace_id="ws1",
            conversation_id="conv1",
            request_id="req7",
            tool_spec=spec,
            mcp_client=FailingMCPClient()
        )
        
        assert_tool_observation(obs, "failure", "non_idempotent_tool")
        assert obs.attempt == 1  # Sin reintentos
        assert call_count == 1
