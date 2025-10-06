"""
Test Suite con Cliente AI - Múltiples escenarios realistas
Simula conversaciones naturales con diferentes personalidades y contextos
"""

import asyncio
import httpx
from uuid import uuid4
from datetime import datetime, timedelta
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

# Configuración
ORCHESTRATOR_URL = "http://localhost:8005"
OLLAMA_URL = "http://localhost:11434"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"

# =========================
# Escenarios de Test
# =========================

class PersonalityType(Enum):
    """Tipo de personalidad del cliente simulado"""
    EFFICIENT = "efficient"  # Da toda la info de golpe
    CONVERSATIONAL = "conversational"  # Habla natural, progresivo
    FORGETFUL = "forgetful"  # A veces olvida dar info
    CHAOTIC = "chaotic"  # Desorganizado, info desordenada
    BRIEF = "brief"  # Respuestas muy cortas

@dataclass
class ClientProfile:
    """Perfil del cliente simulado"""
    name: str
    email: str
    phone: str
    personality: PersonalityType
    style_notes: str

@dataclass
class TestScenario:
    """Escenario de test"""
    id: str
    name: str
    description: str
    vertical: str
    client: ClientProfile
    objective: str  # Lo que quiere hacer
    context: Dict[str, Any]  # Datos del servicio/producto
    expected_slots: List[str]  # Slots que deben ser extraídos
    max_turns: int = 10

# =========================
# Definición de Escenarios
# =========================

SCENARIOS = [
    # Escenario 1: Cliente eficiente (da todo de golpe)
    TestScenario(
        id="servicios_efficient",
        name="Cliente Eficiente - Peluquería",
        description="Cliente que proporciona toda la información en el primer mensaje",
        vertical="servicios",
        client=ClientProfile(
            name="María González",
            email="maria.gonzalez@gmail.com",
            phone="+5491123456789",
            personality=PersonalityType.EFFICIENT,
            style_notes="Directa, concisa, toda la info de una"
        ),
        objective="Agendar corte de pelo",
        context={
            "service": "Corte de Cabello",
            "preferred_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "preferred_time": "15:00",
            "when_human": "mañana a las 3 de la tarde"
        },
        expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    ),

    # Escenario 2: Cliente conversacional (progresivo)
    TestScenario(
        id="servicios_conversational",
        name="Cliente Conversacional - Peluquería",
        description="Cliente que da información de forma natural y progresiva",
        vertical="servicios",
        client=ClientProfile(
            name="Juan Pérez",
            email="juan.perez@hotmail.com",
            phone="+5491198765432",
            personality=PersonalityType.CONVERSATIONAL,
            style_notes="Amigable, responde preguntas de a una, usa 'dale', 'perfecto'"
        ),
        objective="Agendar coloración",
        context={
            "service": "Coloración",
            "preferred_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "preferred_time": "10:00",
            "when_human": "pasado mañana a la mañana"
        },
        expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    ),

    # Escenario 3: Cliente olvidadizo
    TestScenario(
        id="servicios_forgetful",
        name="Cliente Olvidadizo - Peluquería",
        description="Cliente que a veces no responde exactamente lo que se pregunta",
        vertical="servicios",
        client=ClientProfile(
            name="Ana Rodríguez",
            email="ana.rodriguez@yahoo.com",
            phone="+5491187654321",
            personality=PersonalityType.FORGETFUL,
            style_notes="Responde con contexto extra, a veces se olvida de dar dato específico"
        ),
        objective="Agendar brushing",
        context={
            "service": "Brushing",
            "preferred_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
            "preferred_time": "16:30",
            "when_human": "el jueves a las 4:30 PM"
        },
        expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    ),

    # Escenario 4: Cliente caótico (texto pegado)
    TestScenario(
        id="servicios_chaotic",
        name="Cliente Caótico - Peluquería",
        description="Cliente que envía info desordenada, como texto pegado de nota",
        vertical="servicios",
        client=ClientProfile(
            name="Carlos Martínez",
            email="carlos.m@gmail.com",
            phone="+5491156781234",
            personality=PersonalityType.CHAOTIC,
            style_notes="Desorganizado, info desordenada, puede poner fecha antes que servicio"
        ),
        objective="Agendar corte y barba",
        context={
            "service": "Corte y Barba",
            "preferred_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "preferred_time": "11:00",
            "when_human": "mañana 11am"
        },
        expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    ),

    # Escenario 5: Cliente breve
    TestScenario(
        id="servicios_brief",
        name="Cliente Breve - Peluquería",
        description="Cliente que responde con mensajes muy cortos",
        vertical="servicios",
        client=ClientProfile(
            name="Laura Fernández",
            email="lauraf@outlook.com",
            phone="+5491145678901",
            personality=PersonalityType.BRIEF,
            style_notes="Respuestas de 1-3 palabras, 'sí', 'ok', 'dale'"
        ),
        objective="Agendar manicura",
        context={
            "service": "Manicura",
            "preferred_date": (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d"),
            "preferred_time": "14:00",
            "when_human": "viernes 2 de la tarde"
        },
        expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    ),

    # Escenario 6: Gastronomía - Reserva mesa
    TestScenario(
        id="gastronomia_efficient",
        name="Cliente Eficiente - Restaurante",
        description="Cliente que quiere reservar mesa con toda la info",
        vertical="gastronomia",
        client=ClientProfile(
            name="Roberto Sánchez",
            email="roberto.sanchez@gmail.com",
            phone="+5491134567890",
            personality=PersonalityType.EFFICIENT,
            style_notes="Directo, profesional, toda la info de golpe"
        ),
        objective="Reservar mesa",
        context={
            "service": "Reserva de Mesa",
            "party_size": 4,
            "preferred_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "preferred_time": "20:00",
            "when_human": "mañana a las 8 de la noche"
        },
        expected_slots=["party_size", "preferred_date", "preferred_time", "client_name", "client_phone"]
    ),

    # Escenario 7: Inmobiliaria - Visita propiedad
    TestScenario(
        id="inmobiliaria_conversational",
        name="Cliente Conversacional - Inmobiliaria",
        description="Cliente interesado en visitar propiedad",
        vertical="inmobiliaria",
        client=ClientProfile(
            name="Sofía Gutiérrez",
            email="sofia.gutierrez@yahoo.com",
            phone="+5491167890123",
            personality=PersonalityType.CONVERSATIONAL,
            style_notes="Amigable, hace preguntas, da info progresivamente"
        ),
        objective="Agendar visita a departamento",
        context={
            "service": "Visita a Propiedad",
            "property_type": "Departamento 2 ambientes",
            "location": "Palermo",
            "preferred_date": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d"),
            "preferred_time": "17:00",
            "when_human": "pasado mañana a las 5 PM"
        },
        expected_slots=["property_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    )
]

# =========================
# Cliente AI
# =========================

class AIClient:
    """Cliente AI que simula usuario con diferentes personalidades"""

    def __init__(self, scenario: TestScenario):
        self.scenario = scenario
        self.client = httpx.AsyncClient(timeout=30.0)
        self.conversation_history: List[Dict[str, str]] = []
        self.info_given: set = set()  # Track qué info ya dio

    def _build_personality_prompt(self) -> str:
        """Construye prompt según personalidad"""
        profile = self.scenario.client

        base = f"""Eres {profile.name}, un cliente simulado con personalidad {profile.personality.value}.

Tu información personal:
- Nombre: {profile.name}
- Email: {profile.email}
- Teléfono: {profile.phone}

Tu objetivo: {self.scenario.objective}
"""

        if self.scenario.vertical == "servicios":
            base += f"""
Detalles del servicio:
- Servicio: {self.scenario.context.get('service')}
- Cuándo: {self.scenario.context.get('when_human')}
- Fecha exacta: {self.scenario.context.get('preferred_date')}
- Hora exacta: {self.scenario.context.get('preferred_time')}
"""
        elif self.scenario.vertical == "gastronomia":
            base += f"""
Detalles de la reserva:
- Personas: {self.scenario.context.get('party_size')}
- Cuándo: {self.scenario.context.get('when_human')}
- Fecha exacta: {self.scenario.context.get('preferred_date')}
- Hora exacta: {self.scenario.context.get('preferred_time')}
"""
        elif self.scenario.vertical == "inmobiliaria":
            base += f"""
Detalles de la visita:
- Propiedad: {self.scenario.context.get('property_type')}
- Ubicación: {self.scenario.context.get('location')}
- Cuándo: {self.scenario.context.get('when_human')}
- Fecha exacta: {self.scenario.context.get('preferred_date')}
- Hora exacta: {self.scenario.context.get('preferred_time')}
"""

        # Personalizar según tipo
        if profile.personality == PersonalityType.EFFICIENT:
            base += """
COMPORTAMIENTO:
- En el PRIMER mensaje, da TODA tu información (nombre, servicio, fecha, hora, email)
- Ejemplo: "Hola, soy María González, necesito corte de pelo mañana a las 3pm, mi email es maria.gonzalez@gmail.com"
- Después solo confirma o aclara si te preguntan
"""
        elif profile.personality == PersonalityType.CONVERSATIONAL:
            base += """
COMPORTAMIENTO:
- Empieza con SOLO tu objetivo básico, sin toda la info
- Ejemplo inicial: "Hola, quiero sacar un turno para cortarme el pelo"
- Responde cada pregunta de forma natural, dando LA INFO QUE TE PIDEN
- Usa muletillas argentinas: "dale", "perfecto", "genial", "sí, claro"
- Cuando te preguntan tu email, SOLO da tu email
- Cuando te preguntan la fecha, SOLO da la fecha (usando when_human arriba)
"""
        elif profile.personality == PersonalityType.FORGETFUL:
            base += """
COMPORTAMIENTO:
- A veces respondes con contexto extra no pedido
- Puedes no dar exactamente lo que te piden en la primera respuesta
- Ejemplo: si te piden email, puedes responder "Ah sí, uso Gmail generalmente, es ana.rodriguez@yahoo.com"
- Pero SIEMPRE terminas dando la info, aunque de forma indirecta
"""
        elif profile.personality == PersonalityType.CHAOTIC:
            base += """
COMPORTAMIENTO:
- Tu primer mensaje es DESORGANIZADO, como texto pegado de una nota
- Ejemplo: "mañana 11am carlos.m@gmail.com Corte y Barba Carlos Martínez"
- Después respondes más normal, pero breve
"""
        elif profile.personality == PersonalityType.BRIEF:
            base += """
COMPORTAMIENTO:
- Respuestas MUY cortas: 1-3 palabras
- Ejemplos: "sí", "ok", "dale", "mañana 2pm", "Laura"
- Solo das exactamente lo que te piden, nada más
"""

        base += f"""
Notas de estilo: {profile.style_notes}

REGLAS IMPORTANTES:
1. NUNCA inventes información que no está arriba
2. Usa español rioplatense/argentino natural
3. NO uses emojis (esto es WhatsApp real)
4. NO pongas "Usuario:" ni prefijos en tu respuesta
5. Mantén coherencia: si ya diste un dato, no lo cambies
"""
        return base

    async def generate_initial_message(self) -> str:
        """Genera el mensaje inicial del usuario"""
        personality_prompt = self._build_personality_prompt()

        if self.scenario.client.personality == PersonalityType.EFFICIENT:
            # Mensaje con toda la info
            context = self.scenario.context
            return f"Hola, soy {self.scenario.client.name}, necesito {context.get('service', 'turno')} {context.get('when_human')}, mi email es {self.scenario.client.email}"

        elif self.scenario.client.personality == PersonalityType.CHAOTIC:
            # Mensaje desordenado
            context = self.scenario.context
            parts = [
                context.get('when_human'),
                self.scenario.client.email,
                context.get('service'),
                self.scenario.client.name
            ]
            import random
            random.shuffle(parts)
            return " ".join(parts)

        else:
            # Mensaje normal generado por LLM
            prompt = f"""{personality_prompt}

Genera SOLO tu primer mensaje de WhatsApp al asistente (sin prefijos).
Este es tu PRIMER mensaje, acabas de escribir al negocio."""

            response = await self.client.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": "llama3.1:8b",
                    "messages": [
                        {"role": "system", "content": "Eres un usuario natural de WhatsApp iniciando una conversación."},
                        {"role": "user", "content": prompt}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.7}
                }
            )

            result = response.json()
            user_message = result.get("message", {}).get("content", "").strip()
            return self._clean_message(user_message)

    async def generate_response(self, assistant_message: str) -> str:
        """Genera respuesta del usuario basada en mensaje del asistente"""
        personality_prompt = self._build_personality_prompt()

        # Construir historial
        history_text = "\n".join([
            f"{'Tú' if msg['role'] == 'user' else 'Asistente'}: {msg['content']}"
            for msg in self.conversation_history[-4:]
        ])

        prompt = f"""{personality_prompt}

Historial reciente:
{history_text}

El asistente acaba de decirte: "{assistant_message}"

Genera tu respuesta natural según tu personalidad.
IMPORTANTE:
- Si te preguntan algo específico (email, fecha, etc), RESPONDE ESO
- Si te piden confirmar, confirma si ya diste toda la info
- NO repitas info que ya diste antes

Devuelve SOLO tu respuesta (sin prefijos):"""

        response = await self.client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": "llama3.1:8b",
                "messages": [
                    {"role": "system", "content": "Eres un usuario natural de WhatsApp respondiendo al asistente."},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"temperature": 0.7}
            }
        )

        result = response.json()
        user_message = result.get("message", {}).get("content", "").strip()
        return self._clean_message(user_message)

    def _clean_message(self, message: str) -> str:
        """Limpia mensaje removiendo prefijos"""
        prefixes = ["Usuario:", "Tú:", "Cliente:", "Yo:"]
        for prefix in prefixes:
            if message.startswith(prefix):
                message = message.replace(prefix, "", 1).strip()
        return message

    async def send_to_orchestrator(self, conversation_id: str, user_input: str, current_state: dict = None) -> Dict[str, Any]:
        """Envía mensaje al orchestrator"""
        request_data = {
            "conversation_id": conversation_id,
            "user_input": user_input,
            "vertical": self.scenario.vertical,
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

# =========================
# Test Runner
# =========================

@dataclass
class TestResult:
    """Resultado de un test"""
    scenario_id: str
    scenario_name: str
    success: bool
    turns: int
    slots_collected: Dict[str, Any]
    slots_expected: List[str]
    slots_missing: List[str]
    final_action: str
    error: Optional[str] = None
    conversation_log: List[Dict[str, str]] = None
    duration_seconds: float = 0.0

class TestRunner:
    """Ejecuta suite de tests"""

    def __init__(self, scenarios: List[TestScenario]):
        self.scenarios = scenarios
        self.results: List[TestResult] = []

    async def run_scenario(self, scenario: TestScenario) -> TestResult:
        """Ejecuta un escenario de test"""
        print(f"\n{'='*70}")
        print(f"🧪 TEST: {scenario.name}")
        print(f"{'='*70}")
        print(f"📝 {scenario.description}")
        print(f"👤 Cliente: {scenario.client.name} ({scenario.client.personality.value})")
        print(f"🎯 Objetivo: {scenario.objective}")
        print(f"{'='*70}")

        start_time = asyncio.get_event_loop().time()

        ai_client = AIClient(scenario)
        conversation_id = str(uuid4())
        current_state = {}
        conversation_log = []

        try:
            # Turno 1: Mensaje inicial
            initial_message = await ai_client.generate_initial_message()
            print(f"\n👤 Usuario: {initial_message}")

            conversation_log.append({"role": "user", "content": initial_message})
            ai_client.conversation_history.append({"role": "user", "content": initial_message})

            response = await ai_client.send_to_orchestrator(conversation_id, initial_message, current_state)

            assistant_message = response.get('assistant', '')
            print(f"🤖 Asistente: {assistant_message}")
            print(f"📊 Slots: {response.get('slots', {})}")
            print(f"🎯 Next: {response.get('next_action')}")

            conversation_log.append({"role": "assistant", "content": assistant_message, "slots": response.get('slots', {})})
            ai_client.conversation_history.append({"role": "assistant", "content": assistant_message})

            current_state = {
                "greeted": True,
                "slots": response.get('slots', {}),
                "objective": response.get('objective', ''),
                "last_action": response.get('next_action'),
                "attempts_count": 0
            }

            # Continuar conversación
            for turn in range(2, scenario.max_turns + 1):
                # Verificar si terminó
                if response.get('next_action') in ['EXECUTE_ACTION', 'ASK_HUMAN']:
                    break

                # Generar respuesta
                user_message = await ai_client.generate_response(assistant_message)
                print(f"\n👤 Usuario: {user_message}")

                conversation_log.append({"role": "user", "content": user_message})
                ai_client.conversation_history.append({"role": "user", "content": user_message})

                response = await ai_client.send_to_orchestrator(conversation_id, user_message, current_state)

                assistant_message = response.get('assistant', '')
                print(f"🤖 Asistente: {assistant_message}")
                print(f"📊 Slots: {response.get('slots', {})}")
                print(f"🎯 Next: {response.get('next_action')}")

                conversation_log.append({"role": "assistant", "content": assistant_message, "slots": response.get('slots', {})})
                ai_client.conversation_history.append({"role": "assistant", "content": assistant_message})

                current_state = {
                    "greeted": True,
                    "slots": response.get('slots', {}),
                    "objective": response.get('objective', ''),
                    "last_action": response.get('next_action'),
                    "attempts_count": 0
                }

            # Evaluar resultado
            slots_collected = current_state.get('slots', {})
            slots_missing = [slot for slot in scenario.expected_slots if slot not in slots_collected or not slots_collected[slot]]

            success = (
                response.get('next_action') == 'EXECUTE_ACTION' and
                len(slots_missing) == 0
            )

            duration = asyncio.get_event_loop().time() - start_time

            result = TestResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                success=success,
                turns=len([msg for msg in conversation_log if msg['role'] == 'user']),
                slots_collected=slots_collected,
                slots_expected=scenario.expected_slots,
                slots_missing=slots_missing,
                final_action=response.get('next_action', ''),
                conversation_log=conversation_log,
                duration_seconds=duration
            )

            # Print resultado
            print(f"\n{'─'*70}")
            if success:
                print(f"✅ TEST EXITOSO")
            else:
                print(f"❌ TEST FALLIDO")
            print(f"📊 Turnos: {result.turns}")
            print(f"⏱️  Duración: {result.duration_seconds:.1f}s")
            print(f"📋 Slots recolectados: {len(slots_collected)}/{len(scenario.expected_slots)}")
            if slots_missing:
                print(f"⚠️  Slots faltantes: {', '.join(slots_missing)}")
            print(f"🎯 Acción final: {result.final_action}")
            print(f"{'─'*70}")

            await ai_client.close()
            return result

        except Exception as e:
            duration = asyncio.get_event_loop().time() - start_time
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()

            result = TestResult(
                scenario_id=scenario.id,
                scenario_name=scenario.name,
                success=False,
                turns=len([msg for msg in conversation_log if msg['role'] == 'user']),
                slots_collected=current_state.get('slots', {}),
                slots_expected=scenario.expected_slots,
                slots_missing=scenario.expected_slots,
                final_action="ERROR",
                error=str(e),
                conversation_log=conversation_log,
                duration_seconds=duration
            )

            await ai_client.close()
            return result

    async def run_all(self):
        """Ejecuta todos los escenarios"""
        print(f"\n{'='*70}")
        print(f"🚀 EJECUTANDO {len(self.scenarios)} ESCENARIOS DE TEST")
        print(f"{'='*70}")

        for scenario in self.scenarios:
            result = await self.run_scenario(scenario)
            self.results.append(result)

            # Pausa entre tests
            await asyncio.sleep(1)

        self.print_summary()

    def print_summary(self):
        """Imprime resumen de resultados"""
        print(f"\n{'='*70}")
        print(f"📊 RESUMEN DE RESULTADOS")
        print(f"{'='*70}")

        total = len(self.results)
        success = len([r for r in self.results if r.success])
        failed = total - success

        print(f"\n✅ Exitosos: {success}/{total} ({success/total*100:.1f}%)")
        print(f"❌ Fallidos: {failed}/{total} ({failed/total*100:.1f}%)")

        print(f"\n{'─'*70}")
        print(f"{'Escenario':<40} {'Resultado':<10} {'Turnos':<8} {'Tiempo'}")
        print(f"{'─'*70}")

        for result in self.results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{result.scenario_name:<40} {status:<10} {result.turns:<8} {result.duration_seconds:.1f}s")

        print(f"{'─'*70}")

        # Detalles de fallos
        failed_results = [r for r in self.results if not r.success]
        if failed_results:
            print(f"\n🔍 DETALLES DE FALLOS:")
            for result in failed_results:
                print(f"\n❌ {result.scenario_name}")
                if result.slots_missing:
                    print(f"   Slots faltantes: {', '.join(result.slots_missing)}")
                if result.error:
                    print(f"   Error: {result.error}")
                print(f"   Acción final: {result.final_action}")

        # Métricas generales
        avg_turns = sum(r.turns for r in self.results) / len(self.results)
        avg_duration = sum(r.duration_seconds for r in self.results) / len(self.results)

        print(f"\n📈 MÉTRICAS GENERALES:")
        print(f"   Promedio turnos: {avg_turns:.1f}")
        print(f"   Promedio duración: {avg_duration:.1f}s")
        print(f"   Total tiempo: {sum(r.duration_seconds for r in self.results):.1f}s")

        print(f"\n{'='*70}")

        # Guardar resultados a JSON
        self.save_results()

    def save_results(self):
        """Guarda resultados a archivo JSON"""
        output_file = "test_results.json"

        results_dict = [
            {
                "scenario_id": r.scenario_id,
                "scenario_name": r.scenario_name,
                "success": r.success,
                "turns": r.turns,
                "slots_collected": r.slots_collected,
                "slots_expected": r.slots_expected,
                "slots_missing": r.slots_missing,
                "final_action": r.final_action,
                "error": r.error,
                "duration_seconds": r.duration_seconds,
                "conversation_log": r.conversation_log
            }
            for r in self.results
        ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Resultados guardados en: {output_file}")

# =========================
# Main
# =========================

async def main():
    """Ejecuta test suite"""
    runner = TestRunner(SCENARIOS)
    await runner.run_all()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrumpidos por el usuario")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
