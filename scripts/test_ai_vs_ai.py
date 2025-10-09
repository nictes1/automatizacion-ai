#!/usr/bin/env python3
"""
Test AI vs AI: Cliente simulado conversando con el Bot de Peluquería

Este script simula un cliente REAL usando Ollama para generar mensajes naturales.
El cliente tiene una personalidad y objetivo específico (reservar turno de peluquería).
"""

import asyncio
import httpx
import json
from datetime import datetime, timedelta
from uuid import uuid4
from typing import Dict, Any, List

# Config
ORCHESTRATOR_URL = "http://localhost:8005"
OLLAMA_URL = "http://localhost:11434"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440003"  # Estilo Peluquería & Spa
VERTICAL = "servicios"

# Modelo para el cliente simulado (usa uno diferente al bot)
CLIENT_MODEL = "llama3.1:8b"
BOT_MODEL = "qwen2.5:14b"  # El que usa el orchestrator

class AIClientSimulator:
    """Simula un cliente real usando LLM"""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.conversation_history = []
        self.objective = "Quiero sacar un turno para cortarme el pelo mañana por la tarde"
        self.personality = """
Sos un cliente real de Argentina que quiere sacar turno en una peluquería.
Características:
- Hablás de manera casual y natural (argentino)
- Hacés preguntas normales que haría cualquier persona
- No sos demasiado formal ni demasiado informal
- A veces pedís aclaraciones si algo no está claro
- Podés divagar un poco o hacer algún comentario casual

TU OBJETIVO: {objective}

Instrucciones:
- NO escribas mensajes largos (máximo 1-2 oraciones)
- Respondé naturalmente como lo haría un cliente real
- Si el bot te saluda, saludalo de vuelta brevemente
- Si te pregunta algo, respondé lo que necesita
- Si te da información, podés agradecer o pedir más detalles
- NO hagas el proceso automáticamente, conversá naturalmente
""".format(objective=self.objective)

    async def generate_message(self, bot_response: str) -> str:
        """Genera el próximo mensaje del cliente basado en la respuesta del bot"""

        # Construir contexto conversacional
        context_messages = [
            {"role": "system", "content": self.personality},
        ]

        # Agregar historia reciente (últimos 6 mensajes)
        for msg in self.conversation_history[-6:]:
            context_messages.append(msg)

        # Agregar última respuesta del bot
        if bot_response:
            context_messages.append({"role": "assistant", "content": f"[BOT PELUQUERÍA]: {bot_response}"})

        context_messages.append({
            "role": "user",
            "content": "¿Qué le respondés al bot? (escribí SOLO tu mensaje, sin aclaraciones ni contexto adicional)"
        })

        # Llamar a Ollama
        response = await self.client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": CLIENT_MODEL,
                "messages": context_messages,
                "stream": False,
                "options": {
                    "temperature": 0.8,  # Más variabilidad para parecer humano
                    "top_p": 0.9,
                }
            }
        )
        response.raise_for_status()

        result = response.json()
        client_message = result["message"]["content"].strip()

        # Limpiar mensaje si tiene prefijos comunes
        client_message = client_message.replace("[CLIENTE]:", "").replace("Cliente:", "").strip()

        # Actualizar historial
        if bot_response:
            self.conversation_history.append({"role": "assistant", "content": f"[BOT]: {bot_response}"})
        self.conversation_history.append({"role": "user", "content": client_message})

        return client_message


class ConversationTester:
    """Maneja la conversación entre el cliente AI y el bot"""

    def __init__(self):
        self.conversation_id = str(uuid4())
        self.client = httpx.AsyncClient(timeout=60.0)
        self.ai_client = AIClientSimulator()
        self.state = {
            "greeted": False,
            "slots": {},
            "conversation_history": []
        }
        self.turn = 0

    async def send_to_bot(self, user_input: str) -> Dict[str, Any]:
        """Envía mensaje al bot (Orchestrator)"""
        payload = {
            "conversation_id": self.conversation_id,
            "vertical": VERTICAL,
            "user_input": user_input,
            "workspace_id": WORKSPACE_ID,
            "greeted": self.state["greeted"],
            "slots": self.state["slots"],
            "conversation_history": self.state["conversation_history"]
        }

        response = await self.client.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "X-Workspace-Id": WORKSPACE_ID
            }
        )
        response.raise_for_status()
        result = response.json()

        # Actualizar estado
        self.state["greeted"] = result.get("slots", {}).get("greeted", self.state["greeted"])
        self.state["slots"] = result.get("slots", {})

        # Agregar a historial
        self.state["conversation_history"].append({"role": "user", "content": user_input})
        if result.get("assistant"):
            self.state["conversation_history"].append({"role": "assistant", "content": result["assistant"]})

        return result

    def print_turn(self, client_msg: str, bot_response: Dict[str, Any]):
        """Imprime un turno de conversación con formato bonito"""
        self.turn += 1

        print(f"\n{'='*80}")
        print(f"TURN {self.turn}")
        print(f"{'='*80}")

        print(f"\n👤 Cliente: {client_msg}")
        print(f"\n🤖 Bot: {bot_response.get('assistant', '(sin respuesta)')}")

        # Debug info
        print(f"\n🔍 DEBUG:")
        print(f"   Next Action: {bot_response.get('next_action')}")
        print(f"   Greeted: {bot_response.get('slots', {}).get('greeted')}")

        if bot_response.get('tool_calls'):
            print(f"   🛠️  Tools llamados:")
            for tool in bot_response['tool_calls']:
                print(f"      - {tool['name']}")

        slots = bot_response.get('slots', {})
        important_slots = {k: v for k, v in slots.items() if not k.startswith('_')}
        if important_slots:
            print(f"   📝 Slots: {json.dumps(important_slots, ensure_ascii=False, indent=6)}")

    async def run_conversation(self, max_turns: int = 10):
        """Ejecuta una conversación completa AI vs AI"""

        print("="*80)
        print("🎭 TEST AI VS AI - CLIENTE SIMULADO")
        print("="*80)
        print(f"\n📋 Conversation ID: {self.conversation_id}")
        print(f"🏢 Workspace: Estilo Peluquería & Spa")
        print(f"🎯 Vertical: {VERTICAL}")
        print(f"👤 Cliente AI: {CLIENT_MODEL}")
        print(f"🤖 Bot AI: {BOT_MODEL}")
        print(f"\n🎯 Objetivo del cliente: {self.ai_client.objective}")

        # Crear conversación en la BD
        import subprocess
        subprocess.run([
            "docker", "exec", "pulpo-postgres",
            "psql", "-U", "pulpo", "-d", "pulpo", "-c",
            f"""
            INSERT INTO pulpo.conversations (id, workspace_id, channel_id, contact_id, status)
            VALUES (
                '{self.conversation_id}',
                '{WORKSPACE_ID}',
                'f1c6bb91-9e5a-4af7-8a21-8c9ce66ea487',
                '2a1bcd55-fe99-40ad-bcce-3c444d7783b6',
                'active'
            ) ON CONFLICT (id) DO NOTHING;
            """
        ], capture_output=True)

        print("\n⏳ Iniciando conversación...")

        # Cliente inicia la conversación
        bot_last_response = ""

        for turn in range(max_turns):
            try:
                # Cliente genera mensaje
                client_message = await self.ai_client.generate_message(bot_last_response)

                # Cliente envía al bot
                bot_response = await self.send_to_bot(client_message)
                bot_last_response = bot_response.get("assistant", "")

                # Mostrar turno
                self.print_turn(client_message, bot_response)

                # Verificar si terminó
                if bot_response.get("end"):
                    print(f"\n✅ Conversación finalizada en turn {self.turn}")
                    break

                # Verificar si ejecutó acción
                if bot_response.get("next_action") == "EXECUTE_ACTION":
                    print(f"\n✅ Acción ejecutada! Continuando conversación...")
                    # Seguir conversando después de la acción

                # Pequeña pausa para que sea más realista
                await asyncio.sleep(0.5)

            except Exception as e:
                print(f"\n❌ ERROR en turn {turn + 1}: {e}")
                import traceback
                traceback.print_exc()
                break

        # Resumen final
        print("\n" + "="*80)
        print("📊 RESUMEN DE LA CONVERSACIÓN")
        print("="*80)
        print(f"\n✅ Turnos completados: {self.turn}")
        print(f"\n📝 Estado final:")
        print(f"   Greeted: {self.state['greeted']}")
        print(f"   Slots: {json.dumps(self.state['slots'], ensure_ascii=False, indent=6)}")

        # Verificar si logró el objetivo
        slots = self.state['slots']
        if slots.get('service_type') and slots.get('preferred_date'):
            print(f"\n🎉 ¡OBJETIVO LOGRADO! Cliente agendó turno para {slots.get('service_type')}")
        else:
            print(f"\n⚠️  OBJETIVO NO LOGRADO - Faltaron datos para completar la reserva")

        await self.client.aclose()
        await self.ai_client.client.aclose()


async def main():
    tester = ConversationTester()
    await tester.run_conversation(max_turns=15)


if __name__ == "__main__":
    asyncio.run(main())
