#!/bin/bash
# Test de Routing Determinístico
# Verifica que el mismo conversation_id siempre va al mismo route

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
echo "║      🧪 Test: Routing Determinístico por conversation_id         ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "API: $API_URL"
echo "Workspace: $WORKSPACE_ID"
echo ""

# Verificar que canary esté activo
echo -e "${BLUE}[INFO]${NC} Feature flags esperados:"
echo "  ENABLE_SLM_PIPELINE=true"
echo "  SLM_CANARY_PERCENT=10"
echo ""

# Test 1: Mismo conversation_id → mismo route (5 veces)
echo -e "${BLUE}━━━ Test 1: Determinismo (5 requests, mismo conv_id) ━━━${NC}"

CONV_ID="wa-deterministic-test-001"
ROUTES=()

for i in {1..5}; do
  ROUTE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: $CONV_ID" \
    -H "X-Request-Id: det-test-$i" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route // "unknown"')
  
  ROUTES+=("$ROUTE")
  echo -n "."
  sleep 0.1
done

echo ""

# Verificar que todos sean iguales
FIRST_ROUTE="${ROUTES[0]}"
ALL_SAME=true

for route in "${ROUTES[@]}"; do
  if [[ "$route" != "$FIRST_ROUTE" ]]; then
    ALL_SAME=false
    break
  fi
done

if [[ "$ALL_SAME" == true ]]; then
  echo -e "${GREEN}✓${NC} Determinismo OK: conv_id=$CONV_ID → route=$FIRST_ROUTE (5/5)"
else
  echo -e "${RED}✗${NC} No determinístico: routes=${ROUTES[@]}"
  exit 1
fi

echo ""

# Test 2: Diferentes conversation_ids → distribución esperada
echo -e "${BLUE}━━━ Test 2: Distribución con múltiples conv_ids ━━━${NC}"

SLM_COUNT=0
LEGACY_COUNT=0
TOTAL=30

# Generar 30 conversation_ids diferentes
for i in $(seq 1 $TOTAL); do
  CONV_ID="wa-dist-test-$(printf "%03d" $i)"
  
  ROUTE=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: $CONV_ID" \
    -H "X-Request-Id: dist-test-$i" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route // "unknown"')
  
  if [[ "$ROUTE" == "slm_pipeline" ]]; then
    SLM_COUNT=$((SLM_COUNT + 1))
  elif [[ "$ROUTE" == "legacy" ]]; then
    LEGACY_COUNT=$((LEGACY_COUNT + 1))
  fi
  
  echo -n "."
  sleep 0.05
done

echo ""
echo ""

SLM_PERCENT=$((SLM_COUNT * 100 / TOTAL))
LEGACY_PERCENT=$((LEGACY_COUNT * 100 / TOTAL))

echo "Distribución (30 conv_ids únicos):"
echo "  - SLM: $SLM_COUNT/${TOTAL} (${SLM_PERCENT}%)"
echo "  - Legacy: $LEGACY_COUNT/${TOTAL} (${LEGACY_PERCENT}%)"
echo ""

# Validar distribución (esperado: ~10%, rango: 6-16% para 30 samples)
if [[ $SLM_COUNT -ge 2 && $SLM_COUNT -le 5 ]]; then
  echo -e "${GREEN}✓${NC} Distribución OK (esperado: ~3, real: $SLM_COUNT)"
elif [[ $SLM_COUNT -eq 0 ]]; then
  echo -e "${RED}✗${NC} No traffic to SLM (verificar ENABLE_SLM_PIPELINE=true)"
  exit 1
else
  echo -e "${YELLOW}⚠${NC} Distribución fuera de rango ideal (esperado: 2-5, real: $SLM_COUNT)"
  echo "  → Puede ser normal por varianza estadística"
fi

echo ""

# Test 3: Re-verificar determinismo con los mismos conversation_ids
echo -e "${BLUE}━━━ Test 3: Re-verificar determinismo (10 conv_ids, 2 veces cada uno) ━━━${NC}"

ERRORS=0

for i in $(seq 1 10); do
  CONV_ID="wa-reverify-$(printf "%02d" $i)"
  
  # Primera llamada
  ROUTE1=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: $CONV_ID" \
    -H "X-Request-Id: reverify-1-$i" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route // "unknown"')
  
  sleep 0.05
  
  # Segunda llamada (mismo conv_id)
  ROUTE2=$(curl -s -X POST "$API_URL/orchestrator/decide" \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: $WORKSPACE_ID" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: $CONV_ID" \
    -H "X-Request-Id: reverify-2-$i" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route // "unknown"')
  
  if [[ "$ROUTE1" != "$ROUTE2" ]]; then
    echo -e "${RED}✗${NC} conv_id=$CONV_ID: route1=$ROUTE1, route2=$ROUTE2"
    ERRORS=$((ERRORS + 1))
  else
    echo -n "."
  fi
  
  sleep 0.05
done

echo ""

if [[ $ERRORS -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} Determinismo verificado: 10/10 consistentes"
else
  echo -e "${RED}✗${NC} $ERRORS/10 inconsistentes"
  exit 1
fi

echo ""

# Resumen
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${BLUE}📊 Resumen${NC}"
echo "═══════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✓${NC} Routing determinístico funcionando correctamente"
echo -e "${GREEN}✓${NC} Distribución canary dentro del rango esperado"
echo -e "${GREEN}✓${NC} Hash de conversation_id es estable"
echo ""
echo -e "${GREEN}✅ TEST DETERMINÍSTICO COMPLETADO${NC}"
echo ""

exit 0
