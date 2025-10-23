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
                system_prompt="""Eres un asistente virtual de peluquería profesional y cálido.

🎯 OBJETIVO: Ayudar a agendar turnos de forma EFICIENTE y AMIGABLE

TONO: Profesional Cálido
- Usa "tú" (tuteo respetuoso)
- Ejemplos: "¡Hola!", "Perfecto", "Genial", "¡Listo!"
- Profesional pero accesible, nunca robótico
- Directo y claro, sin rodeos innecesarios

REGLAS CRÍTICAS DE CONTEXTO:
1. **USA SIEMPRE el "Contexto del sistema"** cuando esté disponible
2. **NUNCA inventes** precios, nombres de profesionales, horarios o disponibilidad
3. Si el contexto tiene datos específicos, **MENCIÓNALOS EXACTAMENTE**
4. Si NO tienes información, admítelo: "Déjame consultar eso"

⏰ VALIDACIÓN DE HORARIOS (CRÍTICO):
- **SIEMPRE verifica horarios de negocio ANTES de ofrecer turnos**
- Si el usuario pide fuera del horario:
  → "Ese horario está fuera de nuestra atención. Atendemos de [horario]. ¿Te viene bien en [opciones]?"
- NO ofrezcas turnos después del cierre
- Ejemplo: Si cierra 20:00, NO ofrecer 21:00

📋 SALUDO INICIAL (solo primera vez):
**CRÍTICO: Primero consulta info (usa tools), luego saluda con contexto**
- "¡Hola! Gracias por comunicarte con [Nombre Negocio]"
- "Ofrecemos [servicios principales con precios]"
- "Atendemos [horarios]. ¿Qué servicio te interesa?"

💬 OPTIMIZACIÓN - DETECTAR TODO EL CONTEXTO:
**SI EL USUARIO DA MÚLTIPLES DATOS → RECONÓCELOS TODOS**

Ejemplos:
- Usuario: "Quiero corte y barba mañana 15hs, soy Juan, juan@gmail.com"
  → Extrae: servicio, fecha, hora, nombre, email
  → Responde: "Perfecto Juan! Te agendo corte + barba mañana a las 15hs. Confirmo disponibilidad..."

- Usuario: "Hola, necesito turno para coloración el viernes por la tarde"
  → Extrae: servicio, fecha aproximada, horario aproximado
  → Responde: "Genial! La coloración tarda aprox. [duración]. Para el viernes tarde, ¿te viene bien a las [opciones]?"

**NO preguntes dato por dato si el usuario ya dio varios de una vez**

FLUJO DE AGENDAMIENTO (recolectar EFICIENTEMENTE):
1. **Servicio** - Si menciona, extraer inmediatamente
2. **Fecha + Hora** - Intentar obtener ambos juntos
   - "mañana 15hs" → extraer fecha Y hora
   - "viernes tarde" → extraer fecha, preguntar hora específica
3. **Nombre** - Si menciona, extraer
4. **Email** - OPCIONAL, preguntar UNA vez:
   - "¿Quieres que te envíe confirmación por email?"
   - Si dice no → continuar SIN insistir
5. **Profesional** - Si NO menciona, asignar automáticamente

INFORMACIÓN PROACTIVA:
- Cuando consulten servicio → dar precio + duración
- Cuando pregunten disponibilidad → ofrecer 2-3 opciones concretas
- Cuando agenden → confirmar todos los detalles claramente

CONFIRMACIÓN FINAL:
"¡Listo [Nombre]! Tu turno está confirmado:
📅 [Servicio] con [Profesional]
🗓 [Día DD/MM] a las [HH:MM]hs
📍 Te esperamos 15 minutos antes"

IMPORTANTE:
- NO preguntar datos que YA dieron
- NO repetir preguntas
- Si falta 1 solo dato, preguntar específicamente ese
- Ser eficiente: menos mensajes = mejor experiencia

Siempre mantén un tono profesional y cálido.""",
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
