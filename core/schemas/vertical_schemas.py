#!/usr/bin/env python3
"""
Esquemas JSON para cada vertical del sistema
Gastronomía, Inmobiliaria y Servicios/Turnos
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

@dataclass
class MenuItem:
    """Item del menú"""
    sku: str
    name: str
    category: str
    price: float
    options: List[str] = None
    labels: List[str] = None
    available: bool = True
    description: str = ""

@dataclass
class Combo:
    """Combo de items"""
    code: str
    items: List[Dict[str, Any]]  # [{"sku": "EMP-CARNE", "qty": 6}]
    price: float
    name: str = ""

@dataclass
class UpsellRule:
    """Regla de upsell"""
    if_contains: List[str]
    suggest: List[str]

@dataclass
class GastronomiaPolicies:
    """Políticas de gastronomía"""
    delivery_fee: float
    delivery_zones: List[str]
    hours: List[Dict[str, str]]  # [{"days": "lun-dom", "open": "11:30", "close": "23:30"}]
    payment_methods: List[str]
    min_order: float = 0
    max_delivery_time: int = 60  # minutos

@dataclass
class GastronomiaSchema:
    """Esquema completo de gastronomía"""
    menu: List[MenuItem]
    combos: List[Combo]
    upsell_rules: List[UpsellRule]
    policies: GastronomiaPolicies

@dataclass
class Property:
    """Propiedad inmobiliaria"""
    id: str
    operation: str  # venta, alquiler
    type: str  # departamento, casa, ph, oficina, local, terreno
    zone: str
    price: float
    bedrooms: int
    bathrooms: int
    amenities: List[str]
    surface_m2: float
    url: str
    media: List[str]  # URLs de imágenes
    address: str = ""
    description: str = ""
    available: bool = True

@dataclass
class VisitPolicy:
    """Política de visitas"""
    slots_week: List[str]  # ["lun-vie 10:00-18:00", "sab 10:00-14:00"]
    meeting_point: str
    duration_minutes: int = 30
    max_visits_per_slot: int = 1

@dataclass
class InmobiliariaSchema:
    """Esquema completo de inmobiliaria"""
    properties: List[Property]
    visit_policy: VisitPolicy

@dataclass
class Service:
    """Servicio disponible"""
    code: str
    name: str
    duration_min: int
    price: float
    description: str = ""
    category: str = ""
    requirements: List[str] = None

@dataclass
class Staff:
    """Personal del servicio"""
    id: str
    name: str
    skills: List[str]  # códigos de servicios que puede hacer
    phone: str = ""
    email: str = ""

@dataclass
class Schedule:
    """Horario de personal"""
    staff_id: str
    day: str  # lun, mar, mie, jue, vie, sab, dom
    from_time: str  # "10:00"
    to_time: str  # "18:00"
    available: bool = True

@dataclass
class ServiciosPolicies:
    """Políticas de servicios"""
    cancellation_hours: int
    payment_methods: List[str]
    max_advance_days: int = 30
    min_advance_hours: int = 2

@dataclass
class ServiciosSchema:
    """Esquema completo de servicios"""
    services: List[Service]
    staff: List[Staff]
    schedule: List[Schedule]
    policies: ServiciosPolicies

class SchemaValidator:
    """Validador de esquemas"""
    
    @staticmethod
    def validate_gastronomia(data: Dict[str, Any]) -> bool:
        """Validar esquema de gastronomía"""
        try:
            # Validar estructura básica
            required_keys = ["menu", "combos", "upsell_rules", "policies"]
            for key in required_keys:
                if key not in data:
                    return False
            
            # Validar menú
            for item in data["menu"]:
                required_item_keys = ["sku", "name", "category", "price"]
                for key in required_item_keys:
                    if key not in item:
                        return False
                
                # Validar tipos
                if not isinstance(item["price"], (int, float)):
                    return False
                if item["price"] < 0:
                    return False
            
            # Validar políticas
            policies = data["policies"]
            if not isinstance(policies["delivery_fee"], (int, float)):
                return False
            if not isinstance(policies["delivery_zones"], list):
                return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def validate_inmobiliaria(data: Dict[str, Any]) -> bool:
        """Validar esquema de inmobiliaria"""
        try:
            # Validar estructura básica
            required_keys = ["properties", "visit_policy"]
            for key in required_keys:
                if key not in data:
                    return False
            
            # Validar propiedades
            for prop in data["properties"]:
                required_prop_keys = ["id", "operation", "type", "zone", "price", "bedrooms", "bathrooms"]
                for key in required_prop_keys:
                    if key not in prop:
                        return False
                
                # Validar tipos
                if not isinstance(prop["price"], (int, float)):
                    return False
                if prop["price"] < 0:
                    return False
                if not isinstance(prop["bedrooms"], int):
                    return False
                if prop["bedrooms"] < 0:
                    return False
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def validate_servicios(data: Dict[str, Any]) -> bool:
        """Validar esquema de servicios"""
        try:
            # Validar estructura básica
            required_keys = ["services", "staff", "schedule", "policies"]
            for key in required_keys:
                if key not in data:
                    return False
            
            # Validar servicios
            for service in data["services"]:
                required_service_keys = ["code", "name", "duration_min", "price"]
                for key in required_service_keys:
                    if key not in service:
                        return False
                
                # Validar tipos
                if not isinstance(service["price"], (int, float)):
                    return False
                if service["price"] < 0:
                    return False
                if not isinstance(service["duration_min"], int):
                    return False
                if service["duration_min"] <= 0:
                    return False
            
            return True
            
        except Exception:
            return False

class SchemaExamples:
    """Ejemplos de esquemas para testing"""
    
    @staticmethod
    def get_gastronomia_example() -> Dict[str, Any]:
        """Ejemplo de esquema de gastronomía"""
        return {
            "menu": [
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
            ],
            "combos": [
                {
                    "code": "COMBO-EMP12-COCA",
                    "name": "Combo Empanadas + Bebida",
                    "items": [
                        {"sku": "EMP-CARNE", "qty": 6},
                        {"sku": "EMP-JYQ", "qty": 6},
                        {"sku": "COCA-500", "qty": 1}
                    ],
                    "price": 14900
                }
            ],
            "upsell_rules": [
                {
                    "if_contains": ["empanadas"],
                    "suggest": ["COCA-500", "FLAN"]
                },
                {
                    "if_contains": ["pizzas"],
                    "suggest": ["COCA-500", "ENSALADA-MIXTA"]
                }
            ],
            "policies": {
                "delivery_fee": 1500,
                "delivery_zones": ["Centro", "Norte", "Sur"],
                "hours": [
                    {"days": "lun-dom", "open": "11:30", "close": "23:30"}
                ],
                "payment_methods": ["efectivo", "qr", "tarjeta"],
                "min_order": 5000,
                "max_delivery_time": 45
            }
        }
    
    @staticmethod
    def get_inmobiliaria_example() -> Dict[str, Any]:
        """Ejemplo de esquema de inmobiliaria"""
        return {
            "properties": [
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
                    "media": ["https://example.com/foto1.jpg", "https://example.com/foto2.jpg"],
                    "address": "Honduras 1234, Palermo",
                    "description": "Departamento luminoso con balcón a la calle",
                    "available": True
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
                    "media": ["https://example.com/foto3.jpg"],
                    "address": "Av. Santa Fe 4567, Recoleta",
                    "description": "Departamento amplio con amenities",
                    "available": True
                }
            ],
            "visit_policy": {
                "slots_week": [
                    "lun-vie 10:00-18:00",
                    "sab 10:00-14:00"
                ],
                "meeting_point": "Oficina Palermo, Honduras 1234",
                "duration_minutes": 30,
                "max_visits_per_slot": 1
            }
        }
    
    @staticmethod
    def get_servicios_example() -> Dict[str, Any]:
        """Ejemplo de esquema de servicios"""
        return {
            "services": [
                {
                    "code": "CORTE",
                    "name": "Corte de pelo",
                    "duration_min": 45,
                    "price": 7000,
                    "description": "Corte de pelo profesional",
                    "category": "peluqueria",
                    "requirements": []
                },
                {
                    "code": "COLOR",
                    "name": "Color",
                    "duration_min": 90,
                    "price": 18000,
                    "description": "Tintura profesional",
                    "category": "peluqueria",
                    "requirements": ["consulta previa"]
                },
                {
                    "code": "MANICURE",
                    "name": "Manicure",
                    "duration_min": 30,
                    "price": 5000,
                    "description": "Manicure completa",
                    "category": "estetica",
                    "requirements": []
                }
            ],
            "staff": [
                {
                    "id": "STF-ANA",
                    "name": "Ana",
                    "skills": ["CORTE", "COLOR"],
                    "phone": "+5491123456789",
                    "email": "ana@peluqueria.com"
                },
                {
                    "id": "STF-MARIA",
                    "name": "María",
                    "skills": ["CORTE", "MANICURE"],
                    "phone": "+5491123456790",
                    "email": "maria@peluqueria.com"
                }
            ],
            "schedule": [
                {
                    "staff_id": "STF-ANA",
                    "day": "lun",
                    "from_time": "10:00",
                    "to_time": "18:00",
                    "available": True
                },
                {
                    "staff_id": "STF-ANA",
                    "day": "mar",
                    "from_time": "10:00",
                    "to_time": "18:00",
                    "available": True
                },
                {
                    "staff_id": "STF-MARIA",
                    "day": "lun",
                    "from_time": "09:00",
                    "to_time": "17:00",
                    "available": True
                }
            ],
            "policies": {
                "cancellation_hours": 12,
                "payment_methods": ["efectivo", "qr", "tarjeta"],
                "max_advance_days": 30,
                "min_advance_hours": 2
            }
        }

# Función de conveniencia
def get_schema_example(vertical: str) -> Dict[str, Any]:
    """Obtener ejemplo de esquema por vertical"""
    examples = SchemaExamples()
    
    if vertical == "gastronomia":
        return examples.get_gastronomia_example()
    elif vertical == "inmobiliaria":
        return examples.get_inmobiliaria_example()
    elif vertical == "servicios":
        return examples.get_servicios_example()
    else:
        raise ValueError(f"Vertical no soportado: {vertical}")

def validate_schema(vertical: str, data: Dict[str, Any]) -> bool:
    """Validar esquema por vertical"""
    validator = SchemaValidator()
    
    if vertical == "gastronomia":
        return validator.validate_gastronomia(data)
    elif vertical == "inmobiliaria":
        return validator.validate_inmobiliaria(data)
    elif vertical == "servicios":
        return validator.validate_servicios(data)
    else:
        raise ValueError(f"Vertical no soportado: {vertical}")

