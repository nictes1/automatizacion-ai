#!/bin/bash

# =====================================================
# PULPOAI DATABASE RESET SCRIPT
# =====================================================
# Script simple para reinicializar la base de datos
# usando los archivos existentes en database/init/
# =====================================================

set -e

echo "🔄 Reinicializando base de datos de PulpoAI..."
echo "📁 Usando archivos existentes en database/init/"

# Verificar que Docker esté corriendo
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker no está corriendo. Por favor inicia Docker primero."
    exit 1
fi

echo "🛑 Deteniendo servicios dependientes..."
docker-compose stop pulpo-app n8n || true

echo "🗑️ Eliminando volúmenes de PostgreSQL..."
docker-compose down postgres
docker volume rm pulpo_postgres_data 2>/dev/null || true

echo "🚀 Iniciando PostgreSQL con schema limpio..."
docker-compose up -d postgres

echo "⏳ Esperando que PostgreSQL esté listo..."
sleep 15

# Verificar que PostgreSQL esté funcionando
echo "🔍 Verificando conexión a PostgreSQL..."
for i in {1..30}; do
    if docker exec pulpo-postgres pg_isready -U pulpo -d pulpo > /dev/null 2>&1; then
        echo "✅ PostgreSQL está listo!"
        break
    fi
    echo "⏳ Esperando PostgreSQL... ($i/30)"
    sleep 2
done

# Verificar que las tablas se crearon correctamente
echo "🔍 Verificando inicialización del schema..."
TABLES_COUNT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'pulpo';" | tr -d ' ')

if [ "$TABLES_COUNT" -gt 0 ]; then
    echo "✅ Schema inicializado correctamente ($TABLES_COUNT tablas creadas)"
else
    echo "❌ Error: No se crearon tablas en el schema pulpo"
    exit 1
fi

# Verificar funciones
echo "🔍 Verificando funciones..."
FUNCTIONS_COUNT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema = 'pulpo';" | tr -d ' ')

if [ "$FUNCTIONS_COUNT" -gt 0 ]; then
    echo "✅ Funciones creadas correctamente ($FUNCTIONS_COUNT funciones)"
else
    echo "❌ Error: No se crearon funciones en el schema pulpo"
    exit 1
fi

echo ""
echo "🎉 ¡Base de datos reinicializada exitosamente!"
echo ""
echo "📋 Próximos pasos:"
echo "   1. Reiniciar servicios: docker-compose up -d"
echo "   2. Verificar que n8n esté funcionando"
echo "   3. Probar el webhook de Twilio"
echo ""
echo "🔗 URLs importantes:"
echo "   - n8n: http://localhost:5678"
echo "   - PostgreSQL: localhost:5432"
echo "   - Webhook: https://6752146d9dd8.ngrok-free.app/webhook/pulpo/twilio/wa/inbound"

