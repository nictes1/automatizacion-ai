#!/bin/bash

# Script de deployment para PulpoAI
# Uso: ./scripts/deploy.sh [staging|production]

set -e  # Exit on any error

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

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verificar argumentos
ENVIRONMENT=${1:-staging}

if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    error "Entorno inválido. Usar: staging o production"
    exit 1
fi

log "🚀 Iniciando deployment a $ENVIRONMENT"

# ==========================================
# PRE-DEPLOYMENT CHECKS
# ==========================================

log "🔍 Ejecutando checks pre-deployment..."

# Verificar que estamos en el directorio correcto
if [[ ! -f "main.py" ]]; then
    error "No se encontró main.py. Ejecutar desde el directorio raíz del proyecto."
    exit 1
fi

# Verificar que Docker esté instalado
if ! command -v docker &> /dev/null; then
    error "Docker no está instalado"
    exit 1
fi

# Verificar que Docker Compose esté instalado
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose no está instalado"
    exit 1
fi

# Verificar que Python esté instalado
if ! command -v python3 &> /dev/null; then
    error "Python 3 no está instalado"
    exit 1
fi

success "Checks pre-deployment completados"

# ==========================================
# TESTS
# ==========================================

log "🧪 Ejecutando tests..."

# Ejecutar tests
if python3 tests/run_tests.py all; then
    success "Todos los tests pasaron"
else
    error "Algunos tests fallaron. Abortando deployment."
    exit 1
fi

# ==========================================
# BUILD
# ==========================================

log "🏗️  Construyendo imagen Docker..."

# Build de la imagen
if docker build -t pulpo-ai:latest .; then
    success "Imagen Docker construida exitosamente"
else
    error "Error construyendo imagen Docker"
    exit 1
fi

# ==========================================
# DEPLOYMENT
# ==========================================

log "🚀 Desplegando a $ENVIRONMENT..."

# Crear archivo de configuración específico del entorno
if [[ "$ENVIRONMENT" == "production" ]]; then
    # Configuración de producción
    export CANARY_ENABLED=true
    export CANARY_PERCENTAGE=0.05  # 5% inicial
    export LOG_LEVEL=WARNING
    export DATABASE_URL="postgresql://pulpo:pulpo@postgres:5432/pulpo"
    export REDIS_URL="redis://redis:6379/1"
    
    log "Configuración de producción aplicada"
else
    # Configuración de staging
    export CANARY_ENABLED=true
    export CANARY_PERCENTAGE=0.5   # 50% en staging
    export LOG_LEVEL=INFO
    export DATABASE_URL="postgresql://pulpo:pulpo@postgres:5432/pulpo"
    export REDIS_URL="redis://redis:6379/1"
    
    log "Configuración de staging aplicada"
fi

# Detener servicios existentes
log "🛑 Deteniendo servicios existentes..."
docker-compose down || warning "No había servicios ejecutándose"

# Iniciar servicios
log "▶️  Iniciando servicios..."
if docker-compose up -d; then
    success "Servicios iniciados exitosamente"
else
    error "Error iniciando servicios"
    exit 1
fi

# ==========================================
# HEALTH CHECKS
# ==========================================

log "🏥 Ejecutando health checks..."

# Esperar a que los servicios estén listos
log "Esperando a que los servicios estén listos..."
sleep 30

# Health check de la aplicación
log "Verificando salud de la aplicación..."
for i in {1..10}; do
    if curl -f http://localhost:8000/metrics/health > /dev/null 2>&1; then
        success "Aplicación saludable"
        break
    else
        if [[ $i -eq 10 ]]; then
            error "Health check falló después de 10 intentos"
            exit 1
        fi
        log "Intento $i/10 - Esperando..."
        sleep 10
    fi
done

# Health check de Prometheus
log "Verificando Prometheus..."
if curl -f http://localhost:9090/-/healthy > /dev/null 2>&1; then
    success "Prometheus saludable"
else
    warning "Prometheus no responde (puede estar iniciando)"
fi

# Health check de Grafana
log "Verificando Grafana..."
if curl -f http://localhost:3000/api/health > /dev/null 2>&1; then
    success "Grafana saludable"
else
    warning "Grafana no responde (puede estar iniciando)"
fi

# ==========================================
# POST-DEPLOYMENT
# ==========================================

log "📊 Verificando métricas..."

# Verificar que las métricas se estén generando
if curl -f http://localhost:8000/metrics/prometheus > /dev/null 2>&1; then
    success "Métricas disponibles"
else
    warning "Métricas no disponibles aún"
fi

# ==========================================
# SUMMARY
# ==========================================

log "📋 Resumen del deployment:"
echo ""
echo "🌐 URLs disponibles:"
echo "   • Aplicación: http://localhost:8000"
echo "   • API Docs: http://localhost:8000/docs"
echo "   • Métricas: http://localhost:8000/metrics/prometheus"
echo "   • Health: http://localhost:8000/metrics/health"
echo "   • Prometheus: http://localhost:9090"
echo "   • Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo "🔧 Comandos útiles:"
echo "   • Ver logs: docker-compose logs -f pulpo-app"
echo "   • Ver estado: docker-compose ps"
echo "   • Detener: docker-compose down"
echo "   • Reiniciar: docker-compose restart pulpo-app"
echo ""

if [[ "$ENVIRONMENT" == "production" ]]; then
    warning "⚠️  DEPLOYMENT EN PRODUCCIÓN"
    echo "   • Canary habilitado al 5%"
    echo "   • Monitorear métricas en Grafana"
    echo "   • Verificar logs regularmente"
    echo "   • Listo para escalar canary gradualmente"
else
    success "✅ DEPLOYMENT EN STAGING COMPLETADO"
    echo "   • Canary habilitado al 50%"
    echo "   • Listo para testing"
    echo "   • Verificar funcionalidad antes de producción"
fi

success "🎉 Deployment a $ENVIRONMENT completado exitosamente!"
