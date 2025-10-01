#!/usr/bin/env python3
"""
Generador de Tokens JWT para el Sistema Multitenant
"""

import jwt
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Configuración
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')

def generate_token(
    user_id: str,
    workspace_id: str,
    permissions: list,
    expires_hours: int = 24
) -> str:
    """
    Genera un token JWT para autenticación
    
    Args:
        user_id: ID del usuario
        workspace_id: ID del workspace
        permissions: Lista de permisos
        expires_hours: Horas hasta expiración
        
    Returns:
        Token JWT
    """
    now = datetime.utcnow()
    exp = now + timedelta(hours=expires_hours)
    
    payload = {
        'user_id': user_id,
        'workspace_id': workspace_id,
        'permissions': permissions,
        'iat': now,
        'exp': exp
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verifica y decodifica un token JWT
    
    Args:
        token: Token JWT
        
    Returns:
        Payload decodificado
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise Exception("Token expirado")
    except jwt.JWTError:
        raise Exception("Token inválido")

def main():
    """Función principal para generar tokens de prueba"""
    print("🔐 Generador de Tokens JWT para Pulpo")
    print("=" * 50)
    
    # Tokens de ejemplo
    tokens = [
        {
            "name": "Admin Workspace 1",
            "user_id": "user_001",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "permissions": ["file:ingest", "file:delete", "workspace:read", "workspace:admin"]
        },
        {
            "name": "User Workspace 1",
            "user_id": "user_002", 
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "permissions": ["file:ingest", "workspace:read"]
        },
        {
            "name": "Admin Workspace 2",
            "user_id": "user_003",
            "workspace_id": "00000000-0000-0000-0000-000000000002",
            "permissions": ["file:ingest", "file:delete", "workspace:read", "workspace:admin"]
        }
    ]
    
    for token_info in tokens:
        token = generate_token(
            token_info["user_id"],
            token_info["workspace_id"],
            token_info["permissions"]
        )
        
        print(f"\n📋 {token_info['name']}:")
        print(f"  User ID: {token_info['user_id']}")
        print(f"  Workspace ID: {token_info['workspace_id']}")
        print(f"  Permissions: {', '.join(token_info['permissions'])}")
        print(f"  Token: {token}")
        
        # Verificar token
        try:
            payload = verify_token(token)
            print(f"  ✅ Token válido hasta: {datetime.fromtimestamp(payload['exp'])}")
        except Exception as e:
            print(f"  ❌ Error verificando token: {e}")
    
    print("\n" + "=" * 50)
    print("💡 Uso en API:")
    print("  curl -H 'Authorization: Bearer <token>' http://localhost:8080/workspace/stats")
    
    print("\n🔧 Variables de entorno:")
    print(f"  JWT_SECRET={JWT_SECRET}")
    print(f"  JWT_ALGORITHM={JWT_ALGORITHM}")

if __name__ == "__main__":
    main()


