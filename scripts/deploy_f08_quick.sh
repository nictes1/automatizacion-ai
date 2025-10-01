#!/bin/bash

# Despliegue rápido F-08: n8n + Orchestrator + Actions Service
# Incluye todos los fixes y smoke test

set -e

echo "🚀 PulpoAI F-08 Quick Deploy"
echo "============================"

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Verificar dependencias
check_dependencies() {
    log "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    success "Dependencies OK"
}

# Crear directorios
create_directories() {
    log "Creating directories..."
    
    mkdir -p uploads logs data/ollama_testing data/postgres_testing
    
    success "Directories created"
}

# Configurar entorno
setup_environment() {
    log "Setting up environment..."
    
    if [ ! -f .env ]; then
        cat > .env << EOF
# Database
DATABASE_URL=postgresql://pulpo:pulpo@postgres:5432/pulpo

# Redis
REDIS_URL=redis://redis:6379

# Ollama
OLLAMA_URL=http://ollama:11434

# Tika
TIKA_URL=http://tika:9998

# JWT
JWT_SECRET=your-secret-key-change-this-in-production
JWT_ALGORITHM=HS256

# Twilio (configurar con tus credenciales)
TWILIO_ACCOUNT_SID=your-twilio-account-sid
TWILIO_AUTH_TOKEN=your-twilio-auth-token

# n8n
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123
EOF
        warning "Created .env file. Please update with your credentials."
    fi
    
    success "Environment configured"
}

# Construir imágenes
build_images() {
    log "Building Docker images..."
    
    docker-compose -f docker-compose.integrated.yml build --no-cache
    
    success "Images built"
}

# Iniciar servicios base
start_base_services() {
    log "Starting base services..."
    
    docker-compose -f docker-compose.integrated.yml up -d postgres redis
    
    # Esperar PostgreSQL
    log "Waiting for PostgreSQL..."
    sleep 15
    
    success "Base services started"
}

# Aplicar migraciones
apply_migrations() {
    log "Applying database migrations..."
    
    # Aplicar migraciones en orden
    for sql_file in sql/00_all_up.sql sql/14_actions_service.sql; do
        if [ -f "$sql_file" ]; then
            log "Applying $sql_file..."
            docker-compose -f docker-compose.integrated.yml exec -T postgres psql -U pulpo -d pulpo < "$sql_file" || warning "SQL migration $sql_file may have failed"
        fi
    done
    
    success "Database migrations applied"
}

# Iniciar servicios de aplicación
start_application_services() {
    log "Starting application services..."
    
    docker-compose -f docker-compose.integrated.yml up -d
    
    success "Application services started"
}

# Verificar salud
check_health() {
    log "Checking service health..."
    
    sleep 30
    
    # Test servicios
    services=("orchestrator:8005" "actions:8006" "n8n:5678")
    
    for service in "${services[@]}"; do
        name=$(echo $service | cut -d: -f1)
        port=$(echo $service | cut -d: -f2)
        
        if curl -f "http://localhost:$port/health" > /dev/null 2>&1; then
            success "$name is healthy"
        else
            warning "$name may not be ready yet"
        fi
    done
}

# Ejecutar smoke test
run_smoke_test() {
    log "Running F-08 smoke test..."
    
    ./scripts/smoke_test_f08.sh
    
    success "Smoke test completed"
}

# Mostrar información
show_info() {
    log "F-08 Deployment completed!"
    echo ""
    echo "🌐 Services:"
    echo "   • n8n: http://localhost:5678 (admin/admin123)"
    echo "   • Orchestrator: http://localhost:8005"
    echo "   • Actions: http://localhost:8006"
    echo "   • Prometheus: http://localhost:9090"
    echo "   • Grafana: http://localhost:3000 (admin/admin123)"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Import n8n workflow: n8n/n8n-workflow-f08-fixed.json"
    echo "   2. Follow checklist: CHECKLIST_N8N_F08.md"
    echo "   3. Configure Twilio credentials in .env"
    echo "   4. Test with WhatsApp sandbox"
    echo ""
    echo "🧪 Testing:"
    echo "   • Smoke test: ./scripts/smoke_test_f08.sh"
    echo "   • Manual test: curl -X POST http://localhost:5678/webhook/pulpo/twilio/wa/inbound ..."
    echo ""
}

# Función principal
main() {
    log "Starting F-08 Quick Deploy"
    
    check_dependencies
    create_directories
    setup_environment
    build_images
    start_base_services
    apply_migrations
    start_application_services
    check_health
    run_smoke_test
    show_info
    
    success "F-08 Quick Deploy completed!"
}

# Manejo de errores
trap 'error "Deployment failed at line $LINENO"' ERR

# Ejecutar si es llamado directamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
