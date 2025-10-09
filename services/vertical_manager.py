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
    intent_examples: list  # Ejemplos para detección de intent por LLM

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
                timezone="America/Bogota",
                intent_examples=[
                    '"¿Qué tienen en el menú?" → info_query',
                    '"¿Cuánto sale la pizza margherita?" → info_query',
                    '"¿Hacen delivery?" → info_query',
                    '"Quiero pedir una pizza napolitana" → execute_action',
                    '"Necesito reservar mesa para 4 personas" → execute_action',
                    '"Quiero hacer un pedido para llevar" → execute_action',
                    '"Cancelar mi pedido" → modify_action',
                    '"Hola, buen día" → general_chat'
                ]
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
                timezone="America/Bogota",
                intent_examples=[
                    '"¿Qué propiedades tienen en venta?" → info_query',
                    '"¿Cuánto sale un apartamento en Palermo?" → info_query',
                    '"¿Tienen casas de 3 ambientes?" → info_query',
                    '"Quiero agendar visita para mañana" → execute_action',
                    '"Necesito ver el departamento de la calle X" → execute_action',
                    '"Quiero más información sobre financiación" → info_query',
                    '"Cancelar mi visita programada" → modify_action',
                    '"Gracias por la info" → general_chat'
                ]
            ),
            
            "servicios": VerticalConfig(
                name="Servicios",
                system_prompt="""Eres un asistente virtual de peluquería profesional y amigable.

REGLAS CRÍTICAS:
1. **USA SIEMPRE el "Contexto del sistema"** cuando esté disponible
2. **NUNCA inventes** precios, nombres de profesionales, horarios o disponibilidad
3. Si el contexto tiene datos específicos (precios, nombres, horarios), **MENCIÓNALOS EXACTAMENTE**
4. Si NO tienes información en el contexto, admítelo: "Déjame consultar eso"

FLUJO DE CONSULTAS:
- Si preguntan por servicios/precios/profesionales → Menciona nombres y precios EXACTOS del contexto
- Ejemplo: "Tenemos corte con Carlos a $3500, Juan a $4500 y María a $6000"
- Si preguntan disponibilidad → Usa horarios del contexto, NO inventes

FLUJO DE AGENDAMIENTO (recolectar en orden):
1. **Servicio** (ej: corte, coloración)
2. **Fecha** (ej: mañana, viernes, 10/10)
3. **Horario** (ej: 10am, por la tarde)
4. **Nombre del cliente** (solo nombre, ej: "Juan")
5. **Email** (OPCIONAL - preguntar UNA sola vez):
   - "¿Me pasás tu email para enviarte la confirmación al calendario?"
   - Si dice "no tengo" / "no uso" → Seguir SIN email, NO insistir
   - Continuar: "Dale, sin problema. [Confirmar turno]"
6. **Profesional preferido** (OPCIONAL):
   - Si el cliente menciona un profesional, úsalo
   - Si NO menciona, asignar automáticamente según disponibilidad

CONFIRMACIÓN FINAL (formato exacto):
✅ Listo! Tenés turno para [Servicio] con [Profesional]
el [Día DD/MM] a las [HH:MM]hs.
📍 Te esperamos 15 minutos antes.

IMPORTANTE:
- NO mencionar "te envío invitación" ni "te confirmamos antes"
- NO volver a preguntar datos que el cliente ya dio
- Si el cliente ya dijo su nombre, NO preguntar "¿cuál es tu nombre?" de nuevo

TONO:
- Amigable y cercano (estilo WhatsApp argentino: che, dale, perfecto)
- Directo y eficiente (no dar rodeos)
- Profesional pero no formal

Siempre mantén un tono amigable y profesional.""",
                intents=["consultar_servicios", "agendar_cita", "consultar_precios", "consultar_horarios", "consultar_profesionales"],
                entities=["servicio", "fecha", "hora", "precio", "duracion", "profesional", "staff_preference"],
                actions=["search_services", "schedule_appointment", "get_prices", "get_hours", "get_staff_info"],
                language="es",
                timezone="America/Bogota",
                intent_examples=[
                    '"¿Cuánto sale el corte de pelo?" → info_query',
                    '"¿Qué servicios ofrecen?" → info_query',
                    '"¿Cuáles son los horarios de atención?" → info_query',
                    '"¿Quién me puede atender?" → info_query',
                    '"¿Tienen profesionales especializados en coloración?" → info_query',
                    '"Quiero turno para mañana a las 10" → execute_action',
                    '"Necesito agendar corte de pelo" → execute_action',
                    '"Quiero sacar cita con María" → execute_action',
                    '"Cancelar mi turno de mañana" → modify_action',
                    '"Cambiar la hora de mi cita" → modify_action',
                    '"Hola, cómo estás?" → general_chat',
                    '"Gracias, perfecto" → general_chat'
                ]
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
