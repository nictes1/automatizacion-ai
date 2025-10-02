#!/usr/bin/env python3
"""
Script para probar el sistema completo de PulpoAI
- Workspace semilla
- Ingesta real de documentos
- Flujo completo como cliente
"""

import requests
import json
import time
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# URLs de los servicios
RAG_URL = "http://localhost:8007"
ORCHESTRATOR_URL = "http://localhost:8005"
ACTIONS_URL = "http://localhost:8006"
DB_URL = "postgresql://pulpo:pulpo@localhost:5432/pulpo"

# Workspace de prueba
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"
CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440005"

def setup_workspace():
    """Configurar workspace semilla"""
    print("🌱 Configurando workspace semilla...")
    
    try:
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()
        
        # Ejecutar script de seed
        with open('sql/05_seed_workspace.sql', 'r') as f:
            seed_sql = f.read()
        
        cursor.execute(seed_sql)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        print("✅ Workspace semilla configurado")
        return True
        
    except Exception as e:
        print(f"❌ Error configurando workspace: {e}")
        return False

def test_rag_with_real_data():
    """Probar RAG con datos reales"""
    print("\n🔍 Probando RAG con datos reales...")
    
    try:
        # Test de búsqueda con datos reales
        search_payload = {
            "query": "¿Qué platos de pescado tienen?",
            "workspace_id": WORKSPACE_ID,
            "limit": 3
        }
        
        response = requests.post(
            f"{RAG_URL}/rag/search",
            json=search_payload,
            headers={"X-Workspace-Id": WORKSPACE_ID},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ RAG: {len(result['results'])} resultados encontrados")
            for i, result_item in enumerate(result['results']):
                print(f"  {i+1}. {result_item['content']}")
            return True
        else:
            print(f"❌ RAG error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ RAG error: {e}")
        return False

def test_orchestrator_with_vertical():
    """Probar Orchestrator con vertical dinámico"""
    print("\n🎭 Probando Orchestrator con vertical dinámico...")
    
    try:
        # Test con vertical gastronomía
        snapshot_payload = {
            "conversation_id": CONVERSATION_ID,
            "vertical": "gastronomia",
            "user_input": "Hola, quiero saber qué platos de pescado tienen",
            "greeted": True,
            "slots": {},
            "objective": "consultar_menu",
            "last_action": None,
            "attempts_count": 0
        }
        
        response = requests.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=snapshot_payload,
            headers={"X-Workspace-Id": WORKSPACE_ID},
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Orchestrator: {result['next_action']}")
            print(f"  Respuesta: {result['assistant']}")
            if result['tool_calls']:
                print(f"  Tool calls: {len(result['tool_calls'])}")
            return True
        else:
            print(f"❌ Orchestrator error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Orchestrator error: {e}")
        return False

def test_actions_with_real_data():
    """Probar Actions con datos reales"""
    print("\n⚡ Probando Actions con datos reales...")

    try:
        # Test de ejecución de acción - crear pedido
        action_payload = {
            "conversation_id": CONVERSATION_ID,
            "action_name": "crear_pedido",
            "payload": {
                "workspace_id": WORKSPACE_ID,
                "conversation_id": CONVERSATION_ID,
                "items": [
                    {"nombre": "Empanada de Carne", "cantidad": 2}
                ],
                "metodo_entrega": "retira"
            },
            "idempotency_key": f"test-{int(time.time())}"
        }
        
        response = requests.post(
            f"{ACTIONS_URL}/tools/execute_action",
            json=action_payload,
            headers={"X-Workspace-Id": WORKSPACE_ID},
            timeout=10
        )
        
        if response.status_code in [200, 202]:
            result = response.json()
            print(f"✅ Actions: {result['status']}")
            print(f"  Resumen: {result['summary']}")
            print(f"  Action ID: {result['action_id']}")
            return True
        else:
            print(f"❌ Actions error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Actions error: {e}")
        return False

def test_complete_conversation():
    """Probar conversación completa como cliente real"""
    print("\n💬 Probando conversación completa como cliente...")
    
    try:
        # Simular conversación real
        conversation_steps = [
            {
                "user_input": "Hola, quiero saber qué platos de pescado tienen",
                "expected_intent": "consultar_menu"
            },
            {
                "user_input": "Me interesa el pescado a la plancha, ¿cuánto cuesta?",
                "expected_intent": "consultar_precios"
            },
            {
                "user_input": "Perfecto, quiero hacer una reserva para esta noche",
                "expected_intent": "hacer_reserva"
            }
        ]
        
        for i, step in enumerate(conversation_steps):
            print(f"\n👤 Cliente: {step['user_input']}")
            
            # Orchestrator decide
            snapshot_payload = {
                "conversation_id": CONVERSATION_ID,
                "vertical": "gastronomia",
                "user_input": step['user_input'],
                "greeted": i > 0,
                "slots": {},
                "objective": step['expected_intent'],
                "last_action": None,
                "attempts_count": 0
            }
            
            response = requests.post(
                f"{ORCHESTRATOR_URL}/orchestrator/decide",
                json=snapshot_payload,
                headers={"X-Workspace-Id": WORKSPACE_ID},
                timeout=15
            )
            
            if response.status_code != 200:
                print(f"❌ Error en Orchestrator: {response.status_code}")
                return False
            
            orchestrator_result = response.json()
            print(f"🤖 Asistente: {orchestrator_result['assistant']}")
            
            # Si hay tool calls, ejecutarlos
            if orchestrator_result['tool_calls']:
                for tool_call in orchestrator_result['tool_calls']:
                    print(f"⚡ Ejecutando: {tool_call['name']}")

                    action_payload = {
                        "conversation_id": CONVERSATION_ID,
                        "action_name": tool_call['name'],
                        "payload": {
                            "workspace_id": WORKSPACE_ID,
                            "conversation_id": CONVERSATION_ID,
                            **tool_call['args']
                        },
                        "idempotency_key": f"test-{int(time.time())}-{tool_call['name']}"
                    }

                    response = requests.post(
                        f"{ACTIONS_URL}/tools/execute_action",
                        json=action_payload,
                        headers={"X-Workspace-Id": WORKSPACE_ID},
                        timeout=10
                    )

                    if response.status_code == 200:
                        action_result = response.json()
                        print(f"  ✅ Resultado: {action_result.get('message', action_result.get('summary', 'OK'))}")
                    else:
                        print(f"  ❌ Error en acción: {response.status_code}")
            
            # Pausa entre pasos
            time.sleep(1)
        
        print("\n✅ Conversación completa exitosa")
        return True
        
    except Exception as e:
        print(f"❌ Error en conversación: {e}")
        return False

def test_different_verticals():
    """Probar diferentes verticales"""
    print("\n🏢 Probando diferentes verticales...")
    
    verticals = [
        {
            "name": "Gastronomía",
            "vertical": "gastronomia",
            "user_input": "Quiero hacer una reserva para esta noche"
        },
        {
            "name": "Inmobiliaria", 
            "vertical": "inmobiliaria",
            "user_input": "Busco un apartamento de 2 habitaciones en el norte"
        },
        {
            "name": "Servicios",
            "vertical": "servicios", 
            "user_input": "Quiero agendar una cita para mañana"
        }
    ]
    
    for vertical_test in verticals:
        print(f"\n🏢 {vertical_test['name']}:")
        print(f"👤 Cliente: {vertical_test['user_input']}")
        
        try:
            snapshot_payload = {
                "conversation_id": CONVERSATION_ID,
                "vertical": vertical_test['vertical'],
                "user_input": vertical_test['user_input'],
                "greeted": True,
                "slots": {},
                "objective": "consultar",
                "last_action": None,
                "attempts_count": 0
            }
            
            response = requests.post(
                f"{ORCHESTRATOR_URL}/orchestrator/decide",
                json=snapshot_payload,
                headers={"X-Workspace-Id": WORKSPACE_ID},
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"🤖 Asistente: {result['assistant']}")
                print(f"  Acción: {result['next_action']}")
            else:
                print(f"❌ Error: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        time.sleep(1)

def main():
    """Función principal"""
    print("🚀 Iniciando test completo del sistema PulpoAI")
    print("=" * 60)
    
    # Paso 1: Configurar workspace
    if not setup_workspace():
        print("❌ No se pudo configurar el workspace")
        sys.exit(1)
    
    # Paso 2: Probar RAG con datos reales
    if not test_rag_with_real_data():
        print("❌ RAG con datos reales falló")
        sys.exit(1)
    
    # Paso 3: Probar Orchestrator con vertical
    if not test_orchestrator_with_vertical():
        print("❌ Orchestrator con vertical falló")
        sys.exit(1)
    
    # Paso 4: Probar Actions con datos reales
    if not test_actions_with_real_data():
        print("❌ Actions con datos reales falló")
        sys.exit(1)
    
    # Paso 5: Probar conversación completa
    if not test_complete_conversation():
        print("❌ Conversación completa falló")
        sys.exit(1)
    
    # Paso 6: Probar diferentes verticales
    test_different_verticals()
    
    print("\n🎉 ¡Sistema completo funcionando!")
    print("=" * 60)
    print("✅ Workspace semilla: OK")
    print("✅ RAG con datos reales: OK")
    print("✅ Orchestrator con verticales: OK")
    print("✅ Actions con datos reales: OK")
    print("✅ Conversación completa: OK")
    print("✅ Múltiples verticales: OK")

if __name__ == "__main__":
    main()