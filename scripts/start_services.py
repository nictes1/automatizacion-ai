#!/usr/bin/env python3
"""
Script para iniciar todos los servicios del sistema PulpoAI
"""

import os
import sys
import subprocess
import time
import signal
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de servicios
SERVICES = [
    {
        "name": "API de Menús",
        "script": "services/menu_api.py",
        "port": 8002,
        "description": "API para gestión de menús gastronómicos"
    },
    {
        "name": "API RAG Query",
        "script": "services/rag_query_api.py", 
        "port": 8003,
        "description": "API para consultas RAG del LLM"
    }
]

# Procesos en ejecución
running_processes = []

def check_port(port):
    """Verifica si un puerto está en uso"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_service(service):
    """Inicia un servicio"""
    
    print(f"🚀 Iniciando {service['name']}...")
    
    # Verificar si el puerto está en uso
    if check_port(service['port']):
        print(f"⚠️  Puerto {service['port']} ya está en uso")
        return None
    
    # Verificar que el script existe
    script_path = Path(service['script'])
    if not script_path.exists():
        print(f"❌ Script no encontrado: {script_path}")
        return None
    
    try:
        # Iniciar el proceso
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Esperar un poco para verificar que se inició correctamente
        time.sleep(2)
        
        if process.poll() is None:
            print(f"✅ {service['name']} iniciado en puerto {service['port']}")
            print(f"   📄 {service['description']}")
            return process
        else:
            stdout, stderr = process.communicate()
            print(f"❌ Error iniciando {service['name']}")
            print(f"   Salida: {stdout}")
            print(f"   Error: {stderr}")
            return None
            
    except Exception as e:
        print(f"❌ Error iniciando {service['name']}: {e}")
        return None

def stop_services():
    """Detiene todos los servicios"""
    
    print("\n🛑 Deteniendo servicios...")
    
    for process in running_processes:
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ Servicio detenido")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"⚠️  Servicio terminado forzadamente")
            except Exception as e:
                print(f"❌ Error deteniendo servicio: {e}")

def signal_handler(signum, frame):
    """Maneja señales de interrupción"""
    print("\n\n🛑 Recibida señal de interrupción...")
    stop_services()
    sys.exit(0)

def check_dependencies():
    """Verifica dependencias del sistema"""
    
    print("🔍 Verificando dependencias...")
    
    # Verificar variables de entorno
    required_env = ['DATABASE_URL', 'OLLAMA_URL', 'WEAVIATE_URL']
    missing_env = []
    
    for env_var in required_env:
        if not os.getenv(env_var):
            missing_env.append(env_var)
    
    if missing_env:
        print(f"❌ Variables de entorno faltantes: {', '.join(missing_env)}")
        print("💡 Asegúrate de tener un archivo .env configurado")
        return False
    
    # Verificar archivos necesarios
    required_files = [
        "services/menu_api.py",
        "services/rag_query_api.py",
        "examples/menu_completo.txt"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print(f"❌ Archivos faltantes: {', '.join(missing_files)}")
        return False
    
    print("✅ Dependencias verificadas")
    return True

def main():
    """Función principal"""
    
    print("🚀 Iniciador de Servicios PulpoAI")
    print("=" * 50)
    
    # Configurar manejo de señales
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Verificar dependencias
    if not check_dependencies():
        return False
    
    # Iniciar servicios
    print("\n🚀 Iniciando servicios...")
    
    for service in SERVICES:
        process = start_service(service)
        if process:
            running_processes.append(process)
        else:
            print(f"❌ No se pudo iniciar {service['name']}")
            stop_services()
            return False
    
    if not running_processes:
        print("❌ No se pudo iniciar ningún servicio")
        return False
    
    # Mostrar estado
    print(f"\n✅ {len(running_processes)} servicios iniciados correctamente")
    print("\n📋 Servicios en ejecución:")
    for i, service in enumerate(SERVICES, 1):
        if i <= len(running_processes):
            print(f"   {i}. {service['name']} - http://localhost:{service['port']}")
    
    print("\n💡 Para probar el sistema:")
    print("   python scripts/test_complete_system.py")
    print("   python scripts/load_menu_seed.py")
    
    print("\n⏳ Presiona Ctrl+C para detener todos los servicios")
    
    # Mantener servicios ejecutándose
    try:
        while True:
            time.sleep(1)
            
            # Verificar que los procesos sigan ejecutándose
            for i, process in enumerate(running_processes):
                if process.poll() is not None:
                    print(f"❌ Servicio {SERVICES[i]['name']} se detuvo inesperadamente")
                    stop_services()
                    return False
                    
    except KeyboardInterrupt:
        print("\n\n🛑 Interrupción del usuario")
        stop_services()
        return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

