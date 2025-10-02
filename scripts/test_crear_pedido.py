#!/usr/bin/env python3
"""
Script para probar la acción crear_pedido con items reales del catálogo
"""
import requests
import json
import time

# URLs de los servicios
ACTIONS_URL = "http://localhost:8006"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440000"
CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440005"

def test_crear_pedido_exitoso():
    """Probar creación de pedido exitoso con items del catálogo"""
    print("\n🍕 Test 1: Crear pedido exitoso")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "crear_pedido",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "items": [
                {"nombre": "Empanada de Carne", "cantidad": 6},
                {"nombre": "Pizza Muzzarella", "cantidad": 1},
                {"nombre": "Coca Cola 1.5L", "cantidad": 2}
            ],
            "metodo_entrega": "retira"
        },
        "idempotency_key": f"test-pedido-{int(time.time())}"
    }

    print("📦 Pedido:")
    for item in action_payload["payload"]["items"]:
        print(f"  - {item['cantidad']}x {item['nombre']}")
    print(f"  Método: {action_payload['payload']['metodo_entrega']}")

    response = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code in [200, 202]:
        result = response.json()
        print(f"\n✅ Pedido creado exitosamente!")
        print(f"  Estado: {result['status']}")
        print(f"  Resumen: {result['summary']}")
        print(f"  Action ID: {result['action_id']}")

        if 'details' in result:
            details = result['details']
            if 'total' in details:
                print(f"  Total: ${details['total']}")
            if 'items' in details:
                print(f"  Items procesados: {len(details['items'])}")
                for item in details['items']:
                    print(f"    - {item['cantidad']}x {item['nombre']} = ${item['subtotal']}")
            if 'eta_minutes' in details:
                print(f"  ETA: {details['eta_minutes']} minutos")

        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False

def test_crear_pedido_con_delivery():
    """Probar creación de pedido con delivery"""
    print("\n🚚 Test 2: Crear pedido con delivery")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "crear_pedido",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "items": [
                {"nombre": "Milanesa con Papas Fritas", "cantidad": 2},
                {"nombre": "Flan Casero con Dulce de Leche", "cantidad": 2}
            ],
            "metodo_entrega": "envio",
            "direccion": "Av. Corrientes 1234, CABA"
        },
        "idempotency_key": f"test-delivery-{int(time.time())}"
    }

    print("📦 Pedido con delivery:")
    for item in action_payload["payload"]["items"]:
        print(f"  - {item['cantidad']}x {item['nombre']}")
    print(f"  Dirección: {action_payload['payload']['direccion']}")

    response = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code in [200, 202]:
        result = response.json()
        print(f"\n✅ Pedido con delivery creado!")
        print(f"  Estado: {result['status']}")
        print(f"  Resumen: {result['summary']}")

        if 'details' in result and 'total' in result['details']:
            print(f"  Total: ${result['details']['total']}")

        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False

def test_crear_pedido_item_inexistente():
    """Probar creación de pedido con item que no existe en catálogo"""
    print("\n❌ Test 3: Pedido con item inexistente (debe fallar)")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "crear_pedido",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "items": [
                {"nombre": "Sushi de Salmon", "cantidad": 1}  # No existe en catálogo
            ],
            "metodo_entrega": "retira"
        },
        "idempotency_key": f"test-noexiste-{int(time.time())}"
    }

    print("📦 Pedido:")
    for item in action_payload["payload"]["items"]:
        print(f"  - {item['cantidad']}x {item['nombre']} (NO EXISTE)")

    response = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code in [200, 202]:
        result = response.json()
        if result['status'] == 'failed':
            print(f"\n✅ Falló correctamente!")
            print(f"  Estado: {result['status']}")
            print(f"  Resumen: {result['summary']}")
            return True
        else:
            print(f"❌ Debería haber fallado pero tuvo éxito")
            return False
    else:
        print(f"❌ Error inesperado: {response.status_code}")
        return False

def test_idempotencia():
    """Probar que la idempotencia funciona (mismo request = mismo resultado)"""
    print("\n🔄 Test 4: Idempotencia (mismo request 2 veces)")
    print("=" * 60)

    idempotency_key = f"test-idempotent-{int(time.time())}"

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "crear_pedido",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "items": [
                {"nombre": "Pizza Napolitana", "cantidad": 1}
            ],
            "metodo_entrega": "retira"
        },
        "idempotency_key": idempotency_key
    }

    print("📦 Primera solicitud...")
    response1 = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response1.status_code not in [200, 202]:
        print(f"❌ Primera solicitud falló: {response1.status_code}")
        return False

    result1 = response1.json()
    action_id_1 = result1['action_id']
    print(f"  Action ID: {action_id_1}")

    time.sleep(1)

    print("\n📦 Segunda solicitud (misma idempotency key)...")
    response2 = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response2.status_code not in [200, 202]:
        print(f"❌ Segunda solicitud falló: {response2.status_code}")
        return False

    result2 = response2.json()
    action_id_2 = result2['action_id']
    print(f"  Action ID: {action_id_2}")

    if action_id_1 == action_id_2:
        print(f"\n✅ Idempotencia funciona! Mismo action_id en ambas solicitudes")
        return True
    else:
        print(f"\n❌ Idempotencia falló: diferentes action_ids")
        return False

def main():
    print("🚀 Probando Actions Service - crear_pedido")
    print("=" * 60)

    tests = [
        ("Pedido exitoso", test_crear_pedido_exitoso),
        ("Pedido con delivery", test_crear_pedido_con_delivery),
        ("Item inexistente", test_crear_pedido_item_inexistente),
        ("Idempotencia", test_idempotencia)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' falló con excepción: {e}")
            results.append((name, False))

        time.sleep(1)  # Pausa entre tests

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
        print("\n🎉 ¡Todos los tests pasaron!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - passed} test(s) fallaron")
        return 1

if __name__ == "__main__":
    exit(main())
