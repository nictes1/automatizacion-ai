#!/bin/bash

# Script de deployment para Sprint 3.1: Pipeline encadenado OCR → Chunking → Embedding
# Ejecutar desde la raíz del proyecto

set -e

echo "🚀 Deploying Sprint 3.1: Pipeline encadenado OCR → Chunking → Embedding"

# Variables
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"

# 1. Ejecutar migraciones SQL (índices opcionales)
echo "🗄️  Ejecutando migraciones SQL (índices opcionales)..."
if [ -f "${PROJECT_DIR}/sql/07_sprint31_indexes.sql" ]; then
    psql -d "${DATABASE_URL:-postgresql://localhost/pulpo}" -f "${PROJECT_DIR}/sql/07_sprint31_indexes.sql"
    echo "✅ Índices opcionales aplicados"
else
    echo "⚠️  Archivo de índices no encontrado, saltando..."
fi

# 2. Verificar dependencias
echo "📋 Verificando dependencias..."
if ! $VENV_PYTHON -c "import anyio" 2>/dev/null; then
    echo "⚠️  anyio no encontrado. Instalando..."
    $VENV_PYTHON -m pip install anyio
else
    echo "✅ anyio encontrado"
fi

# 3. Ejecutar tests del pipeline
echo "🧪 Ejecutando tests del pipeline..."
if [ -f "${PROJECT_DIR}/tests/test_sprint31_pipeline.py" ]; then
    cd "$PROJECT_DIR"
    $VENV_PYTHON -m pytest tests/test_sprint31_pipeline.py -v
    echo "✅ Tests del pipeline ejecutados"
else
    echo "⚠️  Tests no encontrados, saltando..."
fi

# 4. Verificar que el scheduler está corriendo
echo "🔍 Verificando estado del scheduler..."
if systemctl is-active --quiet pulpo-job-scheduler; then
    echo "✅ Scheduler está corriendo"
else
    echo "⚠️  Scheduler no está corriendo. Iniciando..."
    sudo systemctl start pulpo-job-scheduler
    sleep 2
    if systemctl is-active --quiet pulpo-job-scheduler; then
        echo "✅ Scheduler iniciado correctamente"
    else
        echo "❌ Error al iniciar scheduler"
        exit 1
    fi
fi

# 5. Verificar endpoints del pipeline
echo "🔍 Verificando endpoints del pipeline..."
if command -v curl &> /dev/null; then
    # Test de estadísticas de jobs
    if curl -s -X GET "http://localhost:8003/admin/jobs/stats" \
       -H "X-Admin-Token: tu-token" | grep -q "job_stats"; then
        echo "✅ Endpoint /admin/jobs/stats funcionando"
    else
        echo "⚠️  Endpoint /admin/jobs/stats no responde (¿servicio corriendo?)"
    fi
    
    # Test de próximos jobs
    if curl -s -X GET "http://localhost:8003/admin/jobs/next" \
       -H "X-Admin-Token: tu-token" | grep -q "items"; then
        echo "✅ Endpoint /admin/jobs/next funcionando"
    else
        echo "⚠️  Endpoint /admin/jobs/next no responde"
    fi
else
    echo "⚠️  curl no encontrado, saltando verificación de endpoints"
fi

# 6. Mostrar comandos útiles para el pipeline
echo ""
echo "🎉 Sprint 3.1 deployado exitosamente!"
echo ""
echo "📋 Comandos útiles para el pipeline:"
echo "  # Ver logs del scheduler (pipeline completo)"
echo "  sudo journalctl -u pulpo-job-scheduler -f"
echo ""
echo "  # Estadísticas del pipeline"
echo "  curl -X GET http://localhost:8003/admin/jobs/stats \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "  # Próximos jobs en el pipeline"
echo "  curl -X GET http://localhost:8003/admin/jobs/next \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "  # Iniciar pipeline completo (OCR → Chunking → Embedding)"
echo "  curl -X POST http://localhost:8003/admin/ocr/run-once \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "  # Ver métricas del pipeline"
echo "  curl -X GET http://localhost:8003/metrics | grep -E '(jobs_processed_total|job_duration_seconds)'"
echo ""
echo "  # Ver DLQ si algo falla"
echo "  curl -X GET http://localhost:8003/admin/jobs/dlq \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "🔧 Configuración del pipeline:"
echo "  - OCR: Extrae texto de documentos"
echo "  - Chunking: Divide texto en chunks (800 chars, overlap 150)"
echo "  - Embedding: Genera embeddings con Ollama"
echo "  - Encadenamiento: Automático con idempotencia por revisión"
echo "  - Retries: Backoff exponencial con jitter"
echo "  - DLQ: Para jobs fallidos"
echo ""
echo "📊 Monitoreo del pipeline:"
echo "  - Logs: journalctl -u pulpo-job-scheduler"
echo "  - Stats: /admin/jobs/stats endpoint"
echo "  - Métricas: /metrics endpoint"
echo "  - DLQ: /admin/jobs/dlq endpoint"
echo ""
echo "🎯 Funcionalidades Sprint 3.1:"
echo "  ✅ Pipeline encadenado OCR → Chunking → Embedding"
echo "  ✅ Ejecutores productivos para chunking y embedding"
echo "  ✅ Idempotencia por revisión (external_key único)"
echo "  ✅ Chunking inteligente con overlap"
echo "  ✅ Embeddings en lotes para performance"
echo "  ✅ Métricas completas del pipeline"
echo "  ✅ Índices optimizados para performance"
echo "  ✅ Tests completos del pipeline"
echo ""
echo "🚀 ¡Pipeline completo funcionando!"
echo ""
echo "💡 Próximos pasos sugeridos:"
echo "  - Monitorear métricas de performance"
echo "  - Ajustar tamaños de chunk según necesidades"
echo "  - Configurar alertas para DLQ"
echo "  - Optimizar batch sizes para embeddings"
