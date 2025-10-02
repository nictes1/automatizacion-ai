"""
Actions Service Real - Servicio de ejecución de acciones de negocio
"""

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import asyncio
import uuid
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PulpoAI Actions Service Real", version="1.0.0")

class ActionRequest(BaseModel):
    name: str
    args: Dict[str, Any]
    conversation_id: str
    workspace_id: str
    request_id: str

class ActionResponse(BaseModel):
    ok: bool
    message: str
    data: Dict[str, Any] = {}
    slots_patch: Dict[str, Any] = {}

class ActionsService:
    def __init__(self):
        self.db_url = "postgresql://pulpo:pulpo@localhost:5432/pulpo"
        self.initialized = False
    
    async def initialize(self):
        """Inicializar el servicio Actions"""
        try:
            # Verificar conexión a la base de datos
            conn = psycopg2.connect(self.db_url)
            conn.close()
            
            self.initialized = True
            logger.info("Actions Service inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando Actions Service: {e}")
            raise
    
    async def execute_action(self, action_name: str, args: Dict[str, Any], 
                           conversation_id: str, workspace_id: str) -> ActionResponse:
        """Ejecutar una acción de negocio"""
        try:
            if action_name == "create_reservation":
                return await self._create_reservation(args, conversation_id, workspace_id)
            elif action_name == "create_order":
                return await self._create_order(args, conversation_id, workspace_id)
            elif action_name == "search_menu":
                return await self._search_menu(args, conversation_id, workspace_id)
            else:
                return ActionResponse(
                    ok=False,
                    message=f"Acción '{action_name}' no reconocida",
                    data={},
                    slots_patch={}
                )
                
        except Exception as e:
            logger.error(f"Error ejecutando acción {action_name}: {e}")
            return ActionResponse(
                ok=False,
                message=f"Error ejecutando acción: {str(e)}",
                data={},
                slots_patch={}
            )
    
    async def _create_reservation(self, args: Dict[str, Any], 
                                conversation_id: str, workspace_id: str) -> ActionResponse:
        """Crear una reserva"""
        try:
            user_input = args.get("user_input", "")
            
            # Simular creación de reserva
            reservation_id = str(uuid.uuid4())
            reservation_data = {
                "id": reservation_id,
                "conversation_id": conversation_id,
                "workspace_id": workspace_id,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "user_input": user_input
            }
            
            # Aquí se guardaría en la base de datos real
            # Por ahora solo simulamos
            
            return ActionResponse(
                ok=True,
                message="¡Perfecto! He creado tu reserva. ¿Para cuántas personas y a qué hora te gustaría venir?",
                data=reservation_data,
                slots_patch={
                    "reservation_id": reservation_id,
                    "reservation_status": "pending",
                    "action": "reservation_created"
                }
            )
            
        except Exception as e:
            logger.error(f"Error creando reserva: {e}")
            return ActionResponse(
                ok=False,
                message="Lo siento, no pude procesar tu reserva. ¿Puedes intentar de nuevo?",
                data={},
                slots_patch={}
            )
    
    async def _create_order(self, args: Dict[str, Any], 
                          conversation_id: str, workspace_id: str) -> ActionResponse:
        """Crear un pedido"""
        try:
            user_input = args.get("user_input", "")
            
            # Simular creación de pedido
            order_id = str(uuid.uuid4())
            order_data = {
                "id": order_id,
                "conversation_id": conversation_id,
                "workspace_id": workspace_id,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "user_input": user_input
            }
            
            return ActionResponse(
                ok=True,
                message="¡Excelente! He registrado tu pedido. ¿Te gustaría agregar algo más o proceder con el pago?",
                data=order_data,
                slots_patch={
                    "order_id": order_id,
                    "order_status": "pending",
                    "action": "order_created"
                }
            )
            
        except Exception as e:
            logger.error(f"Error creando pedido: {e}")
            return ActionResponse(
                ok=False,
                message="Lo siento, no pude procesar tu pedido. ¿Puedes intentar de nuevo?",
                data={},
                slots_patch={}
            )
    
    async def _search_menu(self, args: Dict[str, Any], 
                          conversation_id: str, workspace_id: str) -> ActionResponse:
        """Buscar en el menú"""
        try:
            query = args.get("query", "")
            
            # Simular búsqueda en menú
            menu_items = [
                "Pescado a la plancha con arroz y ensalada - $25.000",
                "Ceviche de pescado fresco - $15.000",
                "Paella de mariscos para 2 personas - $45.000"
            ]
            
            return ActionResponse(
                ok=True,
                message=f"Encontré estos platos relacionados con '{query}':\n" + 
                       "\n".join([f"• {item}" for item in menu_items]),
                data={"menu_items": menu_items},
                slots_patch={
                    "search_query": query,
                    "action": "menu_searched"
                }
            )
            
        except Exception as e:
            logger.error(f"Error buscando menú: {e}")
            return ActionResponse(
                ok=False,
                message="Lo siento, no pude buscar en el menú. ¿Puedes intentar de nuevo?",
                data={},
                slots_patch={}
            )

# Instancia global del servicio
actions_service = ActionsService()

@app.on_event("startup")
async def startup_event():
    logger.info("Actions Service Real iniciando...")
    await actions_service.initialize()

@app.post("/actions/execute", response_model=ActionResponse)
async def execute_action(
    request: ActionRequest,
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    """Ejecutar una acción de negocio"""
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")
    
    try:
        response = await actions_service.execute_action(
            action_name=request.name,
            args=request.args,
            conversation_id=request.conversation_id,
            workspace_id=request.workspace_id
        )
        return response
        
    except Exception as e:
        logger.error(f"Error ejecutando acción: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ejecución falló: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "actions_real"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
