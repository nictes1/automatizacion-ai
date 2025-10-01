# Orchestrator API - FastAPI endpoint para el servicio de orquestación (multitenant)
# Mejoras: lifespan API, contexto por headers, rate limiting robusto, validación pydantic v2.

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Any, Literal
import logging
import uuid
import random
from datetime import datetime
from time import monotonic
from collections import defaultdict
from contextlib import asynccontextmanager

from orchestrator_service import (
    OrchestratorService,
    ConversationSnapshot,
    OrchestratorResponse,
    NextAction,
    REQUEST_CONTEXT,
)
from error_utils import (
    error_payload,
    validation_error,
    not_found_error,
    rate_limit_error,
    internal_error,
    ErrorCodes,
    ErrorMessages,
)

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator_api")

# -----------------------------------------------------------------------------
# App (con lifespan)
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Orchestrator Service iniciado v2.1.0")
    try:
        yield
    finally:
        logger.info("🛑 Orchestrator Service cerrando...")
        await orchestrator_service.close()

app = FastAPI(
    title="PulpoAI Orchestrator Service",
    description="Servicio de orquestación determinista para conversaciones WhatsApp (multitenant)",
    version="2.1.0",
    contact={"name": "PulpoAI"},
    license_info={"name": "Proprietary"},
    openapi_tags=[
        {"name": "health", "description": "Estado del servicio"},
        {"name": "orchestrator", "description": "Decisiones y políticas del orquestador"},
    ],
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ajustá en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Context Middleware unificado (contexto + headers + logging)
# -----------------------------------------------------------------------------
class ContextMiddleware(BaseHTTPMiddleware):
    """Middleware que aísla y limpia automáticamente el contexto por request, con logging y headers."""
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        ctx = {
            "x-request-id": rid,
            "x-workspace-id": request.headers.get("X-Workspace-Id", ""),
            "authorization": request.headers.get("Authorization", "")
        }
        token = REQUEST_CONTEXT.set(ctx)
        response: Optional[Response] = None
        try:
            response = await call_next(request)
            # reflejamos trazabilidad
            response.headers["X-Request-Id"] = rid
            if ctx.get("x-workspace-id"):
                response.headers["X-Workspace-Id"] = ctx["x-workspace-id"]
            return response
        except Exception:
            logger.exception("Unhandled error (middleware)")
            rid_fallback = ctx.get("x-request-id", str(uuid.uuid4()))
            return JSONResponse(
                status_code=500,
                content=error_payload(ErrorCodes.INTERNAL, "Error interno inesperado", rid_fallback),
            )
        finally:
            REQUEST_CONTEXT.reset(token)
            logger.info(
                '%s %s -> %s rid=%s ws=%s',
                request.method,
                request.url.path,
                getattr(response, "status_code", "500"),
                rid,
                ctx.get("x-workspace-id", "")
            )

app.add_middleware(ContextMiddleware)

# -----------------------------------------------------------------------------
# Tipos y Modelos
# -----------------------------------------------------------------------------
Vertical = Literal["gastronomia", "inmobiliaria", "servicios"]

class ConversationSnapshotRequest(BaseModel):
    conversation_id: str = Field(..., min_length=1, description="ID único de la conversación")
    vertical: Vertical = Field(..., description="Vertical de negocio")
    user_input: str = Field(..., min_length=1, description="Input del usuario (último turno)")
    greeted: bool = Field(default=False, description="Si ya fue saludado")
    slots: Dict[str, Any] = Field(default_factory=dict, description="Slots actuales (estado del dominio)")
    objective: str = Field(default="", description="Objetivo de la conversación (p.ej., tomar_pedido)")
    last_action: Optional[str] = Field(default=None, description="Última acción ejecutada")
    attempts_count: int = Field(default=0, ge=0, le=10, description="Intentos de progreso")

    # Pydantic v2
    @field_validator("user_input", mode="before")
    @classmethod
    def _cap_user_input(cls, v: Any) -> str:
        if not isinstance(v, str):
            v = str(v)
        return v if len(v) <= 4000 else (v[:4000] + "…")

class OrchestratorResponseModel(BaseModel):
    assistant: str
    slots: Dict[str, Any]
    tool_calls: List[Dict[str, Any]] = []
    context_used: List[Dict[str, Any]] = []
    next_action: Literal["GREET", "SLOT_FILL", "RETRIEVE_CONTEXT", "EXECUTE_ACTION", "ANSWER", "ASK_HUMAN"]
    end: bool = False

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    service: str
    version: str
    request_id: str

class ActionsInfo(BaseModel):
    actions: List[Dict[str, str]]

# -----------------------------------------------------------------------------
# Contexto por Request (headers) - modelo local (evitar colisión de nombres)
# -----------------------------------------------------------------------------
class APIRequestContext(BaseModel):
    request_id: str
    authorization: Optional[str] = None
    workspace_id: Optional[str] = None
    user_agent: Optional[str] = None

def build_context(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    workspace_id: Optional[str] = Header(default=None, alias="X-Workspace-Id"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> APIRequestContext:
    rid = (REQUEST_CONTEXT.get() or {}).get("x-request-id") or request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = rid
    return APIRequestContext(
        request_id=rid,
        authorization=authorization,
        workspace_id=workspace_id,
        user_agent=user_agent,
    )

# -----------------------------------------------------------------------------
# Error handlers uniformes
# -----------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    rid = (REQUEST_CONTEXT.get() or {}).get("x-request-id", str(uuid.uuid4()))
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(ErrorCodes.INTERNAL, str(exc.detail), rid),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    rid = (REQUEST_CONTEXT.get() or {}).get("x-request-id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=422,
        content=error_payload(
            ErrorCodes.VALIDATION_ERROR,
            ErrorMessages.INVALID_INPUT,
            rid,
            exc.errors(),
        ),
    )

# -----------------------------------------------------------------------------
# Instancia del servicio
# -----------------------------------------------------------------------------
orchestrator_service = OrchestratorService()

# -----------------------------------------------------------------------------
# Rate limiting mejorado (por conversation_id) con limpieza TTL
# -----------------------------------------------------------------------------
_last_seen = defaultdict(float)  # monotonic seconds
RATE_LIMIT_SECONDS = 0.4
_CLEAN_EVERY = 2048          # cada N hits limpiamos algo
_TTL_SECONDS = 300.0         # 5 min de inactividad → purge
_hits = 0

def _maybe_clean_rate_map(now: float):
    global _hits
    _hits += 1
    if _hits % _CLEAN_EVERY != 0:
        return
    stale = [k for k, t in _last_seen.items() if (now - t) > _TTL_SECONDS]
    for k in stale:
        _last_seen.pop(k, None)

def rate_limit_guard(conversation_id: str, request_id: str = ""):
    now = monotonic()
    last = _last_seen[conversation_id]
    elapsed_ms = (now - last) * 1000
    if elapsed_ms < RATE_LIMIT_SECONDS * 1000:
        jitter_ms = random.randint(-30, 30)
        retry_after = max(0.0, (RATE_LIMIT_SECONDS * 1000 + jitter_ms - int(elapsed_ms)) / 1000.0)
        raise HTTPException(
            status_code=429,
            detail={"error": {
                "code": "RATE_LIMIT",
                "message": "Too Many Requests",
                "request_id": request_id,
                "retry_after": retry_after
            }},
            headers={"Retry-After": str(max(0, int(retry_after)))}
        )
    _last_seen[conversation_id] = now
    _maybe_clean_rate_map(now)

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check(ctx: APIRequestContext = Depends(build_context)):
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        service="orchestrator",
        version="2.1.0",
        request_id=ctx.request_id,
    )

@app.post("/orchestrator/decide", response_model=OrchestratorResponseModel, tags=["orchestrator"])
async def decide_next_step(
    request_body: ConversationSnapshotRequest,
    response: Response,
    ctx: APIRequestContext = Depends(build_context),
):
    try:
        rate_limit_guard(request_body.conversation_id, ctx.request_id)

        logger.info(
            "decide: conv=%s vertical=%s greeted=%s attempts=%s rid=%s ws=%s",
            request_body.conversation_id,
            request_body.vertical,
            request_body.greeted,
            request_body.attempts_count,
            ctx.request_id,
            ctx.workspace_id,
        )

        snapshot = ConversationSnapshot(
            conversation_id=request_body.conversation_id,
            vertical=request_body.vertical,
            user_input=request_body.user_input,
            greeted=request_body.greeted,
            slots={**request_body.slots, "workspace_id": ctx.workspace_id, "conversation_id": request_body.conversation_id},
            objective=request_body.objective,
            last_action=request_body.last_action,
            attempts_count=request_body.attempts_count,
        )

        orchestrator_resp: OrchestratorResponse = await orchestrator_service.decide(snapshot)

        slots_out = dict(orchestrator_resp.slots)

        # headers de trazabilidad (por si otro middleware los quitó)
        ctx_data = REQUEST_CONTEXT.get() or {}
        if ctx_data.get("x-request-id"):
            response.headers["X-Request-Id"] = ctx_data["x-request-id"]
        if ctx_data.get("x-workspace-id"):
            response.headers["X-Workspace-Id"] = ctx_data["x-workspace-id"]

        return OrchestratorResponseModel(
            assistant=orchestrator_resp.assistant,
            slots=slots_out,
            tool_calls=orchestrator_resp.tool_calls,
            context_used=orchestrator_resp.context_used,
            next_action=orchestrator_resp.next_action.value,
            end=orchestrator_resp.end,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Error en decide_next_step")
        rid = ctx.request_id
        raise HTTPException(status_code=500, detail=f"Error interno. request_id={rid}")

@app.get("/orchestrator/policies/{vertical}", tags=["orchestrator"])
async def get_policies(vertical: Vertical):
    try:
        cfg = orchestrator_service.policy_engine.vertical_configs.get(vertical)
        if not cfg:
            raise not_found_error(f"Vertical {vertical}")
        return {
            "vertical": vertical,
            "required_slots": cfg.get("required_slots", []),
            "optional_slots": cfg.get("optional_slots", []),
            "max_attempts": cfg.get("max_attempts", 3),
            "needs_rag_before_action": cfg.get("needs_rag_before_action", True),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error obteniendo políticas")
        raise internal_error(ErrorMessages.INTERNAL_ERROR)

@app.get("/orchestrator/actions", response_model=ActionsInfo, tags=["orchestrator"])
async def get_available_actions():
    return ActionsInfo(
        actions=[{"name": a.value, "description": _get_action_description(a)} for a in NextAction]
    )

@app.post("/orchestrator/test", tags=["orchestrator"])
async def test_orchestrator(ctx: APIRequestContext = Depends(build_context)):
    try:
        test_snapshot = ConversationSnapshot(
            conversation_id="test-123",
            vertical="gastronomia",
            user_input="Hola, quiero hacer un pedido",
            greeted=False,
            slots={},
            objective="tomar_pedido",
            attempts_count=0,
        )
        resp = await orchestrator_service.decide(test_snapshot)
        return {
            "test": "success",
            "request_id": ctx.request_id,
            "input": test_snapshot.user_input,
            "output": {
                "assistant": resp.assistant,
                "next_action": resp.next_action.value,
                "slots": resp.slots,
            },
        }
    except Exception:
        logger.exception("Error en test")
        raise internal_error("Error en test", ctx.request_id)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _get_action_description(action: NextAction) -> str:
    descriptions = {
        NextAction.GREET: "Saludo inicial al usuario",
        NextAction.SLOT_FILL: "Recolección de información requerida",
        NextAction.RETRIEVE_CONTEXT: "Búsqueda de contexto en RAG",
        NextAction.EXECUTE_ACTION: "Ejecución de acción de negocio",
        NextAction.ANSWER: "Respuesta general al usuario",
        NextAction.ASK_HUMAN: "Escalamiento a agente humano",
    }
    return descriptions.get(action, "Acción no documentada")

if __name__ == "__main__":
    import uvicorn
    # Asegurate que el archivo se llama orchestrator_api.py.
    # Si tu archivo se llama distinto, cambiá el módulo en la siguiente línea.
    uvicorn.run("orchestrator_api:app", host="0.0.0.0", port=8005, reload=True, log_level="info")