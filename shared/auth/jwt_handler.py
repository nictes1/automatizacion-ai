#!/usr/bin/env python3
"""
PulpoAI Shared JWT Handler
Manejo de tokens JWT para autenticación
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

class JWTConfig:
    """Configuración JWT"""
    def __init__(self):
        self.secret_key = os.getenv('JWT_SECRET', 'your-secret-key-here')
        self.algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
        self.access_token_expire_minutes = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', '30'))
        self.refresh_token_expire_days = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRE_DAYS', '7'))

class JWTHandler:
    """Manejador de tokens JWT"""
    
    def __init__(self, config: Optional[JWTConfig] = None):
        self.config = config or JWTConfig()
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Crear token de acceso"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.config.access_token_expire_minutes)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.config.secret_key, algorithm=self.config.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Crear token de refresco"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.config.refresh_token_expire_days)
        
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.config.secret_key, algorithm=self.config.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verificar token"""
        try:
            payload = jwt.decode(token, self.config.secret_key, algorithms=[self.config.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise TokenError(f"JWT verification failed: {e}")
    
    def get_user_from_token(self, token: str) -> Dict[str, Any]:
        """Obtener usuario del token"""
        payload = self.verify_token(token)
        if payload.get("type") != "access":
            raise TokenError("Invalid token type")
        return payload
    
    def hash_password(self, password: str) -> str:
        """Hashear contraseña"""
        return self.pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verificar contraseña"""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def create_service_token(self, service_name: str, permissions: list = None) -> str:
        """Crear token de servicio"""
        data = {
            "service": service_name,
            "permissions": permissions or [],
            "type": "service"
        }
        return self.create_access_token(data, timedelta(days=365))  # Tokens de servicio duran 1 año
    
    def verify_service_token(self, token: str, required_permissions: list = None) -> Dict[str, Any]:
        """Verificar token de servicio"""
        payload = self.verify_token(token)
        if payload.get("type") != "service":
            raise TokenError("Invalid service token")
        
        if required_permissions:
            service_permissions = payload.get("permissions", [])
            if not all(perm in service_permissions for perm in required_permissions):
                raise PermissionError("Insufficient permissions")
        
        return payload

# Instancia global del manejador JWT
jwt_handler = JWTHandler()
