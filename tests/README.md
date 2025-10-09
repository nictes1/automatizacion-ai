# Tests del Sistema de Agentes PulpoAI

Esta suite de tests valida el funcionamiento completo del nuevo sistema de agentes, incluyendo **ToolBroker**, **StateReducer**, **PolicyEngine** y el **loop completo de orquestación**.

## 🏗️ Estructura de Tests

```
tests/
├── conftest.py              # Fixtures y helpers comunes
├── test_tool_broker_http.py # ToolBroker - casos HTTP críticos
├── test_tool_broker_mcp.py  # ToolBroker - casos MCP
├── test_circuit_breaker.py  # Circuit Breaker - transiciones
├── test_state_reducer.py    # StateReducer - aplicación de observaciones
├── test_orchestrator_loop.py # Loop completo del agente
├── test_broker_advanced.py  # Casos edge y métricas
├── run_tests.py             # Script de ejecución
└── README.md               # Esta documentación
```

## 🚀 Ejecución Rápida

```bash
# Todos los tests
python tests/run_tests.py all

# Solo tests de performance
python tests/run_tests.py perf

# Tests específicos por patrón
python tests/run_tests.py pattern:retry_after
python tests/run_tests.py pattern:circuit_breaker
python tests/run_tests.py pattern:agent_loop
```

## 📋 Casos de Test Críticos

### 🔧 ToolBroker HTTP (`test_tool_broker_http.py`)

- **429 con Retry-After** (segundos y fecha RFC-7231) → respeta la espera
- **408/timeout** → reintenta con backoff + jitter, marca TIMEOUT al final
- **5xx** → retries; **4xx≠429** → no retry (lógico)
- **retry_safe=False** (POST) → no retry
- **Idempotencia**: mismo request_id → DUPLICATE desde cache
- **Guardrails**: request/response body > max_body_mb → 413
- **Headers**: X-Tool-Name, X-Tool-Retry-Safe, Authorization bearer/api_key

### 🔌 ToolBroker MCP (`test_tool_broker_mcp.py`)

- **Respuesta estructurada**: `{"success": true, "data": ...}`
- **Respuesta legacy**: objeto directo sin estructura
- **Error estructurado**: `{"success": false, "error": "..."}`
- **Excepciones**: RuntimeError → mcp_error
- **retry_safe**: True por defecto, False evita reintentos

### ⚡ Circuit Breaker (`test_circuit_breaker.py`)

- **CLOSED→OPEN** en N fallos
- **OPEN→HALF_OPEN** después del cooldown
- **HALF_OPEN + éxito** → CLOSED
- **HALF_OPEN + fallo** → vuelve a OPEN
- **Sliding window**: fallos fuera de la ventana se ignoran
- **Aislamiento**: por (workspace_id, tool)
- **force_half_open**: función admin para testing

### 🔄 State Reducer (`test_state_reducer.py`)

- **SUCCESS para tools conocidos**: extrae slots relevantes
- **book_appointment** → booking_id, confirmation_code, confirmed_date/time
- **get_services** → _available_services, _service_prices
- **get_availability** → _available_times, _next_available
- **FAILURE** → propaga a _validation_errors para tools críticos
- **CIRCUIT_OPEN** → mensaje informativo
- **Historial LRU** (K=8) sin mutar estado original
- **Batch processing**: múltiples observaciones

### 🤖 Orchestrator Loop (`test_orchestrator_loop.py`)

- **Feature flag**: enable_agent_loop alterna entre legacy/nuevo
- **Flujo completo**: Planner → Policy → Broker → Reducer → Response
- **Policy denial**: agrega validation_errors
- **Tool failures**: manejo de errores
- **Múltiples tools**: ejecución secuencial
- **Fallback**: al sistema legacy en caso de error
- **Singleton**: get_orchestrator_service

### 🚀 Advanced Features (`test_broker_advanced.py`)

- **Semáforo**: limita calls concurrentes por tool
- **Métricas**: emisión estructurada (tool_call_total)
- **Autenticación**: API key + Bearer token
- **Timeouts personalizados**: por tool
- **Cache TTL**: personalizado por tool
- **Circuit breaker**: habilitado/deshabilitado
- **Shutdown lifecycle**: cierre graceful
- **PII redaction**: en logs

## 🎯 Coverage Objetivo

| Componente | Coverage Target | Casos Críticos |
|------------|----------------|-----------------|
| ToolBroker | 95%+ | HTTP, MCP, retry, CB, idempotencia |
| StateReducer | 90%+ | Extracción slots, inmutabilidad, LRU |
| CircuitBreaker | 100% | Todas las transiciones de estado |
| Orchestrator Loop | 85%+ | Feature flag, flujo completo, fallback |

## 🔍 Debugging Tests

```bash
# Test específico con output detallado
pytest tests/test_tool_broker_http.py::TestToolBrokerHTTP::test_429_retry_after_seconds -v -s

# Con pdb debugger
pytest tests/test_circuit_breaker.py::TestCircuitBreaker::test_cb_transitions --pdb

# Solo tests que fallan
pytest tests/ --lf

# Tests más lentos
pytest tests/ --durations=0
```

## 📊 Métricas y Observabilidad

Los tests validan que se emitan las métricas correctas:

```python
# Métrica de éxito
tool_call_total{tool="get_services", workspace="ws1", result="success", status_code="200"} 1

# Métrica de error
tool_call_total{tool="book_appointment", workspace="ws1", result="error", status_code="500"} 1
```

## 🚨 Tests de Regresión

Casos específicos que previenen regresiones:

1. **Mutación de estado**: StateReducer no debe mutar el estado original
2. **Memory leaks**: Circuit breaker debe podar fallos viejos
3. **PII exposure**: Logs no deben contener PII sin redactar
4. **Infinite retries**: retry_safe=False debe evitar reintentos
5. **Cache poisoning**: Idempotencia debe usar model_copy()

## 🎪 Tests de Integración E2E

Para tests end-to-end más realistas:

```python
# Simulación de cliente real
@pytest.mark.integration
async def test_e2e_booking_flow():
    """Test: Flujo completo de reserva con cliente simulado"""
    # Cliente: "Hola, quiero turno para corte mañana 3pm, soy Juan"
    # Agente: Planner → get_availability → book_appointment → respuesta
    pass
```

## 📈 Performance Benchmarks

```bash
# Tests de carga
python tests/run_tests.py pattern:concurrent

# Circuit breaker bajo carga
python tests/run_tests.py pattern:multiple_rapid

# Latencia de retry con jitter
python tests/run_tests.py pattern:backoff
```

---

## 🔧 Setup de Desarrollo

```bash
# Instalar dependencias de testing
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Ejecutar tests con coverage
python tests/run_tests.py all

# Ver reporte HTML
open htmlcov/index.html
```

Esta suite garantiza que el sistema de agentes funcione correctamente en producción, manejando todos los casos edge y manteniendo robustez empresarial. 🎯
