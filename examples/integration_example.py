"""
Ejemplo completo de integración SLM Pipeline
Muestra cómo inicializar y usar el orchestrator integrado
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict

# ========================================
# 1. Setup básico
# ========================================

# Configurar env vars
os.environ["ENABLE_SLM_PIPELINE"] = "true"
os.environ["SLM_CANARY_PERCENT"] = "10"  # 10% canary
os.environ["SLM_EXTRACTOR_MODEL"] = "qwen2.5:7b"
os.environ["SLM_PLANNER_MODEL"] = "qwen2.5:7b"

# ========================================
# 2. Mock LLM Client (reemplazar con real)
# ========================================

class MockLLMClient:
    """Mock para testing - reemplazar con cliente real"""
    
    async def generate_json(self, system: str, user: str, schema: dict) -> dict:
        """Simula respuesta de LLM"""
        import json
        
        # Parse user prompt
        try:
            user_data = json.loads(user)
        except:
            user_data = {}
        
        # Extractor mock
        if "user_input" in user_data:
            text = user_data["user_input"].lower()
            
            if "hola" in text:
                return {"intent": "greeting", "slots": {}, "confidence": 0.9}
            elif "horario" in text:
                return {"intent": "info_hours", "slots": {}, "confidence": 0.9}
            elif "precio" in text or "cuanto" in text:
                return {"intent": "info_price", "slots": {"service_type": "Corte de Cabello"}, "confidence": 0.9}
            elif "reservar" in text or "turno" in text:
                return {
                    "intent": "book",
                    "slots": {
                        "service_type": "Corte de Cabello",
                        "preferred_date": "2025-10-16",
                        "preferred_time": "15:00"
                    },
                    "confidence": 0.85
                }
            else:
                return {"intent": "chitchat", "slots": {}, "confidence": 0.6}
        
        # Planner mock
        elif "input" in user_data:
            intent = user_data["input"]["intent"]
            slots = user_data["input"]["slots"]
            ws_id = user_data["context"]["workspace_id"]
            
            if intent == "info_hours":
                return {
                    "plan_version": "v1",
                    "actions": [{"tool": "get_business_hours", "args": {"workspace_id": ws_id}}],
                    "needs_confirmation": False
                }
            elif intent == "info_price":
                return {
                    "plan_version": "v1",
                    "actions": [{"tool": "get_available_services", "args": {"workspace_id": ws_id}}],
                    "needs_confirmation": False
                }
            elif intent == "book":
                actions = []
                if slots.get("service_type") and slots.get("preferred_date"):
                    actions.append({
                        "tool": "check_service_availability",
                        "args": {
                            "workspace_id": ws_id,
                            "service_type": slots["service_type"],
                            "date": slots["preferred_date"]
                        }
                    })
                    if slots.get("preferred_time"):
                        actions.append({
                            "tool": "book_appointment",
                            "args": {
                                "workspace_id": ws_id,
                                "service_type": slots["service_type"],
                                "preferred_date": slots["preferred_date"],
                                "preferred_time": slots["preferred_time"]
                            }
                        })
                return {
                    "plan_version": "v1",
                    "actions": actions,
                    "needs_confirmation": not (slots.get("client_name") and slots.get("client_email"))
                }
            else:
                return {"plan_version": "v1", "actions": [], "needs_confirmation": True}
        
        return {}

# ========================================
# 3. Inicializar Orchestrator
# ========================================

from services.orchestrator_integration import OrchestratorServiceIntegrated

async def init_orchestrator():
    """Inicializa orchestrator con dependencias"""
    
    llm_client = MockLLMClient()  # Reemplazar con cliente real
    
    orchestrator = OrchestratorServiceIntegrated(
        llm_json_client=llm_client,
        enable_agent_loop=True
    )
    
    print(f"✅ Orchestrator initialized:")
    print(f"   - SLM Pipeline: {orchestrator.enable_slm_pipeline}")
    print(f"   - Canary: {orchestrator.slm_canary_percent}%")
    print()
    
    return orchestrator

# ========================================
# 4. Crear Snapshot de ejemplo
# ========================================

@dataclass
class UserMessage:
    text: str
    message_id: str

@dataclass
class ConversationSnapshot:
    workspace_id: str
    conversation_id: str
    user_message: UserMessage
    business_name: str
    tool_manifest: Any
    mcp_client: Any
    custom_runners: Dict[str, Any]
    vertical: str = "servicios"
    services_hint: str = None
    hours_hint: str = None
    slots: Dict[str, Any] = None
    greeted: bool = False
    objective: str = ""
    
    def __post_init__(self):
        if self.slots is None:
            self.slots = {}

def create_snapshot(user_input: str) -> ConversationSnapshot:
    """Crea snapshot de prueba"""
    
    # Mock manifest
    from services.tool_manifest import ToolManifest, ToolDefinition
    
    manifest = ToolManifest(
        workspace_id="ws-test-123",
        vertical="servicios",
        tools=[
            ToolDefinition(
                name="get_business_hours",
                description="Obtiene horarios de atención",
                args_schema={"properties": {"workspace_id": {"type": "string"}}},
                requires_slots=[],
                scopes=["read"],
                tier_required="basic",
                rate_limit_per_min=10,
                cost_tokens=100,
                timeout_ms=1000
            ),
            ToolDefinition(
                name="get_available_services",
                description="Lista servicios disponibles",
                args_schema={"properties": {"workspace_id": {"type": "string"}}},
                requires_slots=[],
                scopes=["read"],
                tier_required="basic",
                rate_limit_per_min=10,
                cost_tokens=100,
                timeout_ms=1000
            ),
            ToolDefinition(
                name="check_service_availability",
                description="Verifica disponibilidad",
                args_schema={"properties": {"workspace_id": {"type": "string"}}},
                requires_slots=["service_type", "preferred_date"],
                scopes=["read"],
                tier_required="basic",
                rate_limit_per_min=10,
                cost_tokens=100,
                timeout_ms=2000
            ),
            ToolDefinition(
                name="book_appointment",
                description="Reserva turno",
                args_schema={"properties": {"workspace_id": {"type": "string"}}},
                requires_slots=["service_type", "preferred_date", "preferred_time"],
                scopes=["write"],
                tier_required="premium",
                rate_limit_per_min=5,
                cost_tokens=200,
                timeout_ms=3000
            )
        ]
    )
    
    return ConversationSnapshot(
        workspace_id="ws-test-123",
        conversation_id="conv-test-456",
        user_message=UserMessage(
            text=user_input,
            message_id=f"msg-{hash(user_input)}"
        ),
        business_name="Peluquería Test",
        tool_manifest=manifest,
        mcp_client=None,
        custom_runners={},
        services_hint="Corte, Color, Barba",
        hours_hint="Lunes a Viernes 9-18"
    )

# ========================================
# 5. Ejemplos de uso
# ========================================

async def example_greeting():
    """Ejemplo 1: Saludo"""
    print("=" * 60)
    print("EJEMPLO 1: Saludo")
    print("=" * 60)
    
    orchestrator = await init_orchestrator()
    snapshot = create_snapshot("Hola!")
    
    response = await orchestrator.decide(snapshot)
    
    print(f"Usuario: {snapshot.user_message.text}")
    print(f"Asistente: {response.assistant}")
    print(f"Debug: {response.debug}")
    print()

async def example_info_hours():
    """Ejemplo 2: Consulta horarios"""
    print("=" * 60)
    print("EJEMPLO 2: Consulta Horarios")
    print("=" * 60)
    
    orchestrator = await init_orchestrator()
    snapshot = create_snapshot("Cuál es el horario de atención?")
    
    response = await orchestrator.decide(snapshot)
    
    print(f"Usuario: {snapshot.user_message.text}")
    print(f"Asistente: {response.assistant}")
    print(f"Tools ejecutados: {len(response.tool_calls)}")
    print(f"Debug: {response.debug}")
    print()

async def example_info_price():
    """Ejemplo 3: Consulta precios"""
    print("=" * 60)
    print("EJEMPLO 3: Consulta Precios")
    print("=" * 60)
    
    orchestrator = await init_orchestrator()
    snapshot = create_snapshot("Cuánto sale un corte de pelo?")
    
    response = await orchestrator.decide(snapshot)
    
    print(f"Usuario: {snapshot.user_message.text}")
    print(f"Asistente: {response.assistant}")
    print(f"Tools ejecutados: {len(response.tool_calls)}")
    print(f"Debug: {response.debug}")
    print()

async def example_book_incomplete():
    """Ejemplo 4: Reserva incompleta"""
    print("=" * 60)
    print("EJEMPLO 4: Reserva Incompleta")
    print("=" * 60)
    
    orchestrator = await init_orchestrator()
    snapshot = create_snapshot("Quiero reservar un turno mañana")
    
    response = await orchestrator.decide(snapshot)
    
    print(f"Usuario: {snapshot.user_message.text}")
    print(f"Asistente: {response.assistant}")
    print(f"Slots faltantes: {response.debug.get('needs', [])}")
    print(f"Debug: {response.debug}")
    print()

async def example_book_complete():
    """Ejemplo 5: Reserva completa"""
    print("=" * 60)
    print("EJEMPLO 5: Reserva Completa")
    print("=" * 60)
    
    orchestrator = await init_orchestrator()
    snapshot = create_snapshot(
        "Quiero reservar corte mañana a las 15hs. Soy Juan Perez, mi email es juan@test.com"
    )
    
    response = await orchestrator.decide(snapshot)
    
    print(f"Usuario: {snapshot.user_message.text}")
    print(f"Asistente: {response.assistant}")
    print(f"Tools ejecutados: {len(response.tool_calls)}")
    print(f"Debug: {response.debug}")
    print()

async def example_metrics():
    """Ejemplo 6: Métricas del orchestrator"""
    print("=" * 60)
    print("EJEMPLO 6: Métricas")
    print("=" * 60)
    
    orchestrator = await init_orchestrator()
    
    # Simular varios requests
    for text in ["Hola", "Horarios?", "Precio corte", "Reservar mañana"]:
        snapshot = create_snapshot(text)
        await orchestrator.decide(snapshot)
    
    # Obtener métricas
    metrics = orchestrator.get_metrics()
    
    print("Métricas del Orchestrator:")
    print(f"  - Total requests: {metrics['total_requests']}")
    print(f"  - SLM requests: {metrics['slm_requests']} ({metrics['slm_percentage']:.1f}%)")
    print(f"  - Legacy requests: {metrics['legacy_requests']}")
    print(f"  - SLM error rate: {metrics['slm_error_rate']:.2f}%")
    print(f"  - Legacy error rate: {metrics['legacy_error_rate']:.2f}%")
    print()

# ========================================
# 6. Main
# ========================================

async def main():
    """Ejecuta todos los ejemplos"""
    
    print("\n")
    print("🚀 PulpoAI - Ejemplos de Integración SLM Pipeline")
    print("=" * 60)
    print()
    
    await example_greeting()
    await example_info_hours()
    await example_info_price()
    await example_book_incomplete()
    await example_book_complete()
    await example_metrics()
    
    print("=" * 60)
    print("✅ Todos los ejemplos ejecutados correctamente")
    print()

if __name__ == "__main__":
    asyncio.run(main())




