"""
Vertical Manager - Gestor de verticales con prompts dinámicos
"""

import json
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class VerticalConfig:
    name: str
    system_prompt: str
    intents: list
    entities: list
    actions: list
    language: str
    timezone: str

class VerticalManager:
    def __init__(self):
        self.verticals = self._load_verticals()
    
    def _load_verticals(self) -> Dict[str, VerticalConfig]:
        """Cargar configuraciones de verticales"""
        return {
            "gastronomia": VerticalConfig(
                name="Gastronomía",
                system_prompt="""Eres un asistente de restaurante inteligente. 
Responde de manera amigable y profesional a las consultas de los clientes sobre:
- Menú y platos disponibles
- Reservas y disponibilidad
- Pedidos y delivery
- Horarios de atención
- Precios y promociones

Siempre mantén un tono amigable y profesional. Si no tienes información específica, 
ofrece contactar con el restaurante o pedir más detalles.""",
                intents=["consultar_menu", "hacer_reserva", "hacer_pedido", "consultar_horarios", "consultar_precios"],
                entities=["plato", "cantidad", "fecha", "hora", "personas", "precio"],
                actions=["search_menu", "create_reservation", "create_order", "get_hours", "get_prices"],
                language="es",
                timezone="America/Bogota"
            ),
            
            "inmobiliaria": VerticalConfig(
                name="Inmobiliaria",
                system_prompt="""Eres un asistente de inmobiliaria inteligente.
Responde de manera profesional y útil a las consultas de clientes sobre:
- Propiedades disponibles (casas, apartamentos, oficinas)
- Características y ubicaciones
- Precios y financiación
- Visitas y citas
- Documentación requerida

Siempre mantén un tono profesional y confiable. Si no tienes información específica,
ofrece contactar con un asesor o pedir más detalles.""",
                intents=["consultar_propiedades", "agendar_visita", "consultar_precios", "consultar_financiacion", "solicitar_info"],
                entities=["tipo_propiedad", "ubicacion", "precio", "fecha", "hora", "metros"],
                actions=["search_properties", "schedule_visit", "get_prices", "get_financing", "send_info"],
                language="es",
                timezone="America/Bogota"
            ),
            
            "servicios": VerticalConfig(
                name="Servicios",
                system_prompt="""Eres un asistente de servicios inteligente.
Responde de manera amigable y profesional a las consultas de clientes sobre:
- Servicios disponibles
- Horarios y disponibilidad
- Precios y paquetes
- Citas y reservas
- Información de contacto

Siempre mantén un tono amigable y profesional. Si no tienes información específica,
ofrece contactar con el servicio o pedir más detalles.""",
                intents=["consultar_servicios", "agendar_cita", "consultar_precios", "consultar_horarios", "solicitar_info"],
                entities=["servicio", "fecha", "hora", "precio", "duracion"],
                actions=["search_services", "schedule_appointment", "get_prices", "get_hours", "send_info"],
                language="es",
                timezone="America/Bogota"
            )
        }
    
    def get_vertical_config(self, vertical: str) -> Optional[VerticalConfig]:
        """Obtener configuración de una vertical"""
        return self.verticals.get(vertical)
    
    def get_system_prompt(self, vertical: str, context: str = "") -> str:
        """Obtener system prompt para una vertical"""
        config = self.get_vertical_config(vertical)
        if not config:
            # Fallback a gastronomía
            config = self.verticals["gastronomia"]
        
        base_prompt = config.system_prompt
        if context:
            return f"{base_prompt}\n\nContexto adicional: {context}"
        return base_prompt
    
    def get_intents(self, vertical: str) -> list:
        """Obtener intents de una vertical"""
        config = self.get_vertical_config(vertical)
        return config.intents if config else []
    
    def get_entities(self, vertical: str) -> list:
        """Obtener entities de una vertical"""
        config = self.get_vertical_config(vertical)
        return config.entities if config else []
    
    def get_actions(self, vertical: str) -> list:
        """Obtener actions de una vertical"""
        config = self.get_vertical_config(vertical)
        return config.actions if config else []
    
    def get_language(self, vertical: str) -> str:
        """Obtener idioma de una vertical"""
        config = self.get_vertical_config(vertical)
        return config.language if config else "es"
    
    def get_timezone(self, vertical: str) -> str:
        """Obtener timezone de una vertical"""
        config = self.get_vertical_config(vertical)
        return config.timezone if config else "America/Bogota"
    
    def list_verticals(self) -> list:
        """Listar todas las verticales disponibles"""
        return list(self.verticals.keys())
    
    def add_vertical(self, name: str, config: VerticalConfig):
        """Agregar una nueva vertical"""
        self.verticals[name] = config
        logger.info(f"Vertical '{name}' agregada")
    
    def update_vertical(self, name: str, config: VerticalConfig):
        """Actualizar una vertical existente"""
        if name in self.verticals:
            self.verticals[name] = config
            logger.info(f"Vertical '{name}' actualizada")
        else:
            logger.warning(f"Vertical '{name}' no encontrada para actualizar")
    
    def remove_vertical(self, name: str):
        """Remover una vertical"""
        if name in self.verticals:
            del self.verticals[name]
            logger.info(f"Vertical '{name}' removida")
        else:
            logger.warning(f"Vertical '{name}' no encontrada para remover")

# Instancia global
vertical_manager = VerticalManager()
