# 🚀 Runbook Canary Deployment - SLM Pipeline

Guía ejecutiva para validar Legacy y activar SLM canary en minutos.

---

## ✅ PASO 1: Validar Legacy 100% (EJECUTAR AHORA)

### Variables

```bash
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0
```

### Levantar servicio

```bash
docker compose up -d pulpo-app

# Verificar que levantó
docker ps | grep pulpo-app
docker logs pulpo-app --tail 20
```

### Ejecutar validación

```bash
./tests/smoke/validate_legacy.sh
```

### ✅ Éxito esperado

- **3/3 tests passing**
- En response: `"route":"legacy"`
- Campos presentes: `assistant`, `tool_calls`, `patch`, `telemetry`
- Latencia p90 < 2000ms

### 🚨 Si algo falla

| Error | Causa | Solución |
|-------|-------|----------|
| `404 Not Found` | Path incorrecto | Verificar `/orchestrator/decide` existe |
| `422 Unprocessable` | Schema inválido | Comparar request con `DecideRequest` model |
| `500 Internal Error` | Exception en código | Ver `docker logs pulpo-app` |
| `route != "legacy"` | Flag mal seteado | Verificar `ENABLE_SLM_PIPELINE=false` |
| Latencia alta (>2s) | DB/Redis/MCP slow | Verificar healthchecks: `docker ps` |

**Debug rápido:**
```bash
# Ver logs en tiempo real
docker logs -f pulpo-app

# Verificar env vars
docker exec pulpo-app env | grep SLM

# Test manual
curl -X POST http://localhost:8000/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-debug" \
  -d @tests/fixtures/request_saludo.json | jq
```

---

## 🔹 PASO 2: Activar SLM Canary 10% (CUANDO PASO 1 ESTÉ VERDE)

### Variables

```bash
export ENABLE_SLM_PIPELINE=true
export SLM_CANARY_PERCENT=10   # 10% SLM / 90% Legacy
```

### Restart servicio

```bash
docker compose up -d pulpo-app

# Verificar logs de startup
docker logs pulpo-app --tail 50 | grep -i slm
```

### Validar canary

```bash
./tests/smoke/validate_slm_canary.sh
```

### ✅ Éxito esperado

- Distribución: ~2/20 requests a SLM, resto a Legacy
- Ambos routes funcionan correctamente
- Latencia SLM < 1500ms
- Sin errores 500

---

## 📊 Monitoreo en Vivo

### Ver routing en tiempo real

```bash
# Logs con routing info
docker logs -f pulpo-app | grep -E 'ROUTING|route='

# Contar distribución
docker logs pulpo-app | grep '"route":"slm_pipeline"' | wc -l
docker logs pulpo-app | grep '"route":"legacy"' | wc -l
```

### Ver latencias

```bash
# Latencias por route
docker logs pulpo-app | jq -r 'select(.telemetry) | [.telemetry.route, .telemetry.total_ms] | @tsv' | sort

# p90 approximation
docker logs pulpo-app | jq -r '.telemetry.total_ms' | sort -n | tail -10
```

### Métricas clave

```bash
# Ver telemetría completa
docker logs pulpo-app | jq 'select(.telemetry) | {route, total_ms, intent, confidence}'

# Filtrar solo SLM
docker logs pulpo-app | jq 'select(.telemetry.route == "slm_pipeline") | {total_ms, intent, confidence}'

# Filtrar errores
docker logs pulpo-app | jq 'select(.level == "error")'
```

---

## 🔄 Rollback Instantáneo

### Si algo no funciona

```bash
# Deshabilitar SLM
export ENABLE_SLM_PIPELINE=false
export SLM_CANARY_PERCENT=0

# Restart
docker compose up -d pulpo-app

# Verificar
curl -X POST http://localhost:8000/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-rollback-test" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route'

# Esperado: "legacy"
```

---

## 🧪 Tests con Conversation IDs Forzados

### Forzar route a SLM

```bash
# Conversation ID que cae en bucket < 10 (hash determinístico)
# Ejemplos de IDs que caen en SLM (canary=10):
# - wa-000... (bucket=0)
# - wa-001... (bucket varies, probar)

# Test forzado
curl -X POST http://localhost:8000/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-00000000000" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route'
```

### Forzar route a Legacy

```bash
# Conversation ID que cae en bucket >= 10
curl -X POST http://localhost:8000/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-99999999999" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route'
```

---

## 📈 Escalar Gradualmente

### Canary 50% (después de 48hs monitoreando 10%)

```bash
export SLM_CANARY_PERCENT=50
docker compose up -d pulpo-app
```

### Full SLM (después de 48hs monitoreando 50%)

```bash
export SLM_CANARY_PERCENT=0  # 0 = 100% SLM
docker compose up -d pulpo-app
```

---

## 🎯 Checklist de Validación

### Paso 1: Legacy ✅

- [ ] Tests pasan (3/3)
- [ ] `route=legacy` en todos
- [ ] Latencia < 2000ms
- [ ] Sin errores 500

### Paso 2: SLM Canary ✅

- [ ] Distribución ~10% SLM
- [ ] Ambos routes funcionan
- [ ] Latencia SLM < 1500ms
- [ ] n8n procesa ambos sin problemas

### Paso 3: Producción ✅

- [ ] Monitoreado 48hs sin errores
- [ ] Métricas SLM iguales o mejores que Legacy
- [ ] Sin quejas de usuarios
- [ ] Rollback plan probado

---

## 📞 Contactos de Emergencia

- **On-call Engineer**: [nombre]
- **Slack Channel**: #pulpo-incidents
- **Rollback Command**: Ver sección Rollback arriba

---

**Última actualización:** 16 Enero 2025  
**Estado:** ✅ READY TO EXECUTE




