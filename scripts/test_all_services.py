#!/usr/bin/env python3
"""
Script para probar todos los servicios PulpoAI
"""
import requests
import time
import sys
from typing import Dict, Any

SERVICES = {
    "postgres": {"port": 5432, "type": "tcp"},
    "redis": {"port": 6379, "type": "tcp"},
    "ollama": {"port": 11434, "type": "http", "path": "/api/tags"},
    "orchestrator": {"port": 8005, "type": "http", "path": "/health"},
    "actions": {"port": 8006, "type": "http", "path": "/health"},
    "rag": {"port": 8007, "type": "http", "path": "/rag/health"},
    "n8n": {"port": 5678, "type": "http", "path": "/healthz"}
}

def test_service(name: str, config: Dict[str, Any]) -> bool:
    """Probar un servicio individual"""
    try:
        if config["type"] == "http":
            url = f"http://localhost:{config['port']}{config.get('path', '')}"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        elif config["type"] == "tcp":
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex(('localhost', config['port']))
            sock.close()
            return result == 0
        return False
    except Exception as e:
        print(f"❌ Error probando {name}: {e}")
        return False

def main():
    print("🧪 Probando servicios PulpoAI...")
    print("=" * 50)
    
    all_ok = True
    
    for name, config in SERVICES.items():
        print(f"🔍 Probando {name}...", end=" ")
        
        if test_service(name, config):
            print("✅ OK")
        else:
            print("❌ FALLO")
            all_ok = False
    
    print("=" * 50)
    
    if all_ok:
        print("🎉 ¡Todos los servicios están funcionando!")
        
        # Probar endpoints específicos
        print("\n🔬 Probando endpoints específicos...")
        
        # Probar Orchestrator
        try:
            response = requests.post(
                "http://localhost:8005/orchestrator/decide",
                json={
                    "conversation_id": "test-123",
                    "vertical": "gastronomia",
                    "user_input": "hola",
                    "greeted": False,
                    "slots": {},
                    "objective": "",
                    "last_action": None,
                    "attempts_count": 0
                },
                headers={
                    "X-Workspace-Id": "test-workspace",
                    "X-Request-Id": "test-request"
                },
                timeout=10
            )
            if response.status_code == 200:
                print("✅ Orchestrator responde correctamente")
            else:
                print(f"⚠️ Orchestrator responde con status {response.status_code}")
        except Exception as e:
            print(f"❌ Error probando Orchestrator: {e}")
        
        # Probar RAG
        try:
            response = requests.post(
                "http://localhost:8007/rag/search",
                json={
                    "query": "menú del día",
                    "workspace_id": "test-workspace"
                },
                headers={
                    "X-Workspace-Id": "test-workspace",
                    "X-Request-Id": "test-request"
                },
                timeout=10
            )
            if response.status_code == 200:
                print("✅ RAG Service responde correctamente")
            else:
                print(f"⚠️ RAG Service responde con status {response.status_code}")
        except Exception as e:
            print(f"❌ Error probando RAG: {e}")
        
        print("\n🚀 Sistema listo para usar!")
        print("📱 n8n: http://localhost:5678 (admin/admin123)")
        print("📊 Grafana: http://localhost:3000 (admin/admin123)")
        
    else:
        print("❌ Algunos servicios no están funcionando")
        print("🔍 Revisa los logs: docker-compose -f docker-compose.integrated.yml logs")
        sys.exit(1)

if __name__ == "__main__":
    main()
