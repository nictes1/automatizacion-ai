#!/usr/bin/env python3
"""
Script para cargar el menú de semilla en el workspace de desarrollo
"""

import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración
WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"  # Workspace de desarrollo
MENU_FILE = "examples/menu_completo.txt"
API_BASE_URL = "http://localhost:8002"  # Puerto de la API de menús

def check_api_health():
    """Verifica que la API esté funcionando"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API de menús está funcionando")
            return True
        else:
            print(f"❌ API de menús no responde correctamente: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ No se puede conectar a la API de menús: {e}")
        return False

def upload_menu():
    """Sube el menú al workspace de desarrollo"""
    
    # Verificar que el archivo existe
    menu_path = Path(MENU_FILE)
    if not menu_path.exists():
        print(f"❌ Archivo de menú no encontrado: {MENU_FILE}")
        return False
    
    print(f"📁 Cargando menú: {menu_path}")
    print(f"🏢 Workspace: {WORKSPACE_ID}")
    
    try:
        # Preparar el archivo para subir
        with open(menu_path, 'rb') as file:
            files = {'file': (menu_path.name, file, 'text/plain')}
            params = {'workspace_id': WORKSPACE_ID}
            
            print("🚀 Subiendo menú...")
            response = requests.post(
                f"{API_BASE_URL}/menus/upload",
                files=files,
                params=params,
                timeout=30
            )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Menú cargado exitosamente!")
            print(f"   📄 Archivo: {result['filename']}")
            print(f"   🆔 Menu ID: {result['menu_id']}")
            print(f"   📊 Chunks creados: {result['chunks_created']}")
            print(f"   🧠 Embeddings generados: {result['embeddings_generated']}")
            print(f"   📏 Tamaño: {result['file_size']} bytes")
            return result['menu_id']
        else:
            print(f"❌ Error cargando menú: {response.status_code}")
            print(f"   Respuesta: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def test_menu_search(menu_id):
    """Prueba búsquedas en el menú cargado"""
    
    print("\n🔍 Probando búsquedas en el menú...")
    
    # Consultas de prueba
    test_queries = [
        "quiero una pizza vegetariana",
        "empanadas de carne",
        "bebidas",
        "postres",
        "combos familiares",
        "envío gratis"
    ]
    
    for query in test_queries:
        print(f"\n🔎 Consulta: '{query}'")
        
        try:
            search_data = {
                "query": query,
                "workspace_id": WORKSPACE_ID,
                "limit": 3
            }
            
            response = requests.post(
                f"{API_BASE_URL}/menus/search",
                json=search_data,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                print(f"   ✅ Encontrados {len(results)} resultados:")
                
                for i, result in enumerate(results[:2], 1):  # Mostrar solo los 2 primeros
                    print(f"      {i}. {result['chunk_text'][:100]}...")
                    print(f"         Similitud: {result['similarity_score']:.2f}")
            else:
                print(f"   ❌ Error en búsqueda: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"   ❌ Error de conexión: {e}")

def list_menus():
    """Lista los menús del workspace"""
    
    print("\n📋 Listando menús del workspace...")
    
    try:
        params = {'workspace_id': WORKSPACE_ID}
        response = requests.get(
            f"{API_BASE_URL}/menus",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            menus = response.json()
            print(f"✅ Encontrados {len(menus)} menús:")
            
            for menu in menus:
                print(f"   🆔 {menu['menu_id']}")
                print(f"   📄 {menu['filename']}")
                print(f"   📊 {menu['chunks_count']} chunks")
                print(f"   📅 {menu['created_at']}")
                print(f"   📏 {menu['file_size']} bytes")
                print()
        else:
            print(f"❌ Error listando menús: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error de conexión: {e}")

def main():
    """Función principal"""
    
    print("🍕 Cargador de Menú de Semilla - PulpoAI")
    print("=" * 50)
    
    # 1. Verificar API
    if not check_api_health():
        print("\n💡 Asegúrate de que la API de menús esté ejecutándose:")
        print("   python services/menu_api.py")
        return False
    
    # 2. Subir menú
    menu_id = upload_menu()
    if not menu_id:
        return False
    
    # 3. Listar menús
    list_menus()
    
    # 4. Probar búsquedas
    test_menu_search(menu_id)
    
    print("\n🎉 ¡Menú de semilla cargado exitosamente!")
    print(f"🏢 Workspace: {WORKSPACE_ID}")
    print(f"🆔 Menu ID: {menu_id}")
    print("\n💡 Ahora puedes probar el workflow de n8n con este menú cargado.")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

