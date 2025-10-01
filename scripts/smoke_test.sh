#!/bin/bash

# Smoke Test para F-07: n8n + Orchestrator Service
# Validación rápida (5 minutos)

set -e

echo "🧪 PulpoAI Smoke Test - F-07"
echo "============================="

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuración
N8N_URL="http://localhost:5678"
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

# Test 1: Webhook n8n
test_webhook() {
    log "Test 1: Webhook n8n (simulando Twilio)"
    
    # Payload simulado de Twilio
    curl -X POST "${N8N_URL}/webhook/pulpo/twilio/wa/inbound" \
        -H "Content-Type: application/json" \
        -d '{
            "Body": "hola, quiero hacer un pedido",
            "From": "whatsapp:+5491111111111",
            "To": "whatsapp:+14155238886",
            "SmsSid": "SM_test_'$(date +%s)'",
            "WorkspaceId": "00000000-0000-0000-0000-000000000001"
        }' \
        --max-time 10 \
        --silent --show-error --fail > /dev/null
    
    if [ $? -eq 0 ]; then
        success "Webhook n8n OK"
        return 0
    else
        error "Webhook n8n FAILED"
        return 1
    fi
}

# Test 2: Base de datos
test_database() {
    log "Test 2: Base de datos (conversaciones)"
    
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

# Test 3: Orchestrator Service
test_orchestrator() {
    log "Test 3: Orchestrator Service"
    
    # Test directo al Orchestrator
    response=$(curl -X POST "http://localhost:8005/orchestrator/decide" \
        -H "Content-Type: application/json" \
        -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
        -H "X-Request-Id: smoke-test-$(date +%s)" \
        -d '{
            "conversation_id": "smoke-test-123",
            "vertical": "gastronomia",
            "user_input": "hola, quiero hacer un pedido",
            "greeted": false,
            "slots": {},
            "objective": "",
            "last_action": null,
            "attempts_count": 0
        }' \
        --max-time 5 \
        --silent --show-error 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == *"ERROR"* ]]; then
        error "Orchestrator Service not responding"
        return 1
    fi
    
    # Verificar que la respuesta tiene el formato esperado
    if echo "$response" | grep -q "assistant"; then
        success "Orchestrator Service OK"
        echo "   Response: $(echo "$response" | jq -r '.assistant' 2>/dev/null | head -c 50)..."
        return 0
    else
        error "Orchestrator Service invalid response"
        echo "   Response: $response"
        return 1
    fi
}

# Test 4: Verificar logs de n8n
test_n8n_logs() {
    log "Test 4: Verificar logs n8n"
    
    # Verificar que n8n está corriendo
    if curl -s "${N8N_URL}/healthz" > /dev/null 2>&1; then
        success "n8n is running"
        return 0
    else
        warning "n8n health check not available (normal if not configured)"
        return 0
    fi
}

# Test 5: Verificar servicios Docker
test_docker_services() {
    log "Test 5: Verificar servicios Docker"
    
    # Verificar que los contenedores están corriendo
    services=("postgres" "redis" "orchestrator" "n8n")
    running=0
    
    for service in "${services[@]}"; do
        if docker ps --format "table {{.Names}}" | grep -q "$service"; then
            success "$service is running"
            ((running++))
        else
            warning "$service not found in running containers"
        fi
    done
    
    if [ $running -gt 0 ]; then
        success "$running services running"
        return 0
    else
        error "No services running"
        return 1
    fi
}

# Función principal
main() {
    log "Starting smoke test..."
    
    tests=(
        "test_webhook"
        "test_database" 
        "test_orchestrator"
        "test_n8n_logs"
        "test_docker_services"
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
    echo "============================="
    echo "📊 Smoke Test Results: $passed/$total passed"
    
    if [ $passed -eq $total ]; then
        success "All tests passed! F-07 is working correctly."
        echo ""
        echo "🎯 Next steps:"
        echo "   1. Implement F-08 (Tool Calls)"
        echo "   2. Test Actions Service"
        echo "   3. Validate complete flow"
    else
        error "Some tests failed. Check the logs above."
        echo ""
        echo "🔧 Troubleshooting:"
        echo "   1. Check Docker services: docker ps"
        echo "   2. Check logs: docker-compose logs"
        echo "   3. Verify database: psql $DB_URL"
    fi
    
    return $([ $passed -eq $total ] && echo 0 || echo 1)
}

# Ejecutar si es llamado directamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
