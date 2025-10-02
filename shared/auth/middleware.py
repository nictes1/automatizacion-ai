#!/usr/bin/env python3
"""
PulpoAI Shared Auth Middleware
Middleware de autenticación para FastAPI
"""

import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .client import auth_client
from .exceptions import AuthError, TokenError, PermissionError

logger = logging.getLogger(__name__)

security = HTTPBearer()

class AuthMiddleware:
    """Middleware de autenticación"""
    
    def __init__(self, auth_client_instance=None):
        self.auth_client = auth_client_instance or auth_client
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
        """Obtener usuario actual"""
        try:
            token = credentials.credentials
            user_context = self.auth_client.get_user_context(token)
            return user_context
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    async def get_workspace_id(self, x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id")) -> str:
        """Obtener workspace_id del header"""
        if not x_workspace_id:
            raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")
        return x_workspace_id
    
    async def verify_workspace_access(self, user: Dict[str, Any], workspace_id: str) -> bool:
        """Verificar acceso al workspace"""
        user_workspaces = user.get("workspaces", [])
        if workspace_id not in user_workspaces:
            raise HTTPException(status_code=403, detail="Access denied to workspace")
        return True
    
    async def get_authenticated_user(self, request: Request) -> Dict[str, Any]:
        """Obtener usuario autenticado desde request"""
        try:
            # Obtener token del header Authorization
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
            
            token = auth_header.split(" ")[1]
            user_context = self.auth_client.get_user_context(token)
            return user_context
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    
    async def get_service_context(self, request: Request) -> Dict[str, Any]:
        """Obtener contexto de servicio"""
        try:
            # Obtener token del header Authorization
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
            
            token = auth_header.split(" ")[1]
            service_context = self.auth_client.validate_service_token(token)
            return service_context
        except Exception as e:
            logger.error(f"Service authentication failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid service credentials")

# Instancia global del middleware
auth_middleware = AuthMiddleware()

# Dependencias para FastAPI
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Dependencia para obtener usuario actual"""
    return await auth_middleware.get_current_user(credentials)

async def get_workspace_id(x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id")) -> str:
    """Dependencia para obtener workspace_id"""
    return await auth_middleware.get_workspace_id(x_workspace_id)

async def verify_workspace_access(
    user: Dict[str, Any] = Depends(get_current_user),
    workspace_id: str = Depends(get_workspace_id)
) -> bool:
    """Dependencia para verificar acceso al workspace"""
    return await auth_middleware.verify_workspace_access(user, workspace_id)

async def get_authenticated_user(request: Request) -> Dict[str, Any]:
    """Dependencia para obtener usuario autenticado"""
    return await auth_middleware.get_authenticated_user(request)

async def get_service_context(request: Request) -> Dict[str, Any]:
    """Dependencia para obtener contexto de servicio"""
    return await auth_middleware.get_service_context(request)
