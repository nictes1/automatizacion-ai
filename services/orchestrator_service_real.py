"""
Orchestrator Service Real - Servicio de orquestación con LLM real
"""

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import asyncio
import requests
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PulpoAI Orchestrator Service Real", version="1.0.0")

class ConversationSnapshot(BaseModel):
    conversation_id: str
    vertical: str
    user_input: str
    greeted: bool = False
    slots: Dict[str, Any] = {}
    objective: str = ""
    last_action: Optional[str] = None
    attempts_count: int = 0

class ToolCall(BaseModel):
    name: str
    args: Dict[str, Any]

class OrchestratorResponse(BaseModel):
    assistant: str
    next_action: str  # "answer", "tool_call", "handoff", "wait"
    tool_calls: List[ToolCall] = []
    slots: Dict[str, Any] = {}
    objective: str = ""
    end: bool = False

class OrchestratorService:
    def __init__(self):
        self.ollama_url = "http://localhost:11434"
        self.rag_url = "http://localhost:8007"
        self.actions_url = "http://localhost:8006"
        self.initialized = False
    
    async def initialize(self):
        """Inicializar el servicio Orchestrator"""
        try:
            # Verificar conexión a Ollama
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise Exception("Ollama no está disponible")
            
            self.initialized = True
            logger.info("Orchestrator Service inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando Orchestrator Service: {e}")
            raise
    
    async def generate_response(self, user_input: str, context: str = "") -> str:
        """Generar respuesta usando Ollama"""
        try:
            # Preparar el prompt para el LLM
            system_prompt = f"""Eres un asistente de restaurante inteligente. 
Responde de manera amigable y profesional a las consultas de los clientes.
Contexto: {context}

Usuario: {user_input}

Responde de manera natural y útil:"""
            
            payload = {
                "model": "llama3.2",
                "prompt": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.9,
                    "max_tokens": 500
                }
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "Lo siento, no pude procesar tu consulta.")
            else:
                # Fallback: respuesta simple
                return "Hola! ¿En qué puedo ayudarte hoy?"
                
        except Exception as e:
            logger.error(f"Error generando respuesta: {e}")
            return "Hola! ¿En qué puedo ayudarte hoy?"
    
    async def search_rag(self, query: str, workspace_id: str) -> str:
        """Buscar información relevante usando RAG"""
        try:
            payload = {
                "query": query,
                "workspace_id": workspace_id,
                "limit": 3
            }
            
            response = requests.post(
                f"{self.rag_url}/rag/search",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("results"):
                    # Combinar resultados en contexto
                    context = "\n".join([
                        f"- {r['content']}" for r in result["results"]
                    ])
                    return context
                else:
                    return ""
            else:
                return ""
                
        except Exception as e:
            logger.error(f"Error en búsqueda RAG: {e}")
            return ""
    
    async def decide_next_action(self, snapshot: ConversationSnapshot) -> OrchestratorResponse:
        """Decidir el próximo paso en la conversación"""
        try:
            # Buscar información relevante usando RAG
            rag_context = await self.search_rag(snapshot.user_input, snapshot.conversation_id)
            
            # Generar respuesta usando LLM
            assistant_response = await self.generate_response(snapshot.user_input, rag_context)
            
            # Determinar la próxima acción basada en el input del usuario
            user_input_lower = snapshot.user_input.lower()
            
            # Lógica simple para determinar acciones
            if any(word in user_input_lower for word in ["reservar", "reserva", "mesa", "turno"]):
                next_action = "tool_call"
                tool_calls = [ToolCall(name="create_reservation", args={"user_input": snapshot.user_input})]
            elif any(word in user_input_lower for word in ["pedido", "orden", "comprar", "quiero"]):
                next_action = "tool_call"
                tool_calls = [ToolCall(name="create_order", args={"user_input": snapshot.user_input})]
            elif any(word in user_input_lower for word in ["gracias", "chao", "adiós", "hasta luego"]):
                next_action = "answer"
                tool_calls = []
            else:
                next_action = "answer"
                tool_calls = []
            
            # Actualizar slots basado en el input
            updated_slots = snapshot.slots.copy()
            if "pescado" in user_input_lower:
                updated_slots["preferencia"] = "pescado"
            if "precio" in user_input_lower or "$" in snapshot.user_input:
                updated_slots["interes"] = "precios"
            
            return OrchestratorResponse(
                assistant=assistant_response,
                next_action=next_action,
                tool_calls=tool_calls,
                slots=updated_slots,
                objective=snapshot.objective,
                end=next_action == "answer" and "gracias" in user_input_lower
            )
            
        except Exception as e:
            logger.error(f"Error en decisión: {e}")
            return OrchestratorResponse(
                assistant="Lo siento, hubo un error procesando tu consulta. ¿Puedes intentar de nuevo?",
                next_action="answer",
                tool_calls=[],
                slots=snapshot.slots,
                objective=snapshot.objective,
                end=False
            )

# Instancia global del servicio
orchestrator_service = OrchestratorService()

@app.on_event("startup")
async def startup_event():
    logger.info("Orchestrator Service Real iniciando...")
    await orchestrator_service.initialize()

@app.post("/orchestrator/decide", response_model=OrchestratorResponse)
async def decide_next_step(
    snapshot: ConversationSnapshot,
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    """Decidir el próximo paso en la conversación"""
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")
    
    try:
        response = await orchestrator_service.decide_next_action(snapshot)
        return response
        
    except Exception as e:
        logger.error(f"Error en orquestación: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Orquestación falló: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "orchestrator_real"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
