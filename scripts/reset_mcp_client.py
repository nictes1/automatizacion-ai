#!/usr/bin/env python3
"""
Script para resetear el cliente MCP singleton
"""

import asyncio
import os
import sys
sys.path.append('/home/nictes/workspace/nictes1/pulpo')

from services.mcp_client import close_mcp_client, get_mcp_client

async def reset_mcp_client():
    """Resetea el cliente MCP singleton"""
    
    print("🔄 RESETEANDO CLIENTE MCP SINGLETON")
    print("=" * 40)
    
    # 1. Cerrar cliente existente
    print("🔒 Cerrando cliente existente...")
    await close_mcp_client()
    
    # 2. Establecer variable de entorno
    print("⚙️  Configurando MCP_URL...")
    os.environ['MCP_URL'] = 'http://localhost:8012'
    print(f"   MCP_URL = {os.environ['MCP_URL']}")
    
    # 3. Crear nuevo cliente
    print("🆕 Creando nuevo cliente...")
    client = get_mcp_client()
    print(f"   Base URL: {client.base_url}")
    
    # 4. Probar conexión
    print("🧪 Probando conexión...")
    try:
        tools = await client.list_tools()
        print(f"✅ Conexión exitosa: {len(tools)} tools disponibles")
        
        # Verificar que book_appointment esté disponible
        tool_names = [tool['name'] for tool in tools]
        if 'book_appointment' in tool_names:
            print("✅ Tool book_appointment disponible")
        else:
            print("❌ Tool book_appointment NO disponible")
            print(f"   Tools disponibles: {tool_names}")
            
    except Exception as e:
        print(f"❌ Error en conexión: {e}")
    
    # 5. Probar tool
    print("\n🧪 Probando tool book_appointment...")
    try:
        result = await client.call_tool("book_appointment", {
            "workspace_id": "550e8400-e29b-41d4-a716-446655440003",
            "service_type": "Corte de Cabello",
            "preferred_date": "2025-10-15",
            "preferred_time": "18:00",
            "client_name": "Reset Test",
            "client_email": "reset@email.com"
        })
        print(f"✅ Tool exitoso: {result}")
    except Exception as e:
        print(f"❌ Error en tool: {e}")
    
    await client.client.aclose()

if __name__ == "__main__":
    asyncio.run(reset_mcp_client())


