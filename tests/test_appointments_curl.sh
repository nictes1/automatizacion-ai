#!/bin/bash

# Test de appointments con curl
# Simula el flujo completo de agendamiento de turnos

WORKSPACE_ID="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ACTIONS_URL="http://localhost:8006"

echo "🧪 TEST: Sistema de Agendamiento de Turnos"
echo "==========================================="
echo ""

# 1. Obtener tipos de servicio
echo "1️⃣ Obteniendo tipos de servicio disponibles..."
SERVICE_TYPES=$(curl -s -X GET "$ACTIONS_URL/actions/service-types" \
  -H "X-Workspace-Id: $WORKSPACE_ID")

echo "📋 Servicios disponibles:"
echo "$SERVICE_TYPES" | jq -r '.[] | "  - \(.name): \(.price) \(.currency) (\(.duration_minutes) min)"'
echo ""

# 2. Obtener staff disponible
echo "2️⃣ Obteniendo empleados disponibles..."
STAFF=$(curl -s -X GET "$ACTIONS_URL/actions/staff" \
  -H "X-Workspace-Id: $WORKSPACE_ID")

echo "👥 Empleados:"
echo "$STAFF" | jq -r '.[] | "  - \(.name) (\(.email))"'
echo ""

# Extraer ID del primer staff
STAFF_ID=$(echo "$STAFF" | jq -r '.[0].id')
STAFF_NAME=$(echo "$STAFF" | jq -r '.[0].name')

# 3. Verificar disponibilidad
echo "3️⃣ Verificando disponibilidad de $STAFF_NAME..."
TOMORROW=$(date -d "tomorrow" +%Y-%m-%d)
TIME="14:00"

AVAILABILITY=$(curl -s -X POST "$ACTIONS_URL/actions/check-availability" \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: $WORKSPACE_ID" \
  -d "{
    \"staff_id\": \"$STAFF_ID\",
    \"appointment_date\": \"$TOMORROW\",
    \"appointment_time\": \"$TIME\",
    \"duration_minutes\": 30
  }")

IS_AVAILABLE=$(echo "$AVAILABILITY" | jq -r '.available')
echo "✅ Disponible: $IS_AVAILABLE"
echo ""

# 4. Crear appointment
if [ "$IS_AVAILABLE" = "true" ]; then
    echo "4️⃣ Creando turno para Juan Pérez..."
    APPOINTMENT=$(curl -s -X POST "$ACTIONS_URL/actions/create-appointment" \
      -H "Content-Type: application/json" \
      -H "X-Workspace-Id: $WORKSPACE_ID" \
      -d "{
        \"service_type_name\": \"Corte de pelo\",
        \"client_name\": \"Juan Pérez\",
        \"client_email\": \"juan.perez@example.com\",
        \"client_phone\": \"+5492235551234\",
        \"appointment_date\": \"$TOMORROW\",
        \"appointment_time\": \"$TIME\",
        \"notes\": \"Cliente prefiere estilo moderno\"
      }")

    echo "📅 Turno creado:"
    echo "$APPOINTMENT" | jq '.'

    APPT_ID=$(echo "$APPOINTMENT" | jq -r '.appointment_id')
    GOOGLE_EVENT=$(echo "$APPOINTMENT" | jq -r '.google_event_id')

    echo ""
    echo "✅ Appointment ID: $APPT_ID"
    if [ "$GOOGLE_EVENT" != "null" ]; then
        echo "✅ Google Calendar Event ID: $GOOGLE_EVENT"
    else
        echo "⚠️  Google Calendar not configured"
    fi
    echo ""

    # 5. Cancelar appointment (opcional)
    read -p "¿Cancelar el turno? (y/n): " CANCEL
    if [ "$CANCEL" = "y" ]; then
        echo ""
        echo "5️⃣ Cancelando turno..."
        CANCEL_RESULT=$(curl -s -X POST "$ACTIONS_URL/actions/cancel-appointment" \
          -H "Content-Type: application/json" \
          -H "X-Workspace-Id: $WORKSPACE_ID" \
          -d "{
            \"appointment_id\": \"$APPT_ID\",
            \"cancellation_reason\": \"Test de cancelación\"
          }")

        echo "$CANCEL_RESULT" | jq '.'
    fi
else
    echo "❌ Staff no disponible en ese horario"
fi

echo ""
echo "✅ Test completado"
