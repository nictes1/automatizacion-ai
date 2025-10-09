"""
Multi-Model AI Client
Implementa arquitectura de dos modelos: Router (8B) + Agente (14B)
"""

import httpx
import yaml
import logging
from typing import Dict, Any, Optional, List, Literal
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Intents del sistema"""
    GREET = "GREET"
    ANSWER = "ANSWER"
    SMALLTALK = "SMALLTALK"
    QUERY_INFO = "QUERY_INFO"
    QUERY_PRICES = "QUERY_PRICES"
    QUERY_SCHEDULE = "QUERY_SCHEDULE"
    EXECUTE_ACTION = "EXECUTE_ACTION"
    BOOK_APPOINTMENT = "BOOK_APPOINTMENT"
    CREATE_ORDER = "CREATE_ORDER"
    FILL_SLOTS = "FILL_SLOTS"
    UNKNOWN = "UNKNOWN"


@dataclass
class ModelConfig:
    """Configuración de un modelo"""
    name: str
    base_url: str
    timeout: float = 30.0


@dataclass
class IntentClassification:
    """Resultado de clasificación de intent"""
    intent: Intent
    confidence: float
    requires_agent: bool
    reasoning: Optional[str] = None


@dataclass
class AgentResponse:
    """Respuesta del agente"""
    text: str
    intent: Intent
    action: Optional[Dict[str, Any]] = None
    slots: Optional[Dict[str, Any]] = None
    requires_action: bool = False


class RouterLLM:
    """
    Router LLM - Modelo ligero para intent classification
    Llama-3.1-8B-Instruct 4-bit (~7-8GB VRAM)
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout
        )
        
    async def classify_intent(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> IntentClassification:
        """
        Clasifica el intent del mensaje del usuario
        Latencia objetivo: 50-100ms
        """
        
        # System prompt optimizado para clasificación rápida
        system_prompt = """Eres un clasificador de intenciones para un asistente de peluquería.

Clasifica el mensaje del usuario en UNA de estas categorías:

- GREET: Saludos, despedidas
- ANSWER: Respuesta a pregunta del asistente
- QUERY_INFO: Pregunta sobre servicios, ubicación, etc.
- QUERY_PRICES: Pregunta sobre precios
- QUERY_SCHEDULE: Pregunta sobre horarios disponibles
- EXECUTE_ACTION: Quiere realizar una acción (reservar turno, cancelar, etc.)
- SMALLTALK: Charla casual, comentarios
- UNKNOWN: No se puede clasificar

Responde SOLO con el nombre de la categoría, nada más."""

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Agregar contexto de conversación si existe (últimos 2 mensajes)
        if conversation_history:
            for msg in conversation_history[-2:]:
                messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": self.config.name,
                    "messages": messages,
                    "max_tokens": 20,
                    "temperature": 0.1,
                    "stop": ["\n"]
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            intent_str = result["choices"][0]["message"]["content"].strip()
            
            # Parsear intent
            try:
                intent = Intent[intent_str]
            except KeyError:
                logger.warning(f"Intent desconocido del router: {intent_str}")
                intent = Intent.UNKNOWN
            
            # Determinar si requiere agente
            requires_agent = intent in [
                Intent.EXECUTE_ACTION,
                Intent.BOOK_APPOINTMENT,
                Intent.CREATE_ORDER,
                Intent.FILL_SLOTS
            ]
            
            # Confidence basado en la respuesta (simplificado)
            confidence = 0.9 if intent != Intent.UNKNOWN else 0.5
            
            return IntentClassification(
                intent=intent,
                confidence=confidence,
                requires_agent=requires_agent,
                reasoning=intent_str
            )
            
        except Exception as e:
            logger.error(f"Error en router classification: {e}")
            return IntentClassification(
                intent=Intent.UNKNOWN,
                confidence=0.0,
                requires_agent=True,  # En caso de error, escalar a agente
                reasoning=str(e)
            )
    
    async def generate_simple_response(
        self,
        user_message: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Genera respuesta simple para intents que no requieren agente
        Latencia objetivo: 100-200ms
        """
        
        system_prompt = """Eres un asistente amigable de una peluquería.

Responde de forma breve, natural y profesional.
Si no sabes algo, di que consultarás con el equipo."""

        if context:
            system_prompt += f"\n\nContexto adicional:\n{context}"
        
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Agregar contexto de conversación
        if conversation_history:
            for msg in conversation_history[-4:]:  # Últimos 4 mensajes
                messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": self.config.name,
                    "messages": messages,
                    "max_tokens": 150,
                    "temperature": 0.7,
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result["choices"][0]["message"]["content"].strip()
            
        except Exception as e:
            logger.error(f"Error en router response generation: {e}")
            return "Lo siento, tuve un problema. ¿Podrías repetir tu consulta?"
    
    async def close(self):
        """Cierra el cliente HTTP"""
        await self.client.aclose()


class AgentLLM:
    """
    Agent LLM - Modelo principal para tool calling y slot filling
    Qwen2.5-14B-Instruct-AWQ 4-bit (~10-12GB VRAM)
    """
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout
        )
    
    async def process_with_tools(
        self,
        user_message: str,
        available_tools: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_slots: Optional[Dict[str, Any]] = None
    ) -> AgentResponse:
        """
        Procesa mensaje con herramientas disponibles
        Hace tool calling y slot filling
        Latencia objetivo: 200-400ms
        """
        
        # System prompt optimizado para tool calling
        system_prompt = """Eres un asistente especializado en reservas de peluquería.

Tu trabajo es:
1. Identificar si el usuario quiere realizar una acción (reservar turno, consultar, etc.)
2. Extraer la información necesaria (slots) para completar la acción
3. Llamar a las herramientas disponibles cuando tengas toda la información

Herramientas disponibles:
{tools_description}

Slots requeridos para book_slot:
- service_type: Tipo de servicio (corte_caballero, corte_dama, tintura, etc.)
- preferred_date: Fecha preferida (YYYY-MM-DD)
- preferred_time: Hora preferida (HH:MM)
- client_name: Nombre del cliente
- client_email: Email (opcional)
- client_phone: Teléfono (opcional)

Slots actuales: {current_slots}

Si falta información, pregunta de forma natural.
Si tienes toda la información, genera el llamado a la herramienta en JSON."""

        # Formatear descripción de herramientas
        tools_desc = "\n".join([
            f"- {tool['name']}: {tool.get('description', '')}"
            for tool in available_tools
        ])
        
        system_prompt = system_prompt.format(
            tools_description=tools_desc,
            current_slots=json.dumps(current_slots or {}, indent=2)
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Agregar historial de conversación
        if conversation_history:
            for msg in conversation_history[-6:]:  # Últimos 6 mensajes
                messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            response = await self.client.post(
                "/v1/chat/completions",
                json={
                    "model": self.config.name,
                    "messages": messages,
                    "max_tokens": 512,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}  # Forzar JSON
                }
            )
            
            response.raise_for_status()
            result = response.json()
            
            content = result["choices"][0]["message"]["content"].strip()
            
            # Parsear respuesta JSON
            try:
                parsed = json.loads(content)
                
                return AgentResponse(
                    text=parsed.get("response", ""),
                    intent=Intent.EXECUTE_ACTION,
                    action=parsed.get("action"),
                    slots=parsed.get("slots"),
                    requires_action=bool(parsed.get("action"))
                )
                
            except json.JSONDecodeError:
                logger.warning(f"Respuesta del agente no es JSON válido: {content}")
                return AgentResponse(
                    text=content,
                    intent=Intent.FILL_SLOTS,
                    requires_action=False
                )
            
        except Exception as e:
            logger.error(f"Error en agent processing: {e}")
            return AgentResponse(
                text="Lo siento, tuve un problema procesando tu solicitud.",
                intent=Intent.UNKNOWN,
                requires_action=False
            )
    
    async def close(self):
        """Cierra el cliente HTTP"""
        await self.client.aclose()


class MultiModelOrchestrator:
    """
    Orchestrator que coordina Router y Agente
    Implementa estrategia de routing inteligente
    """
    
    def __init__(self, config_path: str = "config/vllm_config.yaml"):
        # Cargar configuración
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        with open(config_file) as f:
            self.config = yaml.safe_load(f)
        
        # Inicializar clientes
        router_cfg = self.config["router"]
        agent_cfg = self.config["agent"]
        
        self.router = RouterLLM(
            ModelConfig(
                name=router_cfg["model"],
                base_url=f"http://localhost:{router_cfg['port']}",
                timeout=5.0  # Timeout corto para router
            )
        )
        
        self.agent = AgentLLM(
            ModelConfig(
                name=agent_cfg["model"],
                base_url=f"http://localhost:{agent_cfg['port']}",
                timeout=15.0  # Timeout más largo para agente
            )
        )
        
        self.router_only_intents = set(
            self.config["routing"]["router_only_intents"]
        )
        
        logger.info("✅ MultiModelOrchestrator inicializado")
        logger.info(f"   Router: {router_cfg['model']} @ port {router_cfg['port']}")
        logger.info(f"   Agent:  {agent_cfg['model']} @ port {agent_cfg['port']}")
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        current_slots: Optional[Dict[str, Any]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None
    ) -> AgentResponse:
        """
        Procesa un mensaje usando la estrategia de routing óptima
        
        Flujo:
        1. Router clasifica intent (50-100ms)
        2. Si es intent simple → Router genera respuesta (100-200ms)
        3. Si requiere acción → Agente procesa con tools (200-400ms)
        """
        
        # Paso 1: Clasificar intent con router
        classification = await self.router.classify_intent(
            user_message,
            conversation_history
        )
        
        logger.info(
            f"Intent: {classification.intent.value} "
            f"(confidence={classification.confidence:.2f}, "
            f"requires_agent={classification.requires_agent})"
        )
        
        # Paso 2: Routing decision
        if not classification.requires_agent:
            # Usar router para respuesta simple (RÁPIDO)
            response_text = await self.router.generate_simple_response(
                user_message,
                conversation_history=conversation_history
            )
            
            return AgentResponse(
                text=response_text,
                intent=classification.intent,
                requires_action=False
            )
        else:
            # Usar agente para tool calling y slot filling (PRECISO)
            return await self.agent.process_with_tools(
                user_message,
                available_tools or [],
                conversation_history,
                current_slots
            )
    
    async def close(self):
        """Cierra ambos clientes"""
        await self.router.close()
        await self.agent.close()
        logger.info("MultiModelOrchestrator cerrado")


# Función helper para crear orchestrator
async def create_orchestrator(config_path: str = "config/vllm_config.yaml") -> MultiModelOrchestrator:
    """Factory function para crear orchestrator"""
    return MultiModelOrchestrator(config_path)

