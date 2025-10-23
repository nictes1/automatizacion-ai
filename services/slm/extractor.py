"""
Extractor SLM - Intent Classification + NER
Usa SLM pequeño (3B-8B) con constrained decoding para extraer intent y slots
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import jsonschema

logger = logging.getLogger(__name__)

@dataclass
class ExtractorOutput:
    """Salida del Extractor (validada contra schema)"""
    intent: str
    slots: Dict[str, Optional[str]]
    confidence: float
    reasoning: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "slots": self.slots,
            "confidence": self.confidence,
            "reasoning": self.reasoning
        }

class ExtractorSLM:
    """
    Extractor basado en SLM con constrained decoding
    
    Características:
    - Usa schema JSON para constrain output
    - Normaliza fechas relativas (mañana, lunes, etc.)
    - Fallback a LLM si confidence < threshold
    - Latencia objetivo: 150-250ms
    """
    
    def __init__(self, llm_client, schema_path: str = "config/schemas/extractor_v1.json", confidence_threshold: float = 0.7):
        self.llm_client = llm_client
        self.confidence_threshold = confidence_threshold
        
        # Cargar schema JSON
        with open(schema_path, 'r') as f:
            self.schema = json.load(f)
        
        logger.info(f"[EXTRACTOR] Inicializado con schema v1, threshold={confidence_threshold}")
    
    async def extract(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> ExtractorOutput:
        """
        Extrae intent y slots del mensaje del usuario
        
        Args:
            user_input: Mensaje del usuario
            context: Contexto adicional (conversación previa, tenant info, etc.)
            
        Returns:
            ExtractorOutput validado contra schema
        """
        if not user_input or not user_input.strip():
            return ExtractorOutput(
                intent="other",
                slots={},
                confidence=1.0,
                reasoning="Empty input"
            )
        
        # Construir prompt con few-shot examples
        prompt = self._build_extraction_prompt(user_input, context)
        
        try:
            # Llamar al SLM con constrained decoding
            raw_output = await self.llm_client.generate_json(
                system_prompt=prompt,
                user_prompt="",
                schema=self.schema,
                temperature=0.1,  # Bajo para consistencia
                max_tokens=300
            )
            
            # Validar contra schema
            jsonschema.validate(instance=raw_output, schema=self.schema)
            
            # Normalizar slots (fechas, horas, etc.)
            normalized_slots = self._normalize_slots(raw_output.get("slots", {}))
            
            output = ExtractorOutput(
                intent=raw_output["intent"],
                slots=normalized_slots,
                confidence=raw_output["confidence"],
                reasoning=raw_output.get("reasoning")
            )
            
            # Si confidence baja, marcar para fallback
            if output.confidence < self.confidence_threshold:
                logger.warning(f"[EXTRACTOR] Low confidence: {output.confidence:.2f}, consider fallback")
            
            logger.info(f"[EXTRACTOR] Intent={output.intent}, Confidence={output.confidence:.2f}, Slots={len(output.slots)}")
            return output
            
        except jsonschema.ValidationError as e:
            logger.error(f"[EXTRACTOR] Schema validation failed: {e}")
            # Fallback a extracción básica
            return self._fallback_extraction(user_input)
        
        except Exception as e:
            logger.error(f"[EXTRACTOR] Error: {e}")
            return self._fallback_extraction(user_input)
    
    def _build_extraction_prompt(self, user_input: str, context: Optional[Dict[str, Any]]) -> str:
        """Construye prompt con few-shot examples para el SLM"""
        
        # Contexto del tenant (si está disponible)
        tenant_context = ""
        if context and "available_services" in context:
            services = context["available_services"]
            tenant_context = f"\nServicios disponibles: {', '.join(services)}"
        
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        prompt = f"""Eres un extractor de información especializado en servicios y reservas de turnos.

TAREA: Extrae el intent y los slots del mensaje del usuario.

INTENTS VÁLIDOS:
- greeting: saludos iniciales
- info_services: pregunta por servicios disponibles
- info_prices: pregunta por precios
- info_hours: pregunta por horarios de atención
- book: quiere reservar un turno
- cancel: quiere cancelar un turno
- reschedule: quiere cambiar un turno
- chitchat: conversación general
- other: otro tipo de mensaje

SLOTS A EXTRAER:
- service_type: tipo de servicio (Corte de Cabello, Coloración, Barba, etc.)
- preferred_date: fecha en formato YYYY-MM-DD
- preferred_time: hora en formato HH:MM (24h)
- staff_name: nombre del profesional
- client_name: nombre del cliente
- client_email: email del cliente
- client_phone: teléfono del cliente
- booking_id: ID de reserva existente

NORMALIZACIÓN DE FECHAS:
- "hoy" → "{today}"
- "mañana" → "{tomorrow}"
- "10am" → "10:00"
- "3pm" → "15:00"
{tenant_context}

EJEMPLOS:

Entrada: "Hola, buenos días"
Salida: {{"intent": "greeting", "slots": {{}}, "confidence": 0.95}}

Entrada: "¿Qué servicios tienen?"
Salida: {{"intent": "info_services", "slots": {{}}, "confidence": 0.92}}

Entrada: "Cuánto sale un corte de pelo?"
Salida: {{"intent": "info_prices", "slots": {{"service_type": "Corte de Cabello"}}, "confidence": 0.90}}

Entrada: "Quiero turno para corte mañana a las 3pm"
Salida: {{"intent": "book", "slots": {{"service_type": "Corte de Cabello", "preferred_date": "{tomorrow}", "preferred_time": "15:00"}}, "confidence": 0.95}}

Entrada: "Necesito cancelar mi turno del lunes"
Salida: {{"intent": "cancel", "slots": {{}}, "confidence": 0.88}}

Entrada: "Soy Juan Pérez, mi email es juan@example.com"
Salida: {{"intent": "chitchat", "slots": {{"client_name": "Juan Pérez", "client_email": "juan@example.com"}}, "confidence": 0.92}}

REGLAS:
1. Solo extrae información EXPLÍCITA del mensaje
2. NO inventes información que no está
3. Normaliza fechas y horas al formato correcto
4. Confidence alto (>0.9) si es obvio, medio (0.7-0.9) si razonable, bajo (<0.7) si ambiguo
5. Devuelve SOLO JSON válido, sin texto adicional

MENSAJE DEL USUARIO: "{user_input}"

Extrae el intent y slots:"""
        
        return prompt
    
    def _normalize_slots(self, slots: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Normaliza slots (fechas relativas, formatos, etc.)"""
        normalized = {}
        
        for key, value in slots.items():
            if value is None:
                normalized[key] = None
                continue
            
            # Normalizar fechas relativas
            if key == "preferred_date" and isinstance(value, str):
                normalized[key] = self._normalize_date(value)
            
            # Normalizar horas
            elif key == "preferred_time" and isinstance(value, str):
                normalized[key] = self._normalize_time(value)
            
            # Normalizar nombres (capitalizar)
            elif key in ["client_name", "staff_name"] and isinstance(value, str):
                normalized[key] = value.strip().title()
            
            # Email en minúsculas
            elif key == "client_email" and isinstance(value, str):
                normalized[key] = value.strip().lower()
            
            else:
                normalized[key] = value
        
        return normalized
    
    def _normalize_date(self, date_str: str) -> str:
        """Normaliza fecha a formato YYYY-MM-DD"""
        date_str_lower = date_str.lower().strip()
        
        # Fechas relativas
        if date_str_lower in ["hoy", "today"]:
            return datetime.now().strftime("%Y-%m-%d")
        elif date_str_lower in ["mañana", "tomorrow"]:
            return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif date_str_lower in ["pasado mañana", "day after tomorrow"]:
            return (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
        
        # Ya está en formato correcto
        if len(date_str) == 10 and date_str[4] == '-' and date_str[7] == '-':
            return date_str
        
        return date_str
    
    def _normalize_time(self, time_str: str) -> str:
        """Normaliza hora a formato HH:MM (24h)"""
        time_str = time_str.strip().lower()
        
        # Convertir formato 12h a 24h
        if "am" in time_str or "pm" in time_str:
            is_pm = "pm" in time_str
            time_str = time_str.replace("am", "").replace("pm", "").strip()
            
            try:
                hour = int(time_str.split(":")[0] if ":" in time_str else time_str)
                minute = int(time_str.split(":")[1]) if ":" in time_str else 0
                
                if is_pm and hour != 12:
                    hour += 12
                elif not is_pm and hour == 12:
                    hour = 0
                
                return f"{hour:02d}:{minute:02d}"
            except:
                pass
        
        # Ya está en formato HH:MM
        if ":" in time_str and len(time_str) <= 5:
            parts = time_str.split(":")
            if len(parts) == 2:
                try:
                    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                except:
                    pass
        
        return time_str
    
    def _fallback_extraction(self, user_input: str) -> ExtractorOutput:
        """Extracción básica de fallback cuando el SLM falla"""
        logger.warning("[EXTRACTOR] Using fallback extraction")
        
        # Heurística simple para intent
        user_lower = user_input.lower()
        
        if any(word in user_lower for word in ["hola", "buenos", "buenas", "hi", "hello"]):
            intent = "greeting"
        elif any(word in user_lower for word in ["servicios", "services", "qué hacen", "que tienen"]):
            intent = "info_services"
        elif any(word in user_lower for word in ["precio", "cuanto", "cuesta", "vale"]):
            intent = "info_prices"
        elif any(word in user_lower for word in ["horario", "abre", "cierra", "hours"]):
            intent = "info_hours"
        elif any(word in user_lower for word in ["quiero", "necesito", "turno", "cita", "reserva"]):
            intent = "book"
        elif any(word in user_lower for word in ["cancelar", "anular", "cancel"]):
            intent = "cancel"
        else:
            intent = "other"
        
        return ExtractorOutput(
            intent=intent,
            slots={},
            confidence=0.5,  # Baja confidence para indicar fallback
            reasoning="Fallback heuristic"
        )





