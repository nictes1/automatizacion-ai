#!/bin/bash
# cURLs de ejemplo para testing directo del Orchestrator
# Simula exactamente el formato que n8n envía

API_URL="${API_URL:-http://localhost:8000}"
WORKSPACE_ID="${WORKSPACE_ID:-550e8400-e29b-41d4-a716-446655440003}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "========================================="
echo "📋 cURLs de Ejemplo - Contrato n8n"
echo "========================================="
echo ""

echo "1) Saludo (corto)"
echo "──────────────────────────────────────"
curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: $TIMESTAMP-SM001" \
  -d '{
  "user_message": {
    "text": "hola",
    "message_id": "SM001",
    "from": "+5492235261872",
    "to": "+14155238886",
    "waid": "5492235261872",
    "timestamp_iso": "'$TIMESTAMP'",
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
}' | jq .

echo ""
echo ""

echo "2) Consulta de horarios"
echo "──────────────────────────────────────"
curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: $TIMESTAMP-SM002" \
  -d '{
  "user_message": {
    "text": "qué horarios tienen",
    "message_id": "SM002",
    "from": "+5492235261872",
    "to": "+14155238886",
    "waid": "5492235261872",
    "timestamp_iso": "'$TIMESTAMP'",
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
}' | jq .

echo ""
echo ""

echo "3) Consulta de precio"
echo "──────────────────────────────────────"
curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: $TIMESTAMP-SM003" \
  -d '{
  "user_message": {
    "text": "cuánto cuesta un corte de pelo",
    "message_id": "SM003",
    "from": "+5492235261872",
    "to": "+14155238886",
    "waid": "5492235261872",
    "timestamp_iso": "'$TIMESTAMP'",
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
}' | jq .

echo ""
echo ""

echo "4) Reserva incompleta"
echo "──────────────────────────────────────"
curl -s -X POST "$API_URL/orchestrator/decide" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-5492235261872" \
  -H "X-Request-Id: $TIMESTAMP-SM004" \
  -d '{
  "user_message": {
    "text": "quiero reservar mañana 15hs",
    "message_id": "SM004",
    "from": "+5492235261872",
    "to": "+14155238886",
    "waid": "5492235261872",
    "timestamp_iso": "'$TIMESTAMP'",
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
}' | jq .

echo ""
echo ""

echo "========================================="
echo "✅ Ejemplos completados"
echo "========================================="




