"""
Test completo: Crear turno y sincronizar con Google Calendar
"""

import asyncio
import asyncpg
from datetime import date, time
from uuid import UUID
import sys
import os

# IMPORTANTE: Configurar variable de entorno ANTES de importar servicios
os.environ['ENCRYPTION_KEY'] = 'eOFUNNtwytJ_7RCTq6EfYBgDGfTcV_39MWafnHaKRdc='

# Agregar el directorio raíz al path
sys.path.insert(0, '/home/nictes/workspace/nictes1/pulpo')

from services.appointments_service import AppointmentsService
from services.calendar_config_service import calendar_config_service

async def test_create_appointment():
    """Crea un turno de prueba con sincronización a Google Calendar"""

    workspace_id = UUID('550e8400-e29b-41d4-a716-446655440000')

    # Conectar a la DB
    pool = await asyncpg.create_pool(
        'postgresql://pulpo:pulpo@localhost:5432/pulpo',
        min_size=1,
        max_size=5
    )

    # Inicializar servicios
    appointments_service = AppointmentsService()
    await appointments_service.initialize_db(pool)
    await calendar_config_service.initialize_db(pool)

    print("✅ Servicios inicializados")

    # Verificar calendario configurado
    config = await calendar_config_service.get_calendar_config(workspace_id)
    if config and config.get('is_configured'):
        print(f"✅ Calendario configurado: {config['calendar_email']}")
    else:
        print("⚠️  Calendario no configurado (el turno se creará sin evento de Google)")

    # Datos del turno
    print("\n📋 Creando turno con los siguientes datos:")
    print("   Cliente: Juan Pérez")
    print("   Email: juan.perez@example.com")
    print("   Teléfono: +5491123456789")
    print("   Servicio: Corte de Cabello")
    print("   Fecha: 2025-10-06")
    print("   Hora: 14:00")
    print("   Notas: Cliente prefiere tijera, no máquina")

    try:
        # Staff ID de Carlos Ramirez
        staff_id = UUID('a065b08c-49f3-430d-879f-aae8b6fd1c14')

        result = await appointments_service.create_appointment(
            workspace_id=workspace_id,
            conversation_id=None,  # Sin conversación asociada
            service_type_name="Corte de Cabello",
            client_name="Juan Pérez",
            client_email="juan.perez@example.com",
            client_phone="+5491123456789",
            appointment_date=date(2025, 10, 6),
            appointment_time=time(14, 0),
            staff_id=staff_id,  # Asignación directa
            notes="Cliente prefiere tijera, no máquina"
        )

        print("\n✅ ¡Turno creado exitosamente!")
        print(f"\n📝 Detalles del turno:")
        print(f"   ID: {result['appointment_id']}")
        print(f"   Empleado asignado: {result['staff_name']}")
        print(f"   Email empleado: {result['staff_email']}")
        print(f"   Servicio: {result['service_name']}")
        print(f"   Fecha: {result['date']}")
        print(f"   Hora: {result['time']}")
        print(f"   Duración: {result['duration_minutes']} minutos")
        print(f"   Estado: {result['status']}")

        if result.get('google_event_id'):
            print(f"\n📅 Evento creado en Google Calendar")
            print(f"   Event ID: {result['google_event_id']}")
            print(f"\n🔗 Ver evento:")
            print(f"   https://calendar.google.com/calendar/u/0/r/eventedit/{result['google_event_id']}")
        else:
            print("\n⚠️  No se creó evento en Google Calendar (calendario no configurado)")

    except ValueError as e:
        print(f"\n❌ Error de validación: {e}")
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()

    await pool.close()

if __name__ == "__main__":
    asyncio.run(test_create_appointment())
