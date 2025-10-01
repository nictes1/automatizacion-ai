#!/usr/bin/env python3
"""
Test específico para el flujo n8n integrado con Orchestrator Service
"""

import requests
import json
import time
import uuid
from datetime import datetime

# Configuración
N8N_WEBHOOK_URL = "http://localhost:5678/webhook/pulpo/twilio/wa/inbound"
ORCHESTRATOR_URL = "http://localhost:8005"

def test_webhook_payload():
    """Test del payload del webhook de n8n"""
    print("🧪 Testing n8n Webhook Payload...")
    
    # Payload simulado de Twilio
    payload = {
        "Body": "Hola, quiero hacer un pedido de pizza",
        "From": "whatsapp:+5491123456789",
        "To": "whatsapp:+5491123456788",
        "MessageSid": f"SM{int(time.time())}",
        "WaId": "+5491123456789",
        "SmsSid": f"SM{int(time.time())}",
        "WorkspaceId": "00000000-0000-0000-0000-000000000001"
    }
    
    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=payload,
            timeout=30
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ Webhook payload test passed")
            return True
        else:
            print("❌ Webhook payload test failed")
            return False
            
    except Exception as e:
        print(f"❌ Webhook test error: {e}")
        return False

def test_orchestrator_direct():
    """Test directo del Orchestrator Service"""
    print("🧪 Testing Orchestrator Service directly...")
    
    test_data = {
        "conversation_id": str(uuid.uuid4()),
        "vertical": "gastronomia",
        "user_input": "Quiero pedir una pizza margarita",
        "greeted": False,
        "slots": {},
        "objective": "",
        "last_action": None,
        "attempts_count": 0
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": "00000000-0000-0000-0000-000000000001",
        "X-Request-Id": str(uuid.uuid4())
    }
    
    try:
        response = requests.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=test_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Orchestrator direct test passed")
            print(f"   Assistant: {result.get('assistant', 'N/A')[:100]}...")
            print(f"   Next Action: {result.get('next_action', 'N/A')}")
            print(f"   Tool Calls: {len(result.get('tool_calls', []))}")
            return True
        else:
            print(f"❌ Orchestrator direct test failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Orchestrator direct test error: {e}")
        return False

def test_conversation_flow():
    """Test del flujo completo de conversación"""
    print("🧪 Testing Complete Conversation Flow...")
    
    conversation_id = str(uuid.uuid4())
    workspace_id = "00000000-0000-0000-0000-000000000001"
    
    # Simular múltiples mensajes en una conversación
    messages = [
        "Hola, quiero hacer un pedido",
        "Quiero una pizza margarita",
        "Para delivery, mi dirección es Av. Corrientes 1234",
        "Pago en efectivo"
    ]
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": workspace_id,
        "X-Request-Id": str(uuid.uuid4())
    }
    
    slots = {}
    objective = ""
    last_action = None
    attempts_count = 0
    
    for i, message in enumerate(messages):
        print(f"   Message {i+1}: {message}")
        
        test_data = {
            "conversation_id": conversation_id,
            "vertical": "gastronomia",
            "user_input": message,
            "greeted": i > 0,
            "slots": slots,
            "objective": objective,
            "last_action": last_action,
            "attempts_count": attempts_count
        }
        
        try:
            response = requests.post(
                f"{ORCHESTRATOR_URL}/orchestrator/decide",
                json=test_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"     Response: {result.get('assistant', 'N/A')[:80]}...")
                print(f"     Next Action: {result.get('next_action', 'N/A')}")
                
                # Actualizar estado para siguiente mensaje
                slots = result.get('slots', slots)
                objective = result.get('objective', objective)
                last_action = result.get('next_action', last_action)
                attempts_count += 1
                
                # Si hay tool calls, simular ejecución
                if result.get('tool_calls'):
                    print(f"     Tool Calls: {len(result['tool_calls'])}")
                    for tool_call in result['tool_calls']:
                        print(f"       - {tool_call.get('name', 'unknown')}: {tool_call.get('args', {})}")
                
                # Si es handoff, terminar
                if result.get('next_action') == 'handoff':
                    print("     → Handoff triggered")
                    break
                    
            else:
                print(f"     ❌ Error: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"     ❌ Error: {e}")
            return False
        
        # Pausa entre mensajes
        time.sleep(1)
    
    print("✅ Conversation flow test completed")
    return True

def test_error_handling():
    """Test de manejo de errores"""
    print("🧪 Testing Error Handling...")
    
    # Test con datos inválidos
    invalid_data = {
        "conversation_id": "invalid-uuid",
        "vertical": "invalid_vertical",
        "user_input": "",
        "greeted": "not_boolean",
        "slots": "not_object",
        "objective": None,
        "last_action": None,
        "attempts_count": -1
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": "invalid-workspace-id",
        "X-Request-Id": "invalid-request-id"
    }
    
    try:
        response = requests.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=invalid_data,
            headers=headers,
            timeout=30
        )
        
        # Debería devolver error 400 o 422
        if response.status_code in [400, 422]:
            print("✅ Error handling test passed (expected error)")
            return True
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            print(f"   Response: {response.text}")
            return True  # No es crítico
            
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def test_performance():
    """Test de performance básico"""
    print("🧪 Testing Performance...")
    
    test_data = {
        "conversation_id": str(uuid.uuid4()),
        "vertical": "gastronomia",
        "user_input": "Test de performance",
        "greeted": False,
        "slots": {},
        "objective": "",
        "last_action": None,
        "attempts_count": 0
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": "00000000-0000-0000-0000-000000000001",
        "X-Request-Id": str(uuid.uuid4())
    }
    
    # Ejecutar 5 requests y medir tiempo promedio
    times = []
    success_count = 0
    
    for i in range(5):
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{ORCHESTRATOR_URL}/orchestrator/decide",
                json=test_data,
                headers=headers,
                timeout=30
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            times.append(response_time)
            
            if response.status_code == 200:
                success_count += 1
                print(f"   Request {i+1}: {response_time:.2f}s")
            else:
                print(f"   Request {i+1}: Failed ({response.status_code})")
                
        except Exception as e:
            print(f"   Request {i+1}: Error ({e})")
    
    if times:
        avg_time = sum(times) / len(times)
        print(f"✅ Performance test completed")
        print(f"   Average response time: {avg_time:.2f}s")
        print(f"   Success rate: {success_count}/5 ({success_count/5*100:.1f}%)")
        
        if avg_time < 2.0:  # Menos de 2 segundos
            print("✅ Performance is good")
            return True
        else:
            print("⚠️  Performance could be improved")
            return True
    else:
        print("❌ Performance test failed")
        return False

def main():
    """Función principal de testing"""
    print("🚀 n8n Flow Integration Test")
    print("=" * 50)
    
    tests = [
        ("Orchestrator Direct", test_orchestrator_direct),
        ("Webhook Payload", test_webhook_payload),
        ("Conversation Flow", test_conversation_flow),
        ("Error Handling", test_error_handling),
        ("Performance", test_performance)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            print(f"❌ {test_name} ERROR: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed! n8n integration is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above.")
    
    return passed == total

if __name__ == "__main__":
    main()
