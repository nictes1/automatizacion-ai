# 🤖 Tests con Cliente AI - Quickstart

Sistema de tests conversacionales que simula usuarios reales con diferentes personalidades.

## ⚡ Ejecución Rápida

```bash
# Método 1: Script automático (verifica todo)
./scripts/run_ai_tests.sh

# Método 2: Directo
python3 tests/test_ai_client_scenarios.py
```

## 📋 Requisitos Pre-Ejecución

### 1. Servicios activos

```bash
# Verificar orchestrator
curl http://localhost:8005/health

# Si no está activo:
python3 services/orchestrator_app.py
# O con Docker:
docker-compose up -d orchestrator
```

### 2. Ollama con modelos

```bash
# Verificar modelos
docker exec pulpo-ollama ollama list

# Descargar si faltan:
docker exec pulpo-ollama ollama pull qwen2.5:14b
docker exec pulpo-ollama ollama pull llama3.1:8b
```

## 🎭 Escenarios de Test

### 7 Escenarios Pre-configurados

1. **Cliente Eficiente** (Peluquería)
   - Da toda la info de golpe
   - Ejemplo: *"Hola, soy María, necesito corte mañana 3pm, maria@gmail.com"*

2. **Cliente Conversacional** (Peluquería)
   - Info progresiva, natural
   - Usa muletillas: "dale", "perfecto"

3. **Cliente Olvidadizo** (Peluquería)
   - Responde con contexto extra
   - A veces no da exactamente lo pedido

4. **Cliente Caótico** (Peluquería)
   - Info desordenada, texto pegado
   - Ejemplo: *"11am carlos@gmail.com Corte Carlos Martínez"*

5. **Cliente Breve** (Peluquería)
   - Respuestas de 1-3 palabras
   - "sí", "ok", "mañana 2pm"

6. **Cliente Eficiente** (Restaurante)
   - Reserva de mesa con toda la info

7. **Cliente Conversacional** (Inmobiliaria)
   - Visita a propiedad progresiva

## 📊 Salida Esperada

```
================================================================================
🚀 EJECUTANDO 7 ESCENARIOS DE TEST
================================================================================

🧪 TEST: Cliente Eficiente - Peluquería
👤 Usuario: Hola, soy María González, necesito...
🤖 Asistente: ¡Hola María! Perfecto, te anoto...
✅ TEST EXITOSO (2 turnos, 6.3s)

...

================================================================================
📊 RESUMEN DE RESULTADOS
================================================================================

✅ Exitosos: 7/7 (100.0%)
❌ Fallidos: 0/7 (0.0%)

📈 MÉTRICAS GENERALES:
   Promedio turnos: 3.7
   Promedio duración: 11.7s
   Total tiempo: 82.0s

💾 Resultados guardados en: test_results.json
```

## 🔍 Análisis de Resultados

### Ver resultados JSON formateados

```bash
# Resumen
cat test_results.json | jq '.[] | {scenario: .scenario_name, success: .success, turns: .turns}'

# Ver conversación específica
cat test_results.json | jq '.[0].conversation_log'

# Ver slots extraídos
cat test_results.json | jq '.[] | {scenario: .scenario_name, slots: .slots_collected}'
```

### Analizar fallos

```bash
# Tests fallidos
cat test_results.json | jq '.[] | select(.success == false) | {scenario: .scenario_name, missing: .slots_missing, error: .error}'
```

## ⚙️ Configuración

### Modificar escenarios

Edita `tests/test_ai_client_scenarios.py`:

```python
# Agregar nuevo escenario
SCENARIOS.append(
    TestScenario(
        id="servicios_custom",
        name="Mi Test Custom",
        description="Descripción del test",
        vertical="servicios",
        client=ClientProfile(
            name="Juan Pérez",
            email="juan@example.com",
            phone="+5491123456789",
            personality=PersonalityType.CONVERSATIONAL,
            style_notes="Amigable, usa 'dale'"
        ),
        objective="Agendar turno",
        context={
            "service": "Corte",
            "preferred_date": "2025-10-07",
            "preferred_time": "15:00",
            "when_human": "mañana 3pm"
        },
        expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    )
)
```

### Ejecutar solo algunos escenarios

```python
# En test_ai_client_scenarios.py, al final:
if __name__ == "__main__":
    # Solo primeros 3 escenarios
    runner = TestRunner(SCENARIOS[:3])
    asyncio.run(runner.run_all())
```

## 🐛 Troubleshooting

### Error: Orchestrator no disponible

```bash
# Verificar
curl http://localhost:8005/health

# Iniciar
python3 services/orchestrator_app.py
```

### Error: Modelo no encontrado

```bash
# Listar modelos
docker exec pulpo-ollama ollama list

# Descargar faltantes
docker exec pulpo-ollama ollama pull qwen2.5:14b
```

### Tests muy lentos

- Qwen2.5:14b requiere ~11GB VRAM
- Si no tienes GPU suficiente, usa modelo más pequeño:
  ```python
  # En orchestrator_service.py cambiar:
  OLLAMA_MODEL = "qwen2.5:7b-instruct"  # Más rápido, menos preciso
  ```

### Cliente AI responde mal

- llama3.1:8b es usado para simular cliente
- Si respuestas no naturales, ajustar prompts en `AIClient.generate_response()`

## 📈 Métricas de Éxito

### Por Test
- ✅ **Success**: Todos los slots recolectados + EXECUTE_ACTION
- 🔢 **Turns**: Menor es mejor (eficiencia)
- ⏱️ **Duration**: <15s por test es aceptable

### Suite Completa
- 🎯 **Target**: 100% success rate
- ⚡ **Performance**: <2 minutos para 7 tests
- 📊 **Avg Turns**: 3-5 turnos es óptimo

## 📚 Documentación Completa

- `tests/README_AI_TESTS.md` - Guía completa
- `tests/test_ai_client_scenarios.py` - Código fuente
- `SISTEMA_CONVERSACIONAL_FINAL.md` - Sistema conversacional
- `MODEL_COMPARISON.md` - Comparación de modelos

## 🚀 Next Steps

Después de tests exitosos:

1. **Integración continua**
   ```bash
   # Agregar a CI/CD pipeline
   ./scripts/run_ai_tests.sh || exit 1
   ```

2. **Expandir escenarios**
   - Casos edge: fechas inválidas, horarios no disponibles
   - Más personalidades: enojado, confundido, etc.
   - Más verticales: e-commerce, servicios médicos

3. **Validación de producción**
   - Correr tests pre-deploy
   - Monitorear métricas vs producción real

---

**¿Problemas?** Revisa `tests/README_AI_TESTS.md` o logs del orchestrator:
```bash
docker logs pulpo-orchestrator -f
```
