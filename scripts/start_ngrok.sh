#!/bin/bash

# Script para iniciar ngrok y mostrar la URL del webhook

echo "========================================="
echo "🔗 Iniciando ngrok tunnel..."
echo "========================================="

# Matar proceso anterior
pkill ngrok 2>/dev/null

# Iniciar ngrok
nohup ngrok http 5678 > /tmp/ngrok.log 2>&1 &

# Esperar a que inicie
sleep 4

# Obtener URL
NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | jq -r '.tunnels[0].public_url // "ERROR"')

if [ "$NGROK_URL" = "ERROR" ]; then
    echo "❌ Error: ngrok no está respondiendo"
    echo "Verifica que ngrok esté instalado: which ngrok"
    exit 1
fi

WEBHOOK_URL="${NGROK_URL}/webhook/pulpo/twilio/wa/inbound"

echo ""
echo "✅ Ngrok iniciado correctamente"
echo ""
echo "========================================="
echo "📋 CONFIGURACIÓN PARA TWILIO"
echo "========================================="
echo ""
echo "URL del Webhook:"
echo "  $WEBHOOK_URL"
echo ""
echo "Copiar y pegar en Twilio Console:"
echo "  Messaging → Sandbox Settings"
echo "  WHEN A MESSAGE COMES IN: $WEBHOOK_URL"
echo "  METHOD: POST"
echo ""
echo "========================================="
echo "🔍 MONITOREO"
echo "========================================="
echo ""
echo "ngrok Dashboard: http://localhost:4040"
echo "n8n UI: http://localhost:5678"
echo ""
echo "Ver logs de ngrok:"
echo "  tail -f /tmp/ngrok.log"
echo ""
echo "========================================="
echo ""

# Guardar URL en archivo para referencia
echo "$WEBHOOK_URL" > /tmp/ngrok_webhook_url.txt
echo "✅ URL guardada en: /tmp/ngrok_webhook_url.txt"
