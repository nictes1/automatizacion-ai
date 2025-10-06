# Tests con Cliente AI Simulado

Sistema de testing avanzado que simula conversaciones realistas usando un cliente AI con múltiples personalidades.

## 🎯 Objetivo

Validar el sistema conversacional de PulpoAI simulando usuarios reales con diferentes comportamientos, sin necesidad de pruebas manuales.

## 📋 Escenarios Cubiertos

### Personalidades de Cliente

1. **EFFICIENT** - Cliente eficiente
   - Da toda la información en el primer mensaje
   - Ejemplo: *"Hola, soy María González, necesito corte de pelo mañana a las 3pm, mi email es maria.gonzalez@gmail.com"*

2. **CONVERSATIONAL** - Cliente conversacional
   - Da información progresivamente, de forma natural
   - Responde preguntas una por una
   - Usa muletillas argentinas: "dale", "perfecto", "genial"

3. **FORGETFUL** - Cliente olvidadizo
   - A veces no responde exactamente lo que se pregunta
   - Da contexto extra no pedido
   - Ejemplo: *"Ah sí, uso Gmail generalmente, es ana.rodriguez@yahoo.com"*

4. **CHAOTIC** - Cliente caótico
   - Envía información desordenada
   - Como texto pegado de una nota
   - Ejemplo: *"mañana 11am carlos.m@gmail.com Corte y Barba Carlos Martínez"*

5. **BRIEF** - Cliente breve
   - Respuestas muy cortas: 1-3 palabras
   - Ejemplos: "sí", "ok", "dale", "mañana 2pm"

### Verticales Soportadas

- ✅ **Servicios** (Peluquería/Spa): Agendamiento de turnos
- ✅ **Gastronomía** (Restaurante): Reservas de mesa
- ✅ **Inmobiliaria**: Visitas a propiedades

## 🚀 Uso

### Ejecutar Suite Completa

```bash
# Desde el directorio raíz del proyecto
python3 tests/test_ai_client_scenarios.py
```

### Requisitos

1. **Servicios corriendo**:
   ```bash
   # Opción 1: Docker Compose
   docker-compose -f docker-compose.simple.yml up -d

   # Opción 2: Servicios individuales
   python3 services/orchestrator_app.py
   ```

2. **Ollama con modelos**:
   ```bash
   # Verificar modelos
   docker exec pulpo-ollama ollama list

   # Deben estar disponibles:
   # - qwen2.5:14b (orchestrator)
   # - llama3.1:8b (cliente AI)
   ```

## 📊 Salida del Test

### Durante la Ejecución

```
================================================================================
🧪 TEST: Cliente Eficiente - Peluquería
================================================================================
📝 Cliente que proporciona toda la información en el primer mensaje
👤 Cliente: María González (efficient)
🎯 Objetivo: Agendar corte de pelo
================================================================================

👤 Usuario: Hola, soy María González, necesito Corte de Cabello mañana a las 3 de la tarde, mi email es maria.gonzalez@gmail.com
🤖 Asistente: ¡Hola María! Perfecto, te anoto para un corte mañana a las 15:00. ¿Todo correcto?
📊 Slots: {'service_type': 'Corte de Cabello', 'preferred_date': '2025-10-07', 'preferred_time': '15:00', 'client_name': 'María González', 'client_email': 'maria.gonzalez@gmail.com'}
🎯 Next: SLOT_FILL

👤 Usuario: Sí, perfecto
🤖 Asistente: ¡Listo! Tu turno está confirmado para mañana 07/10 a las 15:00. Te envié la confirmación a maria.gonzalez@gmail.com 💈
📊 Slots: {...}
🎯 Next: EXECUTE_ACTION

──────────────────────────────────────────────────────────────────────────────
✅ TEST EXITOSO
📊 Turnos: 2
⏱️  Duración: 6.3s
📋 Slots recolectados: 5/5
🎯 Acción final: EXECUTE_ACTION
──────────────────────────────────────────────────────────────────────────────
```

### Resumen Final

```
================================================================================
📊 RESUMEN DE RESULTADOS
================================================================================

✅ Exitosos: 7/7 (100.0%)
❌ Fallidos: 0/7 (0.0%)

──────────────────────────────────────────────────────────────────────────────
Escenario                                Resultado  Turnos   Tiempo
──────────────────────────────────────────────────────────────────────────────
Cliente Eficiente - Peluquería           ✅ PASS    2        6.3s
Cliente Conversacional - Peluquería      ✅ PASS    4        12.1s
Cliente Olvidadizo - Peluquería          ✅ PASS    5        15.2s
Cliente Caótico - Peluquería             ✅ PASS    3        9.4s
Cliente Breve - Peluquería               ✅ PASS    6        18.7s
Cliente Eficiente - Restaurante          ✅ PASS    2        6.8s
Cliente Conversacional - Inmobiliaria    ✅ PASS    4        13.5s
──────────────────────────────────────────────────────────────────────────────

📈 MÉTRICAS GENERALES:
   Promedio turnos: 3.7
   Promedio duración: 11.7s
   Total tiempo: 82.0s

================================================================================

💾 Resultados guardados en: test_results.json
```

## 📁 Archivos Generados

### `test_results.json`

Contiene resultados detallados de cada test:

```json
[
  {
    "scenario_id": "servicios_efficient",
    "scenario_name": "Cliente Eficiente - Peluquería",
    "success": true,
    "turns": 2,
    "slots_collected": {
      "service_type": "Corte de Cabello",
      "preferred_date": "2025-10-07",
      "preferred_time": "15:00",
      "client_name": "María González",
      "client_email": "maria.gonzalez@gmail.com"
    },
    "slots_expected": ["service_type", "preferred_date", "preferred_time", "client_name", "client_email"],
    "slots_missing": [],
    "final_action": "EXECUTE_ACTION",
    "error": null,
    "duration_seconds": 6.3,
    "conversation_log": [...]
  }
]
```

## 🎛️ Configuración

### Variables de Entorno

```bash
# En .env o environment
ORCHESTRATOR_URL=http://localhost:8005
OLLAMA_URL=http://localhost:11434
WORKSPACE_ID=550e8400-e29b-41d4-a716-446655440000
```

### Modificar Escenarios

Edita `test_ai_client_scenarios.py`:

```python
SCENARIOS = [
    TestScenario(
        id="servicios_custom",
        name="Mi Escenario Custom",
        description="Descripción del test",
        vertical="servicios",
        client=ClientProfile(
            name="Nombre Cliente",
            email="email@example.com",
            phone="+5491123456789",
            personality=PersonalityType.CONVERSATIONAL,
            style_notes="Notas de estilo del cliente"
        ),
        objective="Lo que quiere hacer",
        context={
            "service": "Servicio deseado",
            "preferred_date": "2025-10-07",
            "preferred_time": "15:00",
            "when_human": "mañana a las 3pm"
        },
        expected_slots=["service_type", "preferred_date", "preferred_time", "client_name", "client_email"]
    )
]
```

## 📈 Métricas Evaluadas

### Por Test
- ✅ **Success**: Si se completó exitosamente
- 🔢 **Turns**: Cantidad de intercambios usuario-asistente
- ⏱️ **Duration**: Tiempo total del test
- 📋 **Slots Collected**: Cantidad de slots extraídos correctamente
- ⚠️ **Slots Missing**: Slots que no se pudieron extraer
- 🎯 **Final Action**: Acción final del orchestrator

### Globales
- 📊 **Success Rate**: Porcentaje de tests exitosos
- 🔄 **Avg Turns**: Promedio de turnos por conversación
- ⏱️ **Avg Duration**: Tiempo promedio por test
- 🎯 **Action Coverage**: Cobertura de acciones del sistema

## 🔍 Debugging

### Ver logs del orchestrator

```bash
docker logs pulpo-orchestrator -f
```

### Ver logs detallados en test_results.json

El campo `conversation_log` contiene la conversación completa con slots extraídos en cada turno.

### Test manual de un escenario

```python
# En test_ai_client_scenarios.py
if __name__ == "__main__":
    # Ejecutar solo un escenario
    runner = TestRunner([SCENARIOS[0]])  # Primer escenario
    asyncio.run(runner.run_all())
```

## 🚀 Próximas Mejoras

- [ ] Agregar más personalidades (enojado, confundido, etc.)
- [ ] Tests de casos edge (fecha inválida, horarios no disponibles)
- [ ] Integración con CI/CD (GitHub Actions)
- [ ] Métricas de calidad de respuestas (sentiment, coherencia)
- [ ] Tests de múltiples conversaciones paralelas
- [ ] Validación de respuestas esperadas (assertions)

## 📚 Referencias

- `test_ai_client.py` - Test original con cliente AI
- `test_orchestrator_appointments.py` - Test de flujo completo
- `SISTEMA_CONVERSACIONAL_FINAL.md` - Documentación del sistema
- `MODEL_COMPARISON.md` - Comparación de modelos LLM
