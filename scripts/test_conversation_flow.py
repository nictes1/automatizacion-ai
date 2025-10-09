#!/usr/bin/env python3
"""
Script interactivo para probar el flujo conversacional del agente de peluquería

Uso:
    python3 scripts/test_conversation_flow.py

    - Escribe mensajes como si fueras un cliente
    - El sistema responderá usando el orchestrator
    - Escribe 'salir' o 'exit' para terminar
    - Escribe 'reset' para empezar una nueva conversación
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime
from uuid import uuid4

# Config
ORCHESTRATOR_URL = "http://localhost:8005"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440003"  # Estilo Peluquería & Spa
VERTICAL = "servicios"

# Estado de la conversación
conversation_id = str(uuid4())
conversation_history = []
greeted = False


def print_assistant(text: str):
    """Imprime mensaje del asistente"""
    print(f"\n🤖 Asistente: {text}\n")


def print_user(text: str):
    """Imprime mensaje del usuario"""
    print(f"\n👤 Tú: {text}")


def print_system(text: str):
    """Imprime mensaje del sistema"""
    print(f"\n💡 Sistema: {text}")


def print_debug(data: dict):
    """Imprime información de debug"""
    print(f"\n🔍 Debug:")
    print(f"   - Next Action: {data.get('next_action')}")
    print(f"   - Slots: {data.get('slots', {})}")
    if data.get('tool_calls'):
        print(f"   - Tools llamados: {[t['name'] for t in data['tool_calls']]}")
    print()


async def send_message(user_input: str) -> dict:
    """Envía un mensaje al orchestrator"""
    global greeted, conversation_history

    payload = {
        "conversation_id": conversation_id,
        "vertical": VERTICAL,
        "user_input": user_input,
        "greeted": greeted,
        "slots": {
            "greeted": greeted
        },
        "conversation_history": conversation_history
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
    """Main loop"""
    global greeted, conversation_id, conversation_history

    print("=" * 70)
    print("🎨 SISTEMA DE TESTING CONVERSACIONAL - PELUQUERÍA")
    print("=" * 70)
    print("\nInstrucciones:")
    print("  - Chatea naturalmente como si fueras un cliente")
    print("  - Escribe 'salir' o 'exit' para terminar")
    print("  - Escribe 'reset' para nueva conversación")
    print("  - Escribe 'debug' para ver estado interno")
    print("\n" + "=" * 70 + "\n")

    print_system(f"Conversation ID: {conversation_id}")
    print_system("Esperando tu primer mensaje...\n")

    while True:
        try:
            # Input del usuario
            user_input = input("👤 Tú: ").strip()

            if not user_input:
                continue

            # Comandos especiales
            if user_input.lower() in ["salir", "exit", "quit"]:
                print_system("¡Hasta luego!")
                break

            if user_input.lower() == "reset":
                conversation_id = str(uuid4())
                conversation_history = []
                greeted = False
                print_system(f"Nueva conversación iniciada: {conversation_id}")
                continue

            if user_input.lower() == "debug":
                print_debug({
                    "conversation_id": conversation_id,
                    "greeted": greeted,
                    "history_length": len(conversation_history)
                })
                continue

            # Enviar mensaje al orchestrator
            print_system("Procesando...")

            try:
                response = await send_message(user_input)

                # Mostrar respuesta del asistente
                assistant_msg = response.get("assistant", "")
                if assistant_msg:
                    print_assistant(assistant_msg)

                # Actualizar estado
                greeted = response.get("greeted", greeted)

                # Agregar a historial
                conversation_history.append({
                    "role": "user",
                    "content": user_input
                })
                if assistant_msg:
                    conversation_history.append({
                        "role": "assistant",
                        "content": assistant_msg
                    })

                # Debug info (opcional, comenta si molesta)
                # print_debug(response)

            except httpx.HTTPStatusError as e:
                print(f"\n❌ Error HTTP: {e.response.status_code}")
                print(f"   {e.response.text}\n")
            except httpx.RequestError as e:
                print(f"\n❌ Error de conexión: {e}")
                print("   ¿Está corriendo el orchestrator en http://localhost:8005?\n")
            except Exception as e:
                print(f"\n❌ Error inesperado: {e}\n")

        except KeyboardInterrupt:
            print("\n")
            print_system("Interrumpido por el usuario. ¡Hasta luego!")
            break
        except EOFError:
            print("\n")
            print_system("¡Hasta luego!")
            break


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n¡Hasta luego!")
        sys.exit(0)
