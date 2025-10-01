#!/usr/bin/env python3
"""
Herramientas (Tools) para cada vertical
Implementa las funciones que el orquestador LLM puede llamar
"""

import json
import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import uuid

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GastronomiaTools:
    """Herramientas para vertical de gastronomía"""
    
    def __init__(self, db_connection=None, rag_system=None):
        self.db_connection = db_connection
        self.rag_system = rag_system
    
    async def search_menu(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Buscar items del menú usando AI y base de datos"""
        try:
            query = args.get("query", "")
            categoria = args.get("categoria", "")
            
            # Obtener menú desde base de datos
            menu_items = await self._get_menu_from_db(workspace_id)
            
            if not menu_items:
                return {"error": "No se pudo cargar el menú", "items": []}
            
            # Usar AI para entender la intención y buscar
            prompt = f"""
Analiza la consulta del usuario y encuentra los items del menú más relevantes:

CONSULTA DEL USUARIO: "{query}"
CATEGORÍA SOLICITADA: "{categoria}"

MENÚ DISPONIBLE:
{json.dumps(menu_items, indent=2, ensure_ascii=False)}

INSTRUCCIONES:
1. Entiende la intención del usuario (ej: "algo de carne" = empanadas de carne, "bebida" = coca/agua)
2. Considera sinónimos y variaciones (ej: "empas" = empanadas, "gaseosa" = coca cola)
3. Si pide algo específico que no existe, sugiere alternativas similares
4. Máximo 5 resultados más relevantes
5. Incluye un score de relevancia (0-1)
6. Responde SOLO con JSON válido

FORMATO DE RESPUESTA:
{{
  "items": [
    {{
      "sku": "EMP-CARNE",
      "name": "Empanada de carne",
      "category": "empanadas",
      "price": 1200,
      "relevance_score": 0.95,
      "match_reason": "Coincide exactamente con la búsqueda de carne"
    }}
  ],
  "query_analysis": "Análisis de lo que busca el usuario",
  "total": 1,
  "search_method": "ai_semantic"
}}
"""
            
            # Llamar al LLM para búsqueda inteligente
            response = await self._call_llm_for_search(prompt)
            
            if response:
                return response
            else:
                # Fallback: devolver menú completo o por categoría
                if categoria:
                    filtered_items = [item for item in menu_items if item.get("category") == categoria]
                else:
                    filtered_items = menu_items
                
                return {
                    "items": filtered_items,
                    "categoria": categoria,
                    "query": query,
                    "total": len(filtered_items),
                    "search_method": "db_fallback"
                }
            
        except Exception as e:
            logger.error(f"Error en search_menu: {e}")
            return {"error": str(e), "items": []}
    
    async def _get_menu_from_db(self, workspace_id: str) -> List[Dict[str, Any]]:
        """Obtener menú desde base de datos"""
        try:
            if not self.db_connection:
                # Fallback: datos de ejemplo para testing
                return [
                    {
                        "sku": "EMP-CARNE",
                        "name": "Empanada de carne",
                        "category": "empanadas",
                        "price": 1200,
                        "options": ["al horno", "frita"],
                        "labels": ["picante"],
                        "available": True,
                        "description": "Empanada casera rellena de carne molida con cebolla y especias"
                    },
                    {
                        "sku": "EMP-JYQ",
                        "name": "Empanada de jamón y queso",
                        "category": "empanadas",
                        "price": 1200,
                        "options": ["al horno", "frita"],
                        "labels": [],
                        "available": True,
                        "description": "Empanada casera rellena de jamón cocido y queso mozzarella"
                    },
                    {
                        "sku": "PIZZA-MARGHERITA",
                        "name": "Pizza Margherita",
                        "category": "pizzas",
                        "price": 3500,
                        "options": ["chica", "mediana", "grande"],
                        "labels": ["vegetariana"],
                        "available": True,
                        "description": "Pizza clásica con salsa de tomate, mozzarella fresca y albahaca"
                    },
                    {
                        "sku": "COCA-500",
                        "name": "Coca Cola 500ml",
                        "category": "bebidas",
                        "price": 800,
                        "options": [],
                        "labels": [],
                        "available": True,
                        "description": "Bebida gaseosa de 500ml"
                    }
                ]
            
            # En producción: consulta real a la base de datos
            # cursor = self.db_connection.cursor()
            # cursor.execute("SELECT * FROM menu_items WHERE workspace_id = %s AND available = true", (workspace_id,))
            # results = cursor.fetchall()
            # return [dict(row) for row in results]
            
            return []
            
        except Exception as e:
            logger.error(f"Error obteniendo menú de DB: {e}")
            return []
    
    async def _call_llm_for_search(self, prompt: str) -> Dict[str, Any]:
        """Llamar al LLM para búsqueda inteligente"""
        try:
            import requests
            
            response = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "llama3.1:8b",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("message", {}).get("content", "")
                
                # Extraer JSON de la respuesta
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start:json_end]
                    return json.loads(json_str)
            
            return None
            
        except Exception as e:
            logger.error(f"Error llamando LLM para búsqueda: {e}")
            return None
    
    
    async def create_order(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Crear pedido"""
        try:
            items = args.get("items", [])
            extras = args.get("extras", [])
            metodo_entrega = args.get("metodo_entrega")
            direccion = args.get("direccion")
            metodo_pago = args.get("metodo_pago")
            
            # Calcular total
            total = 0
            order_items = []
            
            for item in items:
                price = item.get("price", 0)
                quantity = item.get("quantity", 1)
                total += price * quantity
                order_items.append({
                    "sku": item.get("sku"),
                    "name": item.get("name"),
                    "price": price,
                    "quantity": quantity
                })
            
            # Agregar extras
            for extra in extras:
                price = extra.get("price", 0)
                total += price
                order_items.append({
                    "sku": extra.get("sku"),
                    "name": extra.get("name"),
                    "price": price,
                    "quantity": 1
                })
            
            # Agregar fee de delivery si aplica
            if metodo_entrega == "delivery":
                delivery_fee = 1500
                total += delivery_fee
                order_items.append({
                    "sku": "DELIVERY-FEE",
                    "name": "Costo de envío",
                    "price": delivery_fee,
                    "quantity": 1
                })
            
            # Calcular ETA
            eta_minutes = 30 if metodo_entrega == "delivery" else 15
            
            # Generar ID de pedido
            order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
            
            # En producción, guardar en base de datos
            order_data = {
                "order_id": order_id,
                "workspace_id": workspace_id,
                "items": order_items,
                "total": total,
                "metodo_entrega": metodo_entrega,
                "direccion": direccion,
                "metodo_pago": metodo_pago,
                "eta_minutes": eta_minutes,
                "status": "confirmed",
                "created_at": datetime.now().isoformat()
            }
            
            return order_data
            
        except Exception as e:
            logger.error(f"Error en create_order: {e}")
            return {"error": str(e)}

class InmobiliariaTools:
    """Herramientas para vertical de inmobiliaria"""
    
    def __init__(self, db_connection=None, rag_system=None):
        self.db_connection = db_connection
        self.rag_system = rag_system
    
    async def list_properties(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Listar propiedades según filtros"""
        try:
            operation = args.get("operation")
            type_prop = args.get("type")
            zone = args.get("zone")
            budget_min = args.get("budget_min")
            budget_max = args.get("budget_max")
            bedrooms = args.get("bedrooms")
            
            # Simular propiedades
            properties = [
                {
                    "id": "PROP-001",
                    "operation": "venta",
                    "type": "departamento",
                    "zone": "Palermo",
                    "price": 150000,
                    "bedrooms": 2,
                    "bathrooms": 1,
                    "amenities": ["balcón", "cochera"],
                    "surface_m2": 65,
                    "url": "https://tusitio.com/prop/PROP-001",
                    "address": "Honduras 1234, Palermo"
                },
                {
                    "id": "PROP-002",
                    "operation": "alquiler",
                    "type": "departamento",
                    "zone": "Recoleta",
                    "price": 180000,
                    "bedrooms": 3,
                    "bathrooms": 2,
                    "amenities": ["balcón", "cochera", "sum"],
                    "surface_m2": 85,
                    "url": "https://tusitio.com/prop/PROP-002",
                    "address": "Av. Santa Fe 4567, Recoleta"
                }
            ]
            
            # Aplicar filtros
            filtered_properties = properties
            
            if operation:
                filtered_properties = [p for p in filtered_properties if p["operation"] == operation]
            
            if type_prop:
                filtered_properties = [p for p in filtered_properties if p["type"] == type_prop]
            
            if zone:
                filtered_properties = [p for p in filtered_properties if zone.lower() in p["zone"].lower()]
            
            if budget_min:
                filtered_properties = [p for p in filtered_properties if p["price"] >= budget_min]
            
            if budget_max:
                filtered_properties = [p for p in filtered_properties if p["price"] <= budget_max]
            
            if bedrooms:
                filtered_properties = [p for p in filtered_properties if p["bedrooms"] >= bedrooms]
            
            return {
                "properties": filtered_properties[:5],  # Máximo 5 propiedades
                "total": len(filtered_properties),
                "filters_applied": {
                    "operation": operation,
                    "type": type_prop,
                    "zone": zone,
                    "budget_min": budget_min,
                    "budget_max": budget_max,
                    "bedrooms": bedrooms
                }
            }
            
        except Exception as e:
            logger.error(f"Error en list_properties: {e}")
            return {"error": str(e), "properties": []}
    
    async def schedule_visit(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Agendar visita"""
        try:
            property_id = args.get("property_id")
            visit_datetime = args.get("visit_datetime")
            
            # Validar que la propiedad existe
            # En producción, verificar en base de datos
            
            # Generar ID de visita
            visit_id = f"VIS-{uuid.uuid4().hex[:8].upper()}"
            
            # En producción, guardar en base de datos
            visit_data = {
                "visit_id": visit_id,
                "property_id": property_id,
                "visit_datetime": visit_datetime,
                "status": "scheduled",
                "workspace_id": workspace_id,
                "created_at": datetime.now().isoformat()
            }
            
            return visit_data
            
        except Exception as e:
            logger.error(f"Error en schedule_visit: {e}")
            return {"error": str(e)}

class ServiciosTools:
    """Herramientas para vertical de servicios/turnos"""
    
    def __init__(self, db_connection=None, rag_system=None):
        self.db_connection = db_connection
        self.rag_system = rag_system
    
    async def list_services(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Listar servicios disponibles"""
        try:
            # Simular servicios
            services = [
                {
                    "code": "CORTE",
                    "name": "Corte de pelo",
                    "duration_min": 45,
                    "price": 7000,
                    "description": "Corte de pelo profesional",
                    "category": "peluqueria"
                },
                {
                    "code": "COLOR",
                    "name": "Color",
                    "duration_min": 90,
                    "price": 18000,
                    "description": "Tintura profesional",
                    "category": "peluqueria"
                },
                {
                    "code": "MANICURE",
                    "name": "Manicure",
                    "duration_min": 30,
                    "price": 5000,
                    "description": "Manicure completa",
                    "category": "estetica"
                }
            ]
            
            return {
                "services": services,
                "total": len(services)
            }
            
        except Exception as e:
            logger.error(f"Error en list_services: {e}")
            return {"error": str(e), "services": []}
    
    async def list_slots(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Listar horarios disponibles"""
        try:
            service_code = args.get("service_code")
            date = args.get("date")
            staff_id = args.get("staff_id")
            
            # Simular horarios disponibles
            # En producción, consultar base de datos
            available_slots = [
                {
                    "time": "10:00",
                    "staff_id": "STF-ANA",
                    "staff_name": "Ana",
                    "available": True
                },
                {
                    "time": "11:00",
                    "staff_id": "STF-ANA",
                    "staff_name": "Ana",
                    "available": True
                },
                {
                    "time": "14:00",
                    "staff_id": "STF-MARIA",
                    "staff_name": "María",
                    "available": True
                }
            ]
            
            # Filtrar por staff si se especifica
            if staff_id:
                available_slots = [slot for slot in available_slots if slot["staff_id"] == staff_id]
            
            return {
                "slots": available_slots,
                "service_code": service_code,
                "date": date,
                "total": len(available_slots)
            }
            
        except Exception as e:
            logger.error(f"Error en list_slots: {e}")
            return {"error": str(e), "slots": []}
    
    async def book_slot(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Reservar turno"""
        try:
            service_code = args.get("service_code")
            date = args.get("date")
            time = args.get("time")
            staff_id = args.get("staff_id")
            payment_method = args.get("payment_method")
            
            # Generar ID de reserva
            booking_id = f"BK-{uuid.uuid4().hex[:8].upper()}"
            
            # En producción, verificar disponibilidad y guardar en base de datos
            booking_data = {
                "booking_id": booking_id,
                "service_code": service_code,
                "date": date,
                "time": time,
                "staff_id": staff_id,
                "payment_method": payment_method,
                "status": "confirmed",
                "workspace_id": workspace_id,
                "created_at": datetime.now().isoformat()
            }
            
            return booking_data
            
        except Exception as e:
            logger.error(f"Error en book_slot: {e}")
            return {"error": str(e)}

class RAGTools:
    """Herramientas RAG para búsqueda en base de conocimientos"""
    
    def __init__(self, rag_system=None):
        self.rag_system = rag_system
    
    async def kb_search(self, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Búsqueda en base de conocimientos"""
        try:
            query = args.get("query")
            top_k = args.get("top_k", 5)
            
            if not self.rag_system:
                return {"error": "RAG system not available", "results": []}
            
            # Buscar en RAG
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
            return {"error": str(e), "results": []}

class ToolsManager:
    """Manager de herramientas para el orquestador"""
    
    def __init__(self, db_connection=None, rag_system=None):
        self.db_connection = db_connection
        self.rag_system = rag_system
        
        # Inicializar herramientas por vertical
        self.gastronomia_tools = GastronomiaTools(db_connection, rag_system)
        self.inmobiliaria_tools = InmobiliariaTools(db_connection, rag_system)
        self.servicios_tools = ServiciosTools(db_connection, rag_system)
        self.rag_tools = RAGTools(rag_system)
        
        # Mapeo de herramientas
        self.tools = {
            # RAG (común a todos)
            "kb_search": self.rag_tools.kb_search,
            
            # Gastronomía
            "search_menu": self.gastronomia_tools.search_menu,
            "create_order": self.gastronomia_tools.create_order,
            
            # Inmobiliaria
            "list_properties": self.inmobiliaria_tools.list_properties,
            "schedule_visit": self.inmobiliaria_tools.schedule_visit,
            
            # Servicios
            "list_services": self.servicios_tools.list_services,
            "list_slots": self.servicios_tools.list_slots,
            "book_slot": self.servicios_tools.book_slot
        }
    
    async def execute_tool(self, tool_name: str, args: Dict[str, Any], workspace_id: str) -> Dict[str, Any]:
        """Ejecutar herramienta"""
        try:
            if tool_name in self.tools:
                result = await self.tools[tool_name](args, workspace_id)
                return result
            else:
                return {"error": f"Tool {tool_name} not found"}
                
        except Exception as e:
            logger.error(f"Error ejecutando tool {tool_name}: {e}")
            return {"error": str(e)}
    
    def get_available_tools(self, vertical: str) -> List[str]:
        """Obtener herramientas disponibles por vertical"""
        base_tools = ["kb_search"]
        
        if vertical == "gastronomia":
            return base_tools + ["search_menu", "create_order"]
        elif vertical == "inmobiliaria":
            return base_tools + ["list_properties", "schedule_visit"]
        elif vertical == "servicios":
            return base_tools + ["list_services", "list_slots", "book_slot"]
        else:
            return base_tools

# Función de conveniencia
def create_tools_manager(db_connection=None, rag_system=None) -> ToolsManager:
    """Crear manager de herramientas"""
    return ToolsManager(db_connection, rag_system)
