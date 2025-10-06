#!/bin/bash
# Script para ejecutar tests con cliente AI simulado

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=================================="
echo "🤖 PulpoAI - Tests con Cliente AI"
echo "=================================="
echo ""

# Verificar servicios
echo -e "${YELLOW}🔍 Verificando servicios...${NC}"

# Verificar orchestrator
if curl -s http://localhost:8005/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Orchestrator OK${NC}"
else
    echo -e "${RED}❌ Orchestrator no disponible en localhost:8005${NC}"
    echo "   Inicia el servicio con: python3 services/orchestrator_app.py"
    exit 1
fi

# Verificar Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama OK${NC}"
else
    echo -e "${RED}❌ Ollama no disponible en localhost:11434${NC}"
    echo "   Inicia Ollama con: docker-compose -f docker-compose.simple.yml up -d ollama"
    exit 1
fi

# Verificar modelos
echo ""
echo -e "${YELLOW}🔍 Verificando modelos LLM...${NC}"

MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys, json; print(' '.join([m['name'] for m in json.load(sys.stdin)['models']]))")

if echo "$MODELS" | grep -q "qwen2.5:14b"; then
    echo -e "${GREEN}✅ qwen2.5:14b disponible${NC}"
else
    echo -e "${RED}❌ qwen2.5:14b no encontrado${NC}"
    echo "   Descarga el modelo con: docker exec pulpo-ollama ollama pull qwen2.5:14b"
    exit 1
fi

if echo "$MODELS" | grep -q "llama3.1:8b"; then
    echo -e "${GREEN}✅ llama3.1:8b disponible${NC}"
else
    echo -e "${RED}❌ llama3.1:8b no encontrado${NC}"
    echo "   Descarga el modelo con: docker exec pulpo-ollama ollama pull llama3.1:8b"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Todos los requisitos OK${NC}"
echo ""
echo "=================================="
echo "🚀 Ejecutando tests..."
echo "=================================="
echo ""

# Ejecutar tests
python3 tests/test_ai_client_scenarios.py

# Mostrar resultados si el archivo existe
if [ -f "test_results.json" ]; then
    echo ""
    echo "=================================="
    echo "📊 Resultados guardados en:"
    echo "   test_results.json"
    echo "=================================="
    echo ""
    echo "Para ver resultados formateados:"
    echo "   cat test_results.json | jq '.[] | {scenario: .scenario_name, success: .success, turns: .turns}'"
fi

echo ""
echo -e "${GREEN}✅ Tests completados${NC}"
