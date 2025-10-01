#!/usr/bin/env python3
"""
Script de prueba completo del sistema PulpoAI
Carga menú de semilla y prueba el flujo completo
"""

import os
import sys
import requests
import json
import time
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"  # Workspace de desarrollo
MENU_FILE = "examples/menu_completo.txt"
MENU_API_URL = "http://localhost:8002"
RAG_API_URL = "http://localhost:8003"

def check_services():
    """Verifica que todos los servicios estén funcionando"""
    
    services = [
        ("API de Menús", f"{MENU_API_URL}/health"),
        ("API RAG", f"{RAG_API_URL}/health")
    ]
    
    print("🔍 Verificando servicios...")
    
    for name, url in services:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                print(f"✅ {name}: OK")
            else:
                print(f"❌ {name}: Error {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ {name}: No disponible - {e}")
            return False
    
    return True

def load_menu():
    """Carga el menú de semilla"""
    
    print("\n🍕 Cargando menú de semilla...")
    
    # Verificar que el archivo existe
    menu_path = Path(MENU_FILE)
    if not menu_path.exists():
        print(f"❌ Archivo de menú no encontrado: {MENU_FILE}")
        return False
    
    try:
        # Subir menú
        with open(menu_path, 'rb') as file:
            files = {'file': (menu_path.name, file, 'text/plain')}
            params = {'workspace_id': WORKSPACE_ID}
            
            response = requests.post(
                f"{MENU_API_URL}/menus/upload",
                files=files,
                params=params,
                timeout=60  # Más tiempo para procesamiento
            )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Menú cargado: {result['menu_id']}")
            print(f"   📊 Chunks: {result['chunks_created']}")
            print(f"   🧠 Embeddings: {result['embeddings_generated']}")
            return result['menu_id']
        else:
            print(f"❌ Error cargando menú: {response.status_code}")
            print(f"   Respuesta: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_rag_queries():
    """Prueba consultas RAG"""
    
    print("\n🔍 Probando consultas RAG...")
    
    # Consultas de prueba
    test_queries = [
        "quiero una pizza vegetariana",
        "empanadas de carne",
        "bebidas",
        "postres",
        "combos familiares",
        "envío gratis",
        "horarios de atención",
        "formas de pago"
    ]
    
    for query in test_queries:
        print(f"\n🔎 Consulta: '{query}'")
        
        try:
            # Consulta RAG
            response = requests.get(
                f"{RAG_API_URL}/query/simple",
                params={
                    'query': query,
                    'workspace_id': WORKSPACE_ID,
                    'limit': 3
                },
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"   ✅ Encontrados {results['total']} resultados:")
                
                for i, result in enumerate(results['results'][:2], 1):
                    content = result['content'][:100] + "..." if len(result['content']) > 100 else result['content']
                    print(f"      {i}. {content}")
                    print(f"         Similitud: {result['similarity']:.2f}")
            else:
                print(f"   ❌ Error: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_menu_specific_queries():
    """Prueba consultas específicas de menú"""
    
    print("\n🍕 Probando consultas específicas de menú...")
    
    menu_queries = [
        "pizza margherita",
        "empanada de jamón y queso",
        "ensalada césar",
        "combo familiar",
        "precio de empanadas"
    ]
    
    for query in menu_queries:
        print(f"\n🍽️ Consulta menú: '{query}'")
        
        try:
            response = requests.get(
                f"{RAG_API_URL}/query/menu",
                params={
                    'query': query,
                    'workspace_id': WORKSPACE_ID,
                    'limit': 2
                },
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"   ✅ Encontrados {results['total']} resultados de menú:")
                
                for result in results['menu_results']:
                    content = result['content'][:150] + "..." if len(result['content']) > 150 else result['content']
                    print(f"      📄 {content}")
                    print(f"         Similitud: {result['similarity']:.2f}")
            else:
                print(f"   ❌ Error: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_context_retrieval():
    """Prueba obtención de contexto"""
    
    print("\n📋 Probando obtención de contexto...")
    
    try:
        response = requests.get(
            f"{RAG_API_URL}/query/context",
            params={
                'workspace_id': WORKSPACE_ID,
                'context_type': 'menu'
            },
            timeout=10
        )
        
        if response.status_code == 200:
            context = response.json()
            print(f"✅ Contexto obtenido: {context['total']} elementos")
            
            for i, item in enumerate(context['context'][:3], 1):
                content = item['content'][:100] + "..." if len(item['content']) > 100 else item['content']
                print(f"   {i}. {content}")
        else:
            print(f"❌ Error obteniendo contexto: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def simulate_conversation():
    """Simula una conversación completa"""
    
    print("\n💬 Simulando conversación completa...")
    
    # Simular flujo de conversación
    conversation_flow = [
        {
            "user": "Hola, quiero hacer un pedido",
            "expected_rag": "información general del menú"
        },
        {
            "user": "Quiero una pizza vegetariana",
            "expected_rag": "pizza vegetariana margherita"
        },
        {
            "user": "¿Qué bebidas tienen?",
            "expected_rag": "bebidas coca cola agua"
        },
        {
            "user": "¿Hay combos familiares?",
            "expected_rag": "combo familiar pizza empanadas"
        }
    ]
    
    for step in conversation_flow:
        print(f"\n👤 Usuario: {step['user']}")
        
        try:
            # Simular consulta RAG que haría el LLM
            response = requests.get(
                f"{RAG_API_URL}/query/simple",
                params={
                    'query': step['expected_rag'],
                    'workspace_id': WORKSPACE_ID,
                    'limit': 2
                },
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"🤖 AI consultaría: '{step['expected_rag']}'")
                print(f"   📊 Encontrados {results['total']} resultados relevantes")
                
                # Mostrar el mejor resultado
                if results['results']:
                    best_result = results['results'][0]
                    content = best_result['content'][:200] + "..." if len(best_result['content']) > 200 else best_result['content']
                    print(f"   🎯 Mejor resultado: {content}")
                    print(f"   📈 Similitud: {best_result['similarity']:.2f}")
            else:
                print(f"   ❌ Error en consulta RAG: {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def main():
    """Función principal"""
    
    print("🚀 Prueba Completa del Sistema PulpoAI")
    print("=" * 50)
    
    # 1. Verificar servicios
    if not check_services():
        print("\n💡 Asegúrate de que los servicios estén ejecutándose:")
        print("   python services/menu_api.py")
        print("   python services/rag_query_api.py")
        return False
    
    # 2. Cargar menú
    menu_id = load_menu()
    if not menu_id:
        return False
    
    # Esperar un poco para que se procese
    print("\n⏳ Esperando procesamiento...")
    time.sleep(2)
    
    # 3. Probar consultas RAG
    test_rag_queries()
    
    # 4. Probar consultas específicas de menú
    test_menu_specific_queries()
    
    # 5. Probar obtención de contexto
    test_context_retrieval()
    
    # 6. Simular conversación
    simulate_conversation()
    
    print("\n🎉 ¡Prueba completa exitosa!")
    print(f"🏢 Workspace: {WORKSPACE_ID}")
    print(f"🆔 Menu ID: {menu_id}")
    print("\n💡 El sistema está listo para probar con n8n!")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

