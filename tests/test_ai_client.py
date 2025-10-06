"""
Test con Cliente AI - Simula un usuario real conversando con el orchestrator
"""

import asyncio
import httpx
from uuid import uuid4
from datetime import datetime, timedelta
import json

# Configuración
ORCHESTRATOR_URL = "http://localhost:8005"
OLLAMA_URL = "http://localhost:11434"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"

class AIClient:
    """Cliente AI que simula un usuario real"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.conversation_history = []

    async def generate_user_response(self, assistant_message: str, context: dict) -> str:
        """Genera respuesta del usuario usando LLM"""

        # Construir historial para contexto
        history_text = "\n".join([
            f"{'Usuario' if msg['role'] == 'user' else 'Asistente'}: {msg['content']}"
            for msg in self.conversation_history[-3:]  # Últimos 3 mensajes
        ])

        prompt = f"""Eres un cliente que quiere agendar un turno en una peluquería por WhatsApp.

Tu información personal:
- Nombre: {context['client_name']}
- Email: {context['client_email']}
- Quieres: {context['service']}
- Cuándo: {context['when_human']}

Historial de conversación:
{history_text}

El asistente acaba de decirte: "{assistant_message}"

Reglas para tu respuesta:
1. Responde de forma NATURAL y BREVE (como en WhatsApp)
2. Si te piden información que tienes arriba, dásela
3. Si te preguntan por confirmación y ya diste toda la info, confirma
4. Usa un tono casual argentino/rioplatense ("dale", "genial", "sí")
5. NO inventes información que no está arriba
6. Si el asistente te saluda por primera vez, NO DES TODA TU INFO de golpe, solo tu intención inicial

Devuelve SOLO tu respuesta de usuario (sin "Usuario:" ni prefijos):"""

        response = await self.client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "llama3.1:8b",
                "messages": [
                    {"role": "system", "content": "Eres un usuario natural de WhatsApp respondiendo a un asistente."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.7}
            }
        )

        result = response.json()
        user_message = result.get("message", {}).get("content", "").strip()

        # Limpiar respuesta si tiene prefijos
        if user_message.startswith("Usuario:"):
            user_message = user_message.replace("Usuario:", "").strip()

        return user_message

    async def send_to_orchestrator(self, conversation_id: str, user_input: str, current_state: dict = None):
        """Envía mensaje al orchestrator"""
        request_data = {
            "conversation_id": conversation_id,
            "user_input": user_input,
            "vertical": "servicios",
            "platform": "whatsapp",
            "current_state": current_state or {}
        }

        response = await self.client.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=request_data,
            headers={"X-Workspace-Id": WORKSPACE_ID}
        )

        return response.json()

    async def close(self):
        await self.client.aclose()


async def simulate_conversation():
    """Simula una conversación completa AI vs AI"""

    ai_client = AIClient()
    conversation_id = str(uuid4())
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    # Contexto del cliente AI
    client_context = {
        "client_name": "Ana García",
        "client_email": "ana.garcia@gmail.com",
        "service": "Corte y brushing",
        "when_human": "mañana a las 4 de la tarde",
        "when_date": tomorrow,
        "when_time": "16:00"
    }

    print("="*70)
    print("🤖 SIMULACIÓN: Cliente AI vs Orchestrator")
    print("="*70)
    print(f"📱 Conversation ID: {conversation_id}")
    print(f"👤 Cliente: {client_context['client_name']}")
    print(f"🎯 Objetivo: Agendar {client_context['service']} {client_context['when_human']}")
    print("="*70)

    # Estado inicial
    current_state = {}

    # Turno 1: Cliente inicia la conversación
    print("\n" + "─"*70)
    initial_message = f"Hola, necesito {client_context['service'].lower()} {client_context['when_human']}"
    print(f"👤 Usuario: {initial_message}")
    print("─"*70)

    ai_client.conversation_history.append({
        "role": "user",
        "content": initial_message
    })

    response = await ai_client.send_to_orchestrator(conversation_id, initial_message, current_state)

    assistant_message = response.get('assistant', '')
    print(f"🤖 Asistente: {assistant_message}")
    print(f"📊 Slots: {response.get('slots', {})}")
    print(f"🎯 Next Action: {response.get('next_action')}")

    ai_client.conversation_history.append({
        "role": "assistant",
        "content": assistant_message
    })

    current_state = {
        "greeted": True,
        "slots": response.get('slots', {}),
        "objective": response.get('objective', ''),
        "last_action": response.get('next_action'),
        "attempts_count": 0
    }

    # Continuar conversación hasta completar o máximo 10 turnos
    max_turns = 10
    for turn in range(2, max_turns + 1):
        # Si ya terminó, salir
        if response.get('end') or response.get('next_action') == 'EXECUTE_ACTION':
            print("\n" + "─"*70)
            print("✅ Conversación completada - listos para ejecutar acción")
            break

        if response.get('next_action') == 'ASK_HUMAN':
            print("\n" + "─"*70)
            print("⚠️ Sistema necesita intervención humana")
            break

        # Cliente AI genera respuesta
        user_message = await ai_client.generate_user_response(assistant_message, client_context)

        print("\n" + "─"*70)
        print(f"👤 Usuario: {user_message}")
        print("─"*70)

        ai_client.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Enviar al orchestrator
        response = await ai_client.send_to_orchestrator(conversation_id, user_message, current_state)

        assistant_message = response.get('assistant', '')
        print(f"🤖 Asistente: {assistant_message}")
        print(f"📊 Slots: {response.get('slots', {})}")
        print(f"🎯 Next Action: {response.get('next_action')}")

        ai_client.conversation_history.append({
            "role": "assistant",
            "content": assistant_message
        })

        # Actualizar estado
        current_state = {
            "greeted": True,
            "slots": response.get('slots', {}),
            "objective": response.get('objective', ''),
            "last_action": response.get('next_action'),
            "attempts_count": 0
        }

    # Resumen final
    print("\n" + "="*70)
    print("📊 RESUMEN FINAL")
    print("="*70)
    print(f"Turnos de conversación: {len(ai_client.conversation_history) // 2}")
    print(f"Slots recolectados: {json.dumps(current_state.get('slots', {}), ensure_ascii=False, indent=2)}")

    if response.get('next_action') == 'EXECUTE_ACTION':
        print("\n🎉 ¡ÉXITO! Todos los datos recolectados, listo para agendar turno")
    elif response.get('next_action') == 'ASK_HUMAN':
        print("\n⚠️ El sistema necesitó derivar a un humano")
    else:
        print(f"\n⚠️ Conversación no completada. Último estado: {response.get('next_action')}")

    print("="*70)

    await ai_client.close()


if __name__ == "__main__":
    try:
        asyncio.run(simulate_conversation())
    except KeyboardInterrupt:
        print("\n\n⚠️ Simulación interrumpida por el usuario")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
