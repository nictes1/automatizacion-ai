#!/usr/bin/env python3
"""
Script para completar la configuración de Google Calendar
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
sys.path.append('/home/nictes/workspace/nictes1/pulpo')

from services.calendar_config_service import calendar_config_service
from utils.db_pool import get_db_pool

async def complete_google_calendar_setup(authorization_code: str):
    """Completa la configuración de Google Calendar con el código de autorización"""
    
    # Cargar variables de entorno
    load_dotenv()
    
    # Configurar credenciales si no están configuradas
    if not os.getenv('GOOGLE_CLIENT_ID'):
        import json
        with open('credentials/google_oauth_credentials.json', 'r') as f:
            creds = json.load(f)
        
        os.environ['GOOGLE_CLIENT_ID'] = creds['web']['client_id']
        os.environ['GOOGLE_CLIENT_SECRET'] = creds['web']['client_secret']
    
    print("🔑 COMPLETANDO CONFIGURACIÓN DE GOOGLE CALENDAR")
    print("=" * 50)
    
    # Workspace de peluquería
    workspace_id = "550e8400-e29b-41d4-a716-446655440003"
    
    # Inicializar servicios
    db_pool = await get_db_pool()
    await calendar_config_service.initialize_db(db_pool)
    
    try:
        # Completar configuración
        redirect_uri = "http://localhost:8000/auth/google/callback"
        result = await calendar_config_service.save_calendar_credentials(
            workspace_id=workspace_id,
            authorization_code=authorization_code,
            redirect_uri=redirect_uri
        )
        
        print(f"✅ Google Calendar configurado exitosamente!")
        print(f"📧 Email del calendario: {result['calendar_email']}")
        print(f"📊 Estado: {result['status']}")
        
        # Verificar configuración
        config = await calendar_config_service.get_calendar_config(workspace_id)
        print(f"\\n📋 Configuración verificada:")
        print(f"   - Email: {config['calendar_email']}")
        print(f"   - Configurado: {config['is_configured']}")
        
    except Exception as e:
        print(f"❌ Error configurando Google Calendar: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await db_pool.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 scripts/complete_google_calendar_setup.py <codigo_autorizacion>")
        sys.exit(1)
    
    authorization_code = sys.argv[1]
    asyncio.run(complete_google_calendar_setup(authorization_code))


