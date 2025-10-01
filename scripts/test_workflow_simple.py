#!/usr/bin/env python3
"""
Test simple del workflow F-08
Solo verifica que n8n esté funcionando y pueda recibir webhooks
"""

import requests
import json
import time
import sys

def test_n8n_webhook():
    """Test básico del webhook de n8n"""
    print("🧪 Test Simple del Workflow F-08")
    print("=" * 40)
    
    # URL del webhook
    webhook_url = "http://localhost:5678/webhook/pulpo/twilio/wa/inbound"
    
    # Datos de prueba (simulando Twilio)
    test_data = {
        "Body": "hola, quiero hacer un pedido",
        "From": "whatsapp:+5491111111111",
        "To": "whatsapp:+14155238886",
        "SmsSid": f"SM_test_{int(time.time())}",
        "WorkspaceId": "00000000-0000-0000-0000-000000000001"
    }
    
    print(f"📤 Enviando webhook a: {webhook_url}")
    print(f"📝 Datos: {json.dumps(test_data, indent=2)}")
    
    try:
        # Enviar request
        response = requests.post(
            webhook_url,
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"📊 Status Code: {response.status_code}")
        print(f"📊 Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            print("✅ Webhook respondió correctamente")
            return True
        else:
            print(f"❌ Webhook falló con status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ No se pudo conectar a n8n. ¿Está corriendo en localhost:5678?")
        return False
    except requests.exceptions.Timeout:
        print("❌ Timeout esperando respuesta de n8n")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

def test_n8n_health():
    """Test de salud de n8n"""
    print("\n🏥 Verificando salud de n8n...")
    
    try:
        response = requests.get("http://localhost:5678", timeout=5)
        if response.status_code == 200:
            print("✅ n8n está respondiendo")
            return True
        else:
            print(f"❌ n8n respondió con status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ No se pudo conectar a n8n: {e}")
        return False

def main():
    """Función principal"""
    print("🚀 Iniciando test simple del workflow F-08")
    
    # Test 1: Salud de n8n
    if not test_n8n_health():
        print("\n❌ n8n no está funcionando. Verifica que esté corriendo.")
        sys.exit(1)
    
    # Test 2: Webhook
    if test_n8n_webhook():
        print("\n🎉 ¡Test completado exitosamente!")
        print("\n📋 Próximos pasos:")
        print("   1. Importa el workflow n8n/n8n-workflow-f08-fixed.json en n8n")
        print("   2. Configura los headers HTTP según CHECKLIST_N8N_F08.md")
        print("   3. Ejecuta el smoke test completo: ./scripts/smoke_test_f08.sh")
    else:
        print("\n❌ Test falló. Revisa la configuración de n8n.")
        sys.exit(1)

if __name__ == "__main__":
    main()
