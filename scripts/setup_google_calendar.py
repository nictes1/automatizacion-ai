#!/usr/bin/env python3
"""
Script para configurar Google Calendar en el workspace
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
sys.path.append('/home/nictes/workspace/nictes1/pulpo')

from services.calendar_config_service import calendar_config_service
from utils.db_pool import get_db_pool

async def setup_google_calendar():
    """Configura Google Calendar para el workspace de peluquería"""
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Configurar credenciales si no están configuradas
    if not os.getenv('GOOGLE_CLIENT_ID'):
        import json
        with open('credentials/google_oauth_credentials.json', 'r') as f:
            creds = json.load(f)
        
        os.environ['GOOGLE_CLIENT_ID'] = creds['web']['client_id']
        os.environ['GOOGLE_CLIENT_SECRET'] = creds['web']['client_secret']
    
    print("🔑 CONFIGURANDO GOOGLE CALENDAR")
    print("=" * 50)
    
    # Workspace de peluquería
    workspace_id = "550e8400-e29b-41d4-a716-446655440003"
    
    # Inicializar servicios
    db_pool = await get_db_pool()
    await calendar_config_service.initialize_db(db_pool)
    
    # Verificar configuración actual
    config = await calendar_config_service.get_calendar_config(workspace_id)
    
    if config and config.get('is_configured'):
        print(f"✅ Google Calendar ya está configurado")
        print(f"📧 Email del calendario: {config.get('calendar_email')}")
        return
    
    print(f"📋 Workspace: {workspace_id}")
    print(f"🔧 Generando URL de autorización...")
    
    # Generar URL de autorización
    redirect_uri = "http://localhost:8000/auth/google/callback"
    auth_url = await calendar_config_service.get_authorization_url(
        workspace_id=workspace_id,
        redirect_uri=redirect_uri
    )
    
    print(f"🌐 URL de autorización generada:")
    print(f"   {auth_url}")
    print(f"")
    print(f"📝 INSTRUCCIONES:")
    print(f"1. Abre la URL en tu navegador")
    print(f"2. Autoriza el acceso a Google Calendar")
    print(f"3. Copia el código de autorización de la URL de callback")
    print(f"4. Ejecuta: python3 scripts/complete_google_calendar_setup.py <codigo>")
    
    await db_pool.close()

if __name__ == "__main__":
    asyncio.run(setup_google_calendar())


