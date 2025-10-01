#!/bin/bash

# Script para probar la nueva arquitectura mejorada
# Uso: ./scripts/test-improved-architecture.sh

set -e

echo "🧪 Probando la nueva arquitectura PulpoAI..."

# Verificar que Docker esté corriendo
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker no está corriendo. Por favor inicia Docker primero."
    exit 1
fi

# Verificar que el contenedor de PostgreSQL esté corriendo
if ! docker ps | grep -q "pulpo-postgres"; then
    echo "❌ El contenedor de PostgreSQL no está corriendo."
    exit 1
fi

echo "🔍 Verificando estructura de base de datos..."

# Verificar que las nuevas tablas existen
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
        echo "✅ Tabla $table existe"
    else
        echo "❌ Tabla $table no encontrada"
        exit 1
    fi
done

echo ""
echo "🔍 Verificando datos de ejemplo..."

# Verificar vertical packs
VERTICALS=("gastronomia" "ecommerce" "inmobiliaria")
for vertical in "${VERTICALS[@]}"; do
    COUNT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM pulpo.vertical_packs WHERE vertical = '$vertical' AND workspace_id = '00000000-0000-0000-0000-000000000001';" | tr -d ' ')
    if [ "$COUNT" -eq 1 ]; then
        echo "✅ Vertical pack '$vertical' configurado correctamente"
    else
        echo "❌ Error: Vertical pack '$vertical' no encontrado o duplicado"
        exit 1
    fi
done

# Verificar herramientas
TOOLS_COUNT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM pulpo.available_tools WHERE workspace_id = '00000000-0000-0000-0000-000000000001';" | tr -d ' ')
if [ "$TOOLS_COUNT" -ge 10 ]; then
    echo "✅ $TOOLS_COUNT herramientas configuradas"
else
    echo "❌ Error: Solo $TOOLS_COUNT herramientas encontradas (esperado: 10+)"
    exit 1
fi

echo ""
echo "🧪 Probando funciones de base de datos..."

# Probar función de vertical pack
echo "📦 Probando get_vertical_pack_config..."
RESULT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT pulpo.get_vertical_pack_config('00000000-0000-0000-0000-000000000001', 'gastronomia');" | head -1)
if [[ $RESULT == *"gastronomia"* ]]; then
    echo "✅ Función get_vertical_pack_config funciona correctamente"
else
    echo "❌ Error en get_vertical_pack_config"
    exit 1
fi

# Probar función de herramientas
echo "🛠️ Probando get_available_tools..."
TOOLS_RESULT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM pulpo.get_available_tools('00000000-0000-0000-0000-000000000001', 'gastronomia');" | tr -d ' ')
if [ "$TOOLS_RESULT" -ge 4 ]; then
    echo "✅ Función get_available_tools funciona correctamente ($TOOLS_RESULT herramientas para gastronomía)"
else
    echo "❌ Error en get_available_tools"
    exit 1
fi

echo ""
echo "🧪 Probando flujo de slots..."

# Simular inicialización de slots
echo "📝 Probando init_conversation_slots..."
SLOT_RESULT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT pulpo.init_conversation_slots('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000c0', 'take_order', '[\"product\", \"quantity\", \"name\", \"phone\"]'::jsonb);" | head -1)
if [[ $SLOT_RESULT == *"00000000"* ]]; then
    echo "✅ Función init_conversation_slots funciona correctamente"
else
    echo "❌ Error en init_conversation_slots"
    exit 1
fi

# Probar actualización de slots
echo "🔄 Probando update_conversation_slots..."
UPDATE_RESULT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT pulpo.update_conversation_slots('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000c0', 'take_order', 'product', 'Pizza Margherita');" | head -1)
if [[ $UPDATE_RESULT == *"00000000"* ]]; then
    echo "✅ Función update_conversation_slots funciona correctamente"
else
    echo "❌ Error en update_conversation_slots"
    exit 1
fi

echo ""
echo "🧪 Probando handoff controller..."

# Probar función de handoff
echo "🚨 Probando should_handoff..."
HANDOFF_RESULT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT pulpo.should_handoff('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-0000000000c0', 'take_order', 0.5, '{}'::jsonb);" | head -1)
if [[ $HANDOFF_RESULT == *"true"* ]]; then
    echo "✅ Función should_handoff detecta confianza baja correctamente"
else
    echo "❌ Error en should_handoff"
    exit 1
fi

echo ""
echo "🧪 Probando RLS (Row Level Security)..."

# Probar aislamiento por workspace
echo "🔒 Probando aislamiento de workspace..."
docker exec pulpo-postgres psql -U pulpo -d pulpo -c "SELECT pulpo.set_ws_context('00000000-0000-0000-0000-000000000001');" > /dev/null 2>&1
WS_COUNT=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "SELECT COUNT(*) FROM pulpo.vertical_packs;" | tr -d ' ')
if [ "$WS_COUNT" -eq 3 ]; then
    echo "✅ RLS funciona correctamente (3 vertical packs visibles para workspace de prueba)"
else
    echo "❌ Error en RLS: $WS_COUNT vertical packs visibles (esperado: 3)"
    exit 1
fi

echo ""
echo "🧪 Probando workflow de n8n..."

# Verificar que el archivo de workflow existe
if [ -f "n8n-flow-improved.json" ]; then
    echo "✅ Archivo n8n-flow-improved.json existe"
    
    # Verificar que es un JSON válido
    if python3 -m json.tool n8n-flow-improved.json > /dev/null 2>&1; then
        echo "✅ Archivo n8n-flow-improved.json es JSON válido"
    else
        echo "❌ Error: n8n-flow-improved.json no es JSON válido"
        exit 1
    fi
    
    # Verificar que tiene los nodos principales
    NODES=("webhook-inbound" "intent-router" "check-handoff" "get-tools" "generate-response")
    for node in "${NODES[@]}"; do
        if grep -q "\"id\": \"$node\"" n8n-flow-improved.json; then
            echo "✅ Nodo '$node' encontrado en workflow"
        else
            echo "❌ Error: Nodo '$node' no encontrado en workflow"
            exit 1
        fi
    done
else
    echo "❌ Archivo n8n-flow-improved.json no encontrado"
    exit 1
fi

echo ""
echo "🎉 ¡Todas las pruebas pasaron exitosamente!"
echo ""
echo "📋 Resumen de pruebas:"
echo "   ✅ Estructura de base de datos"
echo "   ✅ Datos de ejemplo (vertical packs y herramientas)"
echo "   ✅ Funciones de base de datos"
echo "   ✅ Flujo de slots"
echo "   ✅ Handoff controller"
echo "   ✅ Row Level Security (RLS)"
echo "   ✅ Workflow de n8n"
echo ""
echo "🚀 La nueva arquitectura está lista para usar!"
echo ""
echo "📝 Próximos pasos:"
echo "   1. Importar n8n-flow-improved.json en n8n"
echo "   2. Configurar variables de entorno (TWILIO_ACCOUNT_SID, etc.)"
echo "   3. Probar con mensajes reales"
echo "   4. Monitorear logs y métricas"
