#!/bin/bash
# Test del contrato n8n → Orchestrator → n8n
# Simula exactamente el formato que n8n envía

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Config
API_URL="${API_URL:-http://localhost:8000}"
WORKSPACE_ID="${WORKSPACE_ID:-550e8400-e29b-41d4-a716-446655440003}"

echo "========================================="
echo "🧪 Test Contrato n8n → Orchestrator"
echo "========================================="
echo "API: $API_URL"
echo "Workspace: $WORKSPACE_ID"
echo ""

# Timestamp actual
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Casos de prueba
declare -a TESTS=(
  "greeting|hola"
  "info_hours|qué horarios tienen"
  "info_price|cuánto cuesta un corte de pelo"
  "book_incomplete|quiero reservar mañana 15hs"
)

PASSED=0
FAILED=0
TOTAL_LATENCY=0

echo "Ejecutando ${#TESTS[@]} tests..."
echo ""

for test in "${#TESTS[@]}"; do
  IFS='|' read -r test_name user_text <<< "$test"
  
  echo -n "[$test_name] "
  
  # Generar message_id único
  MSG_ID="SM$(date +%s%3N)"
  
  # Payload exacto que envía n8n
  PAYLOAD=$(cat <<EOF
{
  "user_message": {
    "text": "$user_text",
    "message_id": "$MSG_ID",
    "from": "+5492235261872",
    "to": "+14155238886",
    "waid": "5492235261872",
    "timestamp_iso": "$TIMESTAMP",
    "locale": "es-AR"
  },
  "context": {
    "platform": "twilio",
    "channel": "whatsapp",
    "business_name": "Estilo Total - Peluquería & Spa",
    "vertical": "servicios"
  },
  "state": {
    "fsm_state": null,
    "slots": {},
    "last_k_observations": []
  }
}
EOF
)
  
  # Request con headers exactos de n8n
  START=$(date +%s%3N)
  RESPONSE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: wa-5492235261872" \
    -H "X-Request-Id: $TIMESTAMP-$MSG_ID" \
    -d "$PAYLOAD")
  END=$(date +%s%3N)
  
  LATENCY=$((END - START))
  TOTAL_LATENCY=$((TOTAL_LATENCY + LATENCY))
  
  # Parse response
  ASSISTANT_TEXT=$(echo "$RESPONSE" | jq -r '.assistant.text // "ERROR"')
  ROUTE=$(echo "$RESPONSE" | jq -r '.telemetry.route // "unknown"')
  TOTAL_MS=$(echo "$RESPONSE" | jq -r '.telemetry.total_ms // 0')
  
  # Validar
  if [[ "$ASSISTANT_TEXT" != "ERROR" && "$ROUTE" != "error" ]]; then
    echo -e "${GREEN}✓${NC} route=$ROUTE latency=${LATENCY}ms total_ms=${TOTAL_MS}ms"
    echo "  → \"$(echo $ASSISTANT_TEXT | head -c 60)...\""
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}✗${NC} Failed"
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

if [[ ${#TESTS[@]} -gt 0 ]]; then
  echo "Latencia promedio: $((TOTAL_LATENCY / ${#TESTS[@]}))ms"
fi
echo "Latencia total: ${TOTAL_LATENCY}ms"
echo ""

if [[ $FAILED -eq 0 ]]; then
  echo -e "${GREEN}✓ All tests passed!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some tests failed${NC}"
  exit 1
fi




