#!/bin/bash

# Script de deployment para Sprint 2: OCR + Métricas
# Ejecutar desde la raíz del proyecto

set -e

echo "🚀 Deploying Sprint 2: OCR + Prometheus Metrics"

# Variables
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python"
SERVICE_FILE="${PROJECT_DIR}/deploy/pulpo-ocr-worker.service"
SYSTEMD_DIR="/etc/systemd/system"

# 1. Verificar dependencias
echo "📋 Verificando dependencias..."

# Verificar Tesseract
if ! command -v tesseract &> /dev/null; then
    echo "⚠️  Tesseract no encontrado. Instalando..."
    sudo apt-get update
    sudo apt-get install -y tesseract-ocr tesseract-ocr-spa
else
    echo "✅ Tesseract encontrado: $(tesseract --version | head -n1)"
fi

# Verificar prometheus_client
if ! $VENV_PYTHON -c "import prometheus_client" 2>/dev/null; then
    echo "⚠️  prometheus_client no encontrado. Instalando..."
    $VENV_PYTHON -m pip install prometheus-client
else
    echo "✅ prometheus_client encontrado"
fi

# 2. Ejecutar migraciones SQL
echo "🗄️  Ejecutando migraciones SQL..."
if [ -f "${PROJECT_DIR}/sql/05_ocr_metrics.sql" ]; then
    psql -d "${DATABASE_URL:-postgresql://localhost/pulpo}" -f "${PROJECT_DIR}/sql/05_ocr_metrics.sql"
    echo "✅ Migraciones SQL ejecutadas"
else
    echo "❌ Archivo de migraciones no encontrado"
    exit 1
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

# RAG
RRF_K=60
TOPN_BM25=50
TOPN_VECTOR=50
EOF
    echo "✅ Template .env creado. ¡Configura las variables!"
else
    echo "✅ Archivo .env encontrado"
fi

# 4. Instalar servicio systemd
echo "🔧 Instalando servicio systemd..."
if [ -f "$SERVICE_FILE" ]; then
    sudo cp "$SERVICE_FILE" "$SYSTEMD_DIR/"
    sudo systemctl daemon-reload
    echo "✅ Servicio systemd instalado"
else
    echo "❌ Archivo de servicio no encontrado: $SERVICE_FILE"
    exit 1
fi

# 5. Ejecutar tests
echo "🧪 Ejecutando tests..."
if [ -f "${PROJECT_DIR}/tests/test_ocr_and_metrics.py" ]; then
    cd "$PROJECT_DIR"
    $VENV_PYTHON -m pytest tests/test_ocr_and_metrics.py -v
    echo "✅ Tests ejecutados"
else
    echo "⚠️  Tests no encontrados, saltando..."
fi

# 6. Verificar endpoints
echo "🔍 Verificando endpoints..."
if command -v curl &> /dev/null; then
    # Test de métricas
    if curl -s "http://localhost:8003/metrics" | grep -q "rag_requests_total"; then
        echo "✅ Endpoint /metrics funcionando"
    else
        echo "⚠️  Endpoint /metrics no responde (¿servicio corriendo?)"
    fi
    
    # Test de admin OCR
    if curl -s -X POST "http://localhost:8003/admin/ocr/run-once" | grep -q "forbidden"; then
        echo "✅ Endpoint /admin/ocr/run-once protegido"
    else
        echo "⚠️  Endpoint /admin/ocr/run-once no responde"
    fi
else
    echo "⚠️  curl no encontrado, saltando verificación de endpoints"
fi

# 7. Mostrar comandos útiles
echo ""
echo "🎉 Sprint 2 deployado exitosamente!"
echo ""
echo "📋 Comandos útiles:"
echo "  # Iniciar worker OCR"
echo "  sudo systemctl start pulpo-ocr-worker"
echo ""
echo "  # Ver logs del worker"
echo "  sudo journalctl -u pulpo-ocr-worker -f"
echo ""
echo "  # Verificar estado"
echo "  sudo systemctl status pulpo-ocr-worker"
echo ""
echo "  # Habilitar auto-start"
echo "  sudo systemctl enable pulpo-ocr-worker"
echo ""
echo "  # Test de métricas"
echo "  curl http://localhost:8003/metrics"
echo ""
echo "  # Test de OCR (con token admin)"
echo "  curl -X POST http://localhost:8003/admin/ocr/run-once \\"
echo "    -H 'X-Admin-Token: tu-token-secreto'"
echo ""
echo "  # Ver estadísticas OCR"
echo "  curl -X GET http://localhost:8003/admin/ocr/stats \\"
echo "    -H 'X-Admin-Token: tu-token-secreto'"
echo ""
echo "🔧 Configuración:"
echo "  - Worker OCR: systemd service"
echo "  - Métricas: /metrics endpoint"
echo "  - Admin: X-Admin-Token header"
echo "  - Config: .env file"
echo ""
echo "📊 Monitoreo:"
echo "  - Logs: journalctl -u pulpo-ocr-worker"
echo "  - Métricas: http://localhost:8003/metrics"
echo "  - Stats: /admin/ocr/stats endpoint"
