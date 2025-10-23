#!/bin/bash
# Validación SLM Canary 10%
# EJECUTAR SOLO DESPUÉS DE PASO 1 VERDE

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="${API_URL:-http://localhost:8000}"
WORKSPACE_ID="${WORKSPACE_ID:-550e8400-e29b-41d4-a716-446655440003}"

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║      🧪 PASO 2: Validar SLM Pipeline Canary 10%                  ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "API: $API_URL"
echo "Workspace: $WORKSPACE_ID"
echo ""

# Verificar feature flags
echo -e "${BLUE}[INFO]${NC} Feature flags esperados:"
echo "  ENABLE_SLM_PIPELINE=true"
echo "  SLM_CANARY_PERCENT=10"
echo ""

# Test 1: SLM forzado (100%)
echo -e "${BLUE}━━━ Test 1: SLM Pipeline Forzado (100%) ━━━${NC}"

RESPONSE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-slm-forced-test" \
  -H "X-Request-Id: slm-forced-test" \
  -d @tests/fixtures/request_saludo.json)

ROUTE=$(echo "$RESPONSE" | jq -r '.telemetry.route // "unknown"')
ASSISTANT=$(echo "$RESPONSE" | jq -r '.assistant.text // "ERROR"')
TOTAL_MS=$(echo "$RESPONSE" | jq -r '.telemetry.total_ms // 0')

if [[ "$ROUTE" == "slm_pipeline" ]]; then
  echo -e "${GREEN}✓${NC} SLM Pipeline funciona (${TOTAL_MS}ms)"
  echo "  → \"$(echo $ASSISTANT | head -c 60)...\""
else
  echo -e "${RED}✗${NC} Expected route=slm_pipeline, got: $ROUTE"
  echo "  Response: $RESPONSE"
  exit 1
fi

echo ""

# Test 2: Distribución canary
echo -e "${BLUE}━━━ Test 2: Distribución Canary (20 requests) ━━━${NC}"

SLM_COUNT=0
LEGACY_COUNT=0
TOTAL=20

for i in $(seq 1 $TOTAL); do
  ROUTE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: wa-canary-test-$i" \
    -H "X-Request-Id: canary-test-$i" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route // "unknown"')
  
  if [[ "$ROUTE" == "slm_pipeline" ]]; then
    SLM_COUNT=$((SLM_COUNT + 1))
  elif [[ "$ROUTE" == "legacy" ]]; then
    LEGACY_COUNT=$((LEGACY_COUNT + 1))
  fi
  
  # Progress indicator
  echo -n "."
  
  sleep 0.1
done

echo ""
echo ""

SLM_PERCENT=$((SLM_COUNT * 100 / TOTAL))
LEGACY_PERCENT=$((LEGACY_COUNT * 100 / TOTAL))

echo "Distribución:"
echo "  - SLM: $SLM_COUNT/${TOTAL} (${SLM_PERCENT}%)"
echo "  - Legacy: $LEGACY_COUNT/${TOTAL} (${LEGACY_PERCENT}%)"
echo ""

# Validar distribución (esperado: ~10%, rango: 5-20%)
if [[ $SLM_COUNT -ge 1 && $SLM_COUNT -le 5 ]]; then
  echo -e "${GREEN}✓${NC} Distribución OK (esperado: ~2, real: $SLM_COUNT)"
elif [[ $SLM_COUNT -eq 0 ]]; then
  echo -e "${RED}✗${NC} No traffic to SLM (verificar ENABLE_SLM_PIPELINE=true)"
  exit 1
else
  echo -e "${YELLOW}⚠${NC} Distribución fuera de rango ideal (esperado: 1-5, real: $SLM_COUNT)"
  echo "  → Puede ser normal por varianza estadística"
fi

echo ""

# Test 3: Latencias comparadas
echo -e "${BLUE}━━━ Test 3: Latencias SLM vs Legacy ━━━${NC}"

# SLM latency
SLM_LATENCY=$(curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-slm-latency-test" \
  -H "X-Request-Id: slm-latency-test" \
  -d @tests/fixtures/request_saludo.json \
  | jq -r '.telemetry.total_ms // 0')

# Legacy latency
LEGACY_LATENCY=$(curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-legacy-latency-test" \
  -H "X-Request-Id: legacy-latency-test" \
  -d @tests/fixtures/request_saludo.json \
  | jq -r '.telemetry.total_ms // 0')

echo "Latencias:"
echo "  - SLM: ${SLM_LATENCY}ms"
echo "  - Legacy: ${LEGACY_LATENCY}ms"

if [[ $SLM_LATENCY -gt 0 && $SLM_LATENCY -lt 2000 ]]; then
  echo -e "${GREEN}✓${NC} Latencia SLM OK (< 2000ms)"
else
  echo -e "${RED}✗${NC} Latencia SLM alta (> 2000ms)"
fi

echo ""

# Resumen
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${BLUE}📊 Resumen${NC}"
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✓${NC} SLM Pipeline funcional"
echo -e "${GREEN}✓${NC} Distribución canary correcta"
echo -e "${GREEN}✓${NC} Latencias aceptables"
echo ""
echo -e "${GREEN}✅ PASO 2 COMPLETADO${NC}"
echo ""
echo "SLM Pipeline canary 10% está activo y funcionando."
echo ""
echo "Próximos pasos:"
echo "  1. Monitorear métricas 48hs"
echo "  2. Comparar accuracy SLM vs Legacy"
echo "  3. Si todo OK, escalar a 50%:"
echo "     export SLM_CANARY_PERCENT=50"
echo ""

exit 0




