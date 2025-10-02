#!/usr/bin/env python3
"""
PulpoAI Shared Utils Validators
Validadores compartidos
"""

import re
import uuid
from typing import Optional, List, Dict, Any
from .exceptions import ValidationError

def validate_email(email: str) -> bool:
    """Validar email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """Validar número de teléfono"""
    # Limpiar número
    clean_phone = re.sub(r'[^\d+]', '', phone)
    
    # Verificar longitud y formato
    if len(clean_phone) < 10 or len(clean_phone) > 15:
        return False
    
    # Verificar que empiece con + o dígitos
    if not (clean_phone.startswith('+') or clean_phone.isdigit()):
        return False
    
    return True

def validate_uuid(uuid_str: str) -> bool:
    """Validar UUID"""
    try:
        uuid.UUID(uuid_str)
        return True
    except ValueError:
        return False

def validate_workspace_id(workspace_id: str) -> bool:
    """Validar workspace ID"""
    return validate_uuid(workspace_id)

def validate_conversation_id(conversation_id: str) -> bool:
    """Validar conversation ID"""
    return validate_uuid(conversation_id)

def validate_phone_number(phone: str) -> bool:
    """Validar número de teléfono con formato específico"""
    # Patrón para números de teléfono internacionales
    pattern = r'^\+?[1-9]\d{1,14}$'
    clean_phone = re.sub(r'[^\d+]', '', phone)
    return bool(re.match(pattern, clean_phone))

def validate_currency(amount: str) -> bool:
    """Validar formato de moneda"""
    # Patrón para moneda (ej: $123.45, 123.45, 123,45)
    pattern = r'^[\$€£]?\d{1,3}(,\d{3})*(\.\d{2})?$'
    return bool(re.match(pattern, amount))

def validate_date_format(date_str: str, format: str = '%Y-%m-%d') -> bool:
    """Validar formato de fecha"""
    try:
        from datetime import datetime
        datetime.strptime(date_str, format)
        return True
    except ValueError:
        return False

def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Validar datos contra esquema JSON"""
    # Implementación básica de validación de esquema
    for key, value_type in schema.items():
        if key not in data:
            return False
        
        if value_type == 'string' and not isinstance(data[key], str):
            return False
        elif value_type == 'number' and not isinstance(data[key], (int, float)):
            return False
        elif value_type == 'boolean' and not isinstance(data[key], bool):
            return False
        elif value_type == 'array' and not isinstance(data[key], list):
            return False
        elif value_type == 'object' and not isinstance(data[key], dict):
            return False
    
    return True

def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """Validar campos requeridos"""
    for field in required_fields:
        if field not in data or data[field] is None or data[field] == '':
            return False
    return True

def validate_field_length(field: str, min_length: int = 0, max_length: int = None) -> bool:
    """Validar longitud de campo"""
    if not isinstance(field, str):
        return False
    
    if len(field) < min_length:
        return False
    
    if max_length is not None and len(field) > max_length:
        return False
    
    return True

def validate_enum_value(value: str, allowed_values: List[str]) -> bool:
    """Validar valor contra lista de valores permitidos"""
    return value in allowed_values

def validate_range(value: Union[int, float], min_value: Union[int, float] = None, max_value: Union[int, float] = None) -> bool:
    """Validar rango de valor"""
    if min_value is not None and value < min_value:
        return False
    
    if max_value is not None and value > max_value:
        return False
    
    return True

def validate_url(url: str) -> bool:
    """Validar URL"""
    pattern = r'^https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?$'
    return bool(re.match(pattern, url))

def validate_slug(slug: str) -> bool:
    """Validar slug (identificador URL-friendly)"""
    pattern = r'^[a-z0-9]+(?:-[a-z0-9]+)*$'
    return bool(re.match(pattern, slug))

def validate_workspace_settings(settings: Dict[str, Any]) -> bool:
    """Validar configuración de workspace"""
    required_fields = ['vertical', 'plan_tier']
    
    if not validate_required_fields(settings, required_fields):
        return False
    
    # Validar vertical
    valid_verticals = ['gastronomia', 'inmobiliaria', 'servicios', 'otro']
    if not validate_enum_value(settings['vertical'], valid_verticals):
        return False
    
    # Validar plan_tier
    valid_plans = ['agent_basic', 'agent_pro', 'agent_premium', 'agent_custom']
    if not validate_enum_value(settings['plan_tier'], valid_plans):
        return False
    
    return True

def validate_conversation_data(data: Dict[str, Any]) -> bool:
    """Validar datos de conversación"""
    required_fields = ['workspace_id', 'user_phone']
    
    if not validate_required_fields(data, required_fields):
        return False
    
    # Validar workspace_id
    if not validate_workspace_id(data['workspace_id']):
        return False
    
    # Validar user_phone
    if not validate_phone(data['user_phone']):
        return False
    
    return True

def validate_message_data(data: Dict[str, Any]) -> bool:
    """Validar datos de mensaje"""
    required_fields = ['conversation_id', 'text', 'direction']
    
    if not validate_required_fields(data, required_fields):
        return False
    
    # Validar conversation_id
    if not validate_conversation_id(data['conversation_id']):
        return False
    
    # Validar direction
    valid_directions = ['inbound', 'outbound']
    if not validate_enum_value(data['direction'], valid_directions):
        return False
    
    # Validar text
    if not validate_field_length(data['text'], min_length=1, max_length=4000):
        return False
    
    return True

def validate_dialogue_state_data(data: Dict[str, Any]) -> bool:
    """Validar datos de estado de diálogo"""
    required_fields = ['workspace_id', 'conversation_id', 'fsm_state', 'next_action']
    
    if not validate_required_fields(data, required_fields):
        return False
    
    # Validar workspace_id
    if not validate_workspace_id(data['workspace_id']):
        return False
    
    # Validar conversation_id
    if not validate_conversation_id(data['conversation_id']):
        return False
    
    # Validar next_action
    valid_actions = ['answer', 'tool_call', 'handoff', 'wait']
    if not validate_enum_value(data['next_action'], valid_actions):
        return False
    
    return True
