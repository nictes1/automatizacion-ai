#!/usr/bin/env python3
"""
PulpoAI Shared Auth Client
Cliente de autenticación compartido
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from .jwt_handler import jwt_handler
from .exceptions import AuthError, TokenError, PermissionError

logger = logging.getLogger(__name__)

class AuthClient:
    """Cliente de autenticación"""
    
    def __init__(self):
        self.jwt_handler = jwt_handler
    
    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Autenticar usuario"""
        # Mock implementation - reemplazar con implementación real
        # Aquí iría la verificación en base de datos
        
        if email == "admin@pulpo.ai" and password == "admin123":
            return {
                "user_id": "user-123",
                "email": email,
                "name": "Admin User",
                "workspaces": ["550e8400-e29b-41d4-a716-446655440001"]
            }
        else:
            raise AuthError("Invalid credentials")
    
    def create_user_tokens(self, user_data: Dict[str, Any]) -> Dict[str, str]:
        """Crear tokens para usuario"""
        access_token = self.jwt_handler.create_access_token({
            "user_id": user_data["user_id"],
            "email": user_data["email"],
            "name": user_data["name"],
            "workspaces": user_data["workspaces"]
        })
        
        refresh_token = self.jwt_handler.create_refresh_token({
            "user_id": user_data["user_id"]
        })
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 1800  # 30 minutos
        }
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """Refrescar token de acceso"""
        try:
            payload = self.jwt_handler.verify_token(refresh_token)
            if payload.get("type") != "refresh":
                raise TokenError("Invalid refresh token")
            
            # Obtener datos del usuario (mock)
            user_data = {
                "user_id": payload["user_id"],
                "email": "admin@pulpo.ai",
                "name": "Admin User",
                "workspaces": ["550e8400-e29b-41d4-a716-446655440001"]
            }
            
            return self.create_user_tokens(user_data)
        except Exception as e:
            raise TokenError(f"Failed to refresh token: {e}")
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validar token"""
        return self.jwt_handler.get_user_from_token(token)
    
    def get_workspace_permissions(self, user_id: str, workspace_id: str) -> List[str]:
        """Obtener permisos del usuario en un workspace"""
        # Mock implementation - reemplazar con implementación real
        return ["read", "write", "admin"]
    
    def check_permission(self, user_id: str, workspace_id: str, permission: str) -> bool:
        """Verificar permiso específico"""
        permissions = self.get_workspace_permissions(user_id, workspace_id)
        return permission in permissions
    
    def create_service_token(self, service_name: str, permissions: List[str] = None) -> str:
        """Crear token de servicio"""
        return self.jwt_handler.create_service_token(service_name, permissions)
    
    def validate_service_token(self, token: str, required_permissions: List[str] = None) -> Dict[str, Any]:
        """Validar token de servicio"""
        return self.jwt_handler.verify_service_token(token, required_permissions)
    
    def extract_workspace_id(self, token: str) -> Optional[str]:
        """Extraer workspace_id del token"""
        try:
            payload = self.validate_token(token)
            workspaces = payload.get("workspaces", [])
            return workspaces[0] if workspaces else None
        except Exception as e:
            logger.error(f"Failed to extract workspace_id: {e}")
            return None
    
    def get_user_context(self, token: str) -> Dict[str, Any]:
        """Obtener contexto del usuario"""
        try:
            payload = self.validate_token(token)
            return {
                "user_id": payload.get("user_id"),
                "email": payload.get("email"),
                "name": payload.get("name"),
                "workspaces": payload.get("workspaces", []),
                "current_workspace": payload.get("workspaces", [None])[0]
            }
        except Exception as e:
            logger.error(f"Failed to get user context: {e}")
            raise AuthError(f"Failed to get user context: {e}")

# Instancia global del cliente de autenticación
auth_client = AuthClient()
