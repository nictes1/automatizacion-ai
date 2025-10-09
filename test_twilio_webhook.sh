#!/bin/bash
# Script para testear el webhook de Twilio sin enviar mensaje real desde WhatsApp
# Simula un mensaje POST desde Twilio hacia n8n

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "================================================"
echo "🧪 TEST WEBHOOK TWILIO → n8n → Orchestrator"
echo "================================================"

# Obtener URL de ngrok
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url')

if [ -z "$NGROK_URL" ] || [ "$NGROK_URL" == "null" ]; then
    echo -e "${RED}❌ Error: ngrok no está corriendo o no tiene túneles activos${NC}"
    echo "Inicia ngrok con: ngrok http 5678"
    exit 1
fi

echo -e "${GREEN}✅ ngrok URL: $NGROK_URL${NC}"

# Webhook endpoint
WEBHOOK_URL="$NGROK_URL/webhook/pulpo/twilio/wa/inbound"
echo -e "${GREEN}✅ Webhook: $WEBHOOK_URL${NC}"

# Datos del mensaje simulado
FROM="whatsapp:+5491165551234"
TO="whatsapp:+14155238886"
BODY="Hola, quiero información sobre los servicios"
MESSAGE_SID="SM_test_$(date +%s)"

echo ""
echo "📨 Enviando mensaje de prueba..."
echo "   From: $FROM"
echo "   To: $TO"
echo "   Body: $BODY"
echo "   SID: $MESSAGE_SID"
echo ""

# Enviar POST al webhook (simulando Twilio)
RESPONSE=$(curl -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "User-Agent: TwilioProxy/1.1" \
  -d "From=$FROM" \
  -d "To=$TO" \
  -d "Body=$BODY" \
  -d "MessageSid=$MESSAGE_SID" \
  -d "AccountSid=ACtest123" \
  -d "MessagingServiceSid=MGtest123" \
  -d "NumMedia=0" \
  -d "NumSegments=1" \
  -d "MessageStatus=received" \
  -d "ApiVersion=2010-04-01" \
  -w "\nHTTP_CODE:%{http_code}" \
  -s)

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)
BODY_RESPONSE=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

echo "📥 Respuesta del webhook:"
echo "   HTTP Status: $HTTP_CODE"
echo "   Body: $BODY_RESPONSE"
echo ""

if [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}✅ Webhook respondió correctamente (200 OK)${NC}"
else
    echo -e "${YELLOW}⚠️  Webhook respondió con código: $HTTP_CODE${NC}"
fi

echo ""
echo "🔍 Verificando en la base de datos..."

# Buscar el mensaje en la BD
MESSAGE_FOUND=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "
SELECT COUNT(*) FROM pulpo.messages
WHERE content = '$BODY'
  AND sender = 'user'
  AND created_at > NOW() - INTERVAL '1 minute';
")

MESSAGE_FOUND=$(echo $MESSAGE_FOUND | xargs)

if [ "$MESSAGE_FOUND" -gt 0 ]; then
    echo -e "${GREEN}✅ Mensaje encontrado en la base de datos!${NC}"

    # Mostrar último mensaje y respuesta
    echo ""
    echo "📊 Últimos mensajes de la conversación:"
    docker exec pulpo-postgres psql -U pulpo -d pulpo -c "
    SELECT
      sender,
      LEFT(content, 60) as content,
      created_at
    FROM pulpo.messages
    WHERE created_at > NOW() - INTERVAL '1 minute'
    ORDER BY created_at DESC
    LIMIT 5;
    "

    # Verificar si hubo respuesta del bot
    BOT_RESPONSE=$(docker exec pulpo-postgres psql -U pulpo -d pulpo -t -c "
    SELECT COUNT(*) FROM pulpo.messages
    WHERE sender = 'assistant'
      AND created_at > NOW() - INTERVAL '1 minute';
    ")

    BOT_RESPONSE=$(echo $BOT_RESPONSE | xargs)

    if [ "$BOT_RESPONSE" -gt 0 ]; then
        echo ""
        echo -e "${GREEN}✅ Bot generó respuesta!${NC}"
        docker exec pulpo-postgres psql -U pulpo -d pulpo -c "
        SELECT content FROM pulpo.messages
        WHERE sender = 'assistant'
          AND created_at > NOW() - INTERVAL '1 minute'
        ORDER BY created_at DESC
        LIMIT 1;
        "
    else
        echo -e "${YELLOW}⚠️  No se encontró respuesta del bot en la BD${NC}"
        echo "   Revisa los logs:"
        echo "   - docker logs pulpo-n8n --tail 50"
        echo "   - docker logs pulpo-orchestrator --tail 50"
    fi
else
    echo -e "${RED}❌ Mensaje NO encontrado en la base de datos${NC}"
    echo "   El webhook puede haber fallado antes de persistir."
    echo ""
    echo "🔍 Debugging:"
    echo "   1. Verifica logs de n8n:"
    echo "      docker logs pulpo-n8n --tail 20"
    echo ""
    echo "   2. Verifica que el workflow esté activo en n8n UI:"
    echo "      http://localhost:5678"
    echo ""
    echo "   3. Verifica que las funciones SQL existan:"
    echo "      docker exec pulpo-postgres psql -U pulpo -d pulpo -c '\df pulpo.persist_inbound'"
fi

echo ""
echo "================================================"
echo "✅ Test completado"
echo "================================================"
