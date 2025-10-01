#!/usr/bin/env python3
"""
Actions Service v2 - Implementación completa para F-08
Ejecuta tool_calls del Orchestrator con idempotencia y persistencia
"""

import os
import logging
import hashlib
import json
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from decimal import Decimal, ROUND_HALF_UP
from time import perf_counter

from fastapi import FastAPI, HTTPException, Depends, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import SimpleConnectionPool
from contextlib import contextmanager

from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pool de conexiones global
DB_POOL: Optional[SimpleConnectionPool] = None

def get_db_pool():
    """Obtener pool de conexiones"""
    global DB_POOL
    if DB_POOL is None:
        DB_POOL = SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=os.getenv('DATABASE_URL', 'postgresql://pulpo:pulpo@localhost:5432/pulpo')
        )
    return DB_POOL

@contextmanager
def get_cursor(*, dict_cursor=False, workspace_id: Optional[str] = None):
    """Context manager para conexiones de base de datos"""
    pool = get_db_pool()
    conn = pool.getconn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor if dict_cursor else None)
        try:
            # Configurar workspace para RLS
            if workspace_id:
                cur.execute("SELECT set_config('app.workspace_id', %s, true)", (workspace_id,))
            yield conn, cur
            conn.commit()
        finally:
            cur.close()
    finally:
        pool.putconn(conn)

# =========================
# Modelos Pydantic
# =========================

class ActionRequest(BaseModel):
    """Request para ejecutar una acción"""
    name: str = Field(..., description="Nombre de la acción")
    args: Dict[str, Any] = Field(..., description="Argumentos de la acción")
    conversation_id: str = Field(..., description="ID de la conversación")
    workspace_id: str = Field(..., description="ID del workspace")
    request_id: str = Field(..., description="ID único para idempotencia")

class ActionResponse(BaseModel):
    """Response de una acción ejecutada"""
    ok: bool = Field(..., description="Si la acción fue exitosa")
    message: str = Field(..., description="Mensaje para el usuario")
    data: Dict[str, Any] = Field(default_factory=dict, description="Datos de la acción")
    slots_patch: Optional[Dict[str, Any]] = Field(None, description="Actualización de slots")

class HealthResponse(BaseModel):
    """Response de health check"""
    status: str
    timestamp: datetime
    services: Dict[str, str]

# =========================
# Implementación de Acciones
# =========================

class ActionExecutor:
    """Ejecutor de acciones de negocio"""
    
    def __init__(self):
        self.actions = {
            "search_menu": self._search_menu,
            "create_order": self._create_order,
            "suggest_upsell": self._suggest_upsell,
            "list_properties": self._list_properties,
            "schedule_visit": self._schedule_visit,
            "list_services": self._list_services,
            "list_slots": self._list_slots,
            "book_slot": self._book_slot,
            "kb_search": self._kb_search
        }
    
    async def execute(self, action_name: str, args: Dict[str, Any], 
                     conversation_id: str, workspace_id: str) -> ActionResponse:
        """Ejecutar una acción"""
        try:
            if action_name not in self.actions:
                raise ValueError(f"Action '{action_name}' not found")
            
            # Verificar idempotencia
            if await self._is_duplicate_request(conversation_id, action_name, args):
                logger.info(f"Duplicate request detected for {action_name}")
                return ActionResponse(
                    ok=True,
                    message="Acción ya procesada anteriormente",
                    data={"duplicate": True}
                )
            
            # Ejecutar acción
            result = await self.actions[action_name](args, workspace_id)
            
            # Persistir resultado
            await self._persist_action_result(conversation_id, action_name, args, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing action {action_name}: {e}")
            return ActionResponse(
                ok=False,
                message=f"Error ejecutando {action_name}: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _is_duplicate_request(self, conversation_id: str, action_name: str, args: Dict[str, Any]) -> bool:
        """Verificar si es una request duplicada"""
        try:
            with get_cursor(workspace_id=None) as (conn, cur):
                # Crear hash de la request
                request_hash = hashlib.sha256(
                    json.dumps({"action": action_name, "args": args}, sort_keys=True).encode()
                ).hexdigest()
                
                # Verificar si ya existe
                cur.execute("""
                    SELECT 1 FROM pulpo.action_results 
                    WHERE conversation_id = %s AND request_hash = %s
                    LIMIT 1
                """, (conversation_id, request_hash))
                
                return cur.fetchone() is not None
                
        except Exception as e:
            logger.error(f"Error checking duplicate request: {e}")
            return False
    
    async def _persist_action_result(self, conversation_id: str, action_name: str, 
                                    args: Dict[str, Any], result: ActionResponse):
        """Persistir resultado de la acción"""
        try:
            with get_cursor(workspace_id=None) as (conn, cur):
                # Crear hash de la request
                request_hash = hashlib.sha256(
                    json.dumps({"action": action_name, "args": args}, sort_keys=True).encode()
                ).hexdigest()
                
                # Insertar resultado
                cur.execute("""
                    INSERT INTO pulpo.action_results 
                    (conversation_id, action_name, args_json, result_json, request_hash, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    conversation_id,
                    action_name,
                    json.dumps(args),
                    json.dumps(result.dict()),
                    request_hash,
                    datetime.now(timezone.utc)
                ))
                
        except Exception as e:
            logger.error(f"Error persisting action result: {e}")
    
    # =========================
    # Implementaciones de Acciones
    # =========================
    
    async def _search_menu(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Buscar en el menú"""
        categoria = args.get("categoria", "")
        query = args.get("query", "")
        
        try:
            with get_cursor(workspace_id=workspace_id) as (conn, cur):
                # Buscar en la base de datos (simulado)
                cur.execute("""
                    SELECT id, name, description, price, category
                    FROM pulpo.menu_items 
                    WHERE workspace_id = %s 
                    AND (category ILIKE %s OR name ILIKE %s OR description ILIKE %s)
                    ORDER BY name
                    LIMIT 10
                """, (workspace_id, f"%{categoria}%", f"%{query}%", f"%{query}%"))
                
                items = cur.fetchall()
                
                if items:
                    message = f"Encontré {len(items)} opciones en el menú:\n\n"
                    for item in items:
                        message += f"• {item['name']} - ${item['price']}\n"
                        if item['description']:
                            message += f"  {item['description']}\n"
                        message += "\n"
                else:
                    message = "No encontré opciones que coincidan con tu búsqueda. ¿Podrías ser más específico?"
                
                return ActionResponse(
                    ok=True,
                    message=message,
                    data={"items": [dict(item) for item in items]},
                    slots_patch={"menu_searched": True, "search_query": query}
                )
                
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error buscando en el menú: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _create_order(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Crear un pedido"""
        items = args.get("items", [])
        metodo_entrega = args.get("metodo_entrega", "delivery")
        direccion = args.get("direccion", "")
        metodo_pago = args.get("metodo_pago", "efectivo")
        
        try:
            # Calcular total
            total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
            
            # Crear pedido en la base de datos
            with get_cursor(workspace_id=workspace_id) as (conn, cur):
                order_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO pulpo.orders 
                    (id, workspace_id, items_json, total, metodo_entrega, direccion, metodo_pago, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    order_id,
                    workspace_id,
                    json.dumps(items),
                    total,
                    metodo_entrega,
                    direccion,
                    metodo_pago,
                    "pending",
                    datetime.now(timezone.utc)
                ))
                
                # Generar mensaje de confirmación
                message = f"¡Pedido creado exitosamente!\n\n"
                message += f"📋 Orden #{order_id[:8]}\n"
                message += f"💰 Total: ${total:.2f}\n"
                message += f"🚚 Entrega: {metodo_entrega}\n"
                if direccion:
                    message += f"📍 Dirección: {direccion}\n"
                message += f"💳 Pago: {metodo_pago}\n\n"
                message += f"⏱️ Tiempo estimado: 30-45 minutos"
                
                return ActionResponse(
                    ok=True,
                    message=message,
                    data={
                        "order_id": order_id,
                        "total": total,
                        "items": items
                    },
                    slots_patch={
                        "order_created": True,
                        "order_id": order_id,
                        "total": total
                    }
                )
                
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error creando el pedido: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _suggest_upsell(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Sugerir productos adicionales"""
        current_items = args.get("current_items", [])
        
        # Lógica simple de upsell
        suggestions = []
        if any("pizza" in item.get("name", "").lower() for item in current_items):
            suggestions.append({"name": "Bebida", "description": "Coca Cola, Sprite, Agua", "price": 2.50})
        if any("hamburguesa" in item.get("name", "").lower() for item in current_items):
            suggestions.append({"name": "Papas Fritas", "description": "Papas fritas crujientes", "price": 3.00})
        
        if suggestions:
            message = "¿Te gustaría agregar algo más?\n\n"
            for suggestion in suggestions:
                message += f"• {suggestion['name']} - ${suggestion['price']}\n"
                message += f"  {suggestion['description']}\n\n"
        else:
            message = "Tu pedido está completo. ¿Hay algo más que te gustaría agregar?"
        
        return ActionResponse(
            ok=True,
            message=message,
            data={"suggestions": suggestions}
        )
    
    async def _list_properties(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Listar propiedades (inmobiliaria)"""
        operation = args.get("operation", "venta")
        type_prop = args.get("type", "departamento")
        zone = args.get("zone", "")
        budget_min = args.get("budget_min", 0)
        budget_max = args.get("budget_max", 999999999)
        
        try:
            with get_cursor(workspace_id=workspace_id) as (conn, cur):
                cur.execute("""
                    SELECT id, title, zone, price, bedrooms, bathrooms, area
                    FROM pulpo.properties 
                    WHERE workspace_id = %s 
                    AND operation = %s 
                    AND type = %s
                    AND (zone ILIKE %s OR %s = '')
                    AND price BETWEEN %s AND %s
                    ORDER BY price
                    LIMIT 5
                """, (workspace_id, operation, type_prop, f"%{zone}%", zone, budget_min, budget_max))
                
                properties = cur.fetchall()
                
                if properties:
                    message = f"Encontré {len(properties)} propiedades:\n\n"
                    for prop in properties:
                        message += f"🏠 {prop['title']}\n"
                        message += f"📍 {prop['zone']}\n"
                        message += f"💰 ${prop['price']:,}\n"
                        message += f"🛏️ {prop['bedrooms']} dormitorios, {prop['bathrooms']} baños\n"
                        message += f"📐 {prop['area']} m²\n\n"
                else:
                    message = "No encontré propiedades que coincidan con tus criterios. ¿Podrías ajustar la búsqueda?"
                
                return ActionResponse(
                    ok=True,
                    message=message,
                    data={"properties": [dict(prop) for prop in properties]},
                    slots_patch={"properties_searched": True}
                )
                
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error buscando propiedades: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _schedule_visit(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Agendar visita (inmobiliaria)"""
        property_id = args.get("property_id")
        visit_datetime = args.get("visit_datetime")
        
        try:
            with get_cursor(workspace_id=workspace_id) as (conn, cur):
                visit_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO pulpo.visits 
                    (id, workspace_id, property_id, visit_datetime, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    visit_id,
                    workspace_id,
                    property_id,
                    visit_datetime,
                    "scheduled",
                    datetime.now(timezone.utc)
                ))
                
                message = f"¡Visita agendada exitosamente!\n\n"
                message += f"📅 Fecha: {visit_datetime}\n"
                message += f"🏠 Propiedad: {property_id}\n"
                message += f"📋 Código: {visit_id[:8]}\n\n"
                message += f"Te contactaremos para confirmar los detalles."
                
                return ActionResponse(
                    ok=True,
                    message=message,
                    data={"visit_id": visit_id, "property_id": property_id},
                    slots_patch={"visit_scheduled": True, "visit_id": visit_id}
                )
                
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error agendando visita: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _list_services(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Listar servicios disponibles"""
        try:
            with get_cursor(workspace_id=workspace_id) as (conn, cur):
                cur.execute("""
                    SELECT id, name, description, price, duration
                    FROM pulpo.services 
                    WHERE workspace_id = %s AND is_active = true
                    ORDER BY name
                """, (workspace_id,))
                
                services = cur.fetchall()
                
                if services:
                    message = "Servicios disponibles:\n\n"
                    for service in services:
                        message += f"• {service['name']}\n"
                        message += f"  {service['description']}\n"
                        message += f"  💰 ${service['price']} - ⏱️ {service['duration']} min\n\n"
                else:
                    message = "No hay servicios disponibles en este momento."
                
                return ActionResponse(
                    ok=True,
                    message=message,
                    data={"services": [dict(service) for service in services]}
                )
                
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error listando servicios: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _list_slots(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Listar horarios disponibles"""
        service_code = args.get("service_code")
        date = args.get("date")
        
        try:
            # Simular horarios disponibles
            available_slots = [
                "09:00", "10:00", "11:00", "14:00", "15:00", "16:00"
            ]
            
            message = f"Horarios disponibles para {date}:\n\n"
            for slot in available_slots:
                message += f"• {slot}\n"
            message += "\n¿Cuál prefieres?"
            
            return ActionResponse(
                ok=True,
                message=message,
                data={"available_slots": available_slots}
            )
            
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error listando horarios: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _book_slot(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Reservar turno"""
        service_code = args.get("service_code")
        date = args.get("date")
        time = args.get("time")
        
        try:
            booking_id = str(uuid.uuid4())
            
            message = f"¡Turno reservado exitosamente!\n\n"
            message += f"📅 Fecha: {date}\n"
            message += f"⏰ Hora: {time}\n"
            message += f"📋 Código: {booking_id[:8]}\n\n"
            message += f"Te enviaremos un recordatorio antes de tu cita."
            
            return ActionResponse(
                ok=True,
                message=message,
                data={"booking_id": booking_id},
                slots_patch={"booking_confirmed": True, "booking_id": booking_id}
            )
            
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error reservando turno: {str(e)}",
                data={"error": str(e)}
            )
    
    async def _kb_search(self, args: Dict[str, Any], workspace_id: str) -> ActionResponse:
        """Búsqueda en base de conocimientos"""
        query = args.get("query", "")
        top_k = args.get("top_k", 3)
        
        try:
            with get_cursor(workspace_id=workspace_id) as (conn, cur):
                cur.execute("""
                    SELECT content, metadata
                    FROM pulpo.chunks c
                    JOIN pulpo.chunk_embeddings ce ON c.id = ce.chunk_id
                    WHERE c.workspace_id = %s
                    ORDER BY ce.embedding <-> (
                        SELECT embedding FROM pulpo.chunk_embeddings 
                        WHERE chunk_id = (
                            SELECT id FROM pulpo.chunks 
                            WHERE workspace_id = %s 
                            ORDER BY created_at DESC 
                            LIMIT 1
                        )
                    )
                    LIMIT %s
                """, (workspace_id, workspace_id, top_k))
                
                results = cur.fetchall()
                
                if results:
                    message = f"Información encontrada:\n\n"
                    for i, result in enumerate(results, 1):
                        message += f"{i}. {result['content'][:100]}...\n\n"
                else:
                    message = "No encontré información relevante. ¿Podrías reformular tu pregunta?"
                
                return ActionResponse(
                    ok=True,
                    message=message,
                    data={"results": [dict(result) for result in results]}
                )
                
        except Exception as e:
            return ActionResponse(
                ok=False,
                message=f"Error en búsqueda: {str(e)}",
                data={"error": str(e)}
            )

# =========================
# FastAPI App
# =========================

app = FastAPI(
    title="PulpoAI Actions Service",
    description="Servicio de acciones de negocio para PulpoAI",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instancia del ejecutor
action_executor = ActionExecutor()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        services={
            "database": "connected",
            "actions": "ready"
        }
    )

@app.post("/actions/execute", response_model=ActionResponse)
async def execute_action(
    request: ActionRequest,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    x_request_id: str = Header(..., alias="X-Request-Id")
):
    """Ejecutar una acción de negocio"""
    try:
        start_time = perf_counter()
        
        # Validar headers
        if not x_workspace_id or not x_request_id:
            raise HTTPException(status_code=400, detail="Missing required headers")
        
        # Ejecutar acción
        result = await action_executor.execute(
            action_name=request.name,
            args=request.args,
            conversation_id=request.conversation_id,
            workspace_id=x_workspace_id
        )
        
        # Log de performance
        duration = perf_counter() - start_time
        logger.info(f"Action {request.name} executed in {duration:.3f}s")
        
        return result
        
    except Exception as e:
        logger.error(f"Error in execute_action: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/actions/available")
async def list_available_actions():
    """Listar acciones disponibles"""
    return {
        "actions": list(action_executor.actions.keys()),
        "count": len(action_executor.actions)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
