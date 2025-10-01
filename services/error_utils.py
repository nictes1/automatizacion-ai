"""
Utilidades para formato de errores compartido
Proporciona funciones helper para generar respuestas de error consistentes
"""

from typing import Dict, Any, Optional, List
from fastapi import HTTPException

def error_payload(code: str, message: str, request_id: str = "", details: Optional[Any] = None) -> Dict[str, Any]:
    """
    Genera un payload de error consistente para todos los servicios
    
    Args:
        code: Código de error (ej: "VALIDATION_ERROR", "HTTP_ERROR", "INTERNAL")
        message: Mensaje de error legible
        request_id: ID del request para trazabilidad
        details: Detalles adicionales (ej: errores de validación)
    
    Returns:
        Dict con formato estándar de error
    """
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id
        }
    }
    
    if details is not None:
        payload["error"]["details"] = details
    
    return payload

def validation_error(message: str = "Parámetros inválidos", request_id: str = "", details: Optional[List[Dict]] = None) -> HTTPException:
    """
    Crea un HTTPException para errores de validación (422)
    """
    return HTTPException(
        status_code=422,
        detail=error_payload("VALIDATION_ERROR", message, request_id, details)
    )

def not_found_error(resource: str = "Recurso", request_id: str = "") -> HTTPException:
    """
    Crea un HTTPException para recursos no encontrados (404)
    """
    return HTTPException(
        status_code=404,
        detail=error_payload("NOT_FOUND", f"{resource} no encontrado", request_id)
    )

def unauthorized_error(message: str = "No autorizado", request_id: str = "") -> HTTPException:
    """
    Crea un HTTPException para errores de autorización (401)
    """
    return HTTPException(
        status_code=401,
        detail=error_payload("UNAUTHORIZED", message, request_id)
    )

def forbidden_error(message: str = "Acceso denegado", request_id: str = "") -> HTTPException:
    """
    Crea un HTTPException para errores de permisos (403)
    """
    return HTTPException(
        status_code=403,
        detail=error_payload("FORBIDDEN", message, request_id)
    )

def rate_limit_error(message: str = "Demasiadas solicitudes", request_id: str = "", retry_after: Optional[int] = None) -> HTTPException:
    """
    Crea un HTTPException para rate limiting (429)
    """
    detail = error_payload("RATE_LIMIT", message, request_id)
    if retry_after:
        detail["error"]["retry_after"] = retry_after
    
    return HTTPException(
        status_code=429,
        detail=detail
    )

def internal_error(message: str = "Error interno del servidor", request_id: str = "") -> HTTPException:
    """
    Crea un HTTPException para errores internos (500)
    """
    return HTTPException(
        status_code=500,
        detail=error_payload("INTERNAL", message, request_id)
    )

def service_unavailable_error(service: str = "Servicio", request_id: str = "") -> HTTPException:
    """
    Crea un HTTPException para servicios no disponibles (503)
    """
    return HTTPException(
        status_code=503,
        detail=error_payload("SERVICE_UNAVAILABLE", f"{service} no disponible", request_id)
    )

def bad_request_error(message: str = "Solicitud inválida", request_id: str = "") -> HTTPException:
    """
    Crea un HTTPException para bad requests (400)
    """
    return HTTPException(
        status_code=400,
        detail=error_payload("BAD_REQUEST", message, request_id)
    )

# Códigos de error estándar
class ErrorCodes:
    """Códigos de error estándar para todos los servicios"""
    
    # Errores de validación
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Errores de autenticación/autorización
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    
    # Errores de recursos
    NOT_FOUND = "NOT_FOUND"
    RESOURCE_CONFLICT = "RESOURCE_CONFLICT"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    
    # Errores de rate limiting
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    
    # Errores de servicios
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    SERVICE_TIMEOUT = "SERVICE_TIMEOUT"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    
    # Errores internos
    INTERNAL = "INTERNAL"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    
    # Errores de negocio
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    WORKSPACE_NOT_FOUND = "WORKSPACE_NOT_FOUND"

# Mensajes de error estándar
class ErrorMessages:
    """Mensajes de error estándar para todos los servicios"""
    
    # Validación
    INVALID_VERTICAL = "Vertical no válido. Valores permitidos: gastronomia, inmobiliaria, servicios"
    INVALID_CONVERSATION_ID = "ID de conversación inválido"
    INVALID_USER_INPUT = "Input del usuario inválido"
    INVALID_ATTEMPTS_COUNT = "Número de intentos inválido (debe estar entre 0 y 10)"
    
    # Autenticación
    MISSING_AUTHORIZATION = "Header Authorization requerido"
    INVALID_AUTHORIZATION = "Token de autorización inválido"
    EXPIRED_TOKEN = "Token de autorización expirado"
    
    # Workspace
    MISSING_WORKSPACE = "Header X-Workspace-Id requerido"
    INVALID_WORKSPACE = "Workspace no válido o no encontrado"
    WORKSPACE_ACCESS_DENIED = "Acceso denegado al workspace"
    
    # Rate limiting
    TOO_MANY_REQUESTS = "Demasiadas solicitudes. Intenta nuevamente en unos momentos"
    CONVERSATION_RATE_LIMIT = "Demasiadas solicitudes para esta conversación"
    
    # Servicios
    RAG_SERVICE_ERROR = "Error en el servicio de RAG"
    ACTIONS_SERVICE_ERROR = "Error en el servicio de acciones"
    LLM_SERVICE_ERROR = "Error en el servicio de LLM"
    
    # Internos
    INTERNAL_ERROR = "Error interno del servidor"
    CONFIGURATION_ERROR = "Error de configuración del servicio"
    DATABASE_ERROR = "Error en la base de datos"

def extract_request_id_from_exception(exc: HTTPException) -> str:
    """
    Extrae el request_id de un HTTPException si está presente
    
    Args:
        exc: HTTPException
    
    Returns:
        request_id si está presente, string vacío si no
    """
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return exc.detail["error"].get("request_id", "")
    return ""

def is_error_response(response_data: Dict[str, Any]) -> bool:
    """
    Verifica si una respuesta es un error basado en su estructura
    
    Args:
        response_data: Datos de respuesta
    
    Returns:
        True si es un error, False si no
    """
    return isinstance(response_data, dict) and "error" in response_data

def get_error_code(response_data: Dict[str, Any]) -> Optional[str]:
    """
    Obtiene el código de error de una respuesta
    
    Args:
        response_data: Datos de respuesta
    
    Returns:
        Código de error si está presente, None si no
    """
    if is_error_response(response_data):
        return response_data["error"].get("code")
    return None

def get_error_message(response_data: Dict[str, Any]) -> Optional[str]:
    """
    Obtiene el mensaje de error de una respuesta
    
    Args:
        response_data: Datos de respuesta
    
    Returns:
        Mensaje de error si está presente, None si no
    """
    if is_error_response(response_data):
        return response_data["error"].get("message")
    return None
