#!/usr/bin/env python3
"""
Test de Validadores de Slots - Validar que los validadores funcionan correctamente
"""

import asyncio
import json
import uuid
from typing import Dict, Any, List
import sys
import os
from datetime import datetime, timedelta

# Agregar el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.orchestrator_service import orchestrator_service, ConversationSnapshot

# Colores para output
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

# Configuración del test
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440003"  # Servicios
VERTICAL = "servicios"

# Test cases para validadores
TEST_CASES = [
    # Casos válidos
    {
        "name": "Fecha válida (mañana)",
        "input": "mañana",
        "expected_valid": True,
        "expected_slot": "preferred_date"
    },
    {
        "name": "Hora válida (10am)",
        "input": "a las 10am", 
        "expected_valid": True,
        "expected_slot": "preferred_time"
    },
    {
        "name": "Nombre válido",
        "input": "soy Juan Pérez",
        "expected_valid": True,
        "expected_slot": "client_name"
    },
    {
        "name": "Email válido",
        "input": "mi email es juan@gmail.com",
        "expected_valid": True,
        "expected_slot": "client_email"
    },
    
    # Casos inválidos
    {
        "name": "Fecha pasada (ayer)",
        "input": "ayer",
        "expected_valid": False,
        "expected_error": "fecha.*pasada"
    },
    {
        "name": "Hora fuera de horario (7am)",
        "input": "a las 7am",
        "expected_valid": False,
        "expected_error": "horario.*atención"
    },
    {
        "name": "Hora fuera de horario (8pm)",
        "input": "a las 8pm",
        "expected_valid": False,
        "expected_error": "horario.*atención"
    },
    {
        "name": "Email inválido",
        "input": "mi email es juan.gmail.com",
        "expected_valid": False,
        "expected_error": "email.*inválido"
    },
    {
        "name": "Nombre muy corto",
        "input": "soy A",
        "expected_valid": False,
        "expected_error": "nombre.*caracteres"
    }
]

async def test_slot_validators():
    """Test principal de validadores de slots"""
    
    print(f"{Colors.CYAN}{'='*80}")
    print(f"{Colors.BOLD}🧪 TEST DE VALIDADORES DE SLOTS{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}")
    
    conversation_id = str(uuid.uuid4())
    print(f"{Colors.YELLOW}💡 Conversation ID: {conversation_id}")
    print(f"💡 Workspace: {WORKSPACE_ID} ({VERTICAL})")
    print(f"💡 Probando {len(TEST_CASES)} casos de validación")
    print(f"{Colors.END}")
    
    results = []
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"{Colors.BLUE}🧪 Test {i}: {test_case['name']}{Colors.END}")
        print(f"   Input: '{test_case['input']}'")
        
        # Estado inicial
        snapshot = ConversationSnapshot(
            conversation_id=conversation_id,
            workspace_id=WORKSPACE_ID,
            vertical=VERTICAL,
            user_input=test_case['input'],
            greeted=True,  # Ya saludado para evitar GREET
            slots={"greeted": True},
            objective="",
            last_action=None,
            attempts_count=0
        )
        
        try:
            # Procesar con orchestrator
            response = await orchestrator_service.decide(snapshot)
            
            # Analizar resultado
            has_validation_errors = "_validation_errors" in response.slots
            validation_errors = response.slots.get("_validation_errors", [])
            
            if test_case["expected_valid"]:
                # Caso válido - no debería tener errores de validación
                if not has_validation_errors:
                    # Verificar que el slot esperado se llenó
                    expected_slot = test_case.get("expected_slot")
                    if expected_slot and response.slots.get(expected_slot):
                        print(f"   {Colors.GREEN}✅ PASS - Slot válido extraído: {expected_slot}={response.slots[expected_slot]}{Colors.END}")
                        passed += 1
                    elif not expected_slot:
                        print(f"   {Colors.GREEN}✅ PASS - Sin errores de validación{Colors.END}")
                        passed += 1
                    else:
                        print(f"   {Colors.RED}❌ FAIL - Slot esperado '{expected_slot}' no se llenó{Colors.END}")
                        failed += 1
                else:
                    print(f"   {Colors.RED}❌ FAIL - Errores de validación inesperados: {validation_errors}{Colors.END}")
                    failed += 1
            else:
                # Caso inválido - debería tener errores de validación
                if has_validation_errors:
                    # Verificar que el error contiene el patrón esperado
                    expected_error = test_case.get("expected_error", "")
                    error_text = " ".join(validation_errors).lower()
                    
                    import re
                    if re.search(expected_error.lower(), error_text):
                        print(f"   {Colors.GREEN}✅ PASS - Error de validación correcto: {validation_errors[0]}{Colors.END}")
                        passed += 1
                    else:
                        print(f"   {Colors.RED}❌ FAIL - Error no coincide. Esperado: '{expected_error}', Actual: '{error_text}'{Colors.END}")
                        failed += 1
                else:
                    print(f"   {Colors.RED}❌ FAIL - Debería tener errores de validación pero no los tiene{Colors.END}")
                    failed += 1
            
            results.append({
                "test": test_case["name"],
                "input": test_case["input"],
                "response": response.assistant,
                "slots": dict(response.slots),
                "validation_errors": validation_errors,
                "passed": (passed > len(results))  # Si passed aumentó, este test pasó
            })
            
        except Exception as e:
            print(f"   {Colors.RED}❌ ERROR - Excepción: {e}{Colors.END}")
            failed += 1
        
        print()
    
    # Resumen final
    print(f"{Colors.CYAN}{'='*80}")
    print(f"{Colors.BOLD}📊 RESULTADOS FINALES{Colors.END}")
    print(f"{Colors.CYAN}{'='*80}")
    
    total = passed + failed
    success_rate = (passed / total * 100) if total > 0 else 0
    
    if passed == total:
        print(f"{Colors.GREEN}✨ TODOS LOS TESTS PASARON ({passed}/{total}) - {success_rate:.1f}%")
        print(f"Los validadores de slots funcionan correctamente! 🎉{Colors.END}")
    else:
        print(f"{Colors.RED}❌ ALGUNOS TESTS FALLARON ({passed}/{total}) - {success_rate:.1f}%")
        print(f"Necesita ajustes en los validadores{Colors.END}")
    
    print(f"{Colors.CYAN}{'='*80}{Colors.END}")
    
    # Detalle de resultados
    print(f"{Colors.YELLOW}📝 Detalle de resultados:{Colors.END}")
    print()
    
    for result in results:
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{status} {result['test']}")
        print(f"  Input: {result['input']}")
        print(f"  Response: {result['response']}")
        if result['validation_errors']:
            print(f"  Validation Errors: {result['validation_errors']}")
        print(f"  Slots: {json.dumps(result['slots'], ensure_ascii=False, indent=2)}")
        print()

if __name__ == "__main__":
    asyncio.run(test_slot_validators())
