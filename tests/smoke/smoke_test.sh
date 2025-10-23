#!/bin/bash
# Smoke test para validar SLM Pipeline E2E
# Ejecuta 6 casos típicos y reporta latencias + acciones

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Config
API_URL="${API_URL:-http://localhost:8000}"
ENDPOINT="${ENDPOINT:-/orchestrator/decide}"
WORKSPACE_ID="${WORKSPACE_ID:-550e8400-e29b-41d4-a716-446655440003}"

echo "========================================="
echo "🧪 PulpoAI SLM Pipeline - Smoke Test"
echo "========================================="
echo "API: $API_URL$ENDPOINT"
echo "Workspace: $WORKSPACE_ID"
echo ""

# Casos de prueba
declare -a TESTS=(
  "greeting|Hola|greeting|0"
  "info_hours|Cuál es el horario?|info_hours|1"
  "info_price_generic|Cuánto sale un corte?|info_price|1"
  "info_price_specific|Precio de coloración|info_price|1"
  "book_incomplete|Quiero turno mañana|book|1-2"
  "book_complete|Reservar corte mañana 15hs, soy Juan juan@test.com|book|2-3"
)

# Resultados
PASSED=0
FAILED=0
TOTAL_LATENCY=0

echo "Ejecutando ${#TESTS[@]} tests..."
echo ""

for test in "${TESTS[@]}"; do
  IFS='|' read -r test_name user_input expected_intent expected_actions <<< "$test"
  
  echo -n "[$test_name] "
  
  # Payload
  PAYLOAD=$(cat <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "conversation_id": "smoke-test-$(date +%s)",
  "user_input": "$user_input",
  "vertical": "servicios",
  "slots": {}
}
EOF
)
  
  # Request
  START=$(date +%s%3N)
  RESPONSE=$(curl -s -X POST "$API_URL$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
  END=$(date +%s%3N)
  
  LATENCY=$((END - START))
  TOTAL_LATENCY=$((TOTAL_LATENCY + LATENCY))
  
  # Parse response
  INTENT=$(echo "$RESPONSE" | jq -r '.debug.intent // "unknown"')
  ACTIONS=$(echo "$RESPONSE" | jq '.tool_calls | length')
  BODY=$(echo "$RESPONSE" | jq -r '.assistant' | head -c 60)
  
  # Validar
  if [[ "$INTENT" == "$expected_intent" ]]; then
    echo -e "${GREEN}✓${NC} intent=$INTENT actions=$ACTIONS latency=${LATENCY}ms"
    echo "  → \"$BODY...\""
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}✗${NC} Expected intent=$expected_intent, got=$INTENT"
    echo "  Response: $RESPONSE"
    FAILED=$((FAILED + 1))
  fi
  
  # Validar latencia
  if [[ $LATENCY -gt 2000 ]]; then
    echo -e "  ${YELLOW}⚠${NC} High latency: ${LATENCY}ms > 2000ms"
  fi
  
  echo ""
  
  # Rate limit
  sleep 0.5
done

# Resumen
echo "========================================="
echo "📊 Resultados"
echo "========================================="
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo "Total: ${#TESTS[@]}"
echo ""
echo "Latencia promedio: $((TOTAL_LATENCY / ${#TESTS[@]}))ms"
echo "Latencia total: ${TOTAL_LATENCY}ms"
echo ""

if [[ $FAILED -eq 0 ]]; then
  echo -e "${GREEN}✓ All tests passed!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some tests failed${NC}"
  exit 1
fi




