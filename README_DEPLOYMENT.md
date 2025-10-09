# 🚀 PulpoAI - Guía de Deployment y CI/CD

## 📋 Resumen

Hemos implementado un sistema completo de **CI/CD + Canary + Observabilidad** para PulpoAI:

- ✅ **Pipeline CI/CD** con gates de calidad y coverage
- ✅ **Canary deployment** con feature flags configurables
- ✅ **Dashboards** de observabilidad (Prometheus + Grafana)
- ✅ **Smoke tests E2E** del loop completo del agente
- ✅ **Scripts de deployment** automatizados

## 🏗️ Arquitectura Implementada

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub        │    │   Docker        │    │   Monitoring    │
│   Actions       │───▶│   Compose       │───▶│   Stack         │
│   CI/CD         │    │   Services      │    │   (Prometheus   │
└─────────────────┘    └─────────────────┘    │    + Grafana)   │
                                              └─────────────────┘
```

## 🚀 Quick Start

### 1. **Deployment Local**

```bash
# Clonar y configurar
git clone <repo>
cd pulpo

# Instalar dependencias
pip install -r requirements.txt

# Ejecutar tests
python tests/run_tests.py all

# Deploy con Docker Compose
./scripts/deploy.sh staging
```

### 2. **Acceder a Servicios**

- **Aplicación**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Métricas**: http://localhost:8000/metrics/prometheus
- **Health**: http://localhost:8000/metrics/health
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)

## 🔧 Configuración CI/CD

### GitHub Actions

El pipeline se ejecuta automáticamente en:
- **Push** a `main` o `develop`
- **Pull Requests** a `main` o `develop`

**Gates de calidad:**
- ✅ **Linting**: Black, isort, flake8, mypy
- ✅ **Security**: Bandit, Safety
- ✅ **Tests**: Unit + Smoke E2E + Coverage (85%)
- ✅ **Build**: Docker image
- ✅ **Deploy**: Staging automático

### Pre-commit Hooks

```bash
# Instalar pre-commit
pip install pre-commit
pre-commit install

# Ejecutar manualmente
pre-commit run --all-files
```

## 🎯 Canary Deployment

### Configuración

```bash
# Variables de entorno
export CANARY_ENABLED=true
export CANARY_PERCENTAGE=0.1  # 10% de tráfico
export CANARY_STRATEGY=percentage
```

### Estrategias Disponibles

1. **Porcentaje**: `CANARY_STRATEGY=percentage`
2. **Workspace**: `CANARY_STRATEGY=workspace`
3. **Usuario**: `CANARY_STRATEGY=user_id`
4. **Geográfico**: `CANARY_STRATEGY=geographic`

### Control Dinámico

```bash
# Ver estado actual
curl http://localhost:8000/metrics/canary/status

# Actualizar configuración
curl -X POST http://localhost:8000/metrics/canary/config \
  -H "Content-Type: application/json" \
  -d '{"percentage": 0.2, "enabled": true}'
```

## 📊 Observabilidad

### Métricas Prometheus

**Contadores:**
- `pulpo_tool_calls_total` - Total de tool calls
- `pulpo_orchestrator_requests_total` - Requests del orchestrator
- `pulpo_circuit_breaker_state_changes_total` - Cambios de circuit breaker
- `pulpo_rate_limit_hits_total` - Hits de rate limiting

**Histogramas:**
- `pulpo_tool_execution_duration_seconds` - Duración de tools
- `pulpo_orchestrator_duration_seconds` - Duración del orchestrator
- `pulpo_planner_duration_seconds` - Duración del planner
- `pulpo_policy_duration_seconds` - Duración del policy

**Gauges:**
- `pulpo_active_circuit_breakers` - Circuit breakers activos
- `pulpo_cache_size` - Tamaño de caches
- `pulpo_canary_traffic_percentage` - Porcentaje de tráfico canary

### Dashboards Grafana

**Dashboard Principal**: "PulpoAI - System Overview"
- 📈 Request Rate
- ❌ Error Rate  
- ⏱️ P95 Latency
- 🔴 Active Circuit Breakers
- 🛠️ Tool Calls Over Time
- ⚡ Tool Execution Duration
- 🚫 Rate Limit Hits
- 🔄 Circuit Breaker State Changes

### Alertas Configuradas

- **Error Rate > 5%** → Warning
- **P95 Latency > 3s** → Warning
- **Circuit Breaker OPEN** → Critical
- **Rate Limit Hits** → Info

## 🧪 Testing

### Tipos de Tests

```bash
# Todos los tests
python tests/run_tests.py all

# Tests específicos
python tests/run_tests.py unit      # Tests unitarios
python tests/run_tests.py smoke     # Smoke tests E2E
python tests/run_tests.py integration  # Tests de integración
python tests/run_tests.py lint      # Linting
python tests/run_tests.py security  # Security scan
```

### Smoke Tests E2E

Validan el flujo completo del agente:
- ✅ **Consulta de servicios** → `get_services`
- ✅ **Flujo de reserva** → `get_availability` + `book_appointment`
- ✅ **Policy denial** → Manejo de errores
- ✅ **Fallback legacy** → Recuperación de errores
- ✅ **Feature flag** → Alternancia entre sistemas
- ✅ **Telemetría** → Emisión de métricas

## 🚀 Deployment

### Scripts Disponibles

```bash
# Deployment a staging
./scripts/deploy.sh staging

# Deployment a producción
./scripts/deploy.sh production
```

### Proceso de Deployment

1. **Pre-checks**: Docker, Python, archivos
2. **Tests**: Unit + Smoke + Integration
3. **Build**: Imagen Docker
4. **Deploy**: Docker Compose
5. **Health Checks**: Aplicación + Prometheus + Grafana
6. **Verificación**: Métricas y logs

### Rollback

```bash
# Rollback rápido
docker-compose down
docker-compose up -d

# Rollback con imagen anterior
docker tag pulpo-ai:previous pulpo-ai:latest
docker-compose up -d
```

## 📈 Monitoreo en Producción

### SLOs (Service Level Objectives)

- **Disponibilidad**: 99.9%
- **Latencia P95**: < 1 segundo
- **Error Rate**: < 1%

### Métricas Clave

```bash
# Ver estado de SLOs
curl http://localhost:8000/metrics/slo/status

# Ver alertas activas
curl http://localhost:8000/metrics/alerts/active

# Ver performance de tools
curl http://localhost:8000/metrics/tools/performance
```

### Logs Estructurados

```bash
# Ver logs de la aplicación
docker-compose logs -f pulpo-app

# Ver logs con filtros
docker-compose logs -f pulpo-app | grep "AGENT_LOOP"
docker-compose logs -f pulpo-app | grep "ERROR"
```

## 🔧 Troubleshooting

### Problemas Comunes

**1. Tests fallan en CI/CD**
```bash
# Ejecutar localmente
python tests/run_tests.py all
pre-commit run --all-files
```

**2. Circuit Breaker abierto**
```bash
# Ver estado
curl http://localhost:8000/metrics/tools/performance

# Forzar half-open (en código)
circuit_breaker.force_half_open()
```

**3. Canary no funciona**
```bash
# Verificar configuración
curl http://localhost:8000/metrics/canary/status

# Verificar logs
docker-compose logs pulpo-app | grep "CANARY"
```

**4. Métricas no aparecen**
```bash
# Verificar Prometheus
curl http://localhost:9090/-/healthy

# Verificar endpoint
curl http://localhost:8000/metrics/prometheus
```

## 📚 Próximos Pasos

### Fase 3: Optimizaciones

1. **Paralelización de Tools** - Ejecutar tools independientes en paralelo
2. **Load Testing** - Tests de carga con picos y sostenido
3. **Chaos Engineering** - Simular fallos y degradaciones
4. **Auto-scaling** - Escalado automático basado en métricas

### Fase 4: Avanzado

1. **Multi-region** - Deployment en múltiples regiones
2. **Blue-Green** - Deployment sin downtime
3. **A/B Testing** - Testing de features
4. **ML Monitoring** - Monitoreo de modelos LLM

## 🎉 ¡Listo para Producción!

El sistema está **completamente preparado** para producción con:

- ✅ **CI/CD robusto** con gates de calidad
- ✅ **Canary deployment** seguro y configurable
- ✅ **Observabilidad completa** con métricas y dashboards
- ✅ **Tests E2E** que validan el flujo completo
- ✅ **Scripts de deployment** automatizados
- ✅ **Monitoreo y alertas** configurados

**¡PulpoAI está listo para escalar! 🚀**
