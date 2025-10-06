"""
Script para probar la creación de un evento en Google Calendar
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta
from uuid import UUID
import sys
import os
import json

# IMPORTANTE: Configurar variable de entorno ANTES de importar servicios
os.environ['ENCRYPTION_KEY'] = 'eOFUNNtwytJ_7RCTq6EfYBgDGfTcV_39MWafnHaKRdc='

# Agregar el directorio raíz al path
sys.path.insert(0, '/home/nictes/workspace/nictes1/pulpo')

from services.calendar_config_service import calendar_config_service
from services.google_calendar_client import GoogleCalendarClient

async def test_create_event():
    """Crea un evento de prueba en el calendario conectado"""

    workspace_id = UUID('550e8400-e29b-41d4-a716-446655440000')

    # Conectar a la DB
    pool = await asyncpg.create_pool(
        'postgresql://pulpo:pulpo@localhost:5432/pulpo',
        min_size=1,
        max_size=5
    )

    # Inicializar calendar service
    await calendar_config_service.initialize_db(pool)

    # Obtener configuración del calendario
    config = await calendar_config_service.get_calendar_config(workspace_id)

    if not config or not config.get('is_configured'):
        print("❌ Calendario no configurado para este workspace")
        await pool.close()
        return

    calendar_email = config['calendar_email']
    print(f"📅 Calendario: {calendar_email}")

    # Obtener credenciales cifradas desde la DB
    async with pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT settings FROM pulpo.workspaces WHERE id = $1
        """, workspace_id)

        if not row or not row['settings']:
            print("❌ No se encontraron settings")
            await pool.close()
            return

        # asyncpg puede devolver JSONB como string, parsearlo si es necesario
        settings = row['settings']
        if isinstance(settings, str):
            settings = json.loads(settings)

    # Descifrar y crear credentials
    credentials = calendar_config_service.get_credentials_from_workspace(settings)

    if not credentials:
        print("❌ No se pudieron obtener credenciales")
        await pool.close()
        return

    print("✅ Credenciales descifradas correctamente")

    # Crear cliente de Google Calendar
    calendar_client = GoogleCalendarClient(credentials)

    if not calendar_client.is_available():
        print("❌ Google Calendar client no disponible")
        await pool.close()
        return

    print("✅ Google Calendar client inicializado")

    # Crear evento de prueba
    # Hoy a las 12 AM (medianoche) = 00:00
    now = datetime.now()
    start_time = datetime(now.year, now.month, now.day, 0, 0, 0)  # 12 AM
    end_time = start_time + timedelta(hours=1)  # 1 hora de duración

    print(f"\n🗓️  Creando evento:")
    print(f"   Título: Test Evento")
    print(f"   Inicio: {start_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Fin: {end_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Calendario: {calendar_email}")

    event_id = await calendar_client.create_event(
        calendar_id=calendar_email,
        summary="Test Evento",
        description="Evento de prueba creado por PulpoAI para verificar integración con Google Calendar",
        start_datetime=start_time,
        end_datetime=end_time,
        attendees=[],  # Sin asistentes
        location=None,
        timezone='America/Argentina/Buenos_Aires'
    )

    if event_id:
        print(f"\n✅ Evento creado exitosamente!")
        print(f"   Event ID: {event_id}")
        print(f"\n🔗 Ver en Google Calendar:")
        print(f"   https://calendar.google.com/calendar/u/0/r/eventedit/{event_id}")
    else:
        print("\n❌ Error al crear el evento")

    await pool.close()

if __name__ == "__main__":
    asyncio.run(test_create_event())
