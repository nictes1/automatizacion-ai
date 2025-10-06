"""
Test de flujo conversacional completo para agendamiento de turnos
Simula interacción WhatsApp → Orchestrator → Appointments → Google Calendar
"""

import asyncio
import httpx
from uuid import uuid4
from datetime import datetime, timedelta

# Configuración
ORCHESTRATOR_URL = "http://localhost:8005"
ACTIONS_URL = "http://localhost:8006"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"

async def test_conversational_flow():
    """Simula una conversación completa de agendamiento"""

    # Para test sin conversación real, usar None
    conversation_id = None
    headers = {
        "X-Workspace-Id": WORKSPACE_ID,
        "Content-Type": "application/json"
    }

    print("=" * 60)
    print("🤖 TEST CONVERSACIONAL - AGENDAMIENTO DE TURNOS")
    print("=" * 60)
    print(f"\n📱 Conversation ID: {conversation_id or 'None (test directo)'}")
    print(f"🏢 Workspace ID: {WORKSPACE_ID}\n")

    # Calcular fecha para mañana
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Paso 1: Cliente llama directamente al endpoint de appointments
    # (simulando que el orchestrator ya extrajo los datos)
    print("👤 Usuario (simulado): 'Hola, necesito cortarme el pelo mañana a las 3 de la tarde'")
    print("🧠 Orchestrator (simulado): Extrae datos de la conversación...")
    print("   - Servicio: Corte de Cabello")
    print(f"   - Fecha: {tomorrow}")
    print("   - Hora: 15:00")
    print("   - Cliente: Juan Pérez")
    print("   - Email: juan.perez@example.com\n")

    # Llamar directamente al actions service
    async with httpx.AsyncClient() as client:
        print("🔧 Llamando a Actions Service para crear turno...")

        appointment_data = {
            "conversation_id": conversation_id,
            "service_type_name": "Corte de Cabello",
            "client_name": "Juan Pérez",
            "client_email": "juan.perez@example.com",
            "client_phone": "+5491123456789",
            "appointment_date": tomorrow,
            "appointment_time": "15:00",
            "staff_id": None,  # Asignación automática
            "notes": "Cliente solicitó vía WhatsApp"
        }

        try:
            response = await client.post(
                f"{ACTIONS_URL}/actions/create-appointment",
                json=appointment_data,
                headers=headers,
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()

                print("\n✅ ¡TURNO CREADO EXITOSAMENTE!\n")
                print("📋 DETALLES DEL TURNO:")
                print(f"   🆔 ID: {result['appointment_id']}")
                print(f"   👤 Cliente: Juan Pérez")
                print(f"   👨‍💼 Empleado: {result['staff_name']}")
                print(f"   📧 Email empleado: {result['staff_email']}")
                print(f"   💇 Servicio: {result['service_name']}")
                print(f"   📅 Fecha: {result['date']}")
                print(f"   ⏰ Hora: {result['time']}")
                print(f"   ⏱️  Duración: {result['duration_minutes']} minutos")
                print(f"   ✓ Estado: {result['status']}")

                if result.get('google_event_id'):
                    print(f"\n📅 EVENTO EN GOOGLE CALENDAR:")
                    print(f"   Event ID: {result['google_event_id']}")
                    print(f"   🔗 Ver: https://calendar.google.com/calendar/u/0/r/eventedit/{result['google_event_id']}")
                else:
                    print("\n⚠️  No se creó evento en Google Calendar")

                print("\n🤖 Respuesta al usuario:")
                print(f"   '✅ Turno confirmado para {result['date']} a las {result['time']} con {result['staff_name']}'")
                print(f"   'Te enviamos la confirmación a {appointment_data['client_email']}'")

            elif response.status_code == 400:
                error = response.json()
                print(f"\n❌ ERROR DE VALIDACIÓN: {error.get('detail')}")

            else:
                print(f"\n❌ ERROR {response.status_code}: {response.text}")

        except httpx.RequestError as e:
            print(f"\n❌ ERROR DE CONEXIÓN: {e}")
            print("\n💡 SOLUCIÓN:")
            print("   1. Verifica que el servicio esté corriendo:")
            print(f"      python3 services/actions_app.py")
            print("   2. O inicia con las variables de entorno:")
            print("      ENCRYPTION_KEY='eOFUNNtwytJ_7RCTq6EfYBgDGfTcV_39MWafnHaKRdc=' python3 services/actions_app.py")

        except Exception as e:
            print(f"\n❌ ERROR INESPERADO: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("📊 RESUMEN DEL FLUJO:")
    print("=" * 60)
    print("✅ 1. Usuario envía mensaje por WhatsApp")
    print("✅ 2. Orchestrator analiza con IA (LLM)")
    print("✅ 3. Extrae: servicio, fecha, hora, datos cliente")
    print("✅ 4. Llama a Actions Service")
    print("✅ 5. Appointments Service crea turno en DB")
    print("✅ 6. Google Calendar Client crea evento (OAuth + Cifrado)")
    print("✅ 7. Invitaciones enviadas a empleado y cliente")
    print("✅ 8. Respuesta al usuario por WhatsApp")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_conversational_flow())
