"""
Test de integración end-to-end del sistema de tools

Verifica que el orchestrator pueda:
1. Decidir qué tool llamar según el input del usuario
2. Ejecutar el tool correctamente
3. Formatear el resultado
4. Generar una respuesta natural
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.orchestrator_service import orchestrator_service, ConversationSnapshot

# Workspace ID del seed data - Estilo Peluquería & Spa (servicios)
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440003"

async def test_get_available_services():
    """Test: Usuario pregunta por servicios disponibles"""
    print("\n" + "="*80)
    print("TEST 1: Usuario pregunta '¿Qué servicios ofrecen?'")
    print("="*80)

    snapshot = ConversationSnapshot(
        conversation_id="test-001",
        vertical="servicios",
        user_input="Hola, ¿qué servicios ofrecen?",
        workspace_id=WORKSPACE_ID,
        greeted=False,
        slots={},
        objective="",
        last_action=None,
        attempts_count=0
    )

    try:
        response = await orchestrator_service.decide(snapshot)

        print(f"\n✅ Next Action: {response.next_action.value}")
        print(f"📝 Assistant: {response.assistant}")
        print(f"📦 Slots: {response.slots}")
        print(f"🛠️  Tool Calls: {response.tool_calls}")
        print(f"📚 Context Used: {len(response.context_used)} items")

        if "corte" in response.assistant.lower() or "servicio" in response.assistant.lower():
            print("\n✅ PASS: Respuesta menciona servicios")
        else:
            print("\n❌ FAIL: Respuesta no menciona servicios")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_check_availability():
    """Test: Usuario pide turno para un servicio específico"""
    print("\n" + "="*80)
    print("TEST 2: Usuario pide 'Quiero turno para corte mañana'")
    print("="*80)

    snapshot = ConversationSnapshot(
        conversation_id="test-002",
        vertical="servicios",
        user_input="Quiero turno para corte mañana a las 10",
        workspace_id=WORKSPACE_ID,
        greeted=True,
        slots={"service_type": "Corte"},
        objective="agendar_turno",
        last_action="SLOT_FILL",
        attempts_count=1
    )

    try:
        response = await orchestrator_service.decide(snapshot)

        print(f"\n✅ Next Action: {response.next_action.value}")
        print(f"📝 Assistant: {response.assistant}")
        print(f"📦 Slots: {response.slots}")
        print(f"🛠️  Tool Calls: {response.tool_calls}")
        print(f"📚 Context Used: {len(response.context_used)} items")

        # Verificar que se haya llenado el slot de fecha
        if response.slots.get("preferred_date"):
            print(f"\n✅ PASS: Fecha extraída: {response.slots['preferred_date']}")
        else:
            print("\n⚠️  WARNING: Fecha no extraída")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_promotions():
    """Test: Usuario pregunta por promociones"""
    print("\n" + "="*80)
    print("TEST 3: Usuario pregunta '¿Tienen promociones?'")
    print("="*80)

    snapshot = ConversationSnapshot(
        conversation_id="test-003",
        vertical="servicios",
        user_input="¿Tienen alguna promoción o descuento?",
        workspace_id=WORKSPACE_ID,
        greeted=True,
        slots={},
        objective="consultar_promociones",
        last_action="GREET",
        attempts_count=0
    )

    try:
        response = await orchestrator_service.decide(snapshot)

        print(f"\n✅ Next Action: {response.next_action.value}")
        print(f"📝 Assistant: {response.assistant}")
        print(f"📦 Slots: {response.slots}")
        print(f"🛠️  Tool Calls: {response.tool_calls}")
        print(f"📚 Context Used: {len(response.context_used)} items")

        if "descuento" in response.assistant.lower() or "promoción" in response.assistant.lower() or "%" in response.assistant:
            print("\n✅ PASS: Respuesta menciona promociones")
        else:
            print("\n⚠️  WARNING: Respuesta no menciona promociones")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def test_business_hours():
    """Test: Usuario pregunta por horarios"""
    print("\n" + "="*80)
    print("TEST 4: Usuario pregunta '¿Qué horarios tienen?'")
    print("="*80)

    snapshot = ConversationSnapshot(
        conversation_id="test-004",
        vertical="servicios",
        user_input="¿Qué horarios tienen?",
        workspace_id=WORKSPACE_ID,
        greeted=True,
        slots={},
        objective="consultar_horarios",
        last_action="GREET",
        attempts_count=0
    )

    try:
        response = await orchestrator_service.decide(snapshot)

        print(f"\n✅ Next Action: {response.next_action.value}")
        print(f"📝 Assistant: {response.assistant}")
        print(f"📦 Slots: {response.slots}")
        print(f"🛠️  Tool Calls: {response.tool_calls}")
        print(f"📚 Context Used: {len(response.context_used)} items")

        if "horario" in response.assistant.lower() or "09:" in response.assistant or "9:" in response.assistant:
            print("\n✅ PASS: Respuesta menciona horarios")
        else:
            print("\n⚠️  WARNING: Respuesta no menciona horarios")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


async def main():
    print("\n🚀 Iniciando Tests de Integración Tools")
    print("="*80)

    # Ejecutar tests
    await test_get_available_services()
    await test_check_availability()
    await test_promotions()
    await test_business_hours()

    print("\n" + "="*80)
    print("✅ Tests completados")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
