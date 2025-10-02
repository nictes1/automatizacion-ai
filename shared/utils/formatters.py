#!/usr/bin/env python3
"""
PulpoAI Shared Utils Formatters
Formateadores compartidos
"""

import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

def format_phone_number(phone: str, country_code: str = '+54') -> str:
    """Formatear número de teléfono"""
    # Limpiar número
    clean_phone = re.sub(r'[^\d]', '', phone)
    
    # Si no empieza con código de país, agregarlo
    if not clean_phone.startswith('54'):
        clean_phone = '54' + clean_phone
    
    # Formatear con código de país
    if len(clean_phone) >= 10:
        return f"+{clean_phone[:2]} {clean_phone[2:5]} {clean_phone[5:8]}-{clean_phone[8:]}"
    
    return phone

def format_currency(amount: float, currency: str = 'ARS', symbol: str = '$') -> str:
    """Formatear moneda"""
    # Redondear a 2 decimales
    rounded = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Formatear con separadores de miles
    formatted = f"{rounded:,.2f}"
    
    # Agregar símbolo de moneda
    if symbol:
        return f"{symbol} {formatted}"
    
    return f"{formatted} {currency}"

def format_datetime(dt: datetime, format: str = '%Y-%m-%d %H:%M:%S', timezone_str: str = 'UTC') -> str:
    """Formatear datetime"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    return dt.strftime(format)

def format_duration(seconds: float) -> str:
    """Formatear duración"""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def format_file_size(bytes_size: int) -> str:
    """Formatear tamaño de archivo"""
    if bytes_size < 1024:
        return f"{bytes_size}B"
    elif bytes_size < 1024 * 1024:
        return f"{bytes_size / 1024:.1f}KB"
    elif bytes_size < 1024 * 1024 * 1024:
        return f"{bytes_size / (1024 * 1024):.1f}MB"
    else:
        return f"{bytes_size / (1024 * 1024 * 1024):.1f}GB"

def format_percentage(value: float, total: float) -> str:
    """Formatear porcentaje"""
    if total == 0:
        return "0%"
    
    percentage = (value / total) * 100
    return f"{percentage:.1f}%"

def format_list(items: list, separator: str = ', ', max_items: int = None) -> str:
    """Formatear lista"""
    if max_items and len(items) > max_items:
        visible_items = items[:max_items]
        return f"{separator.join(visible_items)} y {len(items) - max_items} más"
    
    return separator.join(items)

def format_dict_as_table(data: Dict[str, Any], headers: list = None) -> str:
    """Formatear diccionario como tabla"""
    if not data:
        return "No hay datos"
    
    # Determinar headers
    if headers is None:
        headers = ['Campo', 'Valor']
    
    # Calcular ancho de columnas
    max_key_length = max(len(str(k)) for k in data.keys())
    max_value_length = max(len(str(v)) for v in data.values())
    
    key_width = max(max_key_length, len(headers[0]))
    value_width = max(max_value_length, len(headers[1]))
    
    # Crear tabla
    table = []
    table.append(f"| {headers[0]:<{key_width}} | {headers[1]:<{value_width}} |")
    table.append(f"|{'-' * (key_width + 2)}|{'-' * (value_width + 2)}|")
    
    for key, value in data.items():
        table.append(f"| {str(key):<{key_width}} | {str(value):<{value_width}} |")
    
    return '\n'.join(table)

def format_json_pretty(data: Dict[str, Any], indent: int = 2) -> str:
    """Formatear JSON de forma legible"""
    import json
    return json.dumps(data, indent=indent, ensure_ascii=False, default=str)

def format_slug(text: str) -> str:
    """Formatear texto como slug"""
    # Convertir a minúsculas
    slug = text.lower()
    
    # Reemplazar espacios y caracteres especiales con guiones
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[-\s]+', '-', slug)
    
    # Remover guiones al inicio y final
    slug = slug.strip('-')
    
    return slug

def format_username(name: str) -> str:
    """Formatear nombre de usuario"""
    # Convertir a minúsculas y reemplazar espacios
    username = name.lower().replace(' ', '_')
    
    # Remover caracteres especiales
    username = re.sub(r'[^\w]', '', username)
    
    return username

def format_workspace_name(name: str) -> str:
    """Formatear nombre de workspace"""
    # Capitalizar primera letra de cada palabra
    return ' '.join(word.capitalize() for word in name.split())

def format_conversation_summary(messages: list, max_length: int = 100) -> str:
    """Formatear resumen de conversación"""
    if not messages:
        return "Sin mensajes"
    
    # Obtener últimos mensajes
    recent_messages = messages[-3:] if len(messages) > 3 else messages
    
    # Crear resumen
    summary_parts = []
    for msg in recent_messages:
        direction = "👤" if msg.get('direction') == 'inbound' else "🤖"
        text = msg.get('text', '')[:50]
        summary_parts.append(f"{direction} {text}")
    
    summary = " | ".join(summary_parts)
    
    if len(summary) > max_length:
        summary = summary[:max_length - 3] + "..."
    
    return summary

def format_error_message(error: Exception, context: Dict[str, Any] = None) -> str:
    """Formatear mensaje de error"""
    error_msg = f"Error: {str(error)}"
    
    if context:
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        error_msg += f" (Contexto: {context_str})"
    
    return error_msg

def format_metrics_summary(metrics: Dict[str, Any]) -> str:
    """Formatear resumen de métricas"""
    summary_parts = []
    
    if 'requests_total' in metrics:
        summary_parts.append(f"Requests: {metrics['requests_total']}")
    
    if 'response_time' in metrics:
        summary_parts.append(f"Tiempo: {format_duration(metrics['response_time'])}")
    
    if 'errors_total' in metrics:
        summary_parts.append(f"Errores: {metrics['errors_total']}")
    
    if 'active_connections' in metrics:
        summary_parts.append(f"Conexiones: {metrics['active_connections']}")
    
    return " | ".join(summary_parts)

def format_vertical_display_name(vertical: str) -> str:
    """Formatear nombre de vertical para mostrar"""
    vertical_names = {
        'gastronomia': 'Gastronomía',
        'inmobiliaria': 'Inmobiliaria',
        'servicios': 'Servicios',
        'otro': 'Otro'
    }
    
    return vertical_names.get(vertical, vertical.capitalize())

def format_plan_tier_display_name(plan_tier: str) -> str:
    """Formatear nombre de plan para mostrar"""
    plan_names = {
        'agent_basic': 'Básico',
        'agent_pro': 'Profesional',
        'agent_premium': 'Premium',
        'agent_custom': 'Personalizado'
    }
    
    return plan_names.get(plan_tier, plan_tier.replace('_', ' ').title())
