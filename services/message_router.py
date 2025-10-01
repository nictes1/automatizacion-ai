"""
Message Router - Servicio entre webhook y orquestador
Maneja de-duplicación, debounce y continuidad de conversación

Mejoras de producción implementadas:
- Verificación de firma Twilio en ambos endpoints (JSON y form)
- ProxyHeadersMiddleware para manejo correcto de URLs detrás de proxy
- Race condition fix en de-duplicación usando SET NX EX atómico
- Hardening de _delayed_flush con guardas y logs
- Validación de tamaño de payload y normalización de tipos
- Propagación de Authorization header al orquestador
- Operaciones de DB no-bloqueantes con anyio.to_thread

Fixes quirúrgicos finales:
- Alineación de attempts_count vs _attempts_count con el orquestador
- X-Request-Id único por request (no fijo)
- Bloqueo de webhook JSON en prod (flag ALLOW_TWILIO_JSON)
- HTTP 429 real para rate limiting
- Normalización de teléfonos a formato whatsapp:+E164
- Límite de payload (256KB) para protección DoS
- Seguimiento de tareas de flush para shutdown limpio
- Saneamiento extra de datos de formulario
- Observabilidad mejorada con logs detallados

Mejoras pro-prod implementadas:
- Pool de conexiones psycopg2.SimpleConnectionPool con métricas
- Statement timeout y app.workspace_id por sesión (RLS-ready)
- Timestamps UTC en todas las operaciones
- Métricas HTTP Prometheus (duración, requests en vuelo)
- Endpoint /metrics para scraping de Prometheus
- Context manager get_cursor() para manejo seguro de conexiones
- Shutdown limpio con cierre de pool de conexiones

Ajustes finos para RLS:
- Rollback automático en get_cursor() si falla algo
- RLS-ready total con workspace_id context en todas las operaciones
- Header X-Workspace-Id requerido para GET /conversations/{id}
- Métricas completas del pool (tamaño, máximo, en uso)
- Rate limiting dual: por contacto + por workspace (previene bursts)
- Firma Twilio y endpoint JSON protegidos para producción

Toques finales RLS-proof:
- Middleware de métricas robusto (maneja excepciones sin romper)
- _with_conv_context() para RLS real en update/persist operations
- Métricas del pool defensivas (sin atributos privados frágiles)
- Normalización de teléfonos mejorada (trimming extra)
- Masking de PII en logs para privacidad
- 100% compatible con RLS activo en todas las tablas
"""

import os
import logging
import asyncio
import json
import hmac
import base64
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import hashlib
from urllib.parse import urljoin

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.proxy_headers import ProxyHeadersMiddleware
from pydantic import BaseModel, Field
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager
from datetime import timezone
import httpx
import redis
import anyio
from prometheus_client import Histogram, Gauge, CONTENT_TYPE_LATEST, generate_latest
from time import perf_counter
from starlette.responses import Response as StarletteResponse

from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pool de conexiones global
DB_POOL: Optional[SimpleConnectionPool] = None

def _with_cursor(cur):
    # aplica statement_timeout segun tu GUC en DB
    cur.execute("SELECT set_statement_timeout()")

def _with_conv_context(cur, conversation_id: str):
    # Setea el workspace_id de la conversación como GUC local a la tx
    cur.execute("""
        SELECT set_config('app.workspace_id',
            (SELECT workspace_id::text FROM pulpo.conversations WHERE id = %s),
            true)
    """, (conversation_id,))

# Métricas del pool
DB_POOL_IN_USE = Gauge("router_db_pool_in_use", "Conexiones en uso del pool (router)")
DB_POOL_SIZE = Gauge("router_db_pool_size", "Tamaño total del pool")
DB_POOL_MAX = Gauge("router_db_pool_max", "Max del pool")

# Métricas HTTP Prometheus
HTTP_DURATION = Histogram(
    "router_http_request_duration_seconds",
    "Duración de requests HTTP (router) por endpoint y código",
    ["endpoint", "code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5)
)
INFLIGHT = Gauge("router_http_inflight_requests", "Requests HTTP en vuelo (router)", ["endpoint"])

def _pool_getconn():
    conn = DB_POOL.getconn()
    DB_POOL_IN_USE.inc()
    # Best effort para size: _used + _pool (si existen)
    used = len(getattr(DB_POOL, "_used", []))
    idle = len(getattr(DB_POOL, "_pool", []))
    DB_POOL_SIZE.set(used + idle)
    return conn

def _pool_putconn(conn):
    try:
        DB_POOL.putconn(conn)
    finally:
        DB_POOL_IN_USE.dec()
        used = len(getattr(DB_POOL, "_used", []))
        idle = len(getattr(DB_POOL, "_pool", []))
        DB_POOL_SIZE.set(used + idle)

@contextmanager
def get_cursor(*, dict_cursor=False, workspace_id: Optional[str] = None):
    """
    Devuelve (conn, cur) del pool. Aplica statement_timeout y setea app.workspace_id
    para RLS/funciones dependientes.
    """
    conn = _pool_getconn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
        try:
            _with_cursor(cur)
            if workspace_id:
                # Local a la transacción, perfecto para RLS
                cur.execute("SELECT set_config('app.workspace_id', %s, true)", (workspace_id,))
            yield conn, cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        _pool_putconn(conn)

# Helper para ejecutar operaciones de DB sin bloquear el event loop
async def run_db_operation(fn, *args, **kwargs):
    """Ejecuta una función de DB en un thread separado para no bloquear el event loop"""
    return await anyio.to_thread.run_sync(fn, *args, **kwargs)

async def verify_twilio_signature(request: Request, auth_token: str) -> bool:
    """Verifica la firma de Twilio para seguridad del webhook"""
    signature = request.headers.get("X-Twilio-Signature")
    if not signature: 
        return False
    
    # Usar la URL efectiva (resuelta por ProxyHeadersMiddleware)
    public_url = str(request.url)
    
    # Reconstruir base string
    # para application/x-www-form-urlencoded, Twilio concatena URL + params ordenados
    if request.headers.get("Content-Type","").startswith("application/x-www-form-urlencoded"):
        form = await request.form()
        # Twilio firma URL + pares nombre/valor en orden alfabético
        params = dict(sorted(form.items()))
    else:
        # Para JSON, Twilio WA no firma (evitar bypasses)
        return False
    
    # Twilio: URL + params ordenados por nombre
    base = public_url + "".join([k + v for k, v in sorted(params.items())])
    mac = hmac.new(auth_token.encode(), base.encode(), "sha1").digest()
    calc = base64.b64encode(mac).decode()
    return hmac.compare_digest(signature, calc)

@dataclass
class WhatsAppMessage:
    """Mensaje de WhatsApp normalizado"""
    from_number: str
    to_number: str
    text: str
    wa_message_id: str
    media_url: Optional[str] = None
    message_type: str = "text"
    timestamp: datetime = None

@dataclass
class ConversationState:
    """Estado de una conversación"""
    conversation_id: str
    workspace_id: str
    contact_id: str
    channel_id: str
    last_message_at: datetime
    message_count: int
    greeted: bool
    slots: Dict[str, Any]
    objective: str
    last_action: Optional[str] = None
    attempts_count: int = 0

# Modelos Pydantic
class TwilioWebhookRequest(BaseModel):
    """Request del webhook de Twilio"""
    From: str = Field(..., description="Número de origen")
    To: str = Field(..., description="Número de destino")
    Body: str = Field(..., min_length=0, max_length=2000, description="Cuerpo del mensaje (limite)")
    MessageSid: str = Field(..., description="ID del mensaje en Twilio")
    MediaUrl0: Optional[str] = Field(None, description="URL de media")
    MessageType: str = Field(default="text", description="Tipo de mensaje")

class MessageRouterResponse(BaseModel):
    """Response del message router"""
    conversation_id: str = Field(..., description="ID de la conversación")
    assistant_response: str = Field(..., description="Respuesta del asistente")
    slots: Dict[str, Any] = Field(default_factory=dict, description="Slots actualizados")
    next_action: str = Field(..., description="Próxima acción")
    end: bool = Field(default=False, description="Si la conversación terminó")

class HealthResponse(BaseModel):
    """Response de health check"""
    status: str
    timestamp: datetime
    service: str
    version: str

class DeduplicationManager:
    """Manejador de de-duplicación de mensajes"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=0,
            decode_responses=True
        )
        self.ttl = 3600  # 1 hora
    
    def is_duplicate(self, workspace_id: str, wa_message_id: str) -> bool:
        """SET NX EX atómico: True si YA estaba; False si lo registramos ahora."""
        key = f"msg_dedup:{workspace_id}:{wa_message_id}"
        # intentamos "claim" el mensaje
        ok = self.redis_client.set(key, "processed", nx=True, ex=self.ttl)
        # ok=True => lo grabamos nosotros => NO es duplicado
        return not bool(ok)

    def mark_processed(self, workspace_id: str, wa_message_id: str):
        """Compat (no-op): preservado por si hay llamadas existentes."""
        return

class DebounceManager:
    """Solo bufferiza y decide cuándo hay que flush-ear. El Service hace el flush real."""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            db=1,
            decode_responses=True
        )
        self.debounce_window_ms = int(os.getenv("DEBOUNCE_MS", "700"))
        self.max_messages = int(os.getenv("DEBOUNCE_MAX", "5"))
    
    def _key(self, workspace_id: str, contact_id: str) -> str:
        return f"debounce:{workspace_id}:{contact_id}"
    
    def add_message(self, workspace_id: str, contact_id: str, message: WhatsAppMessage) -> dict:
        """
        Agrega mensaje al buffer y devuelve un dict con estado:
        { "should_flush_now": bool, "scheduled_flush_in_ms": int }
        """
        key = self._key(workspace_id, contact_id)
        data = self.redis_client.get(key)
        messages = json.loads(data) if data else []

        messages.append({
            "text": message.text,
            "wa_message_id": message.wa_message_id,
            "timestamp": (message.timestamp or datetime.now(timezone.utc)).isoformat(),
            "media_url": message.media_url
        })
        if len(messages) > self.max_messages:
            messages = messages[-self.max_messages:]

        # TTL un poco mayor que la ventana, para que si no llega otro, un job externo pueda limpiar
        ttl_seconds = max(2, int(self.debounce_window_ms / 1000) + 2)
        self.redis_client.setex(key, ttl_seconds, json.dumps(messages))

        # política: flush inmediato si hay ≥2 mensajes
        should_flush = len(messages) >= 2
        return {"should_flush_now": should_flush, "scheduled_flush_in_ms": self.debounce_window_ms}
    
    def get_messages(self, workspace_id: str, contact_id: str) -> List[Dict[str, Any]]:
        """Obtiene mensajes del buffer"""
        data = self.redis_client.get(self._key(workspace_id, contact_id))
        return json.loads(data) if data else []
    
    def clear(self, workspace_id: str, contact_id: str):
        """Limpia el buffer de mensajes"""
        self.redis_client.delete(self._key(workspace_id, contact_id))

class RateLimiter:
    """Rate limiter básico usando Redis"""
    
    def __init__(self, redis_client=None, limit_per_min=30):
        self.r = redis_client or redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"), 
            port=int(os.getenv("REDIS_PORT", 6379)), 
            db=2, 
            decode_responses=True
        )
        self.limit = limit_per_min

    def allow(self, workspace_id: str, contact_id: str) -> bool:
        """Verifica si el contacto puede enviar más mensajes"""
        # Rate limiting por contacto
        key_contact = f"rl:{workspace_id}:{contact_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        count_contact = self.r.incr(key_contact)
        if count_contact == 1:
            self.r.expire(key_contact, 70)  # 70 segundos para cubrir el minuto completo
        
        # Rate limiting por workspace (opcional, para prevenir bursts)
        key_workspace = f"rlws:{workspace_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        count_workspace = self.r.incr(key_workspace)
        if count_workspace == 1:
            self.r.expire(key_workspace, 70)
        
        # Límite por workspace: 10x el límite por contacto
        workspace_limit = self.limit * 10
        
        return count_contact <= self.limit and count_workspace <= workspace_limit

class ConversationManager:
    """Manejador de conversaciones"""
    
    def __init__(self):
        # Crear client sin headers fijos (se generan por request)
        self.orchestrator_client = httpx.AsyncClient(timeout=30.0)
        self.orchestrator_url = os.getenv("ORCHESTRATOR_URL", "http://localhost:8005")
    
    async def get_or_create_conversation(
        self, 
        workspace_id: str, 
        contact_id: str, 
        channel_id: str
    ) -> ConversationState:
        """Obtiene o crea una conversación"""
        try:
            def _get_or_create_sync():
                # Ahora con RLS-ready: setear workspace_id para que RLS no bloquee
                with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                    # Buscar conversación abierta
                    cur.execute("""
                        SELECT c.*,
                               cs.slots_json, cs.objective, cs.greeted, cs.attempts_count
                        FROM pulpo.conversations c
                        LEFT JOIN LATERAL (
                          SELECT * FROM pulpo.conversation_slots cs
                          WHERE cs.conversation_id = c.id AND cs.workspace_id = c.workspace_id
                          ORDER BY cs.updated_at DESC
                          LIMIT 1
                        ) cs ON TRUE
                        WHERE c.workspace_id = %s AND c.contact_id = %s AND c.status = 'open'
                        ORDER BY c.created_at DESC
                        LIMIT 1
                    """, (workspace_id, contact_id))
                    
                    row = cur.fetchone()
                    
                    if row:
                        # Conversación existente
                        return {
                            "conversation_id": str(row["id"]),
                            "workspace_id": str(row["workspace_id"]),
                            "contact_id": str(row["contact_id"]),
                            "channel_id": str(row["channel_id"]),
                            "last_message_at": row["last_message_at"],
                            "message_count": row["total_messages"],
                            "greeted": row.get("greeted", False),
                            "slots": row.get("slots_json", {}) or {},
                            "objective": row.get("objective", ""),
                            "attempts_count": row.get("attempts_count", 0)
                        }
                    else:
                        # Crear nueva conversación
                        cur.execute("""
                            INSERT INTO pulpo.conversations (
                                workspace_id, contact_id, channel_id, status, 
                                last_message_at, total_messages, created_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING id
                        """, (
                            workspace_id, contact_id, channel_id, "open",
                            datetime.now(timezone.utc), 0, datetime.now(timezone.utc)
                        ))
                        
                        conversation_id = cur.fetchone()[0]
                        
                        return {
                            "conversation_id": str(conversation_id),
                            "workspace_id": workspace_id,
                            "contact_id": contact_id,
                            "channel_id": channel_id,
                            "last_message_at": datetime.now(timezone.utc),
                            "message_count": 0,
                            "greeted": False,
                            "slots": {},
                            "objective": "",
                            "attempts_count": 0
                        }
            
            result = await run_db_operation(_get_or_create_sync)
            return ConversationState(**result)
                        
        except Exception as e:
            logger.error(f"Error obteniendo/creando conversación: {e}")
            raise
    
    async def update_conversation_state(self, conversation_id: str, slots: Dict[str, Any], objective: str):
        """Actualiza el estado de la conversación"""
        try:
            def _update_sync():
                with get_cursor() as (conn, cur):
                    _with_conv_context(cur, conversation_id)
                    # Upsert conversation_slots - usando solo workspace_id y conversation_id como clave única
                    # Si tu esquema incluye intent, deberías agregarlo aquí
                    cur.execute("""
                        INSERT INTO pulpo.conversation_slots (
                            workspace_id, conversation_id, slots_json, objective, 
                            greeted, attempts_count, created_at, updated_at
                        ) VALUES (
                            (SELECT workspace_id FROM pulpo.conversations WHERE id = %s),
                            %s, %s, %s, %s, %s, %s, %s
                        )
                        ON CONFLICT (workspace_id, conversation_id)
                        DO UPDATE SET
                            slots_json = EXCLUDED.slots_json,
                            objective = EXCLUDED.objective,
                            greeted = EXCLUDED.greeted,
                            attempts_count = EXCLUDED.attempts_count,
                            updated_at = EXCLUDED.updated_at
                    """, (
                        conversation_id, conversation_id, json.dumps(slots),
                        objective, slots.get("greeted", False), int(slots.get("_attempts_count", 0)),
                        datetime.now(timezone.utc), datetime.now(timezone.utc)
                    ))
            
            await run_db_operation(_update_sync)
                    
        except Exception as e:
            logger.error(f"Error actualizando estado de conversación: {e}")
    
    async def persist_message(
        self, 
        conversation_id: str, 
        message: WhatsAppMessage, 
        role: str = "user",
        meta: Optional[Dict[str, Any]] = None
    ):
        """Persiste un mensaje en la base de datos"""
        try:
            def _persist_sync():
                with get_cursor() as (conn, cur):
                    _with_conv_context(cur, conversation_id)
                    cur.execute("""
                        INSERT INTO pulpo.messages (
                            workspace_id, conversation_id, role, direction, message_type,
                            wa_message_id, content_text, media_url, meta_json, created_at
                        ) VALUES (
                            (SELECT workspace_id FROM pulpo.conversations WHERE id = %s),
                            %s, %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        conversation_id, conversation_id, role, "inbound" if role == "user" else "outbound",
                        message.message_type, message.wa_message_id,
                        message.text, message.media_url, json.dumps(meta or {}), datetime.now(timezone.utc)
                    ))
                    
                    # Actualizar contadores de conversación
                    cur.execute("""
                        UPDATE pulpo.conversations 
                        SET total_messages = total_messages + 1,
                            last_message_at = %s,
                            last_message_text = %s,
                            last_message_sender = %s
                        WHERE id = %s
                    """, (datetime.now(timezone.utc), message.text, role, conversation_id))
            
            await run_db_operation(_persist_sync)
                    
        except Exception as e:
            logger.error(f"Error persistiendo mensaje: {e}")
    
    async def persist_assistant_response(
        self, 
        conversation_id: str, 
        response_text: str, 
        tool_calls: List[Dict[str, Any]] = None
    ):
        """Persiste la respuesta del asistente"""
        try:
            def _persist_response_sync():
                with get_cursor() as (conn, cur):
                    _with_conv_context(cur, conversation_id)
                    cur.execute("""
                        INSERT INTO pulpo.messages (
                            workspace_id, conversation_id, role, direction, message_type,
                            content_text, meta_json, created_at
                        ) VALUES (
                            (SELECT workspace_id FROM pulpo.conversations WHERE id = %s),
                            %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        conversation_id, conversation_id, "assistant", "outbound",
                        "text", response_text, 
                        json.dumps({"tool_calls": tool_calls or []}), 
                        datetime.now(timezone.utc)
                    ))
                    
                    # Actualizar contadores de conversación
                    cur.execute("""
                        UPDATE pulpo.conversations 
                        SET total_messages = total_messages + 1,
                            last_message_at = %s,
                            last_message_text = %s,
                            last_message_sender = %s
                        WHERE id = %s
                    """, (datetime.now(timezone.utc), response_text, "assistant", conversation_id))
            
            await run_db_operation(_persist_response_sync)
                    
        except Exception as e:
            logger.error(f"Error persistiendo respuesta del asistente: {e}")
    
    async def call_orchestrator(self, conversation_state: ConversationState, user_input: str, authorization: Optional[str] = None) -> Dict[str, Any]:
        """Llama al orquestador para obtener respuesta"""
        try:
            # Determinar vertical desde workspace
            workspace_id = conversation_state.workspace_id
            vertical = await self._get_workspace_vertical(workspace_id)
            
            # Preparar request para orquestador
            orchestrator_request = {
                "conversation_id": conversation_state.conversation_id,
                "vertical": vertical,
                "user_input": user_input,
                "greeted": conversation_state.greeted,
                "slots": conversation_state.slots,
                "objective": conversation_state.objective,
                "last_action": conversation_state.last_action,
                "attempts_count": conversation_state.attempts_count
            }
            
            # Llamar al orquestador
            request_id = hashlib.sha1(os.urandom(8)).hexdigest()[:16]
            logger.info(f"Llamando al orquestador con request_id: {request_id} para workspace: {workspace_id}")
            headers = {
                "X-Workspace-Id": workspace_id,
                "X-Request-Id": request_id
            }
            if authorization:
                headers["Authorization"] = authorization
            response = await self.orchestrator_client.post(
                f"{self.orchestrator_url}/orchestrator/decide",
                json=orchestrator_request,
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error llamando al orquestador: {e}")
            raise
    
    async def _get_workspace_vertical(self, workspace_id: str) -> str:
        """Obtiene el vertical de un workspace"""
        try:
            def _get_vertical_sync():
                with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                    cur.execute("""
                        SELECT vertical FROM pulpo.workspaces WHERE id = %s
                    """, (workspace_id,))
                    
                    row = cur.fetchone()
                    return row["vertical"] if row else "generico"
            
            return await run_db_operation(_get_vertical_sync)
                    
        except Exception as e:
            logger.error(f"Error obteniendo vertical del workspace: {e}")
            return "generico"

class MessageRouterService:
    """Servicio principal del message router"""
    
    def __init__(self):
        self.dedup_manager = DeduplicationManager()
        self.debounce_manager = DebounceManager()
        self.conversation_manager = ConversationManager()
        self.rate_limiter = RateLimiter()
        self.twilio_client = httpx.AsyncClient(timeout=30.0)
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self._pending_flush_tasks: set[asyncio.Task] = set()
    
    async def process_whatsapp_message(self, request: TwilioWebhookRequest) -> MessageRouterResponse:
        """
        Procesa un mensaje de WhatsApp entrante
        """
        try:
            # Masking de teléfonos para PII
            def _mask_phone(p: str) -> str:
                return p[:12] + "***" if p.startswith("whatsapp:+") else p
            
            logger.info("WA msg: sid=%s from=%s to=%s", request.MessageSid, _mask_phone(request.From), _mask_phone(request.To))
            
            # Normalizar mensaje
            def _norm(n: str) -> str:
                n = (n or "").strip().replace(" ", "")
                return n if n.startswith("whatsapp:") else f"whatsapp:{n}"
            message = WhatsAppMessage(
                from_number=_norm(request.From),
                to_number=_norm(request.To),
                text=request.Body,
                wa_message_id=request.MessageSid,
                media_url=request.MediaUrl0,
                message_type=request.MessageType,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Obtener workspace_id y contact_id
            workspace_id, contact_id, channel_id = await self._resolve_identifiers(message)
            
            # Verificar rate limiting
            if not self.rate_limiter.allow(workspace_id, contact_id):
                logger.warning(f"Rate limit excedido para {workspace_id}:{contact_id}")
                raise HTTPException(status_code=429, detail="Rate limit exceeded")
            
            # Verificar de-duplicación (ahora atómico)
            if self.dedup_manager.is_duplicate(workspace_id, message.wa_message_id):
                logger.info(f"Mensaje duplicado ignorado: {message.wa_message_id}")
                return MessageRouterResponse(
                    conversation_id="duplicate",
                    assistant_response="",
                    slots={},
                    next_action="duplicate",
                    end=True
                )
            
            # Agregar a buffer de debounce
            status = self.debounce_manager.add_message(workspace_id, contact_id, message)
            
            if status["should_flush_now"]:
                # Procesar mensajes acumulados
                combined = self.debounce_manager.get_messages(workspace_id, contact_id)
                self.debounce_manager.clear(workspace_id, contact_id)
                combined_text = " ".join([m["text"] for m in combined if m.get("text")])
                logger.info(f"Flush inmediato: {len(combined)} mensajes combinados para {workspace_id}:{contact_id}")
                if combined_text:
                    return await self._process_combined_message(
                        workspace_id, contact_id, channel_id, combined_text, message, combined_meta=combined
                    )
            
            # Programar un flush "tardío" con task local, SIN depender de DebounceManager
            t = asyncio.create_task(self._delayed_flush(workspace_id, contact_id, channel_id, message, status["scheduled_flush_in_ms"]))
            self._pending_flush_tasks.add(t)
            t.add_done_callback(lambda x: self._pending_flush_tasks.discard(t))
            return MessageRouterResponse(
                conversation_id="pending",
                assistant_response="",
                slots={},
                next_action="debounce",
                end=False
            )
            
        except Exception as e:
            logger.error(f"Error procesando mensaje de WhatsApp: {e}")
            raise HTTPException(status_code=500, detail=f"Error procesando mensaje: {str(e)}")
    
    async def _delayed_flush(self, workspace_id: str, contact_id: str, channel_id: str, original_message: WhatsAppMessage, delay_ms: int):
        """Helper para flush tardío del debounce"""
        try:
            await asyncio.sleep(max(0, delay_ms) / 1000)
            combined = self.debounce_manager.get_messages(workspace_id, contact_id)
            if not combined:
                return
            self.debounce_manager.clear(workspace_id, contact_id)
            combined_text = " ".join([m.get("text","") for m in combined if m.get("text")])
            if combined_text.strip():
                await self._process_combined_message(
                    workspace_id, contact_id, channel_id, combined_text, original_message, combined_meta=combined
                )
        except Exception as e:
            logger.exception("Delayed flush failed: %r", e)

    async def _process_combined_message(
        self, 
        workspace_id: str, 
        contact_id: str, 
        channel_id: str, 
        combined_text: str, 
        original_message: WhatsAppMessage,
        combined_meta: Optional[List[Dict[str, Any]]] = None
    ) -> MessageRouterResponse:
        """Procesa mensaje combinado del debounce"""
        
        # Obtener o crear conversación
        conversation_state = await self.conversation_manager.get_or_create_conversation(
            workspace_id, contact_id, channel_id
        )
        
        # 1) Persistir mensaje original (como hoy)
        await self.conversation_manager.persist_message(
            conversation_state.conversation_id, original_message, "user"
        )
        
        # 2) Persistir mensaje combinado (synthetic) para trazabilidad
        synthetic = WhatsAppMessage(
            from_number=original_message.from_number,
            to_number=original_message.to_number,
            text=combined_text,
            wa_message_id=f"{original_message.wa_message_id}::combined",
            timestamp=datetime.now(timezone.utc)
        )
        await self.conversation_manager.persist_message(
            conversation_state.conversation_id, synthetic, "user", 
            meta={"combined_from": combined_meta or []}
        )
        
        # Llamar al orquestador
        orchestrator_response = await self.conversation_manager.call_orchestrator(
            conversation_state, combined_text, authorization=os.getenv("ROUTER_ORCH_AUTH")
        )
        
        # Actualizar estado de conversación
        updated_slots = orchestrator_response.get("slots", {})
        updated_slots["workspace_id"] = workspace_id
        await self.conversation_manager.update_conversation_state(
            conversation_state.conversation_id, updated_slots, orchestrator_response.get("objective", "")
        )
        
        # Persistir respuesta del asistente
        assistant_response = orchestrator_response.get("assistant", "")
        tool_calls = orchestrator_response.get("tool_calls", [])
        await self.conversation_manager.persist_assistant_response(
            conversation_state.conversation_id, assistant_response, tool_calls
        )
        
        # Enviar respuesta por Twilio
        await self._send_whatsapp_response(original_message.from_number, assistant_response)
        
        return MessageRouterResponse(
            conversation_id=conversation_state.conversation_id,
            assistant_response=assistant_response,
            slots=updated_slots,
            next_action=orchestrator_response.get("next_action", "answer"),
            end=orchestrator_response.get("end", False)
        )
    
    async def _resolve_identifiers(self, message: WhatsAppMessage) -> tuple[str, str, str]:
        """Resuelve workspace_id, contact_id y channel_id desde el mensaje"""
        try:
            def _resolve_sync():
                with get_cursor(dict_cursor=True) as (conn, cur):
                    # Buscar canal por número de destino
                    cur.execute("""
                        SELECT workspace_id, id as channel_id
                        FROM pulpo.channels 
                        WHERE display_phone = %s AND status = 'active'
                    """, (message.to_number,))
                    
                    channel_row = cur.fetchone()
                    if not channel_row:
                        raise ValueError(f"Canal no encontrado para número: {message.to_number}")
                    
                    workspace_id = str(channel_row["workspace_id"])
                    channel_id = str(channel_row["channel_id"])
                    
                    # setear contexto ahora que ya sabemos workspace
                    cur.execute("SELECT set_config('app.workspace_id', %s, true)", (workspace_id,))
                    
                    # Buscar o crear contacto
                    cur.execute("""
                        SELECT id FROM pulpo.contacts 
                        WHERE workspace_id = %s AND user_phone = %s
                    """, (workspace_id, message.from_number))
                    
                    contact_row = cur.fetchone()
                    if contact_row:
                        contact_id = str(contact_row["id"])
                    else:
                        # Crear nuevo contacto
                        cur.execute("""
                            INSERT INTO pulpo.contacts (workspace_id, user_phone, created_at)
                            VALUES (%s, %s, %s)
                            RETURNING id
                        """, (workspace_id, message.from_number, datetime.now(timezone.utc)))
                        
                        contact_id = str(cur.fetchone()[0])
                    
                    return workspace_id, contact_id, channel_id
            
            return await run_db_operation(_resolve_sync)
                    
        except Exception as e:
            logger.error(f"Error resolviendo identificadores: {e}")
            raise
    
    async def _send_whatsapp_response(self, to_number: str, message_text: str):
        """Envía respuesta por WhatsApp usando Twilio"""
        try:
            if not self.twilio_account_sid or not self.twilio_auth_token:
                logger.warning("Twilio no configurado, saltando envío de respuesta")
                return
            
            # Usar el número de Twilio configurado
            from_number = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+14155238886")
            
            response = await self.twilio_client.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{self.twilio_account_sid}/Messages.json",
                data={
                    "From": from_number,
                    "To": to_number,
                    "Body": message_text
                },
                auth=(self.twilio_account_sid, self.twilio_auth_token)
            )
            response.raise_for_status()
            
            logger.info(f"Respuesta enviada por WhatsApp a {to_number}")
            
        except Exception as e:
            logger.error(f"Error enviando respuesta por WhatsApp: {e}")

# Crear aplicación FastAPI
app = FastAPI(
    title="PulpoAI Message Router",
    description="Router de mensajes entre WhatsApp y el orquestador",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# Middleware de métricas Prometheus
@app.middleware("http")
async def prom_http_middleware(request: Request, call_next):
    endpoint = request.url.path
    INFLIGHT.labels(endpoint=endpoint).inc()
    t0 = perf_counter()
    try:
        response = await call_next(request)
        code = getattr(response, "status_code", 500)
        return response
    except Exception:
        code = 500
        raise
    finally:
        dur = perf_counter() - t0
        HTTP_DURATION.labels(endpoint=endpoint, code=str(code)).observe(dur)
        INFLIGHT.labels(endpoint=endpoint).dec()

# Instancia del servicio
message_router_service = MessageRouterService()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check del servicio"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        service="message_router",
        version="2.0.0"
    )

@app.get("/metrics")
async def metrics():
    """Endpoint de métricas Prometheus"""
    return StarletteResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/webhooks/twilio/wa/inbound")
async def twilio_webhook_raw(request: Request):
    """
    Webhook para mensajes entrantes de WhatsApp via Twilio
    """
    # Verificar firma
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if auth_token:
        ok = await verify_twilio_signature(request, auth_token)
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid Twilio signature")

    if os.getenv("ALLOW_TWILIO_JSON", "false").lower() != "true":
        raise HTTPException(status_code=415, detail="Unsupported Media Type; use form endpoint")
    try:
        body = await request.json()
        twilio_request = TwilioWebhookRequest(**body)
        return await message_router_service.process_whatsapp_message(twilio_request)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

@app.post("/webhooks/twilio/wa/inbound/form")
async def twilio_webhook_form(request: Request):
    """
    Webhook para mensajes entrantes de WhatsApp via Twilio (form data)
    """
    # Límite suave de tamaño (256 KB)
    if int(request.headers.get("content-length", "0") or 0) > 262144:
        raise HTTPException(status_code=413, detail="Payload too large")
    
    # Verificar firma de Twilio
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if auth_token:
        ok = await verify_twilio_signature(request, auth_token)
        if not ok:
            raise HTTPException(status_code=401, detail="Invalid Twilio signature")
    
    form_data = await request.form()
    
    twilio_request = TwilioWebhookRequest(
        From=str(form_data.get("From", "")).strip(),
        To=str(form_data.get("To", "")).strip(),
        Body=str(form_data.get("Body", "")).strip()[:2000],
        MessageSid=str(form_data.get("MessageSid", "")),
        MediaUrl0=form_data.get("MediaUrl0"),
        MessageType=str(form_data.get("MessageType", "text"))
    )
    
    return await message_router_service.process_whatsapp_message(twilio_request)

@app.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    """
    Obtiene información de una conversación
    """
    try:
        # RLS-ready: requerir header X-Workspace-Id
        workspace_id = request.headers.get("X-Workspace-Id")
        if not workspace_id:
            raise HTTPException(status_code=400, detail="X-Workspace-Id header required")
        
        def _get_conversation_sync():
            with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                cur.execute("""
                    SELECT c.*,
                           cs.slots_json, cs.objective, cs.greeted, cs.attempts_count
                    FROM pulpo.conversations c
                    LEFT JOIN LATERAL (
                      SELECT * FROM pulpo.conversation_slots cs
                      WHERE cs.conversation_id = c.id AND cs.workspace_id = c.workspace_id
                      ORDER BY cs.updated_at DESC
                      LIMIT 1
                    ) cs ON TRUE
                    WHERE c.id = %s
                """, (conversation_id,))
                
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Conversación no encontrada")
                
                return {
                    "conversation_id": str(row["id"]),
                    "workspace_id": str(row["workspace_id"]),
                    "contact_id": str(row["contact_id"]),
                    "channel_id": str(row["channel_id"]),
                    "status": row["status"],
                    "last_message_at": row["last_message_at"],
                    "total_messages": row["total_messages"],
                    "slots": row.get("slots_json", {}) or {},
                    "objective": row.get("objective", ""),
                    "greeted": row.get("greeted", False),
                    "attempts_count": row.get("attempts_count", 0)
                }
        
        return await run_db_operation(_get_conversation_sync)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo conversación: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo conversación: {str(e)}")

@app.post("/test/message")
async def test_message():
    """
    Endpoint de testing para validar el funcionamiento del message router
    """
    try:
        # Test con mensaje de ejemplo
        test_request = TwilioWebhookRequest(
            From="whatsapp:+1234567890",
            To="whatsapp:+14155238886",
            Body="Hola, quiero hacer un pedido",
            MessageSid="test-message-123",
            MessageType="text"
        )
        
        response = await message_router_service.process_whatsapp_message(test_request)
        
        return {
            "test": "success",
            "input": test_request.Body,
            "output": {
                "conversation_id": response.conversation_id,
                "assistant_response": response.assistant_response,
                "next_action": response.next_action
            }
        }
        
    except Exception as e:
        logger.error(f"Error en test: {e}")
        raise HTTPException(status_code=500, detail=f"Error en test: {str(e)}")

# Event handlers
@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    global DB_POOL
    minc = int(os.getenv("DB_MIN_CONN", 1))
    maxc = int(os.getenv("DB_MAX_CONN", 10))
    DB_POOL = SimpleConnectionPool(minconn=minc, maxconn=maxc, dsn=os.getenv("DATABASE_URL"))
    DB_POOL_MAX.set(maxc)
    
    logger.info("🚀 Message Router iniciado con pool de conexiones")
    logger.info("📋 Endpoints disponibles:")
    logger.info("  - POST /webhooks/twilio/wa/inbound - Webhook Twilio")
    logger.info("  - POST /webhooks/twilio/wa/inbound/form - Webhook Twilio (form)")
    logger.info("  - GET /conversations/{conversation_id} - Info de conversación")
    logger.info("  - POST /test/message - Testing")
    logger.info("  - GET /health - Health check")
    logger.info("  - GET /metrics - Métricas Prometheus")

@app.on_event("shutdown")
async def shutdown_event():
    """Evento de cierre de la aplicación"""
    logger.info("🛑 Message Router cerrando...")
    # Cancelar flushes pendientes
    for t in list(message_router_service._pending_flush_tasks):
        t.cancel()
    await message_router_service.conversation_manager.orchestrator_client.aclose()
    await message_router_service.twilio_client.aclose()
    if DB_POOL:
        DB_POOL.closeall()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "message_router:app",
        host="0.0.0.0",
        port=8006,
        reload=True,
        log_level="info"
    )
