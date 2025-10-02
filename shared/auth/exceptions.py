#!/usr/bin/env python3
"""
PulpoAI Shared Auth Exceptions
Excepciones compartidas para autenticación
"""

class AuthError(Exception):
    """Error base de autenticación"""
    pass

class TokenError(AuthError):
    """Error de token"""
    pass

class PermissionError(AuthError):
    """Error de permisos"""
    pass

class WorkspaceAccessError(AuthError):
    """Error de acceso a workspace"""
    pass

class ServiceAuthError(AuthError):
    """Error de autenticación de servicio"""
    pass
