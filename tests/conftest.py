# tests/conftest.py
"""
Fixtures y helpers para testing del sistema de agentes
"""

import pytest
from types import SimpleNamespace
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Any, Optional


class DummyResp:
    """Mock de aiohttp.ClientResponse"""
    
    def __init__(self, status: int, data: Any = None, headers: Optional[Dict[str, str]] = None):
        self.status = status
        self._data = data or {}
        self.headers = headers or {}

    async def json(self):
        return self._data

    async def text(self):
        return str(self._data)
    
    def get_encoding(self):
        return "utf-8"


class DummySession:
    """Mock de aiohttp.ClientSession con respuestas scripteadas"""
    
    def __init__(self, scripted: List[Tuple[int, Any, Dict[str, str]]]):
        # scripted: list of (status, data, headers) por request
        self.scripted = list(scripted)
        self.closed = False

    async def request(self, method: str, url: str, **kwargs):
        if not self.scripted:
            raise RuntimeError("No more scripted responses available")
        
        status, data, headers = self.scripted.pop(0)
        return DummyCtx(DummyResp(status, data, headers))

    async def close(self):
        self.closed = True


class DummyCtx:
    """Mock de context manager para aiohttp response"""
    
    def __init__(self, resp: DummyResp):
        self.resp = resp
    
    async def __aenter__(self):
        return self.resp
    
    async def __aexit__(self, *args):
        return False


def http_date_after(seconds: int) -> str:
    """Genera fecha HTTP RFC-7231 en el futuro"""
    dt = datetime.utcnow() + timedelta(seconds=seconds)
    # RFC 7231 IMF-fixdate
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")


class DummyMCPClient:
    """Mock de cliente MCP con respuestas configurables"""
    
    def __init__(self, responses: Dict[str, Any] = None):
        self.responses = responses or {}
        self.call_history = []
    
    async def call_tool(self, tool: str, args: Dict[str, Any]):
        self.call_history.append((tool, args))
        
        if tool in self.responses:
            response = self.responses[tool]
            if isinstance(response, Exception):
                raise response
            return response
        
        # Default success response
        return {"success": True, "data": {"tool": tool, "args": args}}


class TestableToolBroker:
    """ToolBroker testeable que permite inyectar session HTTP"""
    
    def __init__(self, *args, **kwargs):
        from services.tool_broker import ToolBroker
        self._broker = ToolBroker(*args, **kwargs)
        self._test_session = None
    
    def set_test_session(self, session):
        """Inyecta sesión HTTP para testing"""
        self._test_session = session
        self._broker._http_session = session
    
    async def _get_session(self):
        return self._test_session or await self._broker._get_session()
    
    def __getattr__(self, name):
        # Delegar todo lo demás al broker real
        return getattr(self._broker, name)


@pytest.fixture
def make_retry_after_date():
    """Fixture para generar fechas Retry-After"""
    return http_date_after


@pytest.fixture
def dummy_mcp_client():
    """Fixture para cliente MCP mock"""
    return DummyMCPClient()


@pytest.fixture
def testable_broker():
    """Fixture para ToolBroker testeable"""
    return TestableToolBroker(max_retries=3, base_backoff_ms=10)


@pytest.fixture
def sample_tool_spec():
    """Fixture con spec de tool básico"""
    return {
        "type": "http",
        "url": "https://api.test.com/endpoint",
        "method": "GET",
        "timeout_ms": 5000,
        "retry_safe": True
    }


@pytest.fixture
def sample_conversation_state():
    """Fixture con estado conversacional básico"""
    return {
        "conversation_id": "conv_123",
        "workspace_id": "ws_456",
        "user_input": "test message",
        "slots": {"client_name": "Juan", "service_type": "Corte"},
        "greeted": True,
        "objective": "Agendar turno"
    }


# Helpers para assertions
def assert_tool_observation(obs, expected_status: str, expected_tool: str):
    """Helper para validar ToolObservation"""
    assert obs.tool == expected_tool
    assert obs.status.value == expected_status
    
    
def assert_no_mutation(original_dict: dict, modified_dict: dict):
    """Helper para verificar inmutabilidad"""
    assert original_dict is not modified_dict, "Should return new dict, not mutate original"
