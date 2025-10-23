# ✅ Checklist de Deployment - SLM Pipeline

Checklist completo para desplegar el SLM Pipeline a producción con canary deployment.

---

## 📋 Pre-Deployment

### 1. Código y Tests

- [ ] **Código revisado y mergeado a `main`**
  - [ ] `services/slm/extractor.py`
  - [ ] `services/slm/planner.py`
  - [ ] `services/response/simple_nlg.py`
  - [ ] `services/orchestrator_slm_pipeline.py`
  - [ ] `services/orchestrator_integration.py`
  - [ ] `api/webhook_adapter.py`
  - [ ] `api/routes/webhook_twilio.py`

- [ ] **Tests ejecutados y pasando**
  ```bash
  pytest tests/unit/test_planner_slm.py -v
  pytest tests/e2e/test_slm_pipeline_e2e.py -v
  ./tests/smoke/smoke_test.sh
  ```

- [ ] **Linters y type checking OK**
  ```bash
  ruff check services/
  mypy services/ --ignore-missing-imports
  ```

### 2. Configuración

- [ ] **Variables de entorno configuradas**
  - [ ] `ENABLE_SLM_PIPELINE=true`
  - [ ] `SLM_CANARY_PERCENT=10` (empezar con 10%)
  - [ ] `SLM_EXTRACTOR_MODEL=qwen2.5:7b`
  - [ ] `SLM_PLANNER_MODEL=qwen2.5:7b`
  - [ ] `SLM_CONFIDENCE_THRESHOLD=0.7`
  - [ ] `SLM_FALLBACK_TO_LLM=true`
  - [ ] Timeouts configurados (ver `.env.example`)

- [ ] **Schemas JSON presentes**
  - [ ] `config/schemas/extractor_v1.json`
  - [ ] `config/schemas/planner_v1.json`
  - [ ] `config/schemas/response_v1.json`

- [ ] **Modelos SLM disponibles**
  ```bash
  # Ollama
  ollama list | grep qwen2.5:7b
  ollama list | grep phi3:mini
  
  # vLLM (si aplica)
  curl http://localhost:8001/v1/models
  ```

### 3. Infraestructura

- [ ] **Base de datos migrada**
  ```bash
  alembic upgrade head
  ```

- [ ] **Secrets configurados**
  - [ ] API keys (Anthropic, OpenAI, etc.)
  - [ ] Twilio credentials
  - [ ] Database URL

- [ ] **Recursos suficientes**
  - [ ] CPU: 4+ cores
  - [ ] RAM: 16GB+ (para SLMs 7B)
  - [ ] GPU: Opcional pero recomendado (RTX 3090, A100, etc.)
  - [ ] Disk: 50GB+ libre

### 4. Observabilidad

- [ ] **Logging configurado**
  - [ ] Logs estructurados habilitados
  - [ ] Log level: `INFO` en prod, `DEBUG` en staging
  - [ ] Rotación de logs configurada

- [ ] **Métricas configuradas**
  - [ ] Prometheus exporters activos
  - [ ] Dashboard Grafana creado
  - [ ] Alertas configuradas:
    - [ ] Latencia p90 > 2000ms
    - [ ] Error rate > 2%
    - [ ] Confidence < 0.7 (> 10% requests)

- [ ] **Tracing (opcional)**
  - [ ] OpenTelemetry configurado
  - [ ] Jaeger/Zipkin disponible

### 5. Rollback Plan

- [ ] **Backup de código anterior**
  ```bash
  git tag pre-slm-pipeline-$(date +%Y%m%d)
  git push origin --tags
  ```

- [ ] **Rollback script preparado**
  ```bash
  # rollback.sh
  export ENABLE_SLM_PIPELINE=false
  systemctl restart pulpo-api
  ```

- [ ] **Equipo notificado**
  - [ ] Slack/Discord channel activo
  - [ ] On-call engineer asignado
  - [ ] Escalation path definido

---

## 🚀 Deployment

### Fase 1: Staging (Día -1)

- [ ] **Deploy a staging**
  ```bash
  git checkout main
  git pull origin main
  docker-compose -f docker-compose.staging.yml up -d
  ```

- [ ] **Smoke tests en staging**
  ```bash
  API_URL=https://staging.pulpoai.com ./tests/smoke/smoke_test.sh
  ```

- [ ] **Validación manual**
  - [ ] Saludo
  - [ ] Consulta horarios
  - [ ] Consulta precios
  - [ ] Reserva completa
  - [ ] Reserva incompleta
  - [ ] Cancelación

- [ ] **Métricas baseline**
  - [ ] Latencia p50/p90/p99
  - [ ] Error rate
  - [ ] Confidence promedio

### Fase 2: Canary 10% (Día 1-2)

- [ ] **Deploy a producción con canary 10%**
  ```bash
  export ENABLE_SLM_PIPELINE=true
  export SLM_CANARY_PERCENT=10
  
  # Deploy
  docker-compose -f docker-compose.prod.yml up -d
  ```

- [ ] **Monitoreo cada 2 horas**
  - [ ] Dashboard Grafana abierto
  - [ ] Logs en tiempo real
  - [ ] Alertas configuradas

- [ ] **Validaciones (cada 6 horas)**
  - [ ] Smoke tests
  - [ ] Revisar logs de errores
  - [ ] Comparar métricas SLM vs Legacy

- [ ] **Criterios de éxito (48 horas)**
  - [ ] ✅ p90 latency < 1500ms
  - [ ] ✅ Error rate < 1%
  - [ ] ✅ No quejas de usuarios
  - [ ] ✅ Confidence promedio > 0.8

### Fase 3: Canary 50% (Día 3-4)

- [ ] **Elevar a 50%**
  ```bash
  export SLM_CANARY_PERCENT=50
  systemctl restart pulpo-api
  ```

- [ ] **Análisis comparativo**
  - [ ] Latencia: SLM vs Legacy
  - [ ] Accuracy: SLM vs Legacy
  - [ ] User satisfaction: Feedback/quejas

- [ ] **Identificar edge cases**
  - [ ] Revisar requests con confidence < 0.7
  - [ ] Revisar policy denials
  - [ ] Revisar tool failures

- [ ] **Ajustes (si es necesario)**
  - [ ] Prompts de Extractor
  - [ ] Prompts de Planner
  - [ ] Timeouts
  - [ ] Thresholds

### Fase 4: Full SLM (Día 5+)

- [ ] **Elevar a 100%**
  ```bash
  export SLM_CANARY_PERCENT=0  # 0 = 100% SLM
  systemctl restart pulpo-api
  ```

- [ ] **Monitoreo intensivo (48 horas)**
  - [ ] Dashboard abierto 24/7
  - [ ] On-call engineer disponible
  - [ ] Rollback plan listo

- [ ] **Validación final**
  - [ ] Smoke tests cada 12 horas
  - [ ] Revisar métricas diarias
  - [ ] Feedback de usuarios

---

## 📊 Post-Deployment

### Semana 1: Observación

- [ ] **Métricas diarias**
  - [ ] Latencia p50/p90/p99
  - [ ] Error rate
  - [ ] Confidence distribution
  - [ ] Tool success rate
  - [ ] Policy denial rate

- [ ] **Análisis de logs**
  - [ ] Top 10 errores
  - [ ] Requests más lentos
  - [ ] Intents más comunes
  - [ ] Tools más usados

- [ ] **Feedback de usuarios**
  - [ ] Revisar quejas/elogios
  - [ ] Encuestas de satisfacción
  - [ ] NPS score

### Semana 2: Optimización

- [ ] **Fine-tuning de prompts**
  - [ ] Extractor: Mejorar few-shot examples
  - [ ] Planner: Ajustar reglas de decisión
  - [ ] Response: Mejorar plantillas

- [ ] **Optimización de latencia**
  - [ ] Identificar bottlenecks
  - [ ] Paralelizar tools cuando sea posible
  - [ ] Cachear respuestas frecuentes

- [ ] **Golden dataset**
  - [ ] Crear 10 conversaciones por intent
  - [ ] Automatizar tests en CI/CD
  - [ ] Baseline de métricas

### Mes 1: Consolidación

- [ ] **Documentación actualizada**
  - [ ] README principal
  - [ ] Runbook de troubleshooting
  - [ ] Decisiones arquitectónicas

- [ ] **Training del equipo**
  - [ ] Sesión de onboarding
  - [ ] Demo del pipeline
  - [ ] Q&A session

- [ ] **Planificación siguiente fase**
  - [ ] LLM fallback automático
  - [ ] Fine-tuning PEFT
  - [ ] Critic SLM
  - [ ] Multi-vertical support

---

## 🔧 Troubleshooting

### Rollback Inmediato

Si algo sale mal:

```bash
# Opción 1: Deshabilitar SLM
export ENABLE_SLM_PIPELINE=false
systemctl restart pulpo-api

# Opción 2: Canary 100% (todo a legacy)
export SLM_CANARY_PERCENT=100
systemctl restart pulpo-api

# Opción 3: Rollback a versión anterior
git checkout pre-slm-pipeline-YYYYMMDD
docker-compose -f docker-compose.prod.yml up -d --build
```

### Contactos de Emergencia

- **Tech Lead**: [nombre] - [email] - [phone]
- **DevOps**: [nombre] - [email] - [phone]
- **On-Call**: [rotation] - [slack channel]

---

## 📝 Sign-off

### Aprobaciones Requeridas

- [ ] **Tech Lead**: _________________ Fecha: _______
- [ ] **Product Manager**: _________________ Fecha: _______
- [ ] **DevOps**: _________________ Fecha: _______

### Post-Deployment Review

- [ ] **Retrospectiva agendada** (1 semana post-deploy)
- [ ] **Métricas documentadas** (baseline vs post-deploy)
- [ ] **Lecciones aprendidas** documentadas

---

**Última actualización:** 15 Enero 2025  
**Versión:** 1.0  
**Estado:** ✅ READY FOR DEPLOYMENT




