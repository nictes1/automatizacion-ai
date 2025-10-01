#!/bin/bash

# Script para configurar cron job de purga nocturna
# Ejecutar como: ./scripts/setup_cron.sh

echo "🔧 Configurando cron job para purga nocturna..."

# Obtener directorio del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_PATH="$(which python3)"

# Crear archivo de cron
CRON_FILE="/tmp/pulpo_purge_cron"

cat > "$CRON_FILE" << EOF
# Purga nocturna de documentos eliminados - PulpoAI RAG Service
# Ejecuta todos los días a las 2:00 AM
0 2 * * * cd $PROJECT_DIR && $PYTHON_PATH jobs/purge_job.py >> logs/purge_job.log 2>&1

# Purga semanal más agresiva (domingos a las 3:00 AM)
0 3 * * 0 cd $PROJECT_DIR && $PYTHON_PATH jobs/purge_job.py >> logs/purge_job.log 2>&1
EOF

# Instalar cron job
echo "📝 Instalando cron job..."
crontab "$CRON_FILE"

# Verificar instalación
echo "✅ Cron job instalado. Jobs activos:"
crontab -l | grep pulpo

# Crear directorio de logs si no existe
mkdir -p "$PROJECT_DIR/logs"

# Crear archivo de log inicial
touch "$PROJECT_DIR/logs/purge_job.log"

echo "📋 Configuración completada:"
echo "  - Job diario: 2:00 AM"
echo "  - Job semanal: Domingos 3:00 AM"
echo "  - Logs: $PROJECT_DIR/logs/purge_job.log"
echo "  - Retención: 7 días (configurable via PURGE_RETENTION_DAYS)"

# Limpiar archivo temporal
rm "$CRON_FILE"

echo "🎉 ¡Cron job configurado exitosamente!"
