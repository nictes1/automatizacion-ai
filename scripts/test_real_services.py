#!/usr/bin/env python3
"""
Script para probar los servicios reales de PulpoAI
"""

import requests
import json
import time
import sys
from datetime import datetime

# URLs de los servicios
RAG_URL = "http://localhost:8007"
ORCHESTRATOR_URL = "http://localhost:8005"
ACTIONS_URL = "http://localhost:8006"

def test_rag_service():
    """Probar el servicio RAG real"""
    print("🔍 Probando RAG Service...")
    
    try:
        # Test de salud
        response = requests.get(f"{RAG_URL}/rag/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ RAG Service no está disponible: {response.status_code}")
            return False
        
        # Test de búsqueda
        search_payload = {
            "query": "¿Qué platos de pescado tienen?",
            "workspace_id": "test-workspace-123",
            "limit": 3
        }
        
        response = requests.post(
            f"{RAG_URL}/rag/search",
            json=search_payload,
            headers={"X-Workspace-Id": "test-workspace-123"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ RAG Service: {len(result['results'])} resultados encontrados")
            for i, result_item in enumerate(result['results']):
                print(f"  {i+1}. {result_item['content']} (score: {result_item['score']})")
            return True
        else:
            print(f"❌ RAG Service error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ RAG Service error: {e}")
        return False

def test_orchestrator_service():
    """Probar el servicio Orchestrator real"""
    print("\n🎭 Probando Orchestrator Service...")
    
    try:
        # Test de salud
        response = requests.get(f"{ORCHESTRATOR_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Orchestrator Service no está disponible: {response.status_code}")
            return False
        
        # Test de decisión
        snapshot_payload = {
            "conversation_id": "test-conversation-123",
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
            headers={"X-Workspace-Id": "test-workspace-123"},
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Orchestrator Service: {result['next_action']}")
            print(f"  Respuesta: {result['assistant']}")
            if result['tool_calls']:
                print(f"  Tool calls: {len(result['tool_calls'])}")
            return True
        else:
            print(f"❌ Orchestrator Service error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Orchestrator Service error: {e}")
        return False

def test_actions_service():
    """Probar el servicio Actions real"""
    print("\n⚡ Probando Actions Service...")
    
    try:
        # Test de salud
        response = requests.get(f"{ACTIONS_URL}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Actions Service no está disponible: {response.status_code}")
            return False
        
        # Test de ejecución de acción
        action_payload = {
            "name": "search_menu",
            "args": {"query": "pescado"},
            "conversation_id": "test-conversation-123",
            "workspace_id": "test-workspace-123",
            "request_id": f"test-{int(time.time())}"
        }
        
        response = requests.post(
            f"{ACTIONS_URL}/actions/execute",
            json=action_payload,
            headers={"X-Workspace-Id": "test-workspace-123"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Actions Service: {result['ok']}")
            print(f"  Mensaje: {result['message']}")
            if result['data']:
                print(f"  Datos: {result['data']}")
            return True
        else:
            print(f"❌ Actions Service error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Actions Service error: {e}")
        return False

def test_integrated_flow():
    """Probar flujo integrado completo"""
    print("\n🔄 Probando flujo integrado completo...")
    
    try:
        # 1. Usuario envía mensaje
        user_message = "Hola, quiero hacer una reserva para esta noche"
        print(f"👤 Usuario: {user_message}")
        
        # 2. Orchestrator decide
        snapshot_payload = {
            "conversation_id": "test-conversation-456",
            "vertical": "gastronomia",
            "user_input": user_message,
            "greeted": True,
            "slots": {},
            "objective": "hacer_reserva",
            "last_action": None,
            "attempts_count": 0
        }
        
        response = requests.post(
            f"{ORCHESTRATOR_URL}/orchestrator/decide",
            json=snapshot_payload,
            headers={"X-Workspace-Id": "test-workspace-123"},
            timeout=15
        )
        
        if response.status_code != 200:
            print(f"❌ Error en Orchestrator: {response.status_code}")
            return False
        
        orchestrator_result = response.json()
        print(f"🤖 Orchestrator: {orchestrator_result['next_action']}")
        print(f"  Respuesta: {orchestrator_result['assistant']}")
        
        # 3. Si hay tool calls, ejecutarlos
        if orchestrator_result['tool_calls']:
            for tool_call in orchestrator_result['tool_calls']:
                print(f"⚡ Ejecutando acción: {tool_call['name']}")
                
                action_payload = {
                    "name": tool_call['name'],
                    "args": tool_call['args'],
                    "conversation_id": "test-conversation-456",
                    "workspace_id": "test-workspace-123",
                    "request_id": f"test-{int(time.time())}"
                }
                
                response = requests.post(
                    f"{ACTIONS_URL}/actions/execute",
                    json=action_payload,
                    headers={"X-Workspace-Id": "test-workspace-123"},
                    timeout=10
                )
                
                if response.status_code == 200:
                    action_result = response.json()
                    print(f"  ✅ Acción ejecutada: {action_result['message']}")
                else:
                    print(f"  ❌ Error en acción: {response.status_code}")
        
        print("✅ Flujo integrado completado exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error en flujo integrado: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Iniciando test de servicios reales de PulpoAI")
    print("=" * 60)
    
    # Verificar que los servicios estén corriendo
    print("🔍 Verificando servicios...")
    
    services_ok = True
    
    # Test RAG Service
    if not test_rag_service():
        services_ok = False
    
    # Test Orchestrator Service
    if not test_orchestrator_service():
        services_ok = False
    
    # Test Actions Service
    if not test_actions_service():
        services_ok = False
    
    if not services_ok:
        print("\n❌ Algunos servicios no están funcionando")
        print("💡 Asegúrate de que los servicios estén corriendo:")
        print("   - RAG Service: python3 services/rag_service_real.py")
        print("   - Orchestrator Service: python3 services/orchestrator_service_real.py")
        print("   - Actions Service: python3 services/actions_service_real.py")
        sys.exit(1)
    
    # Test flujo integrado
    if not test_integrated_flow():
        print("\n❌ Flujo integrado falló")
        sys.exit(1)
    
    print("\n🎉 ¡Todos los tests pasaron exitosamente!")
    print("=" * 60)
    print("✅ RAG Service: OK")
    print("✅ Orchestrator Service: OK")
    print("✅ Actions Service: OK")
    print("✅ Flujo integrado: OK")

if __name__ == "__main__":
    main()
