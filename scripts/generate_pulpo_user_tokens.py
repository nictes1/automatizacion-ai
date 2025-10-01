#!/usr/bin/env python3
"""
Generador de Tokens de Usuario de Pulpo para Pruebas
Simula tokens que enviaría la app Pulpo
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pulpo_token_validator import create_test_user_token
import json

def main():
    """Genera tokens de prueba para diferentes usuarios y workspaces"""
    print("🔐 Generador de Tokens de Usuario de Pulpo")
    print("=" * 60)
    
    # Usuarios de prueba (simulando datos de la app Pulpo)
    test_users = [
        {
            "name": "Admin Workspace 1",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "email": "admin@workspace1.com",
            "role": "admin",
            "plan": "premium"
        },
        {
            "name": "Manager Workspace 1", 
            "user_id": "00000000-0000-0000-0000-000000000002",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "email": "manager@workspace1.com",
            "role": "manager",
            "plan": "premium"
        },
        {
            "name": "User Workspace 1",
            "user_id": "00000000-0000-0000-0000-000000000003",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "email": "user@workspace1.com",
            "role": "user",
            "plan": "premium"
        },
        {
            "name": "Admin Workspace 2",
            "user_id": "00000000-0000-0000-0000-000000000004",
            "workspace_id": "00000000-0000-0000-0000-000000000002",
            "email": "admin@workspace2.com",
            "role": "admin",
            "plan": "basic"
        },
        {
            "name": "User Workspace 2",
            "user_id": "00000000-0000-0000-0000-000000000005",
            "workspace_id": "00000000-0000-0000-0000-000000000002",
            "email": "user@workspace2.com",
            "role": "user",
            "plan": "basic"
        },
        {
            "name": "Viewer Workspace 2",
            "user_id": "00000000-0000-0000-0000-000000000006",
            "workspace_id": "00000000-0000-0000-0000-000000000002",
            "email": "viewer@workspace2.com",
            "role": "viewer",
            "plan": "basic"
        }
    ]
    
    print("📋 Tokens de Usuario de Pulpo:")
    print()
    
    for user in test_users:
        # Generar token
        token = create_test_user_token(
            user["user_id"],
            user["workspace_id"],
            expires_hours=24
        )
        
        print(f"👤 {user['name']}:")
        print(f"   📧 Email: {user['email']}")
        print(f"   🏢 Workspace: {user['workspace_id']}")
        print(f"   👔 Rol: {user['role']}")
        print(f"   📦 Plan: {user['plan']}")
        print(f"   🔑 Token: {token}")
        print()
    
    print("=" * 60)
    print("🧪 Ejemplos de Uso:")
    print()
    
    # Ejemplo 1: Obtener información del usuario
    admin_token = create_test_user_token(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000001"
    )
    
    print("1️⃣ Obtener información del usuario:")
    print(f"curl -H 'Authorization: Bearer {admin_token}' \\")
    print("     http://localhost:8080/user/info")
    print()
    
    # Ejemplo 2: Verificar quota
    print("2️⃣ Verificar quota del usuario:")
    print(f"curl -H 'Authorization: Bearer {admin_token}' \\")
    print("     http://localhost:8080/user/quota")
    print()
    
    # Ejemplo 3: Subir archivo
    print("3️⃣ Subir archivo:")
    print(f"curl -X POST http://localhost:8080/ingest/upload \\")
    print(f"     -H 'Authorization: Bearer {admin_token}' \\")
    print("     -F 'file=@documento.pdf' \\")
    print("     -F 'title=Documento de prueba'")
    print()
    
    # Ejemplo 4: Ver estadísticas del workspace
    print("4️⃣ Ver estadísticas del workspace:")
    print(f"curl -H 'Authorization: Bearer {admin_token}' \\")
    print("     http://localhost:8080/workspace/stats")
    print()
    
    print("=" * 60)
    print("🔧 Configuración:")
    print(f"JWT_SECRET={os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')}")
    print(f"JWT_ALGORITHM={os.getenv('JWT_ALGORITHM', 'HS256')}")
    print()
    
    print("💡 Notas:")
    print("- Estos tokens simulan usuarios de la app Pulpo")
    print("- Cada token está asociado a un workspace específico")
    print("- Los permisos se basan en el rol del usuario")
    print("- Los límites se basan en el plan del workspace")
    print()
    
    print("🚀 Para probar:")
    print("1. Inicia el servicio: python multitenant_file_ingestor.py")
    print("2. Usa cualquiera de los tokens generados arriba")
    print("3. Prueba los endpoints con los ejemplos")

if __name__ == "__main__":
    main()


