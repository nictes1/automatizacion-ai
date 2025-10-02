#!/bin/bash

echo "🔍 Verificando servicios de PulpoAI..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para verificar servicio
check_service() {
    local service_name=$1
    local check_command=$2
    local expected_output=$3
    
    echo -n "Verificando $service_name... "
    
    if eval "$check_command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FALLO${NC}"
        return 1
    fi
}

echo ""
echo "📊 Estado de contenedores:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🔧 Verificaciones de salud:"

# Verificar PostgreSQL
check_service "PostgreSQL" "docker exec pulpo-postgres psql -U pulpo -d pulpo -c 'SELECT 1;'" "1"

# Verificar Redis
check_service "Redis" "docker exec pulpo-redis redis-cli ping" "PONG"

# Verificar Ollama
check_service "Ollama" "curl -s http://localhost:11434/api/tags" ""

# Verificar pgvector
check_service "pgvector" "docker exec pulpo-postgres psql -U pulpo -d pulpo -c \"SELECT extname FROM pg_extension WHERE extname = 'vector';\"" "vector"

echo ""
echo "🌐 URLs de acceso:"
echo "  PostgreSQL: localhost:5432 (usuario: pulpo, password: pulpo, db: pulpo)"
echo "  Redis: localhost:6379"
echo "  Ollama: http://localhost:11434"

echo ""
echo "✅ Verificación completada!"
