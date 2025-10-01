#!/bin/bash

# Script de deployment para Sprint 3: Retries + Scheduler + DLQ
# Ejecutar desde la raíz del proyecto

set -e

echo "🚀 Deploying Sprint 3: Retries + Scheduler + DLQ"

# Variables
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
SERVICE_FILE="${PROJECT_DIR}/deploy/pulpo-job-scheduler.service"
SYSTEMD_DIR="/etc/systemd/system"

# 1. Ejecutar migraciones SQL
echo "🗄️  Ejecutando migraciones SQL..."
if [ -f "${PROJECT_DIR}/sql/06_retries_scheduler.sql" ]; then
    psql -d "${DATABASE_URL:-postgresql://localhost/pulpo}" -f "${PROJECT_DIR}/sql/06_retries_scheduler.sql"
    echo "✅ Migraciones SQL ejecutadas"
else
    echo "❌ Archivo de migraciones no encontrado"
    exit 1
fi

# 2. Verificar dependencias
echo "📋 Verificando dependencias..."
if ! $VENV_PYTHON -c "import anyio" 2>/dev/null; then
    echo "⚠️  anyio no encontrado. Instalando..."
    $VENV_PYTHON -m pip install anyio
else
    echo "✅ anyio encontrado"
fi

# 3. Configurar variables de entorno
echo "🔧 Configurando variables de entorno..."
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    echo "⚠️  Archivo .env no encontrado. Creando template..."
    cat > "${PROJECT_DIR}/.env" << EOF
# Database
DATABASE_URL=postgresql://localhost/pulpo

# Admin
ADMIN_TOKEN=tu-token-secreto-muy-largo-y-seguro

# OCR
OCR_MAX_CONCURRENCY=2
OCR_MAX_RETRIES=3
OCR_LOOP_INTERVAL=30
OCR_RUN_MODE=loop
TESSERACT_CMD=tesseract
TESSERACT_LANG=spa

# Scheduler
SCHEDULER_POLL_INTERVAL=5
SCHEDULER_MAX_CONCURRENCY=4

# RAG
RRF_K=60
TOPN_BM25=50
TOPN_VECTOR=50

# Micro-nits
MAX_QUERY_LEN=1024
MAX_TOP_K=50
METRICS_WS_LABEL=full
METRICS_PROTECTED=false
CORS_ALLOW_ORIGINS=*
EMB_CACHE_MAX=5000
EOF
    echo "✅ Template .env creado. ¡Configura las variables!"
else
    echo "✅ Archivo .env encontrado"
fi

# 4. Instalar servicio systemd del scheduler
echo "🔧 Instalando servicio systemd del scheduler..."
if [ -f "$SERVICE_FILE" ]; then
    sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
    sudo systemctl daemon-reload
    echo "✅ Servicio systemd del scheduler instalado"
else
    echo "❌ Archivo de servicio no encontrado: $SERVICE_FILE"
    exit 1
fi

# 5. Ejecutar tests
echo "🧪 Ejecutando tests..."
if [ -f "${PROJECT_DIR}/tests/test_sprint3_retries_scheduler.py" ]; then
    cd "$PROJECT_DIR"
    $VENV_PYTHON -m pytest tests/test_sprint3_retries_scheduler.py -v
    echo "✅ Tests ejecutados"
else
    echo "⚠️  Tests no encontrados, saltando..."
fi

# 6. Verificar endpoints
echo "🔍 Verificando endpoints..."
if command -v curl &> /dev/null; then
    # Test de estadísticas de jobs
    if curl -s -X GET "http://localhost:8003/admin/jobs/stats" \
       -H "X-Admin-Token: tu-token" | grep -q "job_stats"; then
        echo "✅ Endpoint /admin/jobs/stats funcionando"
    else
        echo "⚠️  Endpoint /admin/jobs/stats no responde (¿servicio corriendo?)"
    fi
    
    # Test de DLQ
    if curl -s -X GET "http://localhost:8003/admin/jobs/dlq" \
       -H "X-Admin-Token: tu-token" | grep -q "items"; then
        echo "✅ Endpoint /admin/jobs/dlq funcionando"
    else
        echo "⚠️  Endpoint /admin/jobs/dlq no responde"
    fi
else
    echo "⚠️  curl no encontrado, saltando verificación de endpoints"
fi

# 7. Mostrar comandos útiles
echo ""
echo "🎉 Sprint 3 deployado exitosamente!"
echo ""
echo "📋 Comandos útiles:"
echo "  # Iniciar scheduler de jobs"
echo "  sudo systemctl start pulpo-job-scheduler"
echo ""
echo "  # Ver logs del scheduler"
echo "  sudo journalctl -u pulpo-job-scheduler -f"
echo ""
echo "  # Verificar estado"
echo "  sudo systemctl status pulpo-job-scheduler"
echo ""
echo "  # Habilitar auto-start"
echo "  sudo systemctl enable pulpo-job-scheduler"
echo ""
echo "  # Estadísticas de jobs"
echo "  curl -X GET http://localhost:8003/admin/jobs/stats \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "  # Listar DLQ"
echo "  curl -X GET http://localhost:8003/admin/jobs/dlq \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "  # Requeue jobs fallidos"
echo "  curl -X POST http://localhost:8003/admin/jobs/requeue?job_type=ocr \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "  # Próximos jobs a ejecutar"
echo "  curl -X GET http://localhost:8003/admin/jobs/next \\"
echo "    -H 'X-Admin-Token: tu-token'"
echo ""
echo "🔧 Configuración:"
echo "  - Scheduler: systemd service con polling cada 5s"
echo "  - Backoff: exponencial con jitter (base=5s, factor=2.0)"
echo "  - DLQ: vista para jobs fallidos"
echo "  - Idempotencia: external_key único por job_type"
echo "  - Admin: endpoints para gestión completa"
echo ""
echo "📊 Monitoreo:"
echo "  - Logs: journalctl -u pulpo-job-scheduler"
echo "  - Stats: /admin/jobs/stats endpoint"
echo "  - DLQ: /admin/jobs/dlq endpoint"
echo "  - Métricas: /metrics endpoint"
echo ""
echo "🎯 Funcionalidades Sprint 3:"
echo "  ✅ Retries con backoff exponencial + jitter"
echo "  ✅ Scheduler genérico con polling eficiente"
echo "  ✅ Idempotencia con external_key"
echo "  ✅ DLQ (Dead Letter Queue) + requeue"
echo "  ✅ Métricas y observabilidad ampliadas"
echo "  ✅ Endpoints admin para gestión completa"
