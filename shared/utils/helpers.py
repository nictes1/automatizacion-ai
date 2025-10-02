#!/usr/bin/env python3
"""
PulpoAI Shared Utils Helpers
Utilidades compartidas
"""

import uuid
import json
import time
import re
from typing import Dict, Any, Optional, Union
from datetime import datetime, timezone

def generate_uuid() -> str:
    """Generar UUID v4"""
    return str(uuid.uuid4())

def generate_request_id() -> str:
    """Generar ID de request único"""
    timestamp = int(time.time() * 1000)
    return f"req_{timestamp}_{uuid.uuid4().hex[:8]}"

def get_current_timestamp() -> datetime:
    """Obtener timestamp actual"""
    return datetime.now(timezone.utc)

def format_duration(seconds: float) -> str:
    """Formatear duración en segundos"""
    if seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def parse_json_safe(json_str: str, default: Any = None) -> Any:
    """Parsear JSON de forma segura"""
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return default

def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Fusionar diccionarios de forma profunda"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result

def safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Obtener valor de diccionario de forma segura"""
    keys = key.split('.')
    value = dictionary
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default
    
    return value

def safe_set(dictionary: Dict[str, Any], key: str, value: Any) -> None:
    """Establecer valor en diccionario de forma segura"""
    keys = key.split('.')
    current = dictionary
    
    for k in keys[:-1]:
        if k not in current:
            current[k] = {}
        current = current[k]
    
    current[keys[-1]] = value

def chunk_list(lst: list, chunk_size: int) -> list:
    """Dividir lista en chunks"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]

def remove_none_values(dictionary: Dict[str, Any]) -> Dict[str, Any]:
    """Remover valores None del diccionario"""
    return {k: v for k, v in dictionary.items() if v is not None}

def flatten_dict(dictionary: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """Aplanar diccionario anidado"""
    items = []
    for k, v in dictionary.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def unflatten_dict(dictionary: Dict[str, Any], sep: str = '.') -> Dict[str, Any]:
    """Desaplanar diccionario"""
    result = {}
    for key, value in dictionary.items():
        keys = key.split(sep)
        current = result
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
    return result

def is_valid_json(json_str: str) -> bool:
    """Verificar si string es JSON válido"""
    try:
        json.loads(json_str)
        return True
    except (json.JSONDecodeError, TypeError):
        return False

def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncar string a longitud máxima"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def normalize_string(text: str) -> str:
    """Normalizar string (lowercase, strip, etc.)"""
    return text.lower().strip()

def extract_phone_number(text: str) -> Optional[str]:
    """Extraer número de teléfono de texto"""
    # Patrón básico para números de teléfono
    pattern = r'\+?[\d\s\-\(\)]{10,}'
    matches = re.findall(pattern, text)
    if matches:
        # Limpiar y normalizar
        phone = re.sub(r'[^\d+]', '', matches[0])
        if len(phone) >= 10:
            return phone
    return None

def extract_email(text: str) -> Optional[str]:
    """Extraer email de texto"""
    pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    matches = re.findall(pattern, text)
    return matches[0] if matches else None

def mask_sensitive_data(text: str, mask_char: str = '*') -> str:
    """Enmascarar datos sensibles"""
    # Enmascarar emails
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                   lambda m: m.group(0)[:2] + mask_char * (len(m.group(0)) - 4) + m.group(0)[-2:], text)
    
    # Enmascarar números de teléfono
    text = re.sub(r'\+?[\d\s\-\(\)]{10,}', 
                   lambda m: m.group(0)[:3] + mask_char * (len(m.group(0)) - 6) + m.group(0)[-3:], text)
    
    return text

def get_file_extension(filename: str) -> str:
    """Obtener extensión de archivo"""
    return filename.split('.')[-1].lower() if '.' in filename else ''

def is_supported_file_type(filename: str, supported_types: list) -> bool:
    """Verificar si tipo de archivo es soportado"""
    extension = get_file_extension(filename)
    return extension in supported_types

def calculate_similarity(text1: str, text2: str) -> float:
    """Calcular similitud entre dos textos (simple)"""
    # Implementación básica de similitud
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0
