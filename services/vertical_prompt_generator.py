"""
Generador de prompts dinámicos por vertical para el planner
"""

import yaml
import logging
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)

class VerticalPromptGenerator:
    """Genera prompts dinámicos basados en el vertical"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "/home/nictes/workspace/nictes1/pulpo/config/vertical_prompts.yml"
        self._config = None
        self._load_config()
    
    def _load_config(self):
        """Carga la configuración de prompts por vertical"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"✅ Vertical prompts config loaded from {self.config_path}")
        except Exception as e:
            logger.error(f"❌ Error loading vertical prompts config: {e}")
            self._config = {}
    
    def get_vertical_config(self, vertical: str) -> Dict[str, Any]:
        """Obtiene la configuración para un vertical específico"""
        return self._config.get('vertical_configs', {}).get(vertical, {})
    
    def generate_planner_prompt(self, vertical: str, workspace_id: str, tools_description: List[str], 
                              user_input: str, current_slots: Dict[str, Any], 
                              objective: str, greeted: bool) -> str:
        """Genera el prompt del planner dinámicamente basado en el vertical"""
        
        vertical_config = self.get_vertical_config(vertical)
        if not vertical_config:
            logger.warning(f"⚠️ No config found for vertical '{vertical}', using default")
            return self._generate_default_prompt(vertical, workspace_id, tools_description, 
                                               user_input, current_slots, objective, greeted)
        
        vertical_name = vertical_config.get('name', vertical)
        
        # Generar ejemplos de extracción de servicios
        service_extraction_examples = self._generate_service_extraction_examples(vertical_config)
        
        # Generar ejemplos de saludo
        greeting_examples = self._generate_greeting_examples(vertical_config, workspace_id)

        # Generar ejemplos de booking
        booking_examples = self._generate_booking_examples(vertical_config, workspace_id)

        # Generar ejemplos de consulta de información
        info_examples = self._generate_info_examples(vertical_config, workspace_id)
        
        # Generar descripción de slots
        slots_description = self._generate_slots_description(vertical_config)
        
        prompt = f"""Eres un planificador de herramientas especializado en {vertical_name}.

HERRAMIENTAS DISPONIBLES (USA ESTOS NOMBRES EXACTOS):
{chr(10).join(tools_description)}

ESTADO ACTUAL:
- Usuario dice: "{user_input}"
- Información recopilada: {current_slots}
- Objetivo: {objective}
- Ya saludado: {greeted}

REGLAS CRÍTICAS:
1. **USA SOLO los nombres EXACTOS de las herramientas listadas arriba**
2. **NO inventes variaciones de nombres** (ej: "get_services" NO existe, usa "get_available_services")
3. PRIMERO: Extrae TODA la información del mensaje del usuario
4. SEGUNDO: Decide qué herramientas ejecutar para ayudarlo
5. Si es SALUDO INICIAL (hola, buenos días) → usa tools para obtener info del negocio
6. Si el usuario pregunta información → usa tools de consulta
7. Si quiere agendar/reservar → primero verifica disponibilidad, luego confirma
8. Si falta información crítica → no ejecutes tools, el LLM preguntará
9. Ordena las herramientas por prioridad (consultas antes que acciones)
10. CRÍTICO: Extrae TODOS los slots disponibles del mensaje
11. Si tienes TODOS los datos necesarios → ejecuta directamente la acción

EXTRACCIÓN DE INFORMACIÓN:
{service_extraction_examples}
- Fechas: "mañana" → "2025-10-15", "pasado mañana" → "2025-10-16", "el lunes" → "2025-10-20"
- Horas: "10am" → "10:00", "3pm" → "15:00", "6pm" → "18:00"
- Nombres: cualquier nombre propio mencionado
- Emails: cualquier texto con @
- Teléfonos: números de teléfono mencionados

SLOTS DISPONIBLES:
{slots_description}

EJEMPLOS DE SALUDO (OBTENER INFO DEL NEGOCIO):
{greeting_examples}

EJEMPLOS DE CONSULTA:
{info_examples}

EJEMPLOS DE RESERVA/AGENDAMIENTO:
{booking_examples}

Responde SOLO con array JSON de herramientas a ejecutar."""
        
        return prompt
    
    def _generate_service_extraction_examples(self, vertical_config: Dict[str, Any]) -> str:
        """Genera ejemplos de extracción de servicios/productos"""
        examples = vertical_config.get('examples', {}).get('service_extraction', [])
        if not examples:
            return "- Servicios: extrae cualquier servicio/producto mencionado"

        lines = []
        for example in examples:
            lines.append(f"- {example['input']} → {example['output']}")

        return "\n".join(lines)

    def _generate_greeting_examples(self, vertical_config: Dict[str, Any], workspace_id: str) -> str:
        """Genera ejemplos de saludo inicial con tools"""
        examples = vertical_config.get('examples', {}).get('greeting_examples', [])
        if not examples:
            return ""

        lines = []
        for example in examples:
            user = example['user']
            tools = example['tools']

            # Convertir tools a formato JSON
            tools_json = []
            for tool in tools:
                tool_json = f'{{"tool": "{tool["tool"]}", "args": {{"workspace_id": "{workspace_id}"'
                for key, value in tool.get('args', {}).items():
                    if key != 'workspace_id':
                        if isinstance(value, str):
                            tool_json += f', "{key}": "{value}"'
                        else:
                            tool_json += f', "{key}": {value}'
                tool_json += '}}'
                tools_json.append(tool_json)

            tools_str = '[\n  ' + ',\n  '.join(tools_json) + '\n]'
            lines.append(f'Usuario: "{user}"\n→ {tools_str}')

        return "\n\n".join(lines)

    def _generate_booking_examples(self, vertical_config: Dict[str, Any], workspace_id: str) -> str:
        """Genera ejemplos de reserva/agendamiento"""
        examples = vertical_config.get('examples', {}).get('booking_examples', [])
        if not examples:
            return ""
        
        lines = []
        for example in examples:
            user = example['user']
            tools = example['tools']
            
            # Convertir tools a formato JSON
            tools_json = []
            for tool in tools:
                tool_json = f'{{"tool": "{tool["tool"]}", "args": {{"workspace_id": "{workspace_id}"'
                for key, value in tool['args'].items():
                    if key != 'workspace_id':
                        if isinstance(value, str):
                            tool_json += f', "{key}": "{value}"'
                        elif isinstance(value, list):
                            tool_json += f', "{key}": {value}'
                        else:
                            tool_json += f', "{key}": {value}'
                tool_json += '}}'
                tools_json.append(tool_json)
            
            tools_str = '[\n  ' + ',\n  '.join(tools_json) + '\n]'
            lines.append(f'Usuario: "{user}"\n→ {tools_str}')
        
        return "\n\n".join(lines)
    
    def _generate_info_examples(self, vertical_config: Dict[str, Any], workspace_id: str) -> str:
        """Genera ejemplos de consulta de información"""
        examples = vertical_config.get('examples', {}).get('info_examples', [])
        if not examples:
            return ""
        
        lines = []
        for example in examples:
            user = example['user']
            tools = example['tools']
            
            # Convertir tools a formato JSON
            tools_json = []
            for tool in tools:
                tool_json = f'{{"tool": "{tool["tool"]}", "args": {{"workspace_id": "{workspace_id}"'
                for key, value in tool['args'].items():
                    if key != 'workspace_id':
                        if isinstance(value, str):
                            tool_json += f', "{key}": "{value}"'
                        else:
                            tool_json += f', "{key}": {value}'
                tool_json += '}}'
                tools_json.append(tool_json)
            
            tools_str = '[\n  ' + ',\n  '.join(tools_json) + '\n]'
            lines.append(f'Usuario: "{user}"\n→ {tools_str}')
        
        return "\n\n".join(lines)
    
    def _generate_slots_description(self, vertical_config: Dict[str, Any]) -> str:
        """Genera descripción de slots disponibles"""
        slots = vertical_config.get('slots', {})
        if not slots:
            return "- Extrae cualquier información relevante del mensaje"
        
        lines = []
        for slot, description in slots.items():
            lines.append(f"- {slot}: {description}")
        
        return "\n".join(lines)
    
    def _generate_default_prompt(self, vertical: str, workspace_id: str, tools_description: List[str],
                               user_input: str, current_slots: Dict[str, Any], 
                               objective: str, greeted: bool) -> str:
        """Genera un prompt por defecto si no hay configuración específica"""
        return f"""Eres un planificador de herramientas especializado en {vertical}.

HERRAMIENTAS DISPONIBLES:
{chr(10).join(tools_description)}

ESTADO ACTUAL:
- Usuario dice: "{user_input}"
- Información recopilada: {current_slots}
- Objetivo: {objective}
- Ya saludado: {greeted}

REGLAS:
1. PRIMERO: Extrae TODA la información del mensaje del usuario
2. SEGUNDO: Decide qué herramientas ejecutar para ayudarlo
3. Si el usuario pregunta información → usa tools de consulta
4. Si quiere agendar/reservar → primero verifica disponibilidad, luego confirma
5. Si falta información crítica → no ejecutes tools, el LLM preguntará
6. Ordena las herramientas por prioridad (consultas antes que acciones)
7. CRÍTICO: Extrae TODOS los slots disponibles del mensaje
8. Si tienes TODOS los datos necesarios → ejecuta directamente la acción

EXTRACCIÓN DE INFORMACIÓN:
- Servicios/Productos: extrae cualquier servicio/producto mencionado
- Fechas: "mañana" → "2025-10-15", "pasado mañana" → "2025-10-16", "el lunes" → "2025-10-20"
- Horas: "10am" → "10:00", "3pm" → "15:00", "6pm" → "18:00"
- Nombres: cualquier nombre propio mencionado
- Emails: cualquier texto con @
- Teléfonos: números de teléfono mencionados

SLOTS DISPONIBLES:
- Extrae cualquier información relevante del mensaje

Usuario: "hola"
→ []  // Solo saludo, no necesita tools

Responde SOLO con array JSON de herramientas a ejecutar."""

# Instancia global
vertical_prompt_generator = VerticalPromptGenerator()


