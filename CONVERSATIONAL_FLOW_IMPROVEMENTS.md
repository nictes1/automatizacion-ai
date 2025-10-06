# Conversational Flow Improvements

## Overview
Enhanced the orchestrator service to provide natural, intelligent conversational interactions that extract information from user messages without acting like a rigid form-filling bot.

## Key Improvements

### 1. Enhanced GREET Handler (First Message Intelligence)
**File**: `services/orchestrator_service.py:968-1036`

**Changes**:
- Extract **ALL available information** from the first message, not just greet
- Recognize user intent immediately ("necesito cortarme el pelo mañana")
- Interpret time expressions in Spanish:
  - "a las 3 de la tarde" → `preferred_time: "15:00"`
  - "10am" → `preferred_time: "10:00"`
  - "medio día" → `preferred_time: "12:00"`
- Interpret date expressions:
  - "mañana" → `preferred_date: "2025-10-07"` (calculated)
  - "pasado mañana" → next day +2
  - "el viernes" → next Friday

**Result**: User says "Hola, necesito cortarme el pelo mañana a las 3 de la tarde" and system extracts:
```json
{
  "service_type": "Corte de Cabello",
  "preferred_date": "2025-10-07",
  "preferred_time": "15:00"
}
```

### 2. Intelligent SLOT_FILL Handler
**File**: `services/orchestrator_service.py:1036-1123`

**Changes**:
- Extract information from user messages **even when they don't directly answer the question asked**
- User provides name when asked for time? System extracts the name anyway
- Comprehensive extraction prompt with examples for all required and optional fields
- Logging of all extracted slots for debugging

**Example Flow**:
```
System: "¿A qué hora te gustaría venir?"
User: "Mi nombre es Pablo Martínez"
System extracts: client_name = "Pablo Martínez" ✅
System: "Genial Pablo! ¿Y tu email?"
```

### 3. Natural Conversation System Prompt
**File**: `services/orchestrator_service.py:712-763`

**Vertical**: Servicios (Peluquería)

**Character**: Sofía - Recepcionista virtual

**Style Guidelines**:
- Conversational and warm (like talking to a friend)
- Brief and direct (max 2-3 lines - we're on WhatsApp)
- Empathetic and helpful
- Natural and human (uses pauses, colloquial expressions)
- Varies sentence length

**Example Responses**:
- ❌ Old: "Estimado cliente, ¿en qué puedo ayudarle hoy?"
- ✅ New: "¡Hola! Perfecto, te anoto para mañana a las 15hs para un corte. ¿Me pasás tu nombre y email?"

### 4. State Management Enhancement
**File**: `services/orchestrator_app.py:76-102`

**Changes**:
- Added `current_state` parameter to DecideRequest model
- Merges `current_state` with individual state fields (greeted, slots, objective, last_action, attempts_count)
- Allows flexible state passing between conversation turns
- Maintains full context across the conversation

### 5. Vertical-Specific Policy Logic
**File**: `services/orchestrator_service.py:175-192`

**Changes**:
- Added servicios-specific intent detection
- If user has `service_type` or `preferred_date`, they want to book an appointment
- Policy engine correctly routes to SLOT_FILL → EXECUTE_ACTION when ready

## Test Results

### Successful Flow Example

```
Turn 1:
👤 "Hola, necesito cortarme el pelo mañana a las 3 de la tarde"
🤖 "Hola! Buen día, ¡claro que te ayudamos a cortarte el pelo mañana a las 3 de la tarde! Solo necesito un poco más de información."
📊 Extracted: service_type, preferred_date, preferred_time ✅

Turn 2:
👤 "Mi nombre es Pablo Martínez"
🤖 "Hola Pablo! Me alegra que estés aquí. ¿Puedo tener tu dirección de correo electrónico?"
📊 Extracted: client_name ✅

Turn 3:
👤 "Mi email es pablo.martinez@gmail.com"
🤖 "Genial Pablo, me pasaste tu email!"
📊 Extracted: client_email ✅

Turn 4:
👤 "Sí, confirmá por favor"
🎯 Action: EXECUTE_ACTION (all required slots complete) ✅
```

### Logs Evidence

```
INFO:orchestrator:[GREET] ✅ Slots extraídos del primer mensaje: {'service_type': 'Corte de Cabello', 'preferred_date': '2025-10-07', 'preferred_time': '15:00'}
INFO:orchestrator:[SLOT_FILL] ✅ Slots extraídos: {'client_name': 'Pablo Martínez'}
INFO:orchestrator:[SLOT_FILL] ✅ Slots extraídos: {'client_email': 'pablo.martinez@gmail.com'}
INFO:orchestrator:[policy] servicios:None EXECUTE_ACTION - Slots requeridos completos
```

## Required Slots for Servicios Vertical

```python
"required_slots": [
    "service_type",      # Servicio deseado (ej: "Corte de Cabello")
    "preferred_date",    # Fecha en formato YYYY-MM-DD
    "preferred_time",    # Hora en formato HH:MM
    "client_name",       # Nombre del cliente
    "client_email"       # Email del cliente
]
```

## Technical Details

### Time Expression Parsing Examples

The LLM is instructed to interpret:
- "3 de la tarde" → "15:00"
- "a las 3pm" → "15:00"
- "10 de la mañana" → "10:00"
- "10am" → "10:00"
- "medio día" → "12:00"
- "5 y media de la tarde" → "17:30"

### Date Expression Parsing Examples

- "mañana" → calculated tomorrow date (2025-10-07 if today is 2025-10-06)
- "pasado mañana" → calculated day +2
- "el viernes" → calculated next Friday

### LLM Configuration

- **Model**: qwen2.5:14b (via Ollama) - Migrado desde llama3.1:8b
- **Base URL**: `http://localhost:11434`
- **Timeout**: 10 seconds (aumentado para modelo más grande)
- **Response Format**: JSON with `reply` and `updated_state` fields
- **VRAM Required**: ~11GB (ideal para RTX 3090 24GB)

**Por qué Qwen2.5:14b**:
- ✅ 100% de precisión en extracción de slots (vs 60% con llama3.1:8b)
- ✅ Maneja casos extremos perfectamente
- ✅ Extracción consistente y confiable
- ✅ Excelente para español y extracción estructurada
- Ver `MODEL_COMPARISON.md` para detalles completos

## Files Modified

1. `services/orchestrator_service.py`
   - Line 17: Added `timedelta` import
   - Lines 712-763: Enhanced system prompt for servicios vertical
   - Lines 968-1036: Improved GREET handler with slot extraction
   - Lines 1036-1123: Enhanced SLOT_FILL handler for intelligent extraction
   - Lines 175-192: Fixed policy logic for servicios vertical

2. `services/orchestrator_app.py`
   - Lines 33-43: Added `current_state` to DecideRequest model
   - Lines 76-102: Implemented state merging logic

3. `tests/test_orchestrator_appointments.py`
   - Lines 83-90: Fixed state persistence between turns
   - Lines 109-115: Proper state updates after each turn

## Next Steps (Pending)

1. **Conversation History Retrieval**
   - Implement detection of existing vs new conversation
   - Retrieve and use conversation context from database
   - Resume interrupted conversations

2. **Action Service Integration**
   - Fix Actions service DNS resolution (currently using localhost)
   - Implement actual Google Calendar integration
   - Add appointment confirmation messages

3. **Production Deployment**
   - Deploy with proper environment variables
   - Configure service-to-service networking
   - Set up monitoring and alerts

## Usage

To test the conversational flow:

```bash
# Start orchestrator
PYTHONPATH=. OLLAMA_URL=http://localhost:11434 DATABASE_URL=postgresql://pulpo:pulpo@localhost:5432/pulpo python3 services/orchestrator_app.py

# Run test
python3 tests/test_orchestrator_appointments.py
```

## Conclusion

The conversational AI now:
✅ Extracts complete information from first message
✅ Understands natural language date/time expressions
✅ Collects missing information intelligently
✅ Maintains conversation state across turns
✅ Provides warm, natural responses in Spanish
✅ Routes correctly to action execution when ready

The system is ready for WhatsApp integration with natural, professional conversation flow.
