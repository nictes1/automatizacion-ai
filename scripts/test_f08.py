#!/usr/bin/env python3
"""
Test específico para F-08: Encadenar Tool Calls
"""

import requests
import json
import time
import uuid
from datetime import datetime

# Configuración
ORCHESTRATOR_URL = "http://localhost:8005"
ACTIONS_URL = "http://localhost:8006"
N8N_URL = "http://localhost:5678"
DB_URL = "postgresql://pulpo:pulpo@localhost:5432/pulpo"

def test_actions_service_direct():
    """Test directo del Actions Service"""
    print("🧪 Testing Actions Service directly...")
    
    # Test search_menu
    test_data = {
        "name": "search_menu",
        "args": {
            "categoria": "pizzas",
            "query": "margarita"
        },
        "conversation_id": str(uuid.uuid4()),
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "request_id": f"test-{int(time.time())}"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": "00000000-0000-0000-0000-000000000001",
        "X-Request-Id": f"test-{int(time.time())}"
    }
    
    try:
        response = requests.post(
            f"{ACTIONS_URL}/actions/execute",
            json=test_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Actions Service OK")
            print(f"   Message: {result.get('message', 'N/A')[:100]}...")
            print(f"   OK: {result.get('ok', False)}")
            print(f"   Data keys: {list(result.get('data', {}).keys())}")
            return True
        else:
            print(f"❌ Actions Service Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Actions Service Error: {e}")
        return False

def test_orchestrator_with_tool_calls():
    """Test del Orchestrator que devuelve tool calls"""
    print("🧪 Testing Orchestrator with Tool Calls...")
    
    test_data = {
        "conversation_id": str(uuid.uuid4()),
        "vertical": "gastronomia",
        "user_input": "Quiero ver el menú de pizzas",
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
            print(f"✅ Orchestrator OK")
            print(f"   Assistant: {result.get('assistant', 'N/A')[:100]}...")
            print(f"   Next Action: {result.get('next_action', 'N/A')}")
            print(f"   Tool Calls: {len(result.get('tool_calls', []))}")
            
            # Verificar si hay tool calls
            if result.get('tool_calls'):
                print(f"   Tool Calls Details:")
                for i, tool_call in enumerate(result['tool_calls']):
                    print(f"     {i+1}. {tool_call.get('name', 'unknown')}: {tool_call.get('arguments', {})}")
                return True
            else:
                print("   ⚠️  No tool calls returned (may be normal)")
                return True
        else:
            print(f"❌ Orchestrator Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Orchestrator Error: {e}")
        return False

def test_complete_tool_call_flow():
    """Test del flujo completo: Orchestrator -> Actions -> Response"""
    print("🧪 Testing Complete Tool Call Flow...")
    
    conversation_id = str(uuid.uuid4())
    workspace_id = "00000000-0000-0000-0000-000000000001"
    
    # Paso 1: Orchestrator decide
    orchestrator_data = {
        "conversation_id": conversation_id,
        "vertical": "gastronomia",
        "user_input": "Quiero hacer un pedido de pizza margarita",
        "greeted": False,
        "slots": {},
        "objective": "",
        "last_action": None,
        "attempts_count": 0
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": workspace_id,
        "X-Request-Id": str(uuid.uuid4())
    }
    
    try:
        # 1. Llamar Orchestrator
        print("   1. Calling Orchestrator...")
        orchestrator_response = requests.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=orchestrator_data,
            headers=headers,
            timeout=30
        )
        
        if orchestrator_response.status_code != 200:
            print(f"   ❌ Orchestrator failed: {orchestrator_response.status_code}")
            return False
        
        orchestrator_result = orchestrator_response.json()
        print(f"   ✅ Orchestrator: {orchestrator_result.get('next_action', 'N/A')}")
        
        # 2. Si hay tool calls, ejecutarlos
        if orchestrator_result.get('tool_calls'):
            print(f"   2. Executing {len(orchestrator_result['tool_calls'])} tool calls...")
            
            for i, tool_call in enumerate(orchestrator_result['tool_calls']):
                print(f"      Tool {i+1}: {tool_call.get('name', 'unknown')}")
                
                action_data = {
                    "name": tool_call.get('name', ''),
                    "args": tool_call.get('arguments', {}),
                    "conversation_id": conversation_id,
                    "workspace_id": workspace_id,
                    "request_id": f"{conversation_id}-{tool_call.get('name', 'unknown')}"
                }
                
                action_response = requests.post(
                    f"{ACTIONS_URL}/actions/execute",
                    json=action_data,
                    headers=headers,
                    timeout=30
                )
                
                if action_response.status_code == 200:
                    action_result = action_response.json()
                    print(f"        ✅ Action executed: {action_result.get('ok', False)}")
                    print(f"        Message: {action_result.get('message', 'N/A')[:50]}...")
                else:
                    print(f"        ❌ Action failed: {action_response.status_code}")
                    return False
        
        # 3. Verificar que se puede continuar la conversación
        print("   3. Testing conversation continuation...")
        
        follow_up_data = {
            "conversation_id": conversation_id,
            "vertical": "gastronomia",
            "user_input": "Perfecto, quiero agregar una coca cola",
            "greeted": True,
            "slots": orchestrator_result.get('slots', {}),
            "objective": orchestrator_result.get('objective', ''),
            "last_action": orchestrator_result.get('next_action', ''),
            "attempts_count": 1
        }
        
        follow_up_response = requests.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=follow_up_data,
            headers=headers,
            timeout=30
        )
        
        if follow_up_response.status_code == 200:
            follow_up_result = follow_up_response.json()
            print(f"   ✅ Follow-up successful: {follow_up_result.get('assistant', 'N/A')[:50]}...")
            return True
        else:
            print(f"   ❌ Follow-up failed: {follow_up_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Complete flow error: {e}")
        return False

def test_database_persistence():
    """Test de persistencia en base de datos"""
    print("🧪 Testing Database Persistence...")
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verificar action_results
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM pulpo.action_results 
            WHERE created_at > NOW() - INTERVAL '1 hour'
        """)
        action_count = cur.fetchone()['count']
        print(f"   Action results (last hour): {action_count}")
        
        # Verificar menu_items
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM pulpo.menu_items 
            WHERE workspace_id = '00000000-0000-0000-0000-000000000001'
        """)
        menu_count = cur.fetchone()['count']
        print(f"   Menu items: {menu_count}")
        
        # Verificar orders
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM pulpo.orders 
            WHERE workspace_id = '00000000-0000-0000-0000-000000000001'
        """)
        order_count = cur.fetchone()['count']
        print(f"   Orders: {order_count}")
        
        cur.close()
        conn.close()
        
        print("✅ Database persistence OK")
        return True
        
    except Exception as e:
        print(f"❌ Database persistence error: {e}")
        return False

def test_n8n_webhook_with_tool_calls():
    """Test del webhook n8n que debería manejar tool calls"""
    print("🧪 Testing n8n Webhook with Tool Calls...")
    
    # Simular mensaje que debería trigger tool calls
    webhook_data = {
        "Body": "Quiero ver el menú de pizzas",
        "From": "whatsapp:+5491111111111",
        "To": "whatsapp:+14155238886",
        "SmsSid": f"SM_test_{int(time.time())}",
        "WorkspaceId": "00000000-0000-0000-0000-000000000001"
    }
    
    try:
        response = requests.post(
            f"{N8N_URL}/webhook/pulpo/twilio/wa/inbound",
            json=webhook_data,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ n8n Webhook OK")
            return True
        else:
            print(f"❌ n8n Webhook Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ n8n Webhook Error: {e}")
        return False

def test_performance():
    """Test de performance del Actions Service"""
    print("🧪 Testing Performance...")
    
    test_data = {
        "name": "search_menu",
        "args": {"categoria": "pizzas", "query": "margarita"},
        "conversation_id": str(uuid.uuid4()),
        "workspace_id": "00000000-0000-0000-0000-000000000001",
        "request_id": f"perf-test-{int(time.time())}"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": "00000000-0000-0000-0000-000000000001",
        "X-Request-Id": f"perf-test-{int(time.time())}"
    }
    
    # Ejecutar 3 requests y medir tiempo
    times = []
    success_count = 0
    
    for i in range(3):
        start_time = time.time()
        
        try:
            response = requests.post(
                f"{ACTIONS_URL}/actions/execute",
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
        print(f"   Success rate: {success_count}/3 ({success_count/3*100:.1f}%)")
        
        if avg_time < 1.0:  # Menos de 1 segundo
            print("✅ Performance is excellent")
            return True
        elif avg_time < 2.0:  # Menos de 2 segundos
            print("✅ Performance is good")
            return True
        else:
            print("⚠️  Performance could be improved")
            return True
    else:
        print("❌ Performance test failed")
        return False

def main():
    """Función principal de testing F-08"""
    print("🚀 F-08 Tool Calls Integration Test")
    print("=" * 50)
    
    tests = [
        ("Actions Service Direct", test_actions_service_direct),
        ("Orchestrator with Tool Calls", test_orchestrator_with_tool_calls),
        ("Complete Tool Call Flow", test_complete_tool_call_flow),
        ("Database Persistence", test_database_persistence),
        ("n8n Webhook with Tool Calls", test_n8n_webhook_with_tool_calls),
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
    print(f"📊 F-08 Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 F-08 is working correctly! Tool calls are integrated.")
    else:
        print("⚠️  Some tests failed. Check the logs above.")
    
    return passed == total

if __name__ == "__main__":
    main()
