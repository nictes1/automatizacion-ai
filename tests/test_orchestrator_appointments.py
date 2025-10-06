"""
Test de conversación completa con Orchestrator
Simula interacción WhatsApp → Orchestrator → Actions → Google Calendar
"""

import asyncio
import httpx
from uuid import uuid4
from datetime import datetime, timedelta

# Configuración
ORCHESTRATOR_URL = "http://localhost:8005"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"

async def send_message(client: httpx.AsyncClient, conversation_id: str, user_input: str, current_state: dict = None):
    """Envía un mensaje al orchestrator"""
    request_data = {
        "conversation_id": conversation_id,
        "user_input": user_input,
        "vertical": "servicios",
        "platform": "whatsapp",
        "current_state": current_state or {}
    }

    response = await client.post(
        f"{ORCHESTRATOR_URL}/orchestrator/decide",
        json=request_data,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=30.0
    )

    result = response.json()

    # Persistir el mensaje (simular lo que haría n8n)
    persist_data = {
        "conversation_id": conversation_id,
        "user_message": user_input,
        "assistant_message": result.get("assistant", ""),
        "slots": result.get("slots", {}),
        "next_action": result.get("next_action", ""),
        "vertical": "servicios",
        "platform": "whatsapp"
    }

    await client.post(
        f"{ORCHESTRATOR_URL}/orchestrator/persist_message",
        json=persist_data,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10.0
    )

    return result

async def test_appointment_conversation():
    """Simula una conversación completa de agendamiento"""

    conversation_id = str(uuid4())
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    print("=" * 70)
    print("🤖 TEST CONVERSACIONAL - AGENDAMIENTO CON ORCHESTRATOR")
    print("=" * 70)
    print(f"\n📱 Conversation ID: {conversation_id}")
    print(f"🏢 Workspace ID: {WORKSPACE_ID}")
    print(f"📅 Fecha objetivo: {tomorrow}\n")

    async with httpx.AsyncClient() as client:

        # Turno 1: Saludo inicial
        print("\n" + "─" * 70)
        print("👤 Usuario: Hola, necesito cortarme el pelo mañana a las 3 de la tarde")
        print("─" * 70)

        response = await send_message(
            client, conversation_id,
            "Hola, necesito cortarme el pelo mañana a las 3 de la tarde"
        )

        print(f"🤖 Asistente: {response['assistant']}")
        print(f"📊 Slots: {response.get('slots', {})}")
        print(f"🎯 Next Action: {response.get('next_action')}")

        # Construir estado completo para el siguiente turno
        current_state = {
            "greeted": True,
            "slots": response.get('slots', {}),
            "objective": response.get('objective', ''),
            "last_action": response.get('next_action'),
            "attempts_count": 0
        }

        # Turno 2: Proporcionar nombre
        if "nombre" in response['assistant'].lower() or "client_name" not in response.get('slots', {}):
            print("\n" + "─" * 70)
            print("👤 Usuario: Mi nombre es Pablo Martínez")
            print("─" * 70)

            response = await send_message(
                client, conversation_id,
                "Mi nombre es Pablo Martínez",
                current_state=current_state
            )

            print(f"🤖 Asistente: {response['assistant']}")
            print(f"📊 Slots: {response.get('slots', {})}")
            print(f"🎯 Next Action: {response.get('next_action')}")

            # Actualizar estado
            current_state = {
                "greeted": True,
                "slots": response.get('slots', {}),
                "objective": response.get('objective', ''),
                "last_action": response.get('next_action'),
                "attempts_count": 0
            }

        # Turno 3: Proporcionar email
        if "email" in response['assistant'].lower() or "client_email" not in response.get('slots', {}):
            print("\n" + "─" * 70)
            print("👤 Usuario: Mi email es pablo.martinez@gmail.com")
            print("─" * 70)

            response = await send_message(
                client, conversation_id,
                "Mi email es pablo.martinez@gmail.com",
                current_state=current_state
            )

            print(f"🤖 Asistente: {response['assistant']}")
            print(f"📊 Slots: {response.get('slots', {})}")
            print(f"🎯 Next Action: {response.get('next_action')}")

            # Actualizar estado
            current_state = {
                "greeted": True,
                "slots": response.get('slots', {}),
                "objective": response.get('objective', ''),
                "last_action": response.get('next_action'),
                "attempts_count": 0
            }

        # Turno 4: Confirmar/ejecutar
        print("\n" + "─" * 70)
        print("👤 Usuario: Sí, confirmá por favor")
        print("─" * 70)

        response = await send_message(
            client, conversation_id,
            "Sí, confirmá por favor",
            current_state=current_state
        )

        print(f"🤖 Asistente: {response['assistant']}")
        print(f"📊 Slots final: {response.get('slots', {})}")
        print(f"🎯 Next Action: {response.get('next_action')}")

        # Verificar si hubo tool_calls (acción ejecutada)
        if response.get('tool_calls'):
            print(f"\n✅ ACCIÓN EJECUTADA:")
            for tool_call in response['tool_calls']:
                print(f"   Tool: {tool_call.get('name')}")
                print(f"   Args: {tool_call.get('arguments')}")

        # Resumen final
        print("\n" + "=" * 70)
        print("📊 RESUMEN DE LA CONVERSACIÓN")
        print("=" * 70)

        if response.get('end'):
            print("✅ Conversación finalizada exitosamente")

            if response.get('tool_calls'):
                print("\n🎉 ¡TURNO AGENDADO CON ÉXITO!")
                print(f"   Servicio: Corte de Cabello")
                print(f"   Fecha: {tomorrow} 15:00")
                print(f"   Cliente: Pablo Martínez")
                print(f"   Email: pablo.martinez@gmail.com")
            else:
                print("\n⚠️  No se ejecutó acción (revisar slots o lógica)")
        else:
            print("⚠️  Conversación no finalizada (puede requerir más interacción)")

        print("=" * 70)

if __name__ == "__main__":
    try:
        asyncio.run(test_appointment_conversation())
    except httpx.RequestError as e:
        print(f"\n❌ ERROR DE CONEXIÓN: {e}")
        print("\n💡 SOLUCIÓN:")
        print("   Verifica que el orchestrator esté corriendo:")
        print("   ps aux | grep orchestrator_app")
    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
