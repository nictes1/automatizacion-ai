#!/usr/bin/env python3
"""
AI Client Tester - Cliente simulado con LLM para testing automático

El LLM actúa como un cliente real con un objetivo específico:
- "Quiero sacar un turno para cortarme el pelo mañana a las 10am"
- "Soy cliente de María y necesito un turno urgente"
- "Quiero saber precios antes de decidir"

El sistema interactúa con el agente hasta completar (o fallar) el objetivo.

Uso:
    python3 scripts/ai_client_tester.py --scenario "quiero_agendar_turno"
    python3 scripts/ai_client_tester.py --scenario "consulta_precios"
    python3 scripts/ai_client_tester.py --interactive
"""

import asyncio
import httpx
import json
import sys
from datetime import datetime
from uuid import uuid4
from typing import Dict, List, Tuple
import argparse

# Config
ORCHESTRATOR_URL = "http://localhost:8005"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"
VERTICAL = "servicios"
OLLAMA_URL = "http://localhost:11434"

# Escenarios predefinidos
SCENARIOS = {
    "quiero_agendar_turno": {
        "goal": "Quiero agendar un turno para cortarme el pelo mañana a las 10am con el profesional más económico",
        "persona": "Cliente nuevo, busca precio bajo, directo al punto",
        "max_turns": 10
    },
    "consulta_precios": {
        "goal": "Quiero saber los precios de todos los servicios y quiénes son los profesionales antes de decidir",
        "persona": "Cliente indeciso, hace muchas preguntas, compara opciones",
        "max_turns": 8
    },
    "cliente_maria": {
        "goal": "Soy cliente habitual de María García y necesito un turno para la semana que viene",
        "persona": "Cliente frecuente, conoce al staff, rápido",
        "max_turns": 6
    },
    "confundido": {
        "goal": "No sé bien qué quiero, pregunto cosas random y cambio de tema",
        "persona": "Cliente confuso, cambia de opinión, hace preguntas poco claras",
        "max_turns": 12
    },
    "impaciente": {
        "goal": "Necesito un turno YA para hoy, no importa el precio ni el profesional",
        "persona": "Cliente apurado, respuestas cortas, urgente",
        "max_turns": 5
    }
}


class AIClient:
    """Cliente simulado usando LLM local"""

    def __init__(self, scenario: Dict[str, any]):
        self.scenario = scenario
        self.goal = scenario["goal"]
        self.persona = scenario["persona"]
        self.conversation_history = []
        self.client = httpx.AsyncClient(timeout=60.0)

    async def generate_response(self, assistant_message: str) -> str:
        """
        Genera respuesta del cliente usando Ollama
        """
        # Construir prompt para el LLM
        system_prompt = f"""Eres un cliente de una peluquería que está chateando por WhatsApp.

TU OBJETIVO: {self.goal}

TU PERSONALIDAD: {self.persona}

INSTRUCCIONES:
- Actúa como un cliente REAL por WhatsApp (mensajes cortos, naturales, con typos ocasionales)
- NO uses formato de chat, SOLO escribe tu mensaje
- Responde SOLO lo que un cliente diría (sin aclaraciones ni contexto extra)
- Si lograste tu objetivo, di "OBJETIVO_CUMPLIDO: [explicación breve]"
- Si te frustras o no te ayudan, di "OBJETIVO_FALLIDO: [razón]"
- Usa lenguaje coloquial argentino (vos, che, etc.)

Ejemplos de mensajes de cliente:
- "hola, cuanto sale el corte?"
- "y quien me puede atender?"
- "perfecto, quiero turno mañana a las 10"
- "no entiendo, cual es mas barato?"
"""

        # Historial reciente (últimos 6 mensajes)
        recent_history = self.conversation_history[-6:] if self.conversation_history else []

        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Agregar historial
        for msg in recent_history:
            messages.append(msg)

        # Agregar último mensaje del asistente
        if assistant_message:
            messages.append({
                "role": "user",
                "content": f"El asistente de la peluquería te respondió: \"{assistant_message}\"\n\n¿Qué le respondes?"
            })
        else:
            # Primer mensaje
            messages.append({
                "role": "user",
                "content": "Inicia la conversación con el asistente de la peluquería. ¿Qué le escribes?"
            })

        # Llamar a Ollama (usar qwen2.5:14b o llama3.1:8b disponibles)
        response = await self.client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "llama3.1:8b",  # Modelo disponible localmente
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.8,
                    "top_p": 0.9
                }
            }
        )
        response.raise_for_status()
        result = response.json()

        client_message = result["message"]["content"].strip()

        # Guardar en historial
        self.conversation_history.append({
            "role": "assistant",
            "content": assistant_message if assistant_message else "[INICIO]"
        })
        self.conversation_history.append({
            "role": "user",
            "content": client_message
        })

        return client_message

    async def close(self):
        await self.client.aclose()


class ConversationTest:
    """Orquesta la conversación entre AI Client y el sistema"""

    def __init__(self, scenario_name: str):
        self.scenario_name = scenario_name
        self.scenario = SCENARIOS[scenario_name]
        self.ai_client = AIClient(self.scenario)
        self.conversation_id = str(uuid4())
        self.greeted = False
        self.slots = {}  # Mantener slots actualizados
        self.conversation_log = []
        self.orchestrator_history = []

    async def run(self) -> Dict[str, any]:
        """Ejecuta el test completo"""

        print("=" * 80)
        print(f"🤖 AI CLIENT TESTER - Escenario: {self.scenario_name}")
        print("=" * 80)
        print(f"\n📋 Objetivo: {self.scenario['goal']}")
        print(f"👤 Persona: {self.scenario['persona']}")
        print(f"🔄 Max turnos: {self.scenario['max_turns']}\n")
        print("=" * 80 + "\n")

        start_time = datetime.now()
        turn = 0
        assistant_message = None
        goal_achieved = False
        goal_failed = False
        failure_reason = None

        # Loop conversacional
        while turn < self.scenario['max_turns']:
            turn += 1

            # 1. Cliente genera mensaje
            print(f"\n{'='*80}")
            print(f"TURNO {turn}/{self.scenario['max_turns']}")
            print(f"{'='*80}\n")

            print("🤔 [AI Client] Pensando...")
            try:
                client_message = await self.ai_client.generate_response(assistant_message)
            except Exception as e:
                print(f"❌ Error generando mensaje del cliente: {e}")
                failure_reason = f"Error en AI Client: {str(e)}"
                break

            print(f"👤 [Cliente]: {client_message}\n")

            # Detectar si cumplió objetivo
            if "OBJETIVO_CUMPLIDO" in client_message:
                goal_achieved = True
                print("✅ ¡OBJETIVO CUMPLIDO!")
                break

            if "OBJETIVO_FALLIDO" in client_message:
                goal_failed = True
                failure_reason = client_message.split("OBJETIVO_FALLIDO:")[1].strip()
                print(f"❌ OBJETIVO FALLIDO: {failure_reason}")
                break

            # 2. Enviar a orchestrator
            print("⚙️  [Orchestrator] Procesando...")
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{ORCHESTRATOR_URL}/orchestrator/decide",
                        json={
                            "conversation_id": self.conversation_id,
                            "vertical": VERTICAL,
                            "user_input": client_message,
                            "greeted": self.greeted,
                            "slots": self.slots,  # Enviar todos los slots actualizados
                            "conversation_history": self.orchestrator_history
                        },
                        headers={
                            "Content-Type": "application/json",
                            "x-workspace-id": WORKSPACE_ID
                        }
                    )
                    response.raise_for_status()
                    result = response.json()

            except Exception as e:
                print(f"❌ Error en orchestrator: {e}")
                failure_reason = f"Error en orchestrator: {str(e)}"
                break

            assistant_message = result.get("assistant", "")

            # Actualizar estado con la respuesta del orchestrator
            self.slots = result.get("slots", self.slots)  # Guardar slots actualizados

            # IMPORTANTE: greeted se actualiza desde los slots, no desde el top-level
            # Porque el orchestrator lo devuelve dentro de slots
            self.greeted = self.slots.get("greeted", self.greeted)

            next_action = result.get("next_action", "")
            tool_calls = result.get("tool_calls", [])

            print(f"🤖 [Asistente]: {assistant_message}")
            print(f"   → Next Action: {next_action}")
            if tool_calls:
                print(f"   → Tools: {[t['name'] for t in tool_calls]}")
            print()

            # Guardar log
            self.conversation_log.append({
                "turn": turn,
                "client": client_message,
                "assistant": assistant_message,
                "next_action": next_action,
                "tool_calls": tool_calls,
                "timestamp": datetime.now().isoformat()
            })

            # Actualizar historial orchestrator
            self.orchestrator_history.append({"role": "user", "content": client_message})
            if assistant_message:
                self.orchestrator_history.append({"role": "assistant", "content": assistant_message})

            # Delay entre turnos
            await asyncio.sleep(0.5)

        # Resultados
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        result_summary = {
            "scenario": self.scenario_name,
            "goal": self.scenario['goal'],
            "turns": turn,
            "max_turns": self.scenario['max_turns'],
            "duration_seconds": duration,
            "goal_achieved": goal_achieved,
            "goal_failed": goal_failed,
            "failure_reason": failure_reason,
            "conversation_log": self.conversation_log,
            "timestamp": start_time.isoformat()
        }

        # Imprimir resumen
        print("\n" + "=" * 80)
        print("📊 RESUMEN DEL TEST")
        print("=" * 80)
        print(f"Escenario: {self.scenario_name}")
        print(f"Turnos: {turn}/{self.scenario['max_turns']}")
        print(f"Duración: {duration:.1f}s")
        print(f"Resultado: {'✅ Éxito' if goal_achieved else '❌ Fallo' if goal_failed else '⚠️  Timeout'}")
        if failure_reason:
            print(f"Razón: {failure_reason}")
        print("=" * 80 + "\n")

        return result_summary

    async def close(self):
        await self.ai_client.close()


async def run_scenario(scenario_name: str, save_log: bool = True):
    """Ejecuta un escenario de test"""

    if scenario_name not in SCENARIOS:
        print(f"❌ Escenario '{scenario_name}' no existe")
        print(f"Disponibles: {', '.join(SCENARIOS.keys())}")
        return

    test = ConversationTest(scenario_name)

    try:
        result = await test.run()

        # Guardar log
        if save_log:
            log_file = f"logs/ai_test_{scenario_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            import os
            os.makedirs("logs", exist_ok=True)
            with open(log_file, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"📁 Log guardado: {log_file}\n")

        return result

    finally:
        await test.close()


async def run_all_scenarios():
    """Ejecuta todos los escenarios"""
    results = []

    print("🚀 Ejecutando TODOS los escenarios...\n")

    for scenario_name in SCENARIOS.keys():
        print(f"\n{'='*80}")
        print(f"Iniciando: {scenario_name}")
        print(f"{'='*80}\n")

        result = await run_scenario(scenario_name)
        results.append(result)

        await asyncio.sleep(2)  # Pausa entre escenarios

    # Resumen final
    print("\n" + "=" * 80)
    print("📊 RESUMEN FINAL DE TODOS LOS TESTS")
    print("=" * 80)

    for r in results:
        status = "✅" if r["goal_achieved"] else "❌" if r["goal_failed"] else "⚠️"
        print(f"{status} {r['scenario']:30} | {r['turns']}/{r['max_turns']} turnos | {r['duration_seconds']:.1f}s")

    success_rate = sum(1 for r in results if r["goal_achieved"]) / len(results) * 100
    print(f"\nTasa de éxito: {success_rate:.1f}%")
    print("=" * 80 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="AI Client Tester")
    parser.add_argument("--scenario", type=str, help="Escenario a ejecutar")
    parser.add_argument("--all", action="store_true", help="Ejecutar todos los escenarios")
    parser.add_argument("--list", action="store_true", help="Listar escenarios disponibles")

    args = parser.parse_args()

    if args.list:
        print("Escenarios disponibles:\n")
        for name, scenario in SCENARIOS.items():
            print(f"  • {name}")
            print(f"    Goal: {scenario['goal']}")
            print(f"    Persona: {scenario['persona']}\n")
        return

    if args.all:
        await run_all_scenarios()
    elif args.scenario:
        await run_scenario(args.scenario)
    else:
        # Interactivo
        print("Escenarios disponibles:")
        for i, name in enumerate(SCENARIOS.keys(), 1):
            print(f"  {i}. {name}")

        choice = input("\nSelecciona un escenario (número o nombre): ").strip()

        if choice.isdigit():
            scenario_name = list(SCENARIOS.keys())[int(choice) - 1]
        else:
            scenario_name = choice

        await run_scenario(scenario_name)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Test interrumpido")
        sys.exit(0)
