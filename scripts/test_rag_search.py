#!/usr/bin/env python3
"""
Script para probar RAG Service con embeddings reales
"""
import requests
import json

# URLs de los servicios
RAG_URL = "http://localhost:8007"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"

def test_rag_search(query: str, expected_results: int = None):
    """Probar búsqueda RAG"""
    print(f"\n🔍 Consulta: '{query}'")
    print("=" * 60)

    search_payload = {
        "query": query,
        "workspace_id": WORKSPACE_ID,
        "limit": 5
    }

    response = requests.post(
        f"{RAG_URL}/rag/search",
        json=search_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code == 200:
        result = response.json()
        total = result['total']
        results = result['results']

        print(f"✅ Encontrados: {total} resultados")

        if total > 0:
            for i, item in enumerate(results, 1):
                print(f"\n📄 Resultado {i}:")
                print(f"   Fuente: {item['source']}")
                print(f"   Score: {item['score']:.4f}")
                print(f"   Contenido: {item['content'][:200]}...")
                print(f"   Metadata: {item.get('metadata', {})}")

        if expected_results is not None:
            if total >= expected_results:
                print(f"\n✅ Test PASS: Encontró al menos {expected_results} resultados")
                return True
            else:
                print(f"\n❌ Test FAIL: Esperaba al menos {expected_results} resultados, encontró {total}")
                return False
        else:
            return total > 0
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False

def main():
    print("🚀 Probando RAG Service con embeddings reales")
    print("=" * 60)

    tests = [
        {
            "name": "Búsqueda de platos de pescado",
            "query": "platos de pescado",
            "expected": 1
        },
        {
            "name": "Búsqueda de empanadas",
            "query": "empanadas de carne",
            "expected": 1
        },
        {
            "name": "Búsqueda de precios",
            "query": "¿cuánto cuestan los platos?",
            "expected": 1
        },
        {
            "name": "Búsqueda de horarios",
            "query": "horarios de atención",
            "expected": 1
        },
        {
            "name": "Búsqueda de menú completo",
            "query": "menú del restaurante",
            "expected": 1
        }
    ]

    results = []
    for test in tests:
        try:
            result = test_rag_search(test["query"], test["expected"])
            results.append((test["name"], result))
        except Exception as e:
            print(f"\n❌ Test '{test['name']}' falló con excepción: {e}")
            results.append((test["name"], False))

    print("\n" + "=" * 60)
    print("📊 RESULTADOS")
    print("=" * 60)

    passed = 0
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
        if result:
            passed += 1

    print(f"\nTotal: {passed}/{len(results)} tests pasados")

    if passed == len(results):
        print("\n🎉 ¡Todos los tests de RAG pasaron!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) fallaron")
        return 1

if __name__ == "__main__":
    exit(main())
