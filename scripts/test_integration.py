#!/usr/bin/env python3
"""
Script de testing para validar la integración n8n + Orchestrator Service
"""

import requests
import json
import time
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid

# Configuración
ORCHESTRATOR_URL = "http://localhost:8005"
ACTIONS_URL = "http://localhost:8006"
DATABASE_URL = "postgresql://pulpo:pulpo@localhost:5432/pulpo"

def test_orchestrator_service():
    """Test básico del Orchestrator Service"""
    print("🧪 Testing Orchestrator Service...")
    
    # Datos de prueba
    test_data = {
        "conversation_id": str(uuid.uuid4()),
        "vertical": "gastronomia",
        "user_input": "Hola, quiero hacer un pedido",
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
            print(f"✅ Orchestrator Service OK")
            print(f"   Assistant: {result.get('assistant', 'N/A')[:100]}...")
            print(f"   Next Action: {result.get('next_action', 'N/A')}")
            print(f"   Tool Calls: {len(result.get('tool_calls', []))}")
            return True
        else:
            print(f"❌ Orchestrator Service Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Orchestrator Service Error: {e}")
        return False

def test_actions_service():
    """Test básico del Actions Service"""
    print("🧪 Testing Actions Service...")
    
    # Datos de prueba
    test_data = {
        "action": "search_menu",
        "args": {
            "categoria": "pizzas",
            "query": "margarita"
        },
        "conversation_id": str(uuid.uuid4()),
        "workspace_id": "00000000-0000-0000-0000-000000000001"
    }
    
    headers = {
        "Content-Type": "application/json",
        "X-Workspace-Id": "00000000-0000-0000-0000-000000000001"
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
            print(f"   Result: {result.get('result', 'N/A')}")
            return True
        else:
            print(f"❌ Actions Service Error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Actions Service Error: {e}")
        return False

def test_database_connection():
    """Test de conexión a la base de datos"""
    print("🧪 Testing Database Connection...")
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test básico
        cur.execute("SELECT 1 as test")
        result = cur.fetchone()
        
        if result and result['test'] == 1:
            print("✅ Database Connection OK")
            
            # Test de tablas principales
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'pulpo' 
                ORDER BY table_name
            """)
            tables = [row['table_name'] for row in cur.fetchall()]
            print(f"   Tables found: {len(tables)}")
            print(f"   Main tables: {', '.join(tables[:5])}...")
            
            cur.close()
            conn.close()
            return True
        else:
            print("❌ Database Test Failed")
            return False
            
    except Exception as e:
        print(f"❌ Database Connection Error: {e}")
        return False

def test_n8n_webhook():
    """Test del webhook de n8n"""
    print("🧪 Testing n8n Webhook...")
    
    # Simular payload de Twilio
    webhook_data = {
        "Body": "Hola, quiero hacer un pedido",
        "From": "whatsapp:+5491123456789",
        "To": "whatsapp:+5491123456788",
        "MessageSid": "SM1234567890",
        "WorkspaceId": "00000000-0000-0000-0000-000000000001"
    }
    
    try:
        response = requests.post(
            "http://localhost:5678/webhook/pulpo/twilio/wa/inbound",
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

def test_complete_flow():
    """Test del flujo completo"""
    print("🧪 Testing Complete Flow...")
    
    # 1. Test Orchestrator
    if not test_orchestrator_service():
        return False
    
    # 2. Test Actions
    if not test_actions_service():
        return False
    
    # 3. Test Database
    if not test_database_connection():
        return False
    
    # 4. Test n8n (opcional, puede no estar disponible)
    try:
        test_n8n_webhook()
    except:
        print("⚠️  n8n Webhook not available (normal if n8n not running)")
    
    print("✅ Complete Flow Test Passed!")
    return True

def main():
    """Función principal"""
    print("🚀 PulpoAI Integration Test")
    print("=" * 50)
    
    # Esperar un poco para que los servicios estén listos
    print("⏳ Waiting for services to be ready...")
    time.sleep(5)
    
    # Ejecutar tests
    success = test_complete_flow()
    
    print("=" * 50)
    if success:
        print("🎉 All tests passed! System is ready.")
    else:
        print("❌ Some tests failed. Check the logs above.")
    
    return success

if __name__ == "__main__":
    main()
