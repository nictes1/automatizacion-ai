#!/bin/bash

echo "🚀 Iniciando servicios PulpoAI..."

# Limpiar contenedores anteriores
echo "🧹 Limpiando contenedores anteriores..."
docker-compose -f docker-compose.integrated.yml down --volumes

# Construir imágenes
echo "🔨 Construyendo imágenes..."
docker-compose -f docker-compose.integrated.yml build

# Iniciar servicios base
echo "📦 Iniciando servicios base..."
docker-compose -f docker-compose.integrated.yml up -d postgres redis ollama

# Esperar a que PostgreSQL esté listo
echo "⏳ Esperando a que PostgreSQL esté listo..."
sleep 10

# Iniciar servicios de aplicación
echo "🤖 Iniciando servicios de aplicación..."
docker-compose -f docker-compose.integrated.yml up -d orchestrator actions rag

# Esperar un poco más
echo "⏳ Esperando a que los servicios estén listos..."
sleep 5

# Iniciar n8n
echo "🔄 Iniciando n8n..."
docker-compose -f docker-compose.integrated.yml up -d n8n

echo "✅ Servicios iniciados!"
echo ""
echo "📊 Servicios disponibles:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo "  - Ollama: localhost:11434"
echo "  - Orchestrator: localhost:8005"
echo "  - Actions: localhost:8006"
echo "  - RAG: localhost:8007"
echo "  - n8n: localhost:5678 (admin/admin123)"
echo ""
echo "🔍 Para ver logs: docker-compose -f docker-compose.integrated.yml logs -f"
echo "🛑 Para parar: docker-compose -f docker-compose.integrated.yml down"
