"""
Simple NLG - Generador de respuestas determinístico
Usa datos reales del patch + observations para generar respuestas cortas (<200 chars idealmente)
"""

from typing import List, Dict, Any, Optional

def build_user_message(
    intent: str,
    extract: Dict[str, Any],
    plan: Dict[str, Any],
    patch: Any,
    observations: List[Any]
) -> str:
    """
    Genera mensaje al usuario basándose en el intent y datos reales
    
    Args:
        intent: Intent detectado por Extractor
        extract: Output completo del Extractor
        plan: Output del Planner
        patch: State patch del Reducer
        observations: Lista de observaciones de tools
        
    Returns:
        Mensaje corto para el usuario (idealmente <200 chars)
    """
    slots = (extract or {}).get("slots", {}) or {}
    svc = slots.get("service_type")
    
    # 1) Info de horarios
    if intent == "info_hours":
        hours = _from_patch_hours(patch)
        if hours:
            return _fmt_hours(hours)
        return "Consulté los horarios pero no pude leerlos. ¿Probamos de nuevo?"
    
    # 2) Info de precios/servicios
    if intent in ["info_prices", "info_services"]:
        services = _from_patch_services(patch, filter_q=svc)
        if services:
            return _fmt_prices(services, q=svc)
        return "Consulté los servicios pero no encontré resultados. ¿Te ayudo con algo más?"
    
    # 3) Reserva (book)
    if intent == "book":
        if plan.get("needs_confirmation"):
            # Faltan datos - dar feedback sobre qué sigue
            missing = plan.get("missing_slots", [])
            if "preferred_time" in missing:
                return "Tengo la fecha. ¿A qué hora te viene bien? (ej: 15:00)"
            if "preferred_date" in missing:
                return "¿Para qué día querés el turno? (ej: mañana, 16/10)"
            if "client_name" in missing or "client_email" in missing:
                return "Para confirmar necesito tu nombre y email."
            return "¿Me confirmás los datos para la reserva?"
        else:
            # Intentó reservar - verificar si hubo éxito
            booking = _from_patch_booking(patch)
            if booking and booking.get("booking_id"):
                svc_name = booking.get("service_type", "turno")
                date = booking.get("date", "")
                time = booking.get("time", "")
                return f"¡Listo! {svc_name} reservado para {date} a las {time}."
            
            # Verificó disponibilidad pero no reservó aún
            if slots.get("preferred_date") and slots.get("preferred_time"):
                return "Hay disponibilidad. ¿Confirmás nombre y email para reservar?"
            
            return "Verifiqué disponibilidad. ¿Querés que te reserve?"
    
    # 4) Cancelación
    if intent == "cancel":
        # Verificar si se canceló exitosamente
        cancelled = _from_patch_cancelled(patch)
        if cancelled:
            return "Turno cancelado. ¿Querés reagendar?"
        return "Para cancelar necesito el ID de tu turno o tu teléfono."
    
    # 5) Saludo
    if intent == "greeting":
        return "¡Hola! Te ayudo con turnos, precios y horarios. ¿Qué necesitás?"
    
    # 6) Chitchat
    if intent == "chitchat":
        return "Te ayudo con reservas de turnos. ¿Querés agendar?"
    
    # Fallback genérico
    return "Te ayudo con turnos, precios y horarios. ¿Qué necesitás?"


# ========== Extractores de datos del patch ==========

def _from_patch_hours(patch) -> Optional[List[Dict[str, Any]]]:
    """Extrae horarios de atención del patch"""
    if not patch:
        return None
    
    slots_patch = getattr(patch, "slots_patch", {}) if hasattr(patch, "slots_patch") else patch.get("slots_patch", {})
    return slots_patch.get("_business_hours")


def _from_patch_services(patch, filter_q: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extrae lista de servicios del patch, opcionalmente filtrados"""
    if not patch:
        return []
    
    slots_patch = getattr(patch, "slots_patch", {}) if hasattr(patch, "slots_patch") else patch.get("slots_patch", {})
    services = slots_patch.get("_available_services") or []
    
    # Filtrar por query si se especificó
    if filter_q and services:
        filter_lower = filter_q.lower()
        services = [s for s in services if filter_lower in s.get("name", "").lower()]
    
    return services


def _from_patch_booking(patch) -> Optional[Dict[str, Any]]:
    """Extrae datos de booking exitoso del patch"""
    if not patch:
        return None
    
    slots_patch = getattr(patch, "slots_patch", {}) if hasattr(patch, "slots_patch") else patch.get("slots_patch", {})
    
    # Verificar si hay booking_id (indicador de booking exitoso)
    if slots_patch.get("booking_id"):
        return {
            "booking_id": slots_patch.get("booking_id"),
            "service_type": slots_patch.get("service_type"),
            "date": slots_patch.get("preferred_date"),
            "time": slots_patch.get("preferred_time")
        }
    
    return None


def _from_patch_cancelled(patch) -> bool:
    """Verifica si hubo una cancelación exitosa"""
    if not patch:
        return False
    
    slots_patch = getattr(patch, "slots_patch", {}) if hasattr(patch, "slots_patch") else patch.get("slots_patch", {})
    return slots_patch.get("_cancelled", False)


# ========== Formateadores cortos ==========

def _fmt_hours(hours: List[Dict[str, Any]]) -> str:
    """
    Formatea horarios de forma compacta
    Muestra máximo 4 días para no saturar
    """
    if not hours:
        return "No tengo los horarios disponibles ahora."
    
    lines = []
    for day_info in hours[:4]:
        day = day_info.get("day", "")
        blocks = day_info.get("blocks", [])
        
        if blocks:
            # Formatear bloques: [["09:00", "13:00"], ["14:00", "19:00"]]
            blocks_str = ", ".join([f"{start}-{end}" for start, end in blocks])
            lines.append(f"• {day}: {blocks_str}")
        else:
            lines.append(f"• {day}: Cerrado")
    
    # Indicar si hay más días
    tail = "\n…" if len(hours) > 4 else ""
    
    return "Horarios:\n" + "\n".join(lines) + tail


def _fmt_prices(services: List[Dict[str, Any]], q: Optional[str] = None) -> str:
    """
    Formatea precios de forma compacta
    Muestra máximo 3 servicios
    """
    if not services:
        return "No encontré servicios disponibles."
    
    # Header
    if q:
        header = f"Precios de {q}:\n"
    else:
        header = "Servicios disponibles:\n"
    
    lines = []
    for svc in services[:3]:
        name = svc.get("name", "Servicio")
        price_min = svc.get("price_min") or svc.get("price")
        price_max = svc.get("price_max")
        
        # Formatear precio
        if price_min and price_max and price_max != price_min:
            price_str = f"${price_min}-${price_max}"
        elif price_min:
            price_str = f"${price_min}"
        else:
            price_str = "Consultar"
        
        lines.append(f"• {name}: {price_str}")
    
    # Indicar si hay más servicios
    tail = "\n…" if len(services) > 3 else ""
    
    return header + "\n".join(lines) + tail


def _build_missing_prompt(intent: str, missing: List[str], slots: Dict[str, Any]) -> str:
    """
    Genera prompt determinístico para pedir datos faltantes
    UNA pregunta específica, no múltiples
    """
    if intent == "book":
        # Priorizar en orden: servicio → fecha → hora → datos cliente
        if "service_type" in missing:
            return "¿Qué servicio necesitás? (ej: corte, color, barba)"
        
        if "preferred_date" in missing:
            return "¿Para qué día? (ej: mañana, 16/10/2024)"
        
        if "preferred_time" in missing:
            date = slots.get("preferred_date", "ese día")
            return f"¿A qué hora te viene bien? (horarios de 10:00 a 18:00)"
        
        if "client_name" in missing:
            return "¿Cuál es tu nombre completo?"
        
        if "client_email" in missing:
            return "¿Y tu email para confirmar?"
    
    elif intent == "cancel":
        if "booking_id" in missing:
            return "Para cancelar necesito el ID de tu turno o tu teléfono."
    
    # Genérico
    return "¿Me compartís el dato que falta para ayudarte?"




