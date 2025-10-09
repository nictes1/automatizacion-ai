"""
Tool Broker - Ejecución robusta de herramientas con idempotencia, retry y circuit breaker

Características:
- Idempotencia por request_id con LRU cache + TTL
- Retry con exponential backoff + full jitter (cap 3s)
- Circuit breaker con sliding window (deque-based)
- Multi-protocolo: MCP / HTTP / Internal
- Clasificación de errores: Transient vs Logical vs Rate Limited
- Rate limiting con soporte Retry-After header (segundos + fecha RFC-7231)
- Session HTTP reutilizable
- PII redaction y log truncation
- Shutdown lifecycle y semaphore por tool
- Guardrails de request/response size
- Autenticación declarativa
"""

from typing import Dict, Any, Optional, Tuple, Callable
from pydantic import BaseModel, Field
from enum import Enum
from collections import OrderedDict, deque
import time
import random
import logging
import asyncio
import aiohttp
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from datetime import datetime
import json

from services.canonical_slots import redact_pii

logger = logging.getLogger(__name__)


# ==========================================
# ENUMS Y MODELOS
# ==========================================

class ToolStatus(str, Enum):
    """Estados de ejecución de un tool"""
    SUCCESS = "success"
    FAILURE = "failure"
    DUPLICATE = "duplicate"  # Idempotencia
    CIRCUIT_OPEN = "circuit_open"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"


@dataclass
class RunnerResult:
    """Resultado normalizado de ejecución de un runner"""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None
    status_code: Optional[int] = None
    retry_after: Optional[int] = None  # Seconds from Retry-After header


class ToolObservation(BaseModel):
    """Observación de ejecución de un tool"""
    tool: str
    args: Dict[str, Any]
    status: ToolStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0
    attempt: int = 1
    timestamp: float = Field(default_factory=time.time)

    # Metadata for debugging
    status_code: Optional[int] = None
    circuit_breaker_tripped: bool = False
    from_cache: bool = False


# ==========================================
# LRU CACHE CON TTL
# ==========================================

class LRUCache:
    """
    LRU Cache con TTL usando OrderedDict + monotonic clock

    THREAD-SAFETY NOTE: Asume single event loop (asyncio).
    Para multi-threaded, usar threading.Lock.
    """

    def __init__(self, capacity: int = 5000, default_ttl_seconds: int = 1800):
        self.capacity = capacity
        self.default_ttl = default_ttl_seconds
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor si existe y no expiró"""
        if key not in self._cache:
            return None

        value, expires_at = self._cache[key]
        now = time.monotonic()

        if now > expires_at:
            # Expiró, eliminar
            del self._cache[key]
            return None

        # Move to end (marca como reciente)
        self._cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None):
        """Guarda valor con TTL"""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        expires_at = time.monotonic() + ttl

        if key in self._cache:
            # Update existente
            self._cache.move_to_end(key)

        self._cache[key] = (value, expires_at)

        # Evict oldest if over capacity
        if len(self._cache) > self.capacity:
            self._cache.popitem(last=False)

    def clear(self):
        """Limpia cache completo"""
        self._cache.clear()


# ==========================================
# CIRCUIT BREAKER CON SLIDING WINDOW
# ==========================================

class CircuitBreakerState(str, Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject requests
    HALF_OPEN = "half_open" # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker con sliding window (deque-based)

    Estados:
    - CLOSED: Normal (permite requests)
    - OPEN: Fallando (rechaza requests por cooldown_seconds)
    - HALF_OPEN: Probando (permite 1 request de test)
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        window_seconds: int = 60,
        cooldown_seconds: int = 30,
        half_open_max_calls: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_calls = half_open_max_calls

        # Estado por (workspace_id, tool)
        self._state: Dict[str, CircuitBreakerState] = {}
        self._failures: Dict[str, deque] = {}  # deque of timestamps
        self._last_failure_time: Dict[str, float] = {}
        self._half_open_attempts: Dict[str, int] = {}

    def _key(self, workspace_id: str, tool: str) -> str:
        return f"{workspace_id}:{tool}"

    def is_open(self, workspace_id: str, tool: str) -> Tuple[bool, str]:
        """
        Verifica si el circuit breaker está abierto

        Returns:
            (is_open, reason)
        """
        key = self._key(workspace_id, tool)
        state = self._state.get(key, CircuitBreakerState.CLOSED)

        if state == CircuitBreakerState.CLOSED:
            return False, ""

        if state == CircuitBreakerState.OPEN:
            # Verificar si pasó el cooldown
            last_failure = self._last_failure_time.get(key, 0)
            now = time.monotonic()

            if now - last_failure > self.cooldown_seconds:
                # Pasar a HALF_OPEN
                self._state[key] = CircuitBreakerState.HALF_OPEN
                self._half_open_attempts[key] = 0
                logger.info(f"[CB] {key} → HALF_OPEN (cooldown passed)")
                return False, ""

            return True, f"Circuit breaker OPEN (cooldown {self.cooldown_seconds}s)"

        if state == CircuitBreakerState.HALF_OPEN:
            # Permitir solo N intentos
            attempts = self._half_open_attempts.get(key, 0)
            if attempts >= self.half_open_max_calls:
                return True, f"Circuit breaker HALF_OPEN (max {self.half_open_max_calls} test calls)"

            self._half_open_attempts[key] = attempts + 1
            return False, ""

        return False, ""

    def record_success(self, workspace_id: str, tool: str):
        """Registra éxito → cierra circuit breaker"""
        key = self._key(workspace_id, tool)
        state = self._state.get(key, CircuitBreakerState.CLOSED)

        if state == CircuitBreakerState.HALF_OPEN:
            # Éxito en test → cerrar
            self._state[key] = CircuitBreakerState.CLOSED
            self._failures[key] = deque()
            logger.info(f"[CB] {key} → CLOSED (recovery success)")

        elif state == CircuitBreakerState.CLOSED:
            # Limpiar fallos viejos
            self._prune_old_failures(key)

    def record_failure(self, workspace_id: str, tool: str):
        """Registra fallo → puede abrir circuit breaker"""
        key = self._key(workspace_id, tool)
        now = time.monotonic()

        if key not in self._failures:
            self._failures[key] = deque()

        self._failures[key].append(now)
        self._last_failure_time[key] = now
        self._prune_old_failures(key)

        state = self._state.get(key, CircuitBreakerState.CLOSED)

        if state == CircuitBreakerState.HALF_OPEN:
            # Falló en test → volver a OPEN
            self._state[key] = CircuitBreakerState.OPEN
            logger.warning(f"[CB] {key} → OPEN (test failed)")

        elif state == CircuitBreakerState.CLOSED:
            # Verificar threshold
            if len(self._failures[key]) >= self.failure_threshold:
                self._state[key] = CircuitBreakerState.OPEN
                logger.warning(f"[CB] {key} → OPEN ({len(self._failures[key])} failures in {self.window_seconds}s)")

    def _prune_old_failures(self, key: str):
        """Elimina fallos fuera de la ventana"""
        if key not in self._failures:
            return

        now = time.monotonic()
        cutoff = now - self.window_seconds

        while self._failures[key] and self._failures[key][0] < cutoff:
            self._failures[key].popleft()

    def force_half_open(self, workspace_id: str, tool: str):
        """Fuerza estado HALF_OPEN (útil para testing/admin)"""
        key = self._key(workspace_id, tool)
        self._state[key] = CircuitBreakerState.HALF_OPEN
        self._half_open_attempts[key] = 0
        logger.info(f"[CB] {key} → HALF_OPEN (forced)")


# ==========================================
# HELPERS
# ==========================================

def _get(spec, name: str, default=None):
    """
    Robust getter para spec (Pydantic o dict)
    """
    if hasattr(spec, name):
        return getattr(spec, name, default)
    elif isinstance(spec, dict):
        return spec.get(name, default)
    return default


def _backoff_ms(base: int, attempt: int, factor: int = 1, cap: int = 3000) -> int:
    """
    Exponential backoff con full jitter y cap

    Formula: min(base * 2^attempt * factor, cap) con jitter uniforme
    """
    raw = min(base * (2 ** attempt) * factor, cap)
    return int(random.uniform(0, raw))


def _truncate(x: Any, n: int = 2000) -> str:
    """Trunca para logging seguro"""
    s = str(x)
    return s if len(s) <= n else s[:n] + "..."


def _build_std_headers(
    workspace_id: str,
    conversation_id: str,
    request_id: str,
    tool: str,
    retry_safe: bool,
    manifest_version: str = "v1",
    extra: Optional[Dict[str, str]] = None
) -> Dict[str, str]:
    """Construye headers estándar para HTTP tools"""
    headers = {
        "X-Workspace-Id": workspace_id,
        "X-Conversation-Id": conversation_id,
        "X-Request-Id": request_id,
        "X-Tool-Name": tool,
        "X-Tool-Retry-Safe": str(retry_safe).lower(),
        "X-Manifest-Version": manifest_version,
        "User-Agent": "PulpoAI-ToolBroker/1.0",
        "Content-Type": "application/json"
    }

    if extra:
        headers.update(extra)

    return headers


def _parse_retry_after(retry_after_header: str) -> Optional[int]:
    """
    Parsea Retry-After header soportando segundos y fecha RFC-7231
    
    Returns:
        Segundos hasta retry, o None si no se puede parsear
    """
    if not retry_after_header:
        return None
        
    # Formato segundos
    if retry_after_header.isdigit():
        return int(retry_after_header)
    
    # Formato fecha HTTP
    try:
        dt = parsedate_to_datetime(retry_after_header)
        seconds = max(0, int((dt - datetime.utcnow()).total_seconds()))
        return seconds
    except Exception:
        return None


# ==========================================
# TOOL BROKER
# ==========================================

class ToolBroker:
    """
    Broker de ejecución de tools con idempotencia, retry y circuit breaker

    Características:
    - Idempotencia por request_id
    - Retry con exponential backoff + jitter
    - Circuit breaker con sliding window
    - Multi-protocolo: MCP / HTTP / Internal
    - Rate limiting con Retry-After
    - Session HTTP reutilizable
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_backoff_ms: int = 100,
        idempotency_ttl: int = 1800,
        circuit_breaker_enabled: bool = True,
        max_inflight_per_tool: int = 10,
        max_body_mb: int = 5
    ):
        self.max_retries = max_retries
        self.base_backoff_ms = base_backoff_ms
        self.circuit_breaker_enabled = circuit_breaker_enabled
        self.max_body_mb = max_body_mb

        # Caches y estado
        self._idempotency_cache = LRUCache(capacity=5000, default_ttl_seconds=idempotency_ttl)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, window_seconds=60, cooldown_seconds=30)

        # HTTP session (reutilizable)
        self._http_session: Optional[aiohttp.ClientSession] = None

        # Semaphores por (workspace_id, tool) para limitar in-flight
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._max_inflight = max_inflight_per_tool

        # Observability hook
        self._metric_callback: Optional[Callable] = None

    def set_metric_callback(self, callback: Callable):
        """Configura callback para métricas (prometheus, etc.)"""
        self._metric_callback = callback

    def _emit_metric(self, metric: str, value: float, labels: Dict[str, str]):
        """Emite métrica si hay callback configurado"""
        if self._metric_callback:
            try:
                self._metric_callback(metric, value, labels)
            except Exception as e:
                logger.warning(f"[METRICS] Error emitting {metric}: {e}")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Obtiene sesión HTTP reutilizable"""
        if self._http_session is None or self._http_session.closed:
            # Timeout default: 10s total, 2s connect, 10s read
            timeout = aiohttp.ClientTimeout(total=10, sock_connect=2, sock_read=10)
            self._http_session = aiohttp.ClientSession(
                timeout=timeout,
                connector=aiohttp.TCPConnector(limit=100)
            )
        return self._http_session

    async def close(self):
        """Cierra recursos (session HTTP, etc.)"""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
            logger.info("[BROKER] HTTP session closed")

    def _get_semaphore(self, workspace_id: str, tool: str) -> asyncio.Semaphore:
        """Obtiene semaphore para limitar in-flight por tool"""
        key = f"{workspace_id}:{tool}"
        if key not in self._semaphores:
            self._semaphores[key] = asyncio.Semaphore(self._max_inflight)
        return self._semaphores[key]

    async def execute(
        self,
        tool: str,
        args: Dict[str, Any],
        workspace_id: str,
        conversation_id: str,
        request_id: str,
        tool_spec: Optional[Any] = None,
        mcp_client: Optional[Any] = None,
        custom_runners: Optional[Dict[str, Callable]] = None
    ) -> ToolObservation:
        """
        Ejecuta un tool con idempotencia, retry y circuit breaker

        Args:
            tool: Nombre del tool
            args: Argumentos (ya normalizados por PolicyEngine)
            workspace_id: ID del workspace
            conversation_id: ID de la conversación
            request_id: Request ID para idempotencia
            tool_spec: ToolSpec (Pydantic) o dict con spec del tool
            mcp_client: Cliente MCP (opcional, para tools tipo 'mcp')
            custom_runners: Runners custom por tool (opcional)

        Returns:
            ToolObservation con resultado
        """
        start_time = time.monotonic()

        # Redactar PII en logs
        redacted_args = redact_pii(args)
        logger.info(f"[BROKER] execute({tool}) workspace={workspace_id}, request_id={request_id}, args={_truncate(redacted_args)}")

        # 1. Check idempotency cache
        cache_key = f"{workspace_id}:{conversation_id}:{request_id}:{tool}"
        cached = self._idempotency_cache.get(cache_key)

        if cached:
            logger.info(f"[BROKER] Cache HIT for {tool} (request_id={request_id})")
            # NO MUTATION - usar model_copy
            return cached.model_copy(update={"status": ToolStatus.DUPLICATE, "from_cache": True})

        # 2. Check circuit breaker (si está habilitado)
        if self.circuit_breaker_enabled:
            is_open, reason = self.circuit_breaker.is_open(workspace_id, tool)
            if is_open:
                logger.warning(f"[BROKER] Circuit breaker OPEN for {tool}: {reason}")
                observation = ToolObservation(
                    tool=tool,
                    args=args,
                    status=ToolStatus.CIRCUIT_OPEN,
                    error=reason,
                    execution_time_ms=0,
                    circuit_breaker_tripped=True
                )

                # Cache corto para CIRCUIT_OPEN
                self._idempotency_cache.set(cache_key, observation, ttl_seconds=10)
                return observation

        # 3. Semaphore para limitar in-flight
        semaphore = self._get_semaphore(workspace_id, tool)

        async with semaphore:
            # 4. Determinar retry_safe antes del loop
            retry_safe = True
            tool_type = _get(tool_spec, "type", "mcp")
            if tool_type == "http":
                method = _get(tool_spec, "method", "POST").upper()
                retry_safe = _get(tool_spec, "retry_safe", method in ["GET", "PUT"])
            elif tool_type == "mcp":
                retry_safe = _get(tool_spec, "retry_safe", True)

            # 5. Retry loop
            last_error: Optional[str] = None
            last_status_code: Optional[int] = None

            for attempt in range(self.max_retries + 1):
                try:
                    # Ejecutar según tipo
                    if tool_type == "http":
                        result = await self._execute_http_tool(tool, args, tool_spec, workspace_id, conversation_id, request_id, retry_safe)
                    elif tool_type == "mcp":
                        result = await self._execute_mcp_tool(tool, args, mcp_client)
                    else:
                        # Internal / custom
                        if custom_runners and tool in custom_runners:
                            result = await custom_runners[tool](args)
                        else:
                            result = RunnerResult(
                                success=False,
                                data={},
                                error=f"Unknown tool type: {tool_type}",
                                status_code=None
                            )

                    # Guardar status_code para clasificación
                    last_status_code = result.status_code

                    if result.success:
                        # ✅ Éxito
                        execution_time_ms = int((time.monotonic() - start_time) * 1000)

                        observation = ToolObservation(
                            tool=tool,
                            args=args,
                            status=ToolStatus.SUCCESS,
                            result=result.data,
                            execution_time_ms=execution_time_ms,
                            attempt=attempt + 1,
                            status_code=result.status_code
                        )

                        # Guardar en cache
                        ttl = _get(tool_spec, "cache_ttl_seconds", 1800)
                        self._idempotency_cache.set(cache_key, observation, ttl_seconds=ttl)

                        # Circuit breaker success
                        if self.circuit_breaker_enabled:
                            self.circuit_breaker.record_success(workspace_id, tool)

                        # Métrica
                        self._emit_metric("tool_call_total", 1, {
                            "tool": tool, 
                            "workspace": workspace_id,
                            "result": "success",
                            "status_code": str(result.status_code or 0)
                        })

                        logger.info(f"[BROKER] ✅ {tool} SUCCESS (attempt {attempt + 1}, {execution_time_ms}ms)")
                        return observation

                    else:
                        # ❌ Error - clasificar
                        last_error = result.error or "unknown_error"

                        # Clasificar tipo de error
                        is_transient = self._is_transient_error(result)
                        is_rate_limit = result.status_code == 429

                        if is_rate_limit:
                            # Rate limit - retry con backoff especial
                            last_error = "rate_limited"
                            last_status_code = 429

                            if attempt < self.max_retries:
                                # Backoff 5x más largo para rate limits
                                backoff_ms = _backoff_ms(self.base_backoff_ms, attempt, factor=5, cap=3000)

                                # Respetar Retry-After header si existe
                                if result.retry_after:
                                    backoff_ms = max(backoff_ms, result.retry_after * 1000)

                                logger.warning(f"[BROKER] Rate limit {tool} (attempt {attempt + 1}), retry in {backoff_ms}ms")
                                await asyncio.sleep(backoff_ms / 1000)
                                continue

                        elif is_transient and retry_safe:
                            # Error transitorio - retry solo si es safe
                            if attempt < self.max_retries:
                                backoff_ms = _backoff_ms(self.base_backoff_ms, attempt, cap=3000)
                                logger.warning(f"[BROKER] Transient error {tool} (attempt {attempt + 1}): {_truncate(last_error, 500)}, retry in {backoff_ms}ms")
                                await asyncio.sleep(backoff_ms / 1000)

                                # Record en circuit breaker
                                if self.circuit_breaker_enabled:
                                    self.circuit_breaker.record_failure(workspace_id, tool)

                                continue

                        elif not retry_safe:
                            # Tool no idempotente - no retry
                            logger.warning(f"[BROKER] Non-idempotent tool, skipping retries for {tool}")
                            break

                        else:
                            # Error lógico (4xx ≠ 429) - NO retry
                            logger.error(f"[BROKER] Logical error {tool}: {_truncate(last_error, 500)}")
                            break

                except asyncio.TimeoutError:
                    # Timeout
                    last_error = "timeout"
                    last_status_code = 408

                    if attempt < self.max_retries and retry_safe:
                        backoff_ms = _backoff_ms(self.base_backoff_ms, attempt, cap=3000)
                        logger.warning(f"[BROKER] Timeout {tool} (attempt {attempt + 1}), retry in {backoff_ms}ms")
                        await asyncio.sleep(backoff_ms / 1000)

                        if self.circuit_breaker_enabled:
                            self.circuit_breaker.record_failure(workspace_id, tool)

                        continue
                    else:
                        break

                except Exception as e:
                    # Error inesperado
                    last_error = f"unexpected_error: {str(e)}"
                    last_status_code = None

                    logger.exception(f"[BROKER] Unexpected error {tool} (attempt {attempt + 1})")

                    if attempt < self.max_retries and retry_safe:
                        backoff_ms = _backoff_ms(self.base_backoff_ms, attempt, cap=3000)
                        await asyncio.sleep(backoff_ms / 1000)

                        if self.circuit_breaker_enabled:
                            self.circuit_breaker.record_failure(workspace_id, tool)

                        continue
                    else:
                        break

            # Todos los intentos fallaron
            execution_time_ms = int((time.monotonic() - start_time) * 1000)

            # Determinar status final
            if last_status_code == 429:
                final_status = ToolStatus.RATE_LIMITED
            elif last_status_code == 408 or "timeout" in (last_error or "").lower():
                final_status = ToolStatus.TIMEOUT
            else:
                final_status = ToolStatus.FAILURE

            observation = ToolObservation(
                tool=tool,
                args=args,
                status=final_status,
                error=last_error,
                execution_time_ms=execution_time_ms,
                attempt=self.max_retries + 1,
                status_code=last_status_code
            )

            # Guardar en cache (TTL corto para failures)
            self._idempotency_cache.set(cache_key, observation, ttl_seconds=300)

            # Métrica
            self._emit_metric("tool_call_total", 1, {
                "tool": tool, 
                "workspace": workspace_id,
                "result": "error",
                "status_code": str(last_status_code or 0)
            })

            logger.error(f"[BROKER] ❌ {tool} FAILED after {self.max_retries + 1} attempts: {_truncate(last_error, 500)}")
            return observation

    def _is_transient_error(self, result: RunnerResult) -> bool:
        """
        Clasifica si un error es transitorio (retryable)

        Transient:
        - 5xx
        - 408 (timeout)
        - Network errors
        - None status_code (internal errors)

        NOT Transient:
        - 4xx (except 429, que se maneja aparte)
        """
        if result.status_code is None:
            # Sin status_code → asumir transitorio (network, etc.)
            return True

        if result.status_code == 408:
            # Timeout
            return True

        if 500 <= result.status_code < 600:
            # 5xx
            return True

        # 4xx (excepto 429) → NO transitorio
        return False

    async def _execute_mcp_tool(
        self,
        tool: str,
        args: Dict[str, Any],
        mcp_client: Optional[Any]
    ) -> RunnerResult:
        """
        Ejecuta tool vía MCP (Model Context Protocol)
        """
        if not mcp_client:
            return RunnerResult(
                success=False,
                data={},
                error="MCP client not provided",
                status_code=None
            )

        try:
            # Llamar a MCP client
            result = await mcp_client.call_tool(tool, args)

            # Interpretar contrato {"success":..,"data":..,"error":..}
            if isinstance(result, dict):
                success = bool(result.get("success", True))
                data = result.get("data", result)
                err = result.get("error")
                return RunnerResult(
                    success=success, 
                    data=data if data is not None else {}, 
                    error=err, 
                    status_code=None
                )
            
            # Fallback legacy
            return RunnerResult(
                success=True,
                data=result,
                status_code=None  # MCP no tiene status codes HTTP
            )

        except Exception as e:
            logger.exception(f"[BROKER] MCP error for {tool}")
            return RunnerResult(
                success=False,
                data={},
                error=f"mcp_error: {str(e)}",
                status_code=None
            )

    async def _execute_http_tool(
        self,
        tool: str,
        args: Dict[str, Any],
        tool_spec: Any,
        workspace_id: str,
        conversation_id: str,
        request_id: str,
        retry_safe: bool
    ) -> RunnerResult:
        """
        Ejecuta tool vía HTTP REST

        Spec esperado:
        - url: URL del endpoint (requerido si type=http)
        - method: GET, POST, etc. (default: POST)
        - headers: Headers custom (opcional)
        - timeout_ms: Timeout en ms (default: 10000)
        - auth: Autenticación declarativa (opcional)
        """
        # Validar spec
        url = _get(tool_spec, "url")
        if not url:
            return RunnerResult(
                success=False,
                data={},
                error="HTTP tool requires 'url' in spec",
                status_code=None
            )

        method = _get(tool_spec, "method", "POST").upper()
        timeout_ms = _get(tool_spec, "timeout_ms", 10000)
        manifest_version = _get(tool_spec, "manifest_version", "v1")

        # Headers estándar
        headers = _build_std_headers(
            workspace_id, conversation_id, request_id, 
            tool, retry_safe, manifest_version
        )

        # Merge con headers custom del spec
        spec_headers = _get(tool_spec, "headers", {})
        headers.update(spec_headers)

        # Autenticación declarativa
        auth = _get(tool_spec, "auth", None)
        if auth:
            if auth.get("type") == "bearer" and auth.get("token"):
                headers["Authorization"] = f"Bearer {auth['token']}"
            elif auth.get("type") == "api_key":
                headers[auth.get("header", "X-API-Key")] = auth.get("value", "")

        # Timeout granular
        timeout_s = timeout_ms / 1000
        timeout = aiohttp.ClientTimeout(
            total=timeout_s,
            sock_connect=min(2, timeout_s),
            sock_read=timeout_s
        )

        try:
            session = await self._get_session()

            # Construir request
            request_kwargs = {
                "headers": headers,
                "timeout": timeout
            }

            # Body/params según método
            if method in ["GET", "DELETE"]:
                request_kwargs["params"] = args
            else:
                request_kwargs["json"] = args

                # Guardrails: Tamaño máximo de request body
                body_size_mb = len(json.dumps(args).encode()) / (1024 * 1024)
                if body_size_mb > self.max_body_mb:
                    return RunnerResult(
                        success=False,
                        data={},
                        error=f"Request body too large: {body_size_mb:.2f}MB > {self.max_body_mb}MB",
                        status_code=413
                    )

            # Ejecutar request
            async with session.request(method, url, **request_kwargs) as response:
                status_code = response.status

                # Capturar Retry-After header (segundos + fecha)
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))

                # Guardrails: Tamaño máximo de response
                cl = response.headers.get("Content-Length")
                if cl and cl.isdigit():
                    mb = int(cl) / (1024 * 1024)
                    if mb > self.max_body_mb:
                        return RunnerResult(
                            success=False,
                            data={},
                            error=f"Response too large: {mb:.2f}MB > {self.max_body_mb}MB",
                            status_code=413
                        )

                # Leer response
                try:
                    data = await response.json()
                except Exception:
                    # No es JSON, leer como texto (truncado)
                    text = await response.text()
                    data = {"_raw": text[:10000]}

                # Éxito: 2xx
                if 200 <= status_code < 300:
                    return RunnerResult(
                        success=True,
                        data=data,
                        status_code=status_code
                    )

                # Error
                error_msg = data.get("error") or data.get("message") or f"HTTP {status_code}"

                return RunnerResult(
                    success=False,
                    data=data,
                    error=error_msg,
                    status_code=status_code,
                    retry_after=retry_after
                )

        except asyncio.TimeoutError:
            return RunnerResult(
                success=False,
                data={},
                error="http_timeout",
                status_code=408
            )

        except aiohttp.ClientError as e:
            return RunnerResult(
                success=False,
                data={},
                error=f"http_client_error: {str(e)}",
                status_code=None
            )

        except Exception as e:
            logger.exception(f"[BROKER] HTTP error for {tool}")
            return RunnerResult(
                success=False,
                data={},
                error=f"http_unexpected_error: {str(e)}",
                status_code=None
            )


# ==========================================
# SINGLETON GLOBAL
# ==========================================

_broker_instance: Optional[ToolBroker] = None


def get_tool_broker() -> ToolBroker:
    """Obtiene instancia singleton del broker"""
    global _broker_instance
    if _broker_instance is None:
        _broker_instance = ToolBroker()
    return _broker_instance


async def shutdown_tool_broker():
    """Cierra recursos del broker (para shutdown graceful)"""
    global _broker_instance
    if _broker_instance:
        await _broker_instance.close()
        _broker_instance = None
        logger.info("[BROKER] Shutdown completed")
