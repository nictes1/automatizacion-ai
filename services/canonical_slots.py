"""
Canonical Slots - Catálogo centralizado de slots con validators y normalizers

Define slots universales usados por todos los verticals, con:
- Validación de tipos y formatos
- Normalización/coerción automática
- Detección de PII para redacción en logs
"""

from typing import Dict, Any, Tuple, Optional, Callable, List
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import re
import logging

logger = logging.getLogger(__name__)


class SlotDefinition(BaseModel):
    """Definición de un slot canónico"""
    name: str
    description: str
    type: str  # "string", "date", "time", "email", "phone", "number"
    required: bool = False
    is_pii: bool = False  # Para redacción en logs
    normalizer: Optional[str] = None  # Nombre de función normalizadora
    validator: Optional[str] = None  # Nombre de función validadora


# ==========================================
# NORMALIZERS - Coerción de tipos
# ==========================================

def normalize_date(value: Any) -> Tuple[bool, str, Any]:
    """
    Normaliza fechas en formato YYYY-MM-DD

    Acepta:
    - "mañana", "hoy", "pasado mañana"
    - "2025-10-10"
    - timestamps

    Returns:
        (success, error_msg, normalized_value)
    """
    if isinstance(value, str):
        value_lower = value.lower().strip()

        # Fechas relativas
        if value_lower in ["hoy", "today"]:
            return True, "", datetime.now().strftime("%Y-%m-%d")
        elif value_lower in ["mañana", "manana", "tomorrow"]:
            return True, "", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif value_lower in ["pasado mañana", "pasado manana", "overmorrow"]:
            return True, "", (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")

        # Formato YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            try:
                datetime.strptime(value, "%Y-%m-%d")
                return True, "", value
            except ValueError:
                return False, f"Fecha inválida: {value}", None

        # Formato DD/MM/YYYY
        if re.match(r"^\d{2}/\d{2}/\d{4}$", value):
            try:
                dt = datetime.strptime(value, "%d/%m/%Y")
                return True, "", dt.strftime("%Y-%m-%d")
            except ValueError:
                return False, f"Fecha inválida: {value}", None

    return False, f"Formato de fecha no reconocido: {value}", None


def normalize_time(value: Any) -> Tuple[bool, str, Any]:
    """
    Normaliza horas en formato HH:MM

    Acepta:
    - "10am", "3pm", "5:30pm"
    - "10 de la mañana", "3 de la tarde"
    - "HH:MM"

    Returns:
        (success, error_msg, normalized_value)
    """
    if isinstance(value, str):
        value_lower = value.lower().strip()

        # Formato HH:MM directo
        if re.match(r"^\d{1,2}:\d{2}$", value):
            return True, "", value

        # Formato con AM/PM: "10am", "3pm", "5:30pm"
        match = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", value_lower)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            period = match.group(3)

            # Convertir a 24h
            if period == "pm" and hour != 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            return True, "", f"{hour:02d}:{minute:02d}"

        # Formato español: "10 de la mañana", "3 de la tarde"
        patterns = {
            r"(\d{1,2})\s*(?:de la)?\s*ma[ñn]ana": "am",
            r"(\d{1,2})\s*(?:de la)?\s*tarde": "pm",
            r"(\d{1,2})\s*(?:de la)?\s*noche": "pm"
        }

        for pattern, period in patterns.items():
            match = re.match(pattern, value_lower)
            if match:
                hour = int(match.group(1))
                if period == "pm" and hour < 12:
                    hour += 12
                return True, "", f"{hour:02d}:00"

    return False, f"Formato de hora no reconocido: {value}", None


def normalize_email(value: Any) -> Tuple[bool, str, Any]:
    """Normaliza y valida email"""
    if not isinstance(value, str):
        return False, "Email debe ser string", None

    value = value.lower().strip()

    # Regex básico de email
    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", value):
        return True, "", value

    return False, f"Email inválido: {value}", None


def normalize_phone(value: Any) -> Tuple[bool, str, Any]:
    """
    Normaliza teléfono a formato E.164

    Acepta:
    - "+54 11 1234 5678"
    - "11 1234 5678"
    - "1112345678"
    """
    if not isinstance(value, str):
        return False, "Teléfono debe ser string", None

    # Remover espacios, guiones, paréntesis
    cleaned = re.sub(r"[\s\-\(\)]", "", value)

    # Agregar +54 si no tiene código de país
    if not cleaned.startswith("+"):
        if cleaned.startswith("54"):
            cleaned = "+" + cleaned
        else:
            cleaned = "+54" + cleaned

    # Validar formato E.164 (max 15 dígitos)
    if re.match(r"^\+[1-9]\d{1,14}$", cleaned):
        return True, "", cleaned

    return False, f"Teléfono inválido: {value}", None


def normalize_service_type(value: Any) -> Tuple[bool, str, Any]:
    """
    Normaliza nombres de servicios

    Expande abreviaciones:
    - "corte" → "Corte de Cabello"
    - "color" → "Coloración"
    """
    if not isinstance(value, str):
        return False, "Servicio debe ser string", None

    value_lower = value.lower().strip()

    # Mapeo de abreviaciones comunes
    expansions = {
        "corte": "Corte de Cabello",
        "color": "Coloración",
        "coloracion": "Coloración",
        "brushing": "Brushing",
        "manicura": "Manicura",
        "pedicura": "Pedicura",
        "depilacion": "Depilación",
        "depilación": "Depilación"
    }

    return True, "", expansions.get(value_lower, value.title())


# ==========================================
# CATÁLOGO DE SLOTS CANÓNICOS
# ==========================================

CANONICAL_SLOTS: Dict[str, SlotDefinition] = {
    # Información del cliente
    "client_name": SlotDefinition(
        name="client_name",
        description="Nombre completo del cliente",
        type="string",
        required=True,
        is_pii=True,
        normalizer="normalize_name"
    ),

    "client_email": SlotDefinition(
        name="client_email",
        description="Email del cliente",
        type="email",
        required=False,
        is_pii=True,
        normalizer="normalize_email"
    ),

    "client_phone": SlotDefinition(
        name="client_phone",
        description="Teléfono del cliente",
        type="phone",
        required=False,
        is_pii=True,
        normalizer="normalize_phone"
    ),

    # Servicios
    "service_type": SlotDefinition(
        name="service_type",
        description="Tipo de servicio solicitado",
        type="string",
        required=True,
        is_pii=False,
        normalizer="normalize_service_type"
    ),

    # Fecha y hora
    "preferred_date": SlotDefinition(
        name="preferred_date",
        description="Fecha preferida (YYYY-MM-DD)",
        type="date",
        required=True,
        is_pii=False,
        normalizer="normalize_date"
    ),

    "preferred_time": SlotDefinition(
        name="preferred_time",
        description="Hora preferida (HH:MM)",
        type="time",
        required=True,
        is_pii=False,
        normalizer="normalize_time"
    ),

    # Staff
    "staff_id": SlotDefinition(
        name="staff_id",
        description="ID del profesional preferido",
        type="string",
        required=False,
        is_pii=False
    ),

    "staff_preference": SlotDefinition(
        name="staff_preference",
        description="Nombre del profesional preferido",
        type="string",
        required=False,
        is_pii=False
    ),

    # Otros
    "notes": SlotDefinition(
        name="notes",
        description="Notas adicionales",
        type="string",
        required=False,
        is_pii=False
    )
}


# Mapa de normalizadores
NORMALIZERS: Dict[str, Callable] = {
    "normalize_date": normalize_date,
    "normalize_time": normalize_time,
    "normalize_email": normalize_email,
    "normalize_phone": normalize_phone,
    "normalize_service_type": normalize_service_type
}


# ==========================================
# FUNCIONES HELPER
# ==========================================

def normalize_slot(slot_name: str, value: Any) -> Tuple[bool, str, Any]:
    """
    Normaliza un slot usando su normalizer definido

    Returns:
        (success, error_msg, normalized_value)
    """
    slot_def = CANONICAL_SLOTS.get(slot_name)

    if not slot_def:
        # Slot no canónico, retornar sin normalizar
        return True, "", value

    if not slot_def.normalizer:
        # Sin normalizer, retornar sin cambios
        return True, "", value

    normalizer_fn = NORMALIZERS.get(slot_def.normalizer)
    if not normalizer_fn:
        logger.warning(f"Normalizer '{slot_def.normalizer}' no encontrado para slot '{slot_name}'")
        return True, "", value

    return normalizer_fn(value)


def normalize_slots(slots: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Normaliza todos los slots de una vez

    Returns:
        (normalized_slots, errors)
    """
    normalized = {}
    errors = []

    for slot_name, value in slots.items():
        if not value or slot_name.startswith("_"):
            # Skip empty o internal slots
            normalized[slot_name] = value
            continue

        success, error_msg, normalized_value = normalize_slot(slot_name, value)

        if success:
            normalized[slot_name] = normalized_value
        else:
            errors.append(f"{slot_name}: {error_msg}")
            normalized[slot_name] = value  # Keep original

    return normalized, errors


def redact_pii(slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redacta PII de slots para logging

    Returns:
        Dict con PII redactado
    """
    redacted = {}

    for slot_name, value in slots.items():
        slot_def = CANONICAL_SLOTS.get(slot_name)

        if slot_def and slot_def.is_pii and value:
            # Redactar PII
            if isinstance(value, str):
                if "@" in value:  # Email
                    redacted[slot_name] = "***@***.com"
                elif "+" in value:  # Phone
                    redacted[slot_name] = "+***********"
                else:  # Name
                    redacted[slot_name] = "***"
            else:
                redacted[slot_name] = "***"
        else:
            redacted[slot_name] = value

    return redacted
