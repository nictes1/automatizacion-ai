#!/usr/bin/env python3
"""
Sistema de Slot Filling para diálogos orientados a tareas
Integra RAG como herramienta en el flujo de conversación
"""

import json
import uuid
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Vertical(Enum):
    GASTRONOMIA = "gastronomia"
    INMOBILIARIA = "inmobiliaria"
    OTRO = "otro"

class MessageDirection(Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

@dataclass
class Workspace:
    """Configuración de workspace multitenant"""
    id: str
    name: str
    vertical: Vertical
    plan: str
    rag_index: str
    twilio_from: str
    created_at: datetime = None

@dataclass
class Conversation:
    """Conversación con estado de slots"""
    id: str
    workspace_id: str
    user_phone: str
    last_message_at: datetime = None
    state: Dict[str, Any] = None
    total_messages: int = 0
    unread_count: int = 0

@dataclass
class Message:
    """Mensaje individual"""
    id: str
    conversation_id: str
    workspace_id: str
    direction: MessageDirection
    text: str
    wa_message_sid: str = None
    created_at: datetime = None

@dataclass
class Slot:
    """Slot individual en el FSM"""
    name: str
    value: Any = None
    required: bool = True
    filled: bool = False

@dataclass
class FSMState:
    """Estado de la máquina de estados"""
    current_state: str
    slots: Dict[str, Slot]
    context: Dict[str, Any] = None

class GastronomiaFSM:
    """Máquina de estados para gastronomía"""
    
    def __init__(self):
        self.states = {
            "START": {
                "description": "Estado inicial",
                "next_states": ["PEDIR_CATEGORIA", "ARMAR_ITEMS", "MOSTRAR_MENU"]
            },
            "PEDIR_CATEGORIA": {
                "description": "Solicitar categoría de comida",
                "question": "¿De qué categoría querés pedir? (ej: pizzas, empanadas, pastas)",
                "slot": "categoria",
                "next_state": "ARMAR_ITEMS"
            },
            "ARMAR_ITEMS": {
                "description": "Armar items del pedido",
                "question": "Decime cantidad y sabor. Ej: 'media docena de carne y media de jamón y queso'",
                "slot": "items",
                "tool": "search_menu",
                "next_state": "UPSELL"
            },
            "UPSELL": {
                "description": "Sugerir extras",
                "question": "¿Querés agregar bebida o postre?",
                "slot": "extras",
                "tool": "suggest_upsell",
                "next_state": "ENTREGA"
            },
            "ENTREGA": {
                "description": "Método de entrega",
                "question": "¿Retirás por el local o querés delivery?",
                "slot": "metodo_entrega",
                "next_state": "DIRECCION_OR_PAGO"
            },
            "DIRECCION_OR_PAGO": {
                "description": "Dirección si es delivery",
                "conditional": "metodo_entrega == 'delivery'",
                "question": "¿Cuál es tu dirección para el delivery?",
                "slot": "direccion",
                "next_state": "PAGO"
            },
            "PAGO": {
                "description": "Método de pago",
                "question": "¿Cómo pagás? (efectivo/QR/tarjeta)",
                "slot": "metodo_pago",
                "tool": "create_order",
                "next_state": "CONFIRMAR"
            },
            "CONFIRMAR": {
                "description": "Confirmar pedido",
                "message": "Listo, te confirmo el pedido: {resumen}. Tiempo estimado: {eta}.",
                "end": True
            }
        }
        
        self.slots = {
            "categoria": Slot("categoria", required=True),
            "items": Slot("items", required=True),
            "extras": Slot("extras", required=False),
            "metodo_entrega": Slot("metodo_entrega", required=True),
            "direccion": Slot("direccion", required=False),
            "metodo_pago": Slot("metodo_pago", required=True)
        }
    
    def get_current_question(self, state: str) -> str:
        """Obtener pregunta del estado actual"""
        if state in self.states:
            return self.states[state].get("question", "")
        return ""
    
    def get_next_state(self, current_state: str, slot_filled: str = None) -> str:
        """Determinar siguiente estado"""
        if current_state not in self.states:
            return "START"
        
        state_config = self.states[current_state]
        
        # Si hay condición específica
        if "conditional" in state_config:
            # Lógica para manejar condiciones
            pass
        
        return state_config.get("next_state", "START")
    
    def is_complete(self, slots: Dict[str, Slot]) -> bool:
        """Verificar si todos los slots requeridos están llenos"""
        for slot_name, slot in slots.items():
            if slot.required and not slot.filled:
                return False
        return True

class SlotFillingSystem:
    """Sistema principal de slot filling"""
    
    def __init__(self, rag_system=None):
        self.rag_system = rag_system
        self.fsm_gastronomia = GastronomiaFSM()
        self.tools = {
            "kb_search": self._tool_kb_search,
            "search_menu": self._tool_search_menu,
            "suggest_upsell": self._tool_suggest_upsell,
            "create_order": self._tool_create_order
        }
    
    async def _tool_kb_search(self, query: str, top_k: int = 5, workspace_id: str = None) -> Dict[str, Any]:
        """Herramienta RAG para búsqueda en base de conocimientos"""
        try:
            if not self.rag_system:
                return {"error": "RAG system not available"}
            
            results = await self.rag_system.search_similar(
                query, workspace_id, limit=top_k, similarity_threshold=0.7
            )
            
            return {
                "results": results,
                "query": query,
                "total": len(results)
            }
        except Exception as e:
            logger.error(f"Error en kb_search: {e}")
            return {"error": str(e)}
    
    async def _tool_search_menu(self, categoria: str = None, query: str = None, workspace_id: str = None) -> Dict[str, Any]:
        """Buscar items del menú por categoría o texto libre"""
        try:
            # Usar RAG para buscar en el menú
            search_query = categoria or query or "menú"
            
            if self.rag_system:
                results = await self.rag_system.search_similar(
                    search_query, workspace_id, limit=10, similarity_threshold=0.7
                )
                
                # Filtrar y estructurar resultados
                menu_items = []
                for result in results:
                    content = result.get('content', '')
                    metadata = result.get('metadata', {})
                    
                    # Extraer información del item
                    if 'menu_item' in metadata.get('type', ''):
                        menu_items.append({
                            "name": metadata.get('nombre', ''),
                            "price": metadata.get('precio', ''),
                            "description": metadata.get('descripcion', ''),
                            "category": metadata.get('categoria', ''),
                            "content": content
                        })
                
                return {
                    "items": menu_items,
                    "categoria": categoria,
                    "query": query,
                    "total": len(menu_items)
                }
            else:
                return {"error": "RAG system not available"}
                
        except Exception as e:
            logger.error(f"Error en search_menu: {e}")
            return {"error": str(e)}
    
    async def _tool_suggest_upsell(self, items: List[Dict[str, Any]], workspace_id: str = None) -> Dict[str, Any]:
        """Sugerir extras compatibles"""
        try:
            # Buscar bebidas y postres
            suggestions = []
            
            if self.rag_system:
                # Buscar bebidas
                bebidas = await self.rag_system.search_similar(
                    "bebidas", workspace_id, limit=5, similarity_threshold=0.7
                )
                
                # Buscar postres
                postres = await self.rag_system.search_similar(
                    "postres", workspace_id, limit=5, similarity_threshold=0.7
                )
                
                for result in bebidas + postres:
                    metadata = result.get('metadata', {})
                    if 'menu_item' in metadata.get('type', ''):
                        suggestions.append({
                            "name": metadata.get('nombre', ''),
                            "price": metadata.get('precio', ''),
                            "type": "bebida" if "bebida" in metadata.get('categoria', '').lower() else "postre"
                        })
            
            return {
                "suggestions": suggestions,
                "items_count": len(items)
            }
            
        except Exception as e:
            logger.error(f"Error en suggest_upsell: {e}")
            return {"error": str(e)}
    
    async def _tool_create_order(self, items: List[Dict[str, Any]], extras: List[Dict[str, Any]] = None, 
                               metodo_entrega: str = None, direccion: str = None, 
                               metodo_pago: str = None, workspace_id: str = None) -> Dict[str, Any]:
        """Crear pedido y calcular total/ETA"""
        try:
            # Calcular total (simulado)
            total = 0.0
            order_items = []
            
            for item in items:
                # Extraer precio del item
                price_str = item.get('price', '$0')
                price = self._extract_price(price_str)
                quantity = item.get('quantity', 1)
                
                total += price * quantity
                order_items.append({
                    "name": item.get('name', ''),
                    "price": price,
                    "quantity": quantity
                })
            
            # Agregar extras
            if extras:
                for extra in extras:
                    price_str = extra.get('price', '$0')
                    price = self._extract_price(price_str)
                    total += price
                    order_items.append({
                        "name": extra.get('name', ''),
                        "price": price,
                        "quantity": 1
                    })
            
            # Calcular ETA (simulado)
            eta_minutes = 30 if metodo_entrega == "delivery" else 15
            
            order_id = str(uuid.uuid4())
            
            return {
                "order_id": order_id,
                "items": order_items,
                "total": total,
                "eta_minutes": eta_minutes,
                "metodo_entrega": metodo_entrega,
                "direccion": direccion,
                "metodo_pago": metodo_pago,
                "status": "confirmed"
            }
            
        except Exception as e:
            logger.error(f"Error en create_order: {e}")
            return {"error": str(e)}
    
    def _extract_price(self, price_str: str) -> float:
        """Extraer precio numérico del string"""
        import re
        # Buscar patrones como $3.500, $2,500, etc.
        match = re.search(r'\$?(\d{1,3}(?:[.,]\d{3})*)', price_str)
        if match:
            price_clean = match.group(1).replace('.', '').replace(',', '')
            try:
                return float(price_clean)
            except ValueError:
                pass
        return 0.0
    
    async def process_message(self, workspace: Workspace, conversation: Conversation, 
                            message: Message, user_turn: str) -> Tuple[str, Dict[str, Any]]:
        """Procesar mensaje y determinar respuesta"""
        try:
            # Cargar estado actual
            current_state = conversation.state.get('current_state', 'START')
            slots = conversation.state.get('slots', {})
            
            # Convertir slots a objetos Slot
            slot_objects = {}
            for name, slot_data in slots.items():
                slot_objects[name] = Slot(
                    name=name,
                    value=slot_data.get('value'),
                    required=slot_data.get('required', True),
                    filled=slot_data.get('filled', False)
                )
            
            # Determinar intención y llenar slots
            intent = await self._detect_intent(user_turn, current_state, slot_objects)
            
            # Actualizar slots según la intención
            updated_slots = await self._update_slots(intent, user_turn, slot_objects, workspace)
            
            # Determinar siguiente estado
            next_state = self._determine_next_state(current_state, updated_slots, intent)
            
            # Generar respuesta
            response = await self._generate_response(next_state, updated_slots, workspace)
            
            # Actualizar estado
            new_state = {
                'current_state': next_state,
                'slots': {name: asdict(slot) for name, slot in updated_slots.items()},
                'last_updated': datetime.now().isoformat()
            }
            
            return response, new_state
            
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            return "Lo siento, hubo un error. ¿Podrías intentar de nuevo?", conversation.state
    
    async def _detect_intent(self, user_turn: str, current_state: str, slots: Dict[str, Slot]) -> str:
        """Detectar intención del usuario"""
        user_lower = user_turn.lower()
        
        # Intenciones básicas
        if any(word in user_lower for word in ['hola', 'buenas', 'buenos']):
            return 'saludo'
        elif any(word in user_lower for word in ['quiero', 'necesito', 'busco']):
            return 'pedido'
        elif any(word in user_lower for word in ['menú', 'carta', 'qué tienen']):
            return 'consulta_menu'
        elif any(word in user_lower for word in ['precio', 'cuánto', 'cuesta']):
            return 'consulta_precio'
        elif any(word in user_lower for word in ['sí', 'si', 'ok', 'dale']):
            return 'confirmacion'
        elif any(word in user_lower for word in ['no', 'no quiero', 'no gracias']):
            return 'negacion'
        else:
            return 'informacion'
    
    async def _update_slots(self, intent: str, user_turn: str, slots: Dict[str, Slot], 
                          workspace: Workspace) -> Dict[str, Slot]:
        """Actualizar slots según la intención y mensaje del usuario"""
        updated_slots = slots.copy()
        
        # Lógica para llenar slots según el estado actual y la intención
        current_state = slots.get('current_state', Slot('current_state', 'START'))
        
        if intent == 'pedido':
            # Intentar extraer información del pedido
            if 'pizza' in user_turn.lower():
                updated_slots['categoria'] = Slot('categoria', 'pizzas', True, True)
            elif 'empanada' in user_turn.lower():
                updated_slots['categoria'] = Slot('categoria', 'empanadas', True, True)
            elif 'pasta' in user_turn.lower():
                updated_slots['categoria'] = Slot('categoria', 'pastas', True, True)
        
        return updated_slots
    
    def _determine_next_state(self, current_state: str, slots: Dict[str, Slot], intent: str) -> str:
        """Determinar siguiente estado del FSM"""
        if current_state == 'START':
            if intent == 'pedido':
                return 'PEDIR_CATEGORIA'
            elif intent == 'consulta_menu':
                return 'MOSTRAR_MENU'
            else:
                return 'PEDIR_CATEGORIA'
        
        # Lógica para otros estados
        return self.fsm_gastronomia.get_next_state(current_state)
    
    async def _generate_response(self, state: str, slots: Dict[str, Slot], workspace: Workspace) -> str:
        """Generar respuesta basada en el estado actual"""
        if state == 'START':
            return "¡Hola! ¿En qué te puedo ayudar? ¿Querés hacer un pedido o consultar el menú?"
        
        elif state == 'PEDIR_CATEGORIA':
            return "¿De qué categoría querés pedir? Tenemos pizzas, empanadas, pastas, ensaladas y más."
        
        elif state == 'ARMAR_ITEMS':
            categoria = slots.get('categoria', Slot('categoria')).value
            if categoria:
                return f"Perfecto, {categoria}. Decime cantidad y sabor. Ej: 'media docena de carne y media de jamón y queso'."
            else:
                return "Decime qué querés pedir. Ej: 'media docena de empanadas de carne'."
        
        elif state == 'UPSELL':
            return "¿Querés agregar alguna bebida o postre?"
        
        elif state == 'ENTREGA':
            return "¿Retirás por el local o querés delivery?"
        
        elif state == 'PAGO':
            return "¿Cómo pagás? (efectivo/QR/tarjeta)"
        
        elif state == 'CONFIRMAR':
            # Generar resumen del pedido
            items = slots.get('items', Slot('items')).value or []
            total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
            return f"¡Listo! Tu pedido está confirmado. Total: ${total:.0f}. Tiempo estimado: 30 minutos."
        
        else:
            return "¿En qué más te puedo ayudar?"

# Función de conveniencia para crear el sistema
def create_slot_filling_system(rag_system=None) -> SlotFillingSystem:
    """Crear sistema de slot filling con RAG integrado"""
    return SlotFillingSystem(rag_system)
