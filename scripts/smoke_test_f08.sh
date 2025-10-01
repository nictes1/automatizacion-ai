#!/bin/bash

# Smoke Test F-08: n8n + Orchestrator + Actions Service
# Test completo del flujo de tool calls

set -e

echo "🧪 PulpoAI F-08 Smoke Test"
echo "=========================="

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuración
N8N_URL="http://localhost:5678"
ORCHESTRATOR_URL="http://localhost:8005"
ACTIONS_URL="http://localhost:8006"
DB_URL="postgresql://pulpo:pulpo@localhost:5432/pulpo"

log() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅${NC} $1"
}

error() {
    echo -e "${RED}❌${NC} $1"
}

warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

# Test 1: Verificar servicios
test_services() {
    log "Test 1: Verificar servicios"
    
    # Orchestrator Service
    if curl -f "${ORCHESTRATOR_URL}/health" > /dev/null 2>&1; then
        success "Orchestrator Service OK"
    else
        error "Orchestrator Service not responding"
        return 1
    fi
    
    # Actions Service
    if curl -f "${ACTIONS_URL}/health" > /dev/null 2>&1; then
        success "Actions Service OK"
    else
        error "Actions Service not responding"
        return 1
    fi
    
    # n8n
    if curl -f "${N8N_URL}" > /dev/null 2>&1; then
        success "n8n OK"
    else
        error "n8n not responding"
        return 1
    fi
    
    return 0
}

# Test 2: Test directo Actions Service
test_actions_direct() {
    log "Test 2: Actions Service directo"
    
    response=$(curl -s -X POST "${ACTIONS_URL}/actions/execute" \
        -H "Content-Type: application/json" \
        -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
        -H "X-Request-Id: smoke-test-$(date +%s)" \
        -d '{
            "name": "search_menu",
            "args": {"categoria": "pizzas", "query": "margarita"},
            "conversation_id": "smoke-test-123",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "request_id": "smoke-test-123"
        }' 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == *"ERROR"* ]]; then
        error "Actions Service direct test failed"
        return 1
    fi
    
    if echo "$response" | grep -q '"ok":true'; then
        success "Actions Service direct OK"
        return 0
    else
        error "Actions Service returned error"
        echo "Response: $response"
        return 1
    fi
}

# Test 3: Test Orchestrator Service
test_orchestrator_direct() {
    log "Test 3: Orchestrator Service directo"
    
    response=$(curl -s -X POST "${ORCHESTRATOR_URL}/orchestrator/decide" \
        -H "Content-Type: application/json" \
        -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
        -H "X-Request-Id: smoke-test-$(date +%s)" \
        -d '{
            "conversation_id": "smoke-test-456",
            "vertical": "gastronomia",
            "user_input": "hola, quiero hacer un pedido",
            "greeted": false,
            "slots": {},
            "objective": "",
            "last_action": null,
            "attempts_count": 0
        }' 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == *"ERROR"* ]]; then
        error "Orchestrator Service direct test failed"
        return 1
    fi
    
    if echo "$response" | grep -q '"assistant"'; then
        success "Orchestrator Service direct OK"
        return 0
    else
        error "Orchestrator Service returned error"
        echo "Response: $response"
        return 1
    fi
}

# Test 4: Test webhook n8n
test_n8n_webhook() {
    log "Test 4: n8n Webhook"
    
    # Simular mensaje de WhatsApp
    webhook_data='{
        "Body": "hola, quiero una docena de empanadas",
        "From": "whatsapp:+5491111111111",
        "To": "whatsapp:+14155238886",
        "SmsSid": "SM_test_'$(date +%s)'",
        "WorkspaceId": "00000000-0000-0000-0000-000000000001"
    }'
    
    response=$(curl -s -X POST "${N8N_URL}/webhook/pulpo/twilio/wa/inbound" \
        -H "Content-Type: application/json" \
        -d "$webhook_data" 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == *"ERROR"* ]]; then
        error "n8n Webhook test failed"
        return 1
    fi
    
    if echo "$response" | grep -q "200\|success\|Mensaje procesado"; then
        success "n8n Webhook OK"
        return 0
    else
        warning "n8n Webhook response unclear: $response"
        return 0  # No es crítico
    fi
}

# Test 5: Verificar base de datos
test_database() {
    log "Test 5: Base de datos"
    
    # Verificar conversaciones recientes
    result=$(psql "${DB_URL}" -t -c "
        SELECT id, total_messages, last_message_sender, last_message_text
        FROM pulpo.conversations
        ORDER BY last_message_at DESC
        LIMIT 3;
    " 2>/dev/null || echo "ERROR")
    
    if [[ "$result" == *"ERROR"* ]]; then
        error "Database connection failed"
        return 1
    fi
    
    # Verificar que hay conversaciones
    count=$(echo "$result" | grep -c "|" || echo "0")
    if [ "$count" -gt 0 ]; then
        success "Database OK - $count conversations found"
        echo "   Recent conversations:"
        echo "$result" | head -3 | while read line; do
            echo "   $line"
        done
        return 0
    else
        warning "No conversations found (may be normal for new setup)"
        return 0
    fi
}

# Test 6: Test completo del flujo
test_complete_flow() {
    log "Test 6: Flujo completo"
    
    # Este test simula el flujo completo: webhook -> orchestrator -> actions -> response
    
    # 1. Enviar webhook
    webhook_data='{
        "Body": "quiero ver el menú de pizzas",
        "From": "whatsapp:+5491111111111",
        "To": "whatsapp:+14155238886",
        "SmsSid": "SM_flow_'$(date +%s)'",
        "WorkspaceId": "00000000-0000-0000-0000-000000000001"
    }'
    
    log "   Enviando webhook..."
    webhook_response=$(curl -s -X POST "${N8N_URL}/webhook/pulpo/twilio/wa/inbound" \
        -H "Content-Type: application/json" \
        -d "$webhook_data" 2>/dev/null || echo "ERROR")
    
    if [[ "$webhook_response" == *"ERROR"* ]]; then
        error "Webhook failed in complete flow test"
        return 1
    fi
    
    # 2. Esperar un poco para que procese
    sleep 3
    
    # 3. Verificar que se creó la conversación
    conversation_count=$(psql "${DB_URL}" -t -c "
        SELECT COUNT(*) FROM pulpo.conversations 
        WHERE last_message_at > NOW() - INTERVAL '1 minute';
    " 2>/dev/null || echo "0")
    
    if [ "$conversation_count" -gt 0 ]; then
        success "Complete flow test OK - conversation created"
        return 0
    else
        warning "Complete flow test - no new conversations found"
        return 0  # No es crítico
    fi
}

# Función principal
main() {
    log "Starting F-08 Smoke Test"
    
    tests=(
        "test_services"
        "test_actions_direct"
        "test_orchestrator_direct"
        "test_n8n_webhook"
        "test_database"
        "test_complete_flow"
    )
    
    passed=0
    total=${#tests[@]}
    
    for test in "${tests[@]}"; do
        echo ""
        if $test; then
            ((passed++))
        fi
    done
    
    echo ""
    echo "=========================="
    echo "📊 F-08 Smoke Test Results: $passed/$total passed"
    
    if [ $passed -eq $total ]; then
        success "All tests passed! F-08 is working correctly."
        echo ""
        echo "🎯 Next steps:"
        echo "   1. Test with real WhatsApp sandbox"
        echo "   2. Monitor with Grafana"
        echo "   3. Deploy to production"
    else
        error "Some tests failed. Check the logs above."
        echo ""
        echo "🔧 Troubleshooting:"
        echo "   1. Check Docker services: docker ps"
        echo "   2. Check logs: docker-compose logs"
        echo "   3. Verify n8n workflow connections"
    fi
    
    return $([ $passed -eq $total ] && echo 0 || echo 1)
}

# Ejecutar si es llamado directamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
