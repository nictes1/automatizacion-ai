"""
Actions Service - Servicio para ejecutar acciones de negocio
Implementa acciones idempotentes para diferentes verticales
"""

import os
import logging
import hashlib
import json
from typing import Dict, List, Any, Optional, Tuple, Literal
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from time import perf_counter
# from prometheus_client import Counter, Histogram, Gauge, CONTENT_TYPE_LATEST, generate_latest
# from starlette.responses import Response as StarletteResponse
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator, ValidationError
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx
import anyio

from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Prometheus metrics (disabled for now) ---
# ACTIONS_REQUESTS = Counter(
#     "actions_requests_total",
#     "Requests totales por acción y resultado",
#     ["endpoint", "action", "result"]
# )
#
# ACTIONS_DURATION = Histogram(
#     "actions_duration_seconds",
#     "Duración de ejecución de acciones",
#     ["action", "result"],
#     buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10)
# )
#
# HTTP_DURATION = Histogram(
#     "http_request_duration_seconds",
#     "Duración de requests HTTP por endpoint y código",
#     ["endpoint", "code"],
#     buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5)
# )
#
# INFLIGHT = Gauge(
#     "http_inflight_requests",
#     "Requests HTTP en vuelo",
#     ["endpoint"]
# )
#
# POOL_IN_USE = Gauge(
#     "db_pool_in_use",
#     "Conexiones en uso del pool"
# )

# Pool de conexiones global
DB_POOL: Optional[SimpleConnectionPool] = None

def _pool_getconn():
    conn = DB_POOL.getconn()
    # POOL_IN_USE.inc()
    return conn

def _pool_putconn(conn):
    try:
        DB_POOL.putconn(conn)
    finally:
        pass
        # POOL_IN_USE.dec()

@contextmanager
def get_cursor(*, dict_cursor=False, workspace_id: Optional[str] = None):
    """
    Entrega (conn, cur) desde el pool, aplica statement_timeout
    y setea app.workspace_id para RLS/funciones dependientes.
    """
    conn = _pool_getconn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
        try:
            _with_cursor(cur)  # statement_timeout por sesión
            if workspace_id:
                cur.execute("SELECT set_config('app.workspace_id', %s, true)", (workspace_id,))
            yield conn, cur
            conn.commit()
        finally:
            cur.close()
    finally:
        _pool_putconn(conn)

class ActionStatus(Enum):
    """Estados de las acciones"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class ActionResult:
    """Resultado de una acción"""
    action_id: str
    status: ActionStatus
    summary: str
    details: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

# Modelos Pydantic para contexto de request
class RequestContext(BaseModel):
    """Contexto de la request con información de seguridad"""
    request_id: str
    workspace_id: str
    authorization: Optional[str] = None

# Modelos Pydantic específicos por acción
class PedidoItem(BaseModel):
    """Item de un pedido"""
    nombre: str = Field(..., description="Nombre del item")
    cantidad: int = Field(..., ge=1, description="Cantidad del item")
    precio: Optional[float] = Field(default=None, ge=0, description="Precio unitario (opcional si se calcula desde catálogo)")
    sku: Optional[str] = Field(default=None, description="SKU del producto")

class CrearPedidoPayload(BaseModel):
    """Payload para crear pedido"""
    conversation_id: str
    workspace_id: str
    items: List[PedidoItem]
    metodo_entrega: Literal["envio", "retira"]
    direccion: Optional[str] = None
    notas: Optional[str] = None

    @validator("direccion", always=True)
    def _require_address_for_envio(cls, v, values):
        if values.get("metodo_entrega") == "envio" and not v:
            raise ValueError('direccion es requerida cuando metodo_entrega="envio"')
        return v

class ScheduleVisitPayload(BaseModel):
    """Payload para agendar visita"""
    conversation_id: str
    workspace_id: str
    property_id: str
    preferred_date: datetime = Field(..., description="Fecha preferida (ISO)")
    contact_info: Dict[str, Any] = Field(..., description="Información de contacto")

class BookSlotPayload(BaseModel):
    """Payload para reservar turno"""
    conversation_id: str
    workspace_id: str
    service_type: str
    preferred_date: str = Field(..., description="Fecha preferida (YYYY-MM-DD)")
    preferred_time: str = Field(..., description="Hora preferida (HH:MM)")
    client_name: str = Field(..., description="Nombre del cliente")
    client_email: Optional[str] = Field(None, description="Email del cliente")
    client_phone: Optional[str] = Field(None, description="Teléfono del cliente")

# Modelos Pydantic
class ExecuteActionRequest(BaseModel):
    """Request para ejecutar una acción"""
    conversation_id: str = Field(..., description="ID de la conversación")
    action_name: str = Field(..., description="Nombre de la acción")
    payload: Dict[str, Any] = Field(..., description="Datos de la acción")
    idempotency_key: str = Field(..., description="Clave de idempotencia")

class ExecuteActionResponse(BaseModel):
    """Response para ejecutar una acción"""
    action_id: str = Field(..., description="ID de la acción")
    status: str = Field(..., description="Estado de la acción")
    summary: str = Field(..., description="Resumen de la acción")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detalles adicionales")
    created_at: datetime = Field(..., description="Fecha de creación")
    eta_minutes: Optional[int] = Field(None, description="ETA en minutos")

class ActionStatusResponse(BaseModel):
    """Response para consultar estado de acción"""
    action_id: str = Field(..., description="ID de la acción")
    status: str = Field(..., description="Estado actual")
    summary: str = Field(..., description="Resumen")
    details: Dict[str, Any] = Field(default_factory=dict, description="Detalles")
    created_at: datetime = Field(..., description="Fecha de creación")
    completed_at: Optional[datetime] = Field(None, description="Fecha de finalización")
    error_message: Optional[str] = Field(None, description="Mensaje de error")

class HealthResponse(BaseModel):
    """Response de health check"""
    status: str
    timestamp: datetime
    service: str
    version: str

# Funciones helper para DB async
async def db_exec(fn, *args, **kwargs):
    """Ejecuta función síncrona en thread separado para no bloquear event loop"""
    return await anyio.to_thread.run_sync(fn, *args, **kwargs)

def safe_json_loads(s: Any) -> Dict[str, Any]:
    """Carga JSON segura desde DB, siempre dict."""
    if isinstance(s, dict):
        return s
    try:
        data = json.loads(s) if isinstance(s, str) else {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}

def _money(x) -> float:
    """Convierte a float con redondeo a 2 decimales para dinero."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def _with_cursor(cur):
    """Aplica statement timeout al cursor"""
    # cur.execute("SELECT set_statement_timeout()")  # Function doesn't exist in current schema
    pass

def build_context(
    request: Request,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    authorization: Optional[str] = Header(None, alias="Authorization")
) -> RequestContext:
    """Construye contexto de request con información de seguridad"""
    rid = request.headers.get("X-Request-Id") or hashlib.sha1(os.urandom(8)).hexdigest()[:16]
    request.state.request_id = rid
    return RequestContext(
        request_id=rid, 
        workspace_id=x_workspace_id, 
        authorization=authorization
    )

class IdempotencyManager:
    """Manejador de idempotencia persistida en DB"""
    
    def generate_key(self, conversation_id: str, action_name: str, payload: Dict[str, Any]) -> str:
        """Genera clave de idempotencia"""
        payload_str = json.dumps(payload, sort_keys=True)
        key_data = f"{conversation_id}:{action_name}:{payload_str}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]
    
    def _insert_or_get_action(self, workspace_id: str, conversation_id: str, action_name: str, 
                             idem_key: str, initial_details: Dict[str, Any]):
        """Inserta nueva acción o obtiene existente con ON CONFLICT"""
        def _fn():
            with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                # Intentar insertar nueva acción
                cur.execute("""
                    INSERT INTO pulpo.action_executions
                        (workspace_id, conversation_id, action_name, idempotency_key, 
                         status, summary, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (workspace_id, idempotency_key) DO NOTHING
                    RETURNING id, status, summary, details, created_at, completed_at
                """, (
                    workspace_id, conversation_id, action_name, idem_key, 
                    "processing", "Acción aceptada", json.dumps(initial_details)
                ))
                row = cur.fetchone()
                if row:
                    return ("inserted", row)
                
                # Si no insertó, leer existente
                cur.execute("""
                    SELECT id, status, summary, details, created_at, completed_at
                    FROM pulpo.action_executions
                    WHERE workspace_id = %s AND idempotency_key = %s
                """, (workspace_id, idem_key))
                row = cur.fetchone()
                return ("existing", row)
        return _fn
    
    def _finish_action(self, action_id: str, status: str, summary: str, 
                      details: Dict[str, Any], completed_at: datetime):
        """Finaliza una acción actualizando su estado"""
        def _fn():
            with get_cursor(workspace_id=None) as (conn, cur):
                cur.execute("""
                    UPDATE pulpo.action_executions
                    SET status = %s, summary = %s, details = %s, completed_at = %s
                    WHERE id = %s
                """, (status, summary, json.dumps(details), completed_at, action_id))
        return _fn

class GastronomiaActions:
    """Acciones específicas para gastronomía"""

    def __init__(self):
        # self.n8n_client = httpx.AsyncClient(timeout=30.0)  # Not used currently
        self.n8n_base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678")
    
    async def crear_pedido(self, payload: Dict[str, Any]) -> ActionResult:
        """Crea un pedido de comida con validación y precios desde catálogo"""
        try:
            # Validar payload con Pydantic
            data = CrearPedidoPayload(**payload)
            
            # Resolver precios desde catálogo
            enriched_items, total = await db_exec(
                self._resolve_prices(data.items, data.workspace_id)
            )
            
            # Crear pedido en base de datos
            pedido_id = await self._persistir_pedido(data, enriched_items, total)
            
            return ActionResult(
                action_id=pedido_id,
                status=ActionStatus.SUCCESS,
                summary=f"Pedido #{pedido_id} creado exitosamente",
                details={
                    "pedido_id": pedido_id,
                    "total": total,
                    "items": enriched_items,
                    "metodo_entrega": data.metodo_entrega,
                    "eta_minutes": self._calcular_eta(data)
                },
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc)
            )
            
        except ValidationError:
            # Dejar que se propague como 422
            raise
        except Exception as e:
            logger.error(f"Error creando pedido: {e}")
            return ActionResult(
                action_id="error",
                status=ActionStatus.FAILED,
                summary="Error creando pedido",
                details={"error": str(e)},
                created_at=datetime.now(timezone.utc),
                error_message=str(e)
            )
    
    def _resolve_prices(self, items: List[PedidoItem], workspace_id: str):
        """Resuelve precios desde catálogo y calcula total"""
        def _fn():
            with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                total = Decimal("0.00")
                enriched = []
                for item in items:
                    # Buscar por SKU primero, luego por nombre
                    if item.sku:
                        cur.execute("""
                            SELECT name as nombre, price as precio FROM pulpo.menu_items
                            WHERE workspace_id = %s AND sku = %s AND is_active = true
                        """, (workspace_id, item.sku))
                    else:
                        cur.execute("""
                            SELECT name as nombre, price as precio FROM pulpo.menu_items
                            WHERE workspace_id = %s AND LOWER(name) = LOWER(%s) AND is_active = true
                            LIMIT 1
                        """, (workspace_id, item.nombre))
                    
                    row = cur.fetchone()
                    if not row:
                        raise ValueError(f"Item no encontrado en catálogo: {item.nombre}")
                    
                    precio = Decimal(str(row["precio"]))
                    subtotal = precio * Decimal(item.cantidad)
                    total += subtotal
                    
                    enriched.append({
                        "nombre": row["nombre"],
                        "cantidad": item.cantidad,
                        "precio_unit": _money(precio),
                        "subtotal": _money(subtotal),
                        "sku": item.sku
                    })
                
                return enriched, _money(total)
        return _fn
    
    def _calcular_eta(self, data: CrearPedidoPayload) -> int:
        """Calcula ETA del pedido en minutos"""
        items_count = len(data.items)
        base_time = 15  # 15 minutos base
        item_time = items_count * 2  # 2 minutos por item
        return base_time + item_time
    
    async def _persistir_pedido(self, data: CrearPedidoPayload, enriched_items: List[Dict[str, Any]], total: float) -> str:
        """Persiste el pedido en base de datos"""
        def _fn():
            with get_cursor(workspace_id=data.workspace_id) as (conn, cur):
                cur.execute("""
                    INSERT INTO pulpo.pedidos (
                        workspace_id, conversation_id, items,
                        metodo_entrega, direccion, total, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data.workspace_id,
                    data.conversation_id,
                    json.dumps(enriched_items),
                    data.metodo_entrega,
                    data.direccion,
                    total,
                    "draft",
                    datetime.now(timezone.utc)
                ))
                
                pedido_id = cur.fetchone()[0]
                return str(pedido_id)
        return await db_exec(_fn)

class InmobiliariaActions:
    """Acciones específicas para inmobiliaria"""

    def __init__(self):
        # self.n8n_client = httpx.AsyncClient(timeout=30.0)  # Not used currently
        self.n8n_base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678")
    
    async def schedule_visit(self, payload: Dict[str, Any]) -> ActionResult:
        """Agenda una visita a propiedad con validación"""
        try:
            # Validar payload con Pydantic
            data = ScheduleVisitPayload(**payload)
            
            # Verificar que la propiedad existe
            await self._validate_property(data.property_id, data.workspace_id)
            
            # Crear visita en base de datos
            visita_id = await self._persistir_visita(data)
            
            
            return ActionResult(
                action_id=visita_id,
                status=ActionStatus.SUCCESS,
                summary=f"Visita #{visita_id} agendada exitosamente",
                details={
                    "visita_id": visita_id,
                    "property_id": data.property_id,
                    "preferred_date": data.preferred_date,
                    "contact_info": data.contact_info,
                    "status": "scheduled"
                },
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc)
            )
            
        except ValidationError:
            # Dejar que se propague como 422
            raise
        except Exception as e:
            logger.error(f"Error agendando visita: {e}")
            return ActionResult(
                action_id="error",
                status=ActionStatus.FAILED,
                summary="Error agendando visita",
                details={"error": str(e)},
                created_at=datetime.now(timezone.utc),
                error_message=str(e)
            )
    
    async def _validate_property(self, property_id: str, workspace_id: str):
        """Valida que la propiedad existe y está disponible"""
        def _fn():
            with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                cur.execute("""
                    SELECT id, description as titulo FROM pulpo.properties
                    WHERE workspace_id = %s AND property_id = %s AND is_available = true
                """, (workspace_id, property_id))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Propiedad no encontrada o no disponible: {property_id}")
                return row
        return await db_exec(_fn)
    
    async def _persistir_visita(self, data: ScheduleVisitPayload) -> str:
        """Persiste la visita en base de datos"""
        def _fn():
            with get_cursor(workspace_id=data.workspace_id) as (conn, cur):
                cur.execute("""
                    INSERT INTO pulpo.visitas (
                        workspace_id, conversation_id, property_id,
                        preferred_date, contact_info, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data.workspace_id,
                    data.conversation_id,
                    data.property_id,
                    data.preferred_date,
                    json.dumps(data.contact_info),
                    "scheduled",
                    datetime.now(timezone.utc)
                ))
                
                visita_id = cur.fetchone()[0]
                return str(visita_id)
        return await db_exec(_fn)

class ServiciosActions:
    """Acciones específicas para servicios"""
    
    async def book_slot(self, payload: Dict[str, Any]) -> ActionResult:
        """Reserva un turno de servicio con validación"""
        try:
            # Validar payload con Pydantic
            data = BookSlotPayload(**payload)

            # Verificar que el servicio existe y obtener su ID
            service = await self._validate_service(data.service_type, data.workspace_id)
            service_type_id = service['id']

            # Crear reserva en base de datos
            reserva_id = await self._persistir_reserva(data, service_type_id)
            
            
            return ActionResult(
                action_id=reserva_id,
                status=ActionStatus.SUCCESS,
                summary=f"Turno #{reserva_id} reservado exitosamente",
                details={
                    "reserva_id": reserva_id,
                    "service_type": data.service_type,
                    "preferred_date": data.preferred_date,
                    "preferred_time": data.preferred_time,
                    "client_name": data.client_name,
                    "client_email": data.client_email,
                    "client_phone": data.client_phone,
                    "status": "confirmed"
                },
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc)
            )
            
        except ValidationError:
            # Dejar que se propague como 422
            raise
        except Exception as e:
            logger.error(f"Error reservando turno: {e}")
            return ActionResult(
                action_id="error",
                status=ActionStatus.FAILED,
                summary="Error reservando turno",
                details={"error": str(e)},
                created_at=datetime.now(timezone.utc),
                error_message=str(e)
            )
    
    async def _validate_service(self, service_type: str, workspace_id: str):
        """Valida que el servicio existe y está disponible - busca por nombre (case-insensitive)"""
        def _fn():
            with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                cur.execute("""
                    SELECT id, name as nombre FROM pulpo.service_types
                    WHERE workspace_id = %s AND LOWER(name) = LOWER(%s) AND is_active = true
                    LIMIT 1
                """, (workspace_id, service_type))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Servicio no encontrado o no disponible: {service_type}")
                return row
        return await db_exec(_fn)
    
    async def _persistir_reserva(self, data: BookSlotPayload, service_type_id: str) -> str:
        """Persiste la reserva en base de datos usando el schema normalizado"""
        def _fn():
            with get_cursor(workspace_id=data.workspace_id) as (conn, cur):
                # Combinar fecha y hora en un datetime para scheduled_at
                try:
                    from datetime import datetime as dt
                    scheduled_at = dt.fromisoformat(f"{data.preferred_date}T{data.preferred_time}:00")
                except ValueError:
                    # Fallback si el formato no es correcto
                    scheduled_at = dt.fromisoformat(data.preferred_date)

                # Insertar usando el schema normalizado
                cur.execute("""
                    INSERT INTO pulpo.reservas (
                        workspace_id, conversation_id, service_type_id,
                        scheduled_at, client_name, client_email, client_phone,
                        status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    data.workspace_id,
                    data.conversation_id,
                    service_type_id,
                    scheduled_at,
                    data.client_name,
                    data.client_email,
                    data.client_phone,
                    "confirmed",
                    datetime.now(timezone.utc)
                ))

                reserva_id = cur.fetchone()[0]
                return str(reserva_id)
        return await db_exec(_fn)

class ActionsService:
    """Servicio principal de acciones"""
    
    def __init__(self):
        self.idempotency_manager = IdempotencyManager()
        self.gastronomia_actions = GastronomiaActions()
        self.inmobiliaria_actions = InmobiliariaActions()
        self.servicios_actions = ServiciosActions()
        
        # Mapeo de acciones
        self.action_handlers = {
            "crear_pedido": self.gastronomia_actions.crear_pedido,
            "schedule_visit": self.inmobiliaria_actions.schedule_visit,
            "book_slot": self.servicios_actions.book_slot,
            "schedule_appointment": self.servicios_actions.book_slot  # Alias para vertical servicios
        }
    
    async def execute_action(self, request: ExecuteActionRequest, workspace_id: str, request_id: str = None) -> ExecuteActionResponse:
        """
        Ejecuta una acción de negocio con idempotencia persistida
        """
        t0 = perf_counter()
        action_label = request.action_name
        try:
            logger.info(f"Ejecutando acción: {request.action_name} para conversación {request.conversation_id}")
            
            # Validar coherencia de workspace_id (defensa en profundidad)
            payload_workspace = request.payload.get("workspace_id")
            if payload_workspace and payload_workspace != workspace_id:
                logger.warning(f"Workspace mismatch: header={workspace_id}, payload={payload_workspace}")
            
            # Validar tamaño de idempotency_key
            if len(request.idempotency_key) > 64:
                raise HTTPException(status_code=400, detail="idempotency_key too long")
            
            # Auditar mismatch entre key y payload (sin romper backwards)
            fingerprint = hashlib.sha256(json.dumps(request.payload, sort_keys=True).encode()).hexdigest()
            if fingerprint[:16] != request.idempotency_key[:16]:
                logger.warning("Idempotency key does not match payload fingerprint")
            
            # Forzar workspace_id del contexto (seguridad)
            request.payload["workspace_id"] = workspace_id
            
            # Verificar que la acción existe
            if request.action_name not in self.action_handlers:
                raise ValueError(f"Acción no soportada: {request.action_name}")
            
            # Insertar o obtener acción existente (idempotencia)
            initial_details = {
                "payload_fingerprint": hashlib.sha256(
                    json.dumps(request.payload, sort_keys=True).encode()
                ).hexdigest()
            }
            
            status, row = await db_exec(self.idempotency_manager._insert_or_get_action(
                workspace_id, request.conversation_id, request.action_name, 
                request.idempotency_key, initial_details
            ))
            
            # Si ya existe y está completada, retornar resultado
            if status == "existing" and row["status"] in ("success", "failed", "cancelled"):
                logger.info(f"Acción ya ejecutada (idempotencia): {request.idempotency_key}")
                details_dict = safe_json_loads(row["details"])
                res = ExecuteActionResponse(
                    action_id=str(row["id"]),  # action_execution_id
                    status=row["status"],
                    summary=row["summary"],
                    details=details_dict,
                    created_at=row["created_at"],
                    eta_minutes=details_dict.get("eta_minutes") if details_dict else None
                )
                # ACTIONS_REQUESTS.labels(endpoint="/tools/execute_action", action=action_label, result=row["status"]).inc()
                # ACTIONS_DURATION.labels(action=action_label, result=row["status"]).observe(perf_counter() - t0)
                return res
            
            # Si otra instancia ya está procesando, devolvemos 202-like
            if status == "existing" and row["status"] == "processing":
                res = ExecuteActionResponse(
                    action_id=str(row["id"]),
                    status="processing",
                    summary="Acción en curso",
                    details=safe_json_loads(row["details"]) or {},
                    created_at=row["created_at"],
                    eta_minutes=None
                )
                # ACTIONS_REQUESTS.labels(endpoint="/tools/execute_action", action=action_label, result="processing").inc()
                # ACTIONS_DURATION.labels(action=action_label, result="processing").observe(perf_counter() - t0)
                return res
            
            # Ejecutar acción (único owner del trabajo)
            action_handler = self.action_handlers[request.action_name]
            result = await action_handler(request.payload)
            
            # Finalizar acción en DB
            await db_exec(self.idempotency_manager._finish_action(
                row["id"], result.status.value, result.summary, 
                result.details, datetime.now(timezone.utc)
            ))
            
            # Enviar a outbox para N8N si la acción fue exitosa
            if result.status == ActionStatus.SUCCESS:
                await self._enqueue_outbox_for_action(
                    workspace_id, request.action_name, str(row["id"]), result
                )
            
            # Métricas para acción ejecutada
            outcome = result.status.value  # success | failed | cancelled
            # ACTIONS_REQUESTS.labels(endpoint="/tools/execute_action", action=action_label, result=outcome).inc()
            # ACTIONS_DURATION.labels(action=action_label, result=outcome).observe(perf_counter() - t0)
            
            # Convertir a response
            return ExecuteActionResponse(
                action_id=str(row["id"]),  # action_execution_id
                status=result.status.value,
                summary=result.summary,
                details={**result.details, "domain_id": result.action_id},
                created_at=result.created_at,
                eta_minutes=result.details.get("eta_minutes")
            )
            
        except ValidationError as ve:
            # Responder 422 para validaciones Pydantic
            # ACTIONS_REQUESTS.labels(endpoint="/tools/execute_action", action=action_label, result="validation_error").inc()
            # ACTIONS_DURATION.labels(action=action_label, result="validation_error").observe(perf_counter() - t0)
            raise HTTPException(status_code=422, detail=ve.errors())
        except Exception as e:
            logger.error(f"Error ejecutando acción: {e}")
            # ACTIONS_REQUESTS.labels(endpoint="/tools/execute_action", action=action_label, result="error").inc()
            # ACTIONS_DURATION.labels(action=action_label, result="error").observe(perf_counter() - t0)
            error_detail = f"Error ejecutando acción: {str(e)}"
            if request_id:
                error_detail += f" (request_id: {request_id})"
            raise HTTPException(status_code=500, detail=error_detail)
    
    async def get_action_status(self, action_id: str, workspace_id: str) -> ActionStatusResponse:
        """
        Obtiene el estado de una acción desde la base de datos
        """
        def _fn():
            with get_cursor(dict_cursor=True, workspace_id=workspace_id) as (conn, cur):
                cur.execute("""
                    SELECT id, status, summary, details, created_at, completed_at
                    FROM pulpo.action_executions
                    WHERE id = %s AND workspace_id = %s
                """, (action_id, workspace_id))
                return cur.fetchone()
        
        row = await db_exec(_fn)
        if not row:
            raise HTTPException(status_code=404, detail="Acción no encontrada")
        
        details_dict = safe_json_loads(row["details"]) or {}
        return ActionStatusResponse(
            action_id=str(row["id"]),
            status=row["status"],
            summary=row["summary"],
            details=details_dict,
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            error_message=details_dict.get("error")
        )
    
    async def _enqueue_outbox_for_action(self, workspace_id: str, action_name: str, 
                                       action_execution_id: str, result: ActionResult):
        """Encola evento en outbox para envío a N8N"""
        try:
            # Mapear tipos de acción a tipos de evento
            event_type_map = {
                "crear_pedido": "pedido_creado",
                "schedule_visit": "visita_agendada",
                "book_slot": "turno_reservado"
            }
            
            event_type = event_type_map.get(action_name, f"{action_name}_completado")
            
            # Preparar payload con action_execution_id para correlación
            outbox_payload = {
                "action_execution_id": action_execution_id,
                **result.details
            }
            
            def _fn():
                with get_cursor(workspace_id=workspace_id) as (conn, cur):
                    cur.execute("""
                        INSERT INTO pulpo.outbox_events (workspace_id, event_type, payload)
                        VALUES (%s, %s, %s)
                    """, (workspace_id, event_type, json.dumps(outbox_payload)))
            
            await db_exec(_fn)
            logger.info(f"Evento {event_type} encolado para action_execution_id {action_execution_id}")
            
        except Exception as e:
            logger.error(f"Error encolando evento para outbox: {e}")
            # No fallar la acción principal por error en outbox

# Crear aplicación FastAPI
app = FastAPI(
    title="PulpoAI Actions Service",
    description="Servicio para ejecutar acciones de negocio con idempotencia",
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

# Instancia del servicio
actions_service = ActionsService()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check del servicio"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        service="actions",
        version="2.0.0"
    )

# @app.get("/metrics")
# async def metrics():
#     """Endpoint de métricas de Prometheus"""
#     return StarletteResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/tools/execute_action", response_model=ExecuteActionResponse)
async def execute_action(request: ExecuteActionRequest, response: Response, ctx: RequestContext = Depends(build_context)):
    """
    Endpoint principal para ejecutar acciones - usado por el orquestador
    """
    logger.info("exec_action rid=%s ws=%s conv=%s action=%s", 
                ctx.request_id, ctx.workspace_id, request.conversation_id, request.action_name)
    res = await actions_service.execute_action(request, ctx.workspace_id, ctx.request_id)
    if res.status == "processing":
        response.status_code = 202
    return res

@app.get("/actions/{action_id}/status", response_model=ActionStatusResponse)
async def get_action_status(action_id: str, ctx: RequestContext = Depends(build_context)):
    """
    Obtiene el estado de una acción específica
    """
    return await actions_service.get_action_status(action_id, ctx.workspace_id)

@app.get("/actions/available")
async def get_available_actions():
    """
    Obtiene las acciones disponibles
    """
    return {
        "actions": [
            # Gastronomía
            {
                "name": "crear_pedido",
                "description": "Crear pedido de comida",
                "vertical": "gastronomia",
                "required_fields": ["items", "metodo_entrega"],
                "conditional_rules": [
                    {"when": {"metodo_entrega": "envio"}, "require": ["direccion"]}
                ]
            },
            {
                "name": "cancelar_pedido",
                "description": "Cancelar pedido existente",
                "vertical": "gastronomia",
                "required_fields": ["pedido_id", "motivo"]
            },
            {
                "name": "consultar_menu",
                "description": "Consultar disponibilidad del menú",
                "vertical": "gastronomia",
                "required_fields": ["fecha", "categoria"]
            },
            # Inmobiliaria
            {
                "name": "schedule_visit",
                "description": "Agendar visita a propiedad",
                "vertical": "inmobiliaria",
                "required_fields": ["property_id", "preferred_date", "contact_info"]
            },
            {
                "name": "cancel_visit",
                "description": "Cancelar visita agendada",
                "vertical": "inmobiliaria",
                "required_fields": ["visit_id", "motivo"]
            },
            {
                "name": "property_search",
                "description": "Buscar propiedades disponibles",
                "vertical": "inmobiliaria",
                "required_fields": ["filters", "preferences"]
            },
            # Servicios
            {
                "name": "book_slot",
                "description": "Reservar turno de servicio",
                "vertical": "servicios",
                "required_fields": ["service_type", "preferred_date", "preferred_time", "client_name"],
                "optional_fields": ["client_email", "client_phone"]
            },
            {
                "name": "cancel_booking",
                "description": "Cancelar reserva de servicio",
                "vertical": "servicios",
                "required_fields": ["booking_id", "motivo"]
            },
            {
                "name": "check_availability",
                "description": "Verificar disponibilidad de servicios",
                "vertical": "servicios",
                "required_fields": ["service_type", "date_range"]
            }
        ]
    }

@app.post("/actions/test")
async def test_action(ctx: RequestContext = Depends(build_context)):
    """
    Endpoint de testing para validar el funcionamiento de las acciones
    """
    try:
        # Test con acción de ejemplo
        test_request = ExecuteActionRequest(
            conversation_id="test-123",
            action_name="crear_pedido",
            payload={
                "conversation_id": "test-123",
                "items": [
                    {"nombre": "Empanada de Carne", "cantidad": 6}
                ],
                "metodo_entrega": "retira",
                "direccion": "Test Address"
            },
            idempotency_key="test-key-123"
        )
        
        response = await actions_service.execute_action(test_request, ctx.workspace_id)
        
        return {
            "test": "success",
            "action": test_request.action_name,
            "workspace_id": ctx.workspace_id,
            "request_id": ctx.request_id,
            "result": {
                "action_id": response.action_id,
                "status": response.status,
                "summary": response.summary
            }
        }
        
    except Exception as e:
        logger.error(f"Error en test: {e}")
        raise HTTPException(status_code=500, detail=f"Error en test: {str(e)}")

# Middleware de métricas HTTP
@app.middleware("http")
async def prom_http_middleware(request: Request, call_next):
    endpoint = request.url.path
    # INFLIGHT.labels(endpoint=endpoint).inc()
    t0 = perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        dur = perf_counter() - t0
        code = getattr(response, "status_code", 500)
        # HTTP_DURATION.labels(endpoint=endpoint, code=str(code)).observe(dur)
        # INFLIGHT.labels(endpoint=endpoint).dec()

# Event handlers
@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    global DB_POOL
    DB_POOL = SimpleConnectionPool(
        minconn=int(os.getenv("DB_MIN_CONN", 1)),
        maxconn=int(os.getenv("DB_MAX_CONN", 10)),
        dsn=os.getenv("DATABASE_URL"),
    )
    logger.info("🚀 Actions Service iniciado con pool de conexiones")
    logger.info("📋 Endpoints disponibles:")
    logger.info("  - POST /tools/execute_action - Ejecutar acción")
    logger.info("  - GET /actions/{action_id}/status - Estado de acción")
    logger.info("  - GET /actions/available - Acciones disponibles")
    logger.info("  - POST /actions/test - Testing")
    logger.info("  - GET /health - Health check")
    logger.info("  - GET /metrics - Métricas de Prometheus")

@app.on_event("shutdown")
async def shutdown_event():
    """Evento de cierre de la aplicación"""
    logger.info("🛑 Actions Service cerrando...")
    # n8n_client was removed as it's not currently used
    # await actions_service.gastronomia_actions.n8n_client.aclose()
    # await actions_service.inmobiliaria_actions.n8n_client.aclose()
    # await actions_service.servicios_actions.n8n_client.aclose()
    if DB_POOL:
        DB_POOL.closeall()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "actions_service:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info"
    )
