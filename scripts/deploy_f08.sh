#!/bin/bash

# Script de despliegue para F-08: Tool Calls Integration
# Incluye Actions Service v2 y workflow n8n actualizado

set -e

echo "🚀 PulpoAI F-08 Deployment - Tool Calls Integration"
echo "===================================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para logging
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Verificar dependencias
check_dependencies() {
    log "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
    fi
    
    success "Dependencies OK"
}

# Crear directorios necesarios
create_directories() {
    log "Creating necessary directories..."
    
    mkdir -p uploads
    mkdir -p logs
    mkdir -p data/ollama_testing
    mkdir -p data/postgres_testing
    
    success "Directories created"
}

# Configurar variables de entorno
setup_environment() {
    log "Setting up environment variables..."
    
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

# Construir imágenes Docker
build_images() {
    log "Building Docker images..."
    
    docker-compose -f docker-compose.integrated.yml build --no-cache
    
    success "Images built"
}

# Iniciar servicios base
start_base_services() {
    log "Starting base services..."
    
    # Iniciar servicios base primero
    docker-compose -f docker-compose.integrated.yml up -d postgres redis
    
    # Esperar a que PostgreSQL esté listo
    log "Waiting for PostgreSQL to be ready..."
    sleep 15
    
    success "Base services started"
}

# Aplicar migraciones SQL
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
    
    # Iniciar el resto de servicios
    docker-compose -f docker-compose.integrated.yml up -d
    
    success "Application services started"
}

# Verificar salud de servicios
check_health() {
    log "Checking service health..."
    
    # Esperar a que los servicios estén listos
    sleep 30
    
    # Test Orchestrator Service
    if curl -f http://localhost:8005/health > /dev/null 2>&1; then
        success "Orchestrator Service is healthy"
    else
        warning "Orchestrator Service may not be ready yet"
    fi
    
    # Test Actions Service
    if curl -f http://localhost:8006/health > /dev/null 2>&1; then
        success "Actions Service is healthy"
    else
        warning "Actions Service may not be ready yet"
    fi
    
    # Test n8n
    if curl -f http://localhost:5678 > /dev/null 2>&1; then
        success "n8n is accessible"
    else
        warning "n8n may not be ready yet"
    fi
    
    # Test PostgreSQL
    if docker-compose -f docker-compose.integrated.yml exec postgres pg_isready -U pulpo > /dev/null 2>&1; then
        success "PostgreSQL is healthy"
    else
        error "PostgreSQL is not ready"
    fi
}

# Ejecutar tests de integración
run_tests() {
    log "Running integration tests..."
    
    # Instalar dependencias de testing
    pip install requests psycopg2-binary
    
    # Test F-07 (smoke test)
    log "Running F-07 smoke test..."
    ./scripts/smoke_test.sh
    
    # Test F-08 (tool calls)
    log "Running F-08 tool calls test..."
    python scripts/test_f08.py
    
    success "Integration tests completed"
}

# Mostrar información de acceso
show_access_info() {
    log "F-08 Deployment completed! Access information:"
    echo ""
    echo "🌐 Services:"
    echo "   • n8n: http://localhost:5678 (admin/admin123)"
    echo "   • Orchestrator: http://localhost:8005"
    echo "   • Actions Service: http://localhost:8006"
    echo "   • Ingestion: http://localhost:8007"
    echo "   • RAG Worker: http://localhost:8002"
    echo "   • Prometheus: http://localhost:9090"
    echo "   • Grafana: http://localhost:3000 (admin/admin123)"
    echo ""
    echo "📊 Database:"
    echo "   • PostgreSQL: localhost:5432 (pulpo/pulpo)"
    echo "   • Redis: localhost:6379"
    echo ""
    echo "🔧 F-08 Features:"
    echo "   • Tool calls execution via Actions Service"
    echo "   • Idempotent action processing"
    echo "   • Database persistence for actions"
    echo "   • n8n workflow with tool call handling"
    echo ""
    echo "📋 Next steps:"
    echo "   1. Import n8n workflow: n8n/n8n-workflow-f08.json"
    echo "   2. Configure Twilio credentials in .env"
    echo "   3. Test tool calls: python scripts/test_f08.py"
    echo "   4. Monitor with Grafana"
    echo ""
    echo "🧪 Testing commands:"
    echo "   • Smoke test: ./scripts/smoke_test.sh"
    echo "   • F-08 test: python scripts/test_f08.py"
    echo "   • Complete test: python scripts/test_integration.py"
    echo ""
}

# Función principal
main() {
    log "Starting F-08 Deployment"
    
    check_dependencies
    create_directories
    setup_environment
    build_images
    start_base_services
    apply_migrations
    start_application_services
    check_health
    run_tests
    show_access_info
    
    success "F-08 Deployment completed successfully!"
}

# Manejo de errores
trap 'error "Deployment failed at line $LINENO"' ERR

# Ejecutar si es llamado directamente
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
