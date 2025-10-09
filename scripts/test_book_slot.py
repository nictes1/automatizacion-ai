#!/usr/bin/env python3
"""
Script para probar la acción book_slot (reservar turno de peluquería)
"""
import requests
import json
import time

# URLs de los servicios
ACTIONS_URL = "http://localhost:8006"
WORKSPACE_ID = "550e8400-e29b-41d4-a716-446655440003"  # Estilo Peluquería & Spa (servicios)
CONVERSATION_ID = "550e8400-e29b-41d4-a716-446655440006"

def test_book_slot_exitoso():
    """Probar reserva de turno exitoso con todos los campos"""
    print("\n💇 Test 1: Reservar turno exitoso")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "book_slot",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "service_type": "Corte de Cabello",  # Nombre exacto de la BD
            "preferred_date": "2025-10-15",
            "preferred_time": "14:30",
            "client_name": "Juan Pérez",
            "client_email": "juan.perez@example.com",
            "client_phone": "+54 11 4567-8901"
        },
        "idempotency_key": f"test-turno-{int(time.time())}"
    }

    print("📋 Reserva:")
    print(f"  Servicio: {action_payload['payload']['service_type']}")
    print(f"  Fecha: {action_payload['payload']['preferred_date']}")
    print(f"  Hora: {action_payload['payload']['preferred_time']}")
    print(f"  Cliente: {action_payload['payload']['client_name']}")
    print(f"  Email: {action_payload['payload']['client_email']}")
    print(f"  Teléfono: {action_payload['payload']['client_phone']}")

    response = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code in [200, 202]:
        result = response.json()
        print(f"\n✅ Turno reservado exitosamente!")
        print(f"  Estado: {result['status']}")
        print(f"  Resumen: {result['summary']}")
        print(f"  Action ID: {result['action_id']}")

        if 'details' in result:
            details = result['details']
            print(f"  Reserva ID: {details.get('reserva_id')}")
            print(f"  Servicio: {details.get('service_type')}")
            print(f"  Fecha: {details.get('preferred_date')}")
            print(f"  Hora: {details.get('preferred_time')}")
            print(f"  Cliente: {details.get('client_name')}")
            print(f"  Estado: {details.get('status')}")

        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False

def test_book_slot_sin_email():
    """Probar reserva de turno sin email (campo opcional)"""
    print("\n💇 Test 2: Reservar turno sin email")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "book_slot",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "service_type": "Coloración",  # Servicio en la BD
            "preferred_date": "2025-10-16",
            "preferred_time": "10:00",
            "client_name": "María González",
            "client_phone": "+54 11 9876-5432"
        },
        "idempotency_key": f"test-turno-noemail-{int(time.time())}"
    }

    print("📋 Reserva:")
    print(f"  Servicio: {action_payload['payload']['service_type']}")
    print(f"  Fecha: {action_payload['payload']['preferred_date']}")
    print(f"  Hora: {action_payload['payload']['preferred_time']}")
    print(f"  Cliente: {action_payload['payload']['client_name']}")
    print(f"  Email: (no proporcionado)")
    print(f"  Teléfono: {action_payload['payload']['client_phone']}")

    response = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code in [200, 202]:
        result = response.json()
        print(f"\n✅ Turno reservado exitosamente!")
        print(f"  Estado: {result['status']}")
        print(f"  Resumen: {result['summary']}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False

def test_book_slot_sin_telefono():
    """Probar reserva de turno sin teléfono (campo opcional)"""
    print("\n💇 Test 3: Reservar turno sin teléfono")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "book_slot",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "service_type": "Barba",  # Servicio en la BD
            "preferred_date": "2025-10-17",
            "preferred_time": "15:00",
            "client_name": "Ana López",
            "client_email": "ana.lopez@example.com"
        },
        "idempotency_key": f"test-turno-notel-{int(time.time())}"
    }

    print("📋 Reserva:")
    print(f"  Servicio: {action_payload['payload']['service_type']}")
    print(f"  Cliente: {action_payload['payload']['client_name']}")
    print(f"  Email: {action_payload['payload']['client_email']}")
    print(f"  Teléfono: (no proporcionado)")

    response = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code in [200, 202]:
        result = response.json()
        print(f"\n✅ Turno reservado exitosamente!")
        print(f"  Estado: {result['status']}")
        print(f"  Resumen: {result['summary']}")
        return True
    else:
        print(f"❌ Error: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False

def test_book_slot_sin_campos_obligatorios():
    """Probar reserva sin campos obligatorios (debe fallar con 422)"""
    print("\n❌ Test 4: Reservar turno sin campos obligatorios (debe fallar)")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "book_slot",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "service_type": "Corte de Cabello",
            # Faltan: preferred_date, preferred_time, client_name
        },
        "idempotency_key": f"test-turno-incompleto-{int(time.time())}"
    }

    print("📋 Reserva incompleta (faltan campos obligatorios)")

    response = requests.post(
        f"{ACTIONS_URL}/tools/execute_action",
        json=action_payload,
        headers={"X-Workspace-Id": WORKSPACE_ID},
        timeout=10
    )

    if response.status_code == 422:
        print(f"\n✅ Falló correctamente con 422 Unprocessable Entity!")
        print(f"   Respuesta: {response.json()}")
        return True
    else:
        print(f"❌ Debería haber fallado con 422, pero obtuvo: {response.status_code}")
        print(f"   Respuesta: {response.text}")
        return False

def test_book_slot_servicio_inexistente():
    """Probar reserva con servicio que no existe (debe fallar)"""
    print("\n❌ Test 5: Reservar turno con servicio inexistente (debe fallar)")
    print("=" * 60)

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "book_slot",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "service_type": "servicio_que_no_existe",
            "preferred_date": "2025-10-18",
            "preferred_time": "11:00",
            "client_name": "Pedro Ramírez",
            "client_email": "pedro@example.com"
        },
        "idempotency_key": f"test-turno-noexiste-{int(time.time())}"
    }

    print("📋 Reserva con servicio inexistente")

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
        print(f"   Respuesta: {response.text}")
        return False

def test_idempotencia():
    """Probar que la idempotencia funciona (mismo request = mismo resultado)"""
    print("\n🔄 Test 6: Idempotencia (mismo request 2 veces)")
    print("=" * 60)

    idempotency_key = f"test-idempotent-turno-{int(time.time())}"

    action_payload = {
        "conversation_id": CONVERSATION_ID,
        "action_name": "book_slot",
        "payload": {
            "workspace_id": WORKSPACE_ID,
            "conversation_id": CONVERSATION_ID,
            "service_type": "Corte de Cabello",
            "preferred_date": "2025-10-20",
            "preferred_time": "16:00",
            "client_name": "Carlos Martínez",
            "client_email": "carlos@example.com"
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
        print(f"   Respuesta: {response1.text}")
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
    print("🚀 Probando Actions Service - book_slot")
    print("=" * 60)

    tests = [
        ("Turno exitoso con todos los campos", test_book_slot_exitoso),
        ("Turno sin email", test_book_slot_sin_email),
        ("Turno sin teléfono", test_book_slot_sin_telefono),
        ("Turno sin campos obligatorios", test_book_slot_sin_campos_obligatorios),
        ("Servicio inexistente", test_book_slot_servicio_inexistente),
        ("Idempotencia", test_idempotencia)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' falló con excepción: {e}")
            import traceback
            traceback.print_exc()
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

