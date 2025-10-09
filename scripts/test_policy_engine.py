#!/usr/bin/env python3
"""
Test de Policy Engine V2 - Validación de Tool Manifest y Políticas

Tests:
1. Carga de manifest desde YAML
2. Validación de tier
3. Validación de requires_slots
4. Validación de args contra JSON Schema
5. Validación de rate limits
6. Validación de tools_first
"""

import sys
sys.path.insert(0, '/app')  # Para Docker
sys.path.insert(0, '.')     # Para local

from services.tool_manifest import get_manifest, TierLevel
from services.policy_engine import PolicyEngine, PlanAction, WorkspacePolicy

def print_test(name: str, passed: bool, reason: str = ""):
    symbol = "✅" if passed else "❌"
    print(f"{symbol} {name}")
    if reason:
        print(f"   → {reason}")

def test_manifest_loading():
    """Test 1: Carga de manifest"""
    print("\n" + "="*60)
    print("TEST 1: Carga de Manifest")
    print("="*60)

    manifest = get_manifest("test-workspace", "servicios")

    print_test(
        "Manifest cargado",
        manifest is not None,
        f"Vertical: {manifest.vertical}, Tools: {len(manifest.tools)}"
    )

    # Verificar tools específicos
    tools = {tool.name for tool in manifest.tools}
    expected = {"get_services", "get_staff", "get_availability", "book_appointment"}

    print_test(
        "Tools esperados presentes",
        expected.issubset(tools),
        f"Encontrados: {tools}"
    )

    # Verificar estructura de un tool
    get_services = manifest.get_tool("get_services")
    print_test(
        "get_services tiene schema válido",
        get_services and "type" in get_services.args_schema,
        f"Schema: {get_services.args_schema if get_services else 'N/A'}"
    )

    return manifest

def test_tier_validation(engine: PolicyEngine, manifest):
    """Test 2: Validación de tier"""
    print("\n" + "="*60)
    print("TEST 2: Validación de Tier")
    print("="*60)

    # Test 2.1: Tool basic con workspace basic → OK
    action = PlanAction(tool="get_services", args={})
    workspace_basic = {
        "id": "test-1",
        "tier": "basic",
        "status": "active",
        "policy": {}
    }

    result = engine.validate(action, {"slots": {}}, workspace_basic, manifest)
    print_test(
        "Basic tool con tier BASIC",
        result.is_allowed,
        f"Decision: {result.decision}, Reason: {result.reason}"
    )

    # Test 2.2: Tool pro con workspace basic → DENY
    action_pro = PlanAction(tool="cancel_appointment", args={"appointment_id": "123"})
    result_denied = engine.validate(action_pro, {"slots": {}}, workspace_basic, manifest)
    print_test(
        "PRO tool con tier BASIC (debe denegar)",
        not result_denied.is_allowed,
        f"Decision: {result_denied.decision}, Reason: {result_denied.reason}"
    )

    # Test 2.3: Tool pro con workspace pro → OK
    workspace_pro = {**workspace_basic, "tier": "pro"}
    result_allowed = engine.validate(action_pro, {"slots": {}}, workspace_pro, manifest)
    print_test(
        "PRO tool con tier PRO",
        result_allowed.is_allowed,
        f"Decision: {result_allowed.decision}"
    )

def test_requires_slots_validation(engine: PolicyEngine, manifest):
    """Test 3: Validación de requires_slots"""
    print("\n" + "="*60)
    print("TEST 3: Validación de Requires Slots")
    print("="*60)

    workspace = {
        "id": "test-1",
        "tier": "basic",
        "status": "active",
        "policy": {}
    }

    # Test 3.1: book_appointment sin slots → DENY
    action = PlanAction(
        tool="book_appointment",
        args={
            "service_type": "Corte",
            "preferred_date": "2025-10-10",
            "preferred_time": "14:00",
            "client_name": "Juan"
        }
    )

    result_missing = engine.validate(action, {"slots": {}}, workspace, manifest)
    print_test(
        "book_appointment sin slots (debe denegar)",
        not result_missing.is_allowed,
        f"Missing slots: {result_missing.missing_slots}"
    )

    # Test 3.2: book_appointment con slots → OK
    state_complete = {
        "slots": {
            "service_type": "Corte de Cabello",
            "preferred_date": "2025-10-10",
            "preferred_time": "14:00",
            "client_name": "Juan Pérez"
        }
    }

    result_ok = engine.validate(action, state_complete, workspace, manifest)
    print_test(
        "book_appointment con slots completos",
        result_ok.is_allowed,
        f"Decision: {result_ok.decision}"
    )

def test_args_schema_validation(engine: PolicyEngine, manifest):
    """Test 4: Validación de args contra JSON Schema"""
    print("\n" + "="*60)
    print("TEST 4: Validación de Args Schema")
    print("="*60)

    workspace = {
        "id": "test-1",
        "tier": "basic",
        "status": "active",
        "policy": {}
    }

    state = {
        "slots": {
            "service_type": "Corte",
            "preferred_date": "2025-10-10",
            "preferred_time": "14:00",
            "client_name": "Juan"
        }
    }

    # Test 4.1: Args válidos → OK
    action_valid = PlanAction(
        tool="book_appointment",
        args={
            "service_type": "Corte de Cabello",
            "preferred_date": "2025-10-10",
            "preferred_time": "14:00",
            "client_name": "Juan Pérez",
            "client_email": "juan@example.com"
        }
    )

    result_valid = engine.validate(action_valid, state, workspace, manifest)
    print_test(
        "Args válidos",
        result_valid.is_allowed,
        f"Decision: {result_valid.decision}"
    )

    # Test 4.2: Args inválidos (email mal formado) → DENY
    action_invalid = PlanAction(
        tool="book_appointment",
        args={
            "service_type": "Corte",
            "preferred_date": "2025-10-10",
            "preferred_time": "14:00",
            "client_name": "Juan",
            "client_email": "not-an-email"  # ❌ Inválido
        }
    )

    result_invalid = engine.validate(action_invalid, state, workspace, manifest)
    print_test(
        "Args inválidos (debe denegar)",
        not result_invalid.is_allowed,
        f"Errors: {result_invalid.validation_errors}"
    )

def test_rate_limits(engine: PolicyEngine, manifest):
    """Test 5: Validación de rate limits"""
    print("\n" + "="*60)
    print("TEST 5: Validación de Rate Limits")
    print("="*60)

    workspace = {
        "id": "test-rate-limit",
        "tier": "basic",
        "status": "active",
        "policy": {}
    }

    action = PlanAction(tool="get_services", args={})
    state = {"slots": {}}

    # Simular 5 llamadas (dentro del límite de 60/min)
    for i in range(5):
        result = engine.validate(action, state, workspace, manifest)
        print_test(
            f"Llamada {i+1}/5",
            result.is_allowed,
            f"Decision: {result.decision}"
        )

def test_tools_first(engine: PolicyEngine, manifest):
    """Test 6: Validación de tools_first"""
    print("\n" + "="*60)
    print("TEST 6: Validación de Tools First")
    print("="*60)

    workspace = {
        "id": "test-1",
        "tier": "basic",
        "status": "active",
        "policy": {
            "tools_first": ["get_services", "get_availability"]
        }
    }

    # Test 6.1: Intentar book_appointment sin haber llamado get_services → DENY
    action_book = PlanAction(
        tool="book_appointment",
        args={
            "service_type": "Corte",
            "preferred_date": "2025-10-10",
            "preferred_time": "14:00",
            "client_name": "Juan"
        }
    )

    state_no_tools = {
        "slots": {
            "service_type": "Corte",
            "preferred_date": "2025-10-10",
            "preferred_time": "14:00",
            "client_name": "Juan"
        },
        "called_tools": []
    }

    result_denied = engine.validate(action_book, state_no_tools, workspace, manifest)
    print_test(
        "book_appointment sin tools_first (debe denegar)",
        not result_denied.is_allowed,
        f"Reason: {result_denied.reason}"
    )

    # Test 6.2: Con get_services ya llamado → OK
    state_with_tools = {
        **state_no_tools,
        "called_tools": ["get_services", "get_availability"]
    }

    result_ok = engine.validate(action_book, state_with_tools, workspace, manifest)
    print_test(
        "book_appointment con tools_first cumplidos",
        result_ok.is_allowed,
        f"Decision: {result_ok.decision}"
    )

def main():
    print("\n" + "="*60)
    print("🧪 TEST SUITE - Policy Engine V2")
    print("="*60)

    try:
        # Cargar manifest
        manifest = test_manifest_loading()

        # Crear engine
        engine = PolicyEngine()

        # Ejecutar tests
        test_tier_validation(engine, manifest)
        test_requires_slots_validation(engine, manifest)
        test_args_schema_validation(engine, manifest)
        test_rate_limits(engine, manifest)
        test_tools_first(engine, manifest)

        print("\n" + "="*60)
        print("✅ TODOS LOS TESTS COMPLETADOS")
        print("="*60)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
