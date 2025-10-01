#!/bin/bash

# Script para aplicar las migraciones de la nueva arquitectura
# Uso: ./scripts/apply-migrations.sh

set -e

echo "🚀 Aplicando migraciones de la nueva arquitectura PulpoAI..."

# Verificar que Docker esté corriendo
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker no está corriendo. Por favor inicia Docker primero."
    exit 1
fi

# Verificar que el contenedor de PostgreSQL esté corriendo
if ! docker ps | grep -q "pulpo-postgres"; then
    echo "❌ El contenedor de PostgreSQL no está corriendo. Ejecuta 'docker-compose -f docker-compose.integrated.yml up -d postgres' primero."
    exit 1
fi

# Aplicar migraciones
echo "📊 Aplicando migraciones de base de datos..."

docker exec -i pulpo-postgres psql -U pulpo -d pulpo < sql/00_all_up.sql

if [ $? -eq 0 ]; then
    echo "✅ Migraciones aplicadas exitosamente!"
else
    echo "❌ Error aplicando migraciones. Revisa los logs."
    exit 1
fi

# Verificar que las nuevas tablas se crearon correctamente
echo "🔍 Verificando nuevas tablas..."

TABLES=(
    "pulpo.vertical_packs"
    "pulpo.conversation_slots"
    "pulpo.conversation_flow_state"
    "pulpo.available_tools"
    "pulpo.intent_classifications"
    "pulpo.handoff_events"
)

for table in "${TABLES[@]}"; do
    if docker exec pulpo-postgres psql -U pulpo -d pulpo -c "\d $table" > /dev/null 2>&1; then
        echo "✅ Tabla $table creada correctamente"
    else
        echo "❌ Error: Tabla $table no encontrada"
        exit 1
    fi
done

# Verificar datos de ejemplo
echo "🔍 Verificando datos de ejemplo..."

VERTICAL_COUNT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM pulpo.vertical_packs WHERE workspace_id = '00000000-0000-0000-0000-000000000001';" | tr -d ' ')

if [ "$VERTICAL_COUNT" -ge 3 ]; then
    echo "✅ Vertical packs creados correctamente ($VERTICAL_COUNT packs)"
else
    echo "❌ Error: Solo se encontraron $VERTICAL_COUNT vertical packs (esperado: 3+)"
    exit 1
fi

TOOLS_COUNT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM pulpo.available_tools WHERE workspace_id = '00000000-0000-0000-0000-000000000001';" | tr -d ' ')

if [ "$TOOLS_COUNT" -ge 10 ]; then
    echo "✅ Herramientas creadas correctamente ($TOOLS_COUNT herramientas)"
else
    echo "❌ Error: Solo se encontraron $TOOLS_COUNT herramientas (esperado: 10+)"
    exit 1
fi

echo ""
echo "🎉 ¡Migraciones completadas exitosamente!"
echo ""
echo "📋 Resumen de la nueva arquitectura:"
echo "   • ✅ Vertical Packs (gastronomía, e-commerce, inmobiliaria)"
echo "   • ✅ Slot Manager para form filling"
echo "   • ✅ Policy Orchestrator para flujo de conversación"
echo "   • ✅ Handoff Controller para escalamiento humano"
echo "   • ✅ Router de intenciones con clasificación"
echo "   • ✅ Sistema de herramientas por vertical"
echo ""
echo "🔄 Próximos pasos:"
echo "   1. Importar el nuevo workflow de n8n: n8n-flow-improved.json"
echo "   2. Configurar las variables de entorno necesarias"
echo "   3. Probar el flujo con mensajes de ejemplo"
echo ""
echo "📚 Documentación disponible en: docs/readme.md"
