#!/bin/bash
# Script de validación del contrato n8n con Legacy 100%
# Paso 1: Aislar variables antes de activar SLM

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Config
API_URL="${API_URL:-http://localhost:8000}"
WORKSPACE_ID="${WORKSPACE_ID:-550e8400-e29b-41d4-a716-446655440003}"

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║      🧪 PASO 1: Validar Contrato n8n con Legacy 100%             ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "API: $API_URL"
echo "Workspace: $WORKSPACE_ID"
echo ""

# Verificar que Legacy esté activo
echo -e "${BLUE}[INFO]${NC} Verificando feature flags..."
echo "ENABLE_SLM_PIPELINE should be: false"
echo "SLM_CANARY_PERCENT should be: 0"
echo ""

# Tests
PASSED=0
FAILED=0

# Función helper para tests
run_test() {
  local test_name=$1
  local fixture=$2
  local conversation_id=$3
  local msg_id=$4
  
  echo -n "[$test_name] "
  
  START=$(date +%s%3N)
  RESPONSE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: $conversation_id" \
    -H "X-Request-Id: $(date -u +%Y-%m-%dT%H:%M:%SZ)-$msg_id" \
    -d @"$fixture")
  END=$(date +%s%3N)
  
  LATENCY=$((END - START))
  
  # Parse response
  ASSISTANT_TEXT=$(echo "$RESPONSE" | jq -r '.assistant.text // "ERROR"')
  ROUTE=$(echo "$RESPONSE" | jq -r '.telemetry.route // "unknown"')
  TOTAL_MS=$(echo "$RESPONSE" | jq -r '.telemetry.total_ms // 0')
  HAS_PATCH=$(echo "$RESPONSE" | jq 'has("patch")')
  HAS_TOOL_CALLS=$(echo "$RESPONSE" | jq 'has("tool_calls")')
  
  # Validaciones
  local errors=0
  
  if [[ "$ASSISTANT_TEXT" == "ERROR" ]]; then
    echo -e "${RED}✗${NC} assistant.text missing"
    errors=$((errors + 1))
  fi
  
  if [[ "$ROUTE" != "legacy" ]]; then
    echo -e "${RED}✗${NC} route=$ROUTE (expected: legacy)"
    errors=$((errors + 1))
  fi
  
  if [[ "$HAS_PATCH" != "true" ]]; then
    echo -e "${RED}✗${NC} patch field missing"
    errors=$((errors + 1))
  fi
  
  if [[ "$HAS_TOOL_CALLS" != "true" ]]; then
    echo -e "${RED}✗${NC} tool_calls field missing"
    errors=$((errors + 1))
  fi
  
  if [[ $LATENCY -gt 2000 ]]; then
    echo -e "${YELLOW}⚠${NC} High latency: ${LATENCY}ms"
  fi
  
  # Resultado
  if [[ $errors -eq 0 ]]; then
    echo -e "${GREEN}✓${NC} latency=${LATENCY}ms total_ms=${TOTAL_MS}ms"
    echo "  → \"$(echo $ASSISTANT_TEXT | head -c 60)...\""
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}✗${NC} $errors validation(s) failed"
    echo "  Response: $RESPONSE"
    FAILED=$((FAILED + 1))
  fi
  
  echo ""
}

# Test 1: Saludo
echo -e "${BLUE}━━━ Test 1: Saludo ━━━${NC}"
run_test "Saludo" "tests/fixtures/request_saludo.json" "wa-5492235261872" "SM001"

# Test 2: Consulta precio
echo -e "${BLUE}━━━ Test 2: Consulta Precio ━━━${NC}"
run_test "Precio" "tests/fixtures/request_precio.json" "wa-5492235261872" "SM002"

# Test 3: Reserva
echo -e "${BLUE}━━━ Test 3: Reserva ━━━${NC}"
run_test "Reserva" "tests/fixtures/request_reserva.json" "wa-5492235261872" "SM003"

# Rate limit
sleep 0.5

# Resumen
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${BLUE}📊 Resumen${NC}"
echo "═══════════════════════════════════════════════════════════════════"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
echo ""

if [[ $FAILED -eq 0 ]]; then
  echo -e "${GREEN}✅ PASO 1 COMPLETADO${NC}"
  echo ""
  echo "El contrato n8n funciona perfectamente con Legacy."
  echo ""
  echo "Próximo paso:"
  echo "  1. Implementar _decide_with_slm_pipeline() en api/orchestrator.py"
  echo "  2. Inicializar singletons en startup"
  echo "  3. Activar SLM canary 10%:"
  echo "     export ENABLE_SLM_PIPELINE=true"
  echo "     export SLM_CANARY_PERCENT=10"
  echo ""
  exit 0
else
  echo -e "${RED}❌ PASO 1 FALLÓ${NC}"
  echo ""
  echo "Revisar errores antes de continuar con SLM Pipeline."
  echo ""
  exit 1
fi




