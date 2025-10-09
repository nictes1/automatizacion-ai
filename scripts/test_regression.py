#!/usr/bin/env python3
"""
Test de regresión - Reproduce la conversación problemática de ayer

Problemas a validar:
1. ❌ Saluda múltiples veces
2. ❌ No llama tools cuando pregunta "que servicios tenes"
3. ❌ Pregunta "¿cómo estás?" después de que ya respondiste
4. ❌ Confunde vertical (gastronomía vs servicios)

Esperado después de fixes:
1. ✅ Saluda UNA vez
2. ✅ Llama get_available_services cuando pregunta por servicios
3. ✅ No repite preguntas
4. ✅ Usa vertical 'servicios' correctamente
"""

import asyncio
import httpx
import json
from uuid import uuid4

# Config
ORCHESTRATOR_URL = "http://localhost:8005"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440003"  # Servicios/Peluquería
VERTICAL = "servicios"

# Conversación de prueba (la que falló ayer)
TEST_MESSAGES = [
    "hola",
    "muy bien y vos",
    "que servicios tenes",  # ← Debe llamar get_available_services
]


class Colors:
    USER = '\033[94m'
    ASSISTANT = '\033[92m'
    SYSTEM = '\033[93m'
    ERROR = '\033[91m'
    SUCCESS = '\033[96m'
    END = '\033[0m'


def print_user(msg: str):
    print(f"\n{Colors.USER}👤 Usuario:{Colors.END} {msg}")


def print_assistant(msg: str):
    print(f"{Colors.ASSISTANT}🤖 Asistente:{Colors.END} {msg}")


def print_system(msg: str):
    print(f"{Colors.SYSTEM}💡 {msg}{Colors.END}")


def print_check(passed: bool, msg: str):
    if passed:
        print(f"{Colors.SUCCESS}✅ {msg}{Colors.END}")
    else:
        print(f"{Colors.ERROR}❌ {msg}{Colors.END}")


async def send_message(conversation_id: str, user_input: str, slots: dict) -> dict:
    """Envía un mensaje al orchestrator"""
    payload = {
        "conversation_id": conversation_id,
        "vertical": VERTICAL,
        "user_input": user_input,
        "greeted": slots.get("greeted", False),
        "slots": slots,
        "objective": "",
        "attempts_count": slots.get("_attempts_count", 0)
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Workspace-Id": WORKSPACE_ID
            }
        )
        response.raise_for_status()
        return response.json()


async def main():
    print("=" * 80)
    print(f"{Colors.SUCCESS}🧪 TEST DE REGRESIÓN - Validando Fixes de Orchestrator{Colors.END}")
    print("=" * 80)

    conversation_id = str(uuid4())
    print_system(f"Conversation ID: {conversation_id}")
    print_system(f"Workspace: {WORKSPACE_ID} (servicios)")
    print_system(f"Reproduciendo conversación problemática...\n")

    # Estado
    slots = {}
    responses = []
    greeting_count = 0
    tools_called = []

    # Ejecutar conversación
    for i, user_msg in enumerate(TEST_MESSAGES, 1):
        print_user(user_msg)

        try:
            response = await send_message(conversation_id, user_msg, slots)

            assistant_msg = response.get("assistant", "")
            print_assistant(assistant_msg)

            # Guardar respuesta
            responses.append({
                "turn": i,
                "user": user_msg,
                "assistant": assistant_msg,
                "next_action": response.get("next_action"),
                "tool_calls": response.get("tool_calls", []),
                "slots": response.get("slots", {})
            })

            # Actualizar slots
            slots = response.get("slots", {})

            # Tracking de saludos
            if any(word in assistant_msg.lower() for word in ["hola", "buen día", "cómo estás"]):
                greeting_count += 1

            # Tracking de tool calls
            for tool in response.get("tool_calls", []):
                tools_called.append(tool.get("name"))

            # Pequeña pausa entre mensajes (simular humano)
            await asyncio.sleep(0.5)

        except Exception as e:
            print_system(f"ERROR: {e}")
            break

    # Validaciones
    print("\n" + "=" * 80)
    print(f"{Colors.SUCCESS}📊 RESULTADOS DE VALIDACIÓN{Colors.END}")
    print("=" * 80 + "\n")

    # Check 1: Saluda solo una vez
    print_check(
        greeting_count <= 1,
        f"Saluda UNA sola vez (actual: {greeting_count} veces)"
    )

    # Check 2: Llama get_available_services cuando pregunta por servicios
    called_services_tool = "get_available_services" in tools_called
    print_check(
        called_services_tool,
        f"Llama get_available_services en 'que servicios tenes' (tools: {tools_called})"
    )

    # Check 3: No repite "¿cómo estás?" después de "muy bien"
    second_response = responses[1]["assistant"].lower() if len(responses) > 1 else ""
    asks_how_again = "cómo estás" in second_response or "cómo te va" in second_response
    print_check(
        not asks_how_again,
        f"No pregunta '¿cómo estás?' de nuevo después de responder (repetición: {asks_how_again})"
    )

    # Check 4: Usa vertical 'servicios' correctamente
    mentions_wrong_vertical = any(
        word in " ".join([r["assistant"].lower() for r in responses])
        for word in ["helado", "pizza", "restaurante", "menu", "pedido", "delivery"]
    )
    print_check(
        not mentions_wrong_vertical,
        f"No menciona conceptos de gastronomía (confusión de vertical: {mentions_wrong_vertical})"
    )

    # Check 5: Slots están correctos
    has_greeted = slots.get("greeted", False)
    print_check(
        has_greeted,
        f"Estado 'greeted' persistido correctamente (greeted={has_greeted})"
    )

    # Resumen final
    print("\n" + "=" * 80)
    total_checks = 5
    passed_checks = sum([
        greeting_count <= 1,
        called_services_tool,
        not asks_how_again,
        not mentions_wrong_vertical,
        has_greeted
    ])

    if passed_checks == total_checks:
        print(f"{Colors.SUCCESS}✨ TODOS LOS CHECKS PASARON ({passed_checks}/{total_checks}){Colors.END}")
        print(f"{Colors.SUCCESS}Los fixes están funcionando correctamente! 🎉{Colors.END}")
    else:
        print(f"{Colors.ERROR}⚠️  ALGUNOS CHECKS FALLARON ({passed_checks}/{total_checks}){Colors.END}")
        print(f"{Colors.ERROR}Revisa los logs arriba para detalles.{Colors.END}")

    print("=" * 80 + "\n")

    # Debug info
    print(f"{Colors.SYSTEM}📝 Transcripción completa:{Colors.END}\n")
    for r in responses:
        print(f"Turn {r['turn']}:")
        print(f"  Usuario: {r['user']}")
        print(f"  Asistente: {r['assistant']}")
        print(f"  Action: {r['next_action']}")
        if r['tool_calls']:
            print(f"  Tools: {[t.get('name') for t in r['tool_calls']]}")
        print()

    return passed_checks == total_checks


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n¡Test interrumpido!")
        exit(1)
    except Exception as e:
        print(f"\n{Colors.ERROR}Error fatal: {e}{Colors.END}")
        exit(1)
