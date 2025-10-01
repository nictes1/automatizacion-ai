#!/usr/bin/env python3
"""
Script de prueba para el sistema de ingesta de archivos mejorado
"""

import os
import sys
import requests
import time
import json
from pathlib import Path

# Configuración
INGESTOR_URL = "http://localhost:8080"
TIKA_URL = "http://localhost:9998"
OLLAMA_URL = "http://localhost:11434"
WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"

def test_health_checks():
    """Prueba los health checks de todos los servicios"""
    print("🔍 Probando health checks...")
    
    # Tika
    try:
        response = requests.get(f"{TIKA_URL}/tika", timeout=10)
        tika_ok = response.status_code == 200
        print(f"  Tika: {'✅' if tika_ok else '❌'}")
    except:
        print("  Tika: ❌")
        tika_ok = False
    
    # Ollama
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        ollama_ok = response.status_code == 200
        print(f"  Ollama: {'✅' if ollama_ok else '❌'}")
    except:
        print("  Ollama: ❌")
        ollama_ok = False
    
    # File Ingestor
    try:
        response = requests.get(f"{INGESTOR_URL}/health", timeout=10)
        ingestor_ok = response.status_code == 200
        if ingestor_ok:
            health_data = response.json()
            print(f"  File Ingestor: {'✅' if health_data['status'] == 'healthy' else '❌'}")
            print(f"    - Tika: {'✅' if health_data['tika_ready'] else '❌'}")
            print(f"    - Ollama: {'✅' if health_data['ollama_ready'] else '❌'}")
            print(f"    - Database: {'✅' if health_data['database_ready'] else '❌'}")
        else:
            print("  File Ingestor: ❌")
    except:
        print("  File Ingestor: ❌")
        ingestor_ok = False
    
    return tika_ok and ollama_ok and ingestor_ok

def test_supported_types():
    """Prueba el endpoint de tipos soportados"""
    print("\n📋 Probando tipos de archivos soportados...")
    
    try:
        response = requests.get(f"{INGESTOR_URL}/supported-types")
        if response.status_code == 200:
            data = response.json()
            print(f"  ✅ {len(data['supported_extensions'])} tipos soportados")
            print(f"  Modelo de embeddings: {data['embedding_model']}")
            print(f"  Dimensiones: {data['embedding_dimensions']}")
            return True
        else:
            print(f"  ❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def create_test_file():
    """Crea un archivo de prueba"""
    test_content = """
# Documento de Prueba para RAG

Este es un documento de prueba para verificar el funcionamiento del sistema de ingesta de archivos.

## Sección 1: Introducción

El sistema de gestión de archivos para RAG permite:
- Subir archivos de diferentes tipos
- Extraer texto usando Apache Tika
- Generar embeddings con Ollama
- Almacenar en base de datos vectorial

## Sección 2: Características

### Tipos de archivos soportados:
- PDF, DOCX, XLSX, PPTX
- TXT, MD, HTML, JSON
- Código fuente (Python, JavaScript, etc.)

### Procesamiento:
1. Extracción de texto con Tika
2. Chunking inteligente
3. Generación de embeddings
4. Almacenamiento vectorial

## Sección 3: Conclusión

Este sistema está diseñado para ser escalable y robusto, permitiendo la gestión eficiente de documentos para sistemas RAG.
"""
    
    test_file = "test_document.md"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(test_content)
    
    return test_file

def test_file_ingestion():
    """Prueba la ingesta de un archivo"""
    print("\n📁 Probando ingesta de archivo...")
    
    # Crear archivo de prueba
    test_file = create_test_file()
    print(f"  Archivo de prueba creado: {test_file}")
    
    try:
        # Preparar request
        request_data = {
            "workspace_id": WORKSPACE_ID,
            "file_path": os.path.abspath(test_file),
            "title": "Documento de Prueba RAG",
            "language": "es"
        }
        
        print("  Enviando archivo para procesamiento...")
        response = requests.post(f"{INGESTOR_URL}/ingest", json=request_data, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Archivo procesado exitosamente")
            print(f"    - File ID: {result['file_id']}")
            print(f"    - Document ID: {result['document_id']}")
            print(f"    - Chunks creados: {result['chunks_created']}")
            print(f"    - Embeddings generados: {result['embeddings_generated']}")
            print(f"    - Tiempo de procesamiento: {result['processing_time']:.2f}s")
            return result['file_id']
        else:
            print(f"  ❌ Error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None
    finally:
        # Limpiar archivo de prueba
        if os.path.exists(test_file):
            os.remove(test_file)

def test_file_stats():
    """Prueba las estadísticas de archivos"""
    print("\n📊 Probando estadísticas de archivos...")
    
    try:
        response = requests.get(f"{INGESTOR_URL}/files/{WORKSPACE_ID}/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"  ✅ Estadísticas obtenidas:")
            print(f"    - Total archivos: {stats['total_files']}")
            print(f"    - Tamaño total: {stats['total_size']} bytes")
            print(f"    - Total documentos: {stats['total_documents']}")
            print(f"    - Total chunks: {stats['total_chunks']}")
            print(f"    - Total embeddings: {stats['total_embeddings']}")
            return True
        else:
            print(f"  ❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_list_files():
    """Prueba el listado de archivos"""
    print("\n📋 Probando listado de archivos...")
    
    try:
        response = requests.get(f"{INGESTOR_URL}/files/{WORKSPACE_ID}")
        if response.status_code == 200:
            files = response.json()
            print(f"  ✅ {len(files)} archivos encontrados:")
            for file_info in files:
                print(f"    - {file_info['filename']} ({file_info['status']})")
            return True
        else:
            print(f"  ❌ Error: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_async_ingestion():
    """Prueba la ingesta asíncrona"""
    print("\n⚡ Probando ingesta asíncrona...")
    
    # Crear archivo de prueba
    test_file = create_test_file()
    
    try:
        request_data = {
            "workspace_id": WORKSPACE_ID,
            "file_path": os.path.abspath(test_file),
            "title": "Documento Asíncrono de Prueba"
        }
        
        response = requests.post(f"{INGESTOR_URL}/ingest/async", json=request_data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            print(f"  ✅ Archivo agregado a cola: {result['message']}")
            
            # Esperar un poco para que se procese
            print("  Esperando procesamiento...")
            time.sleep(5)
            
            # Verificar que se procesó
            stats_response = requests.get(f"{INGESTOR_URL}/files/{WORKSPACE_ID}/stats")
            if stats_response.status_code == 200:
                stats = stats_response.json()
                print(f"  ✅ Procesamiento asíncrono completado")
                return True
            else:
                print("  ⚠️ No se pudo verificar el procesamiento")
                return False
        else:
            print(f"  ❌ Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    finally:
        # Limpiar archivo de prueba
        if os.path.exists(test_file):
            os.remove(test_file)

def main():
    """Función principal de prueba"""
    print("🧪 Iniciando pruebas del sistema de ingesta de archivos mejorado")
    print("=" * 60)
    
    # Verificar que los servicios estén corriendo
    if not test_health_checks():
        print("\n❌ Algunos servicios no están disponibles. Asegúrate de que estén corriendo:")
        print("  - Tika Server: docker-compose -f docker-compose.tika.yml up -d")
        print("  - Ollama: docker-compose up -d ollama")
        print("  - File Ingestor: python file_ingestor.py")
        return False
    
    # Ejecutar pruebas
    tests = [
        ("Tipos soportados", test_supported_types),
        ("Ingesta de archivo", test_file_ingestion),
        ("Estadísticas", test_file_stats),
        ("Listado de archivos", test_list_files),
        ("Ingesta asíncrona", test_async_ingestion)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Error inesperado en {test_name}: {e}")
            results.append((test_name, False))
    
    # Resumen de resultados
    print("\n" + "=" * 60)
    print("📊 Resumen de pruebas:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{len(results)} pruebas pasaron")
    
    if passed == len(results):
        print("🎉 ¡Todas las pruebas pasaron! El sistema está funcionando correctamente.")
        return True
    else:
        print("⚠️ Algunas pruebas fallaron. Revisa los logs para más detalles.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


