# Arquitectura de Memoria Conversacional - PulpoAI SaaS

**Versión**: 1.0
**Fecha**: 2025-10-09
**Estado**: Production-Ready Design
**Owner**: Sistema de Orchestrator

---

## 1. Executive Summary

### Problema
El sistema actual solo mantiene "memoria de trabajo" (`dialogue_states.slots`) durante una conversación activa. Esto causa:
- Pérdida de contexto al completar una acción
- Clientes recurrentes tratados como nuevos
- Imposibilidad de personalizar experiencia
- No hay inteligencia de negocio (lead scoring, preferencias)

### Solución: Arquitectura de 3 Capas

```
┌─────────────────────────────────────────────────────────────┐
│  Capa 3: Long-Term Memory (client_profiles)                │
│  Scope: Histórico completo del cliente                     │
│  TTL: Permanente (hasta GDPR deletion)                     │
│  Carga: Solo clientes recurrentes (>3 interacciones)       │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ load_client_profile()
                            │
┌─────────────────────────────────────────────────────────────┐
│  Capa 2: Short-Term Memory (conversation_summaries)        │
│  Scope: Interacciones del día/semana con mismo cliente     │
│  TTL: Redis 24h + PostgreSQL permanente                    │
│  Carga: Si última interacción < 8 horas                    │
└─────────────────────────────────────────────────────────────┘
                            ▲
                            │ load_daily_context()
                            │
┌─────────────────────────────────────────────────────────────┐
│  Capa 1: Working Memory (dialogue_states.slots)            │
│  Scope: Conversación activa actual                         │
│  TTL: 30 min inactividad o hasta completar acción          │
│  Carga: SIEMPRE (es el estado base)                        │
└─────────────────────────────────────────────────────────────┘
```

### Principios de Diseño

1. **Estado es verdad única**: No usar historial de mensajes en prompts (caro, lento)
2. **Compresión progresiva**: Conversación → Summary → Profile (cada capa más compacta)
3. **Multi-tenant isolation**: RLS en PostgreSQL + prefijos de workspace en Redis
4. **Carga condicional**: Solo cargar capas superiores cuando aportan valor
5. **Costo-beneficio**: Cada feature debe justificar su costo de LLM/storage

---

## 2. Arquitectura de Capas de Memoria

### Capa 1: Working Memory (Session State)

**Propósito**: Estado volátil de la conversación activa

**Storage**: PostgreSQL `pulpo.dialogue_states`

**Estructura Actual**:
```sql
-- Ya existe en el sistema
dialogue_states (
    workspace_id uuid,
    conversation_id uuid,
    fsm_state text,  -- active|completed|abandoned|escalated
    intent text,
    slots jsonb,  -- ← Memoria de trabajo
    next_action text,
    meta jsonb,  -- greeted, attempts_count, objective
    created_at, updated_at
)
```

**Contenido de `slots`**:
```json
{
  "greeted": true,
  "service_type": "Corte de Cabello",
  "preferred_date": "2025-10-10",
  "preferred_time": "15:00",
  "client_name": "Juan Pérez",
  "client_email": "juan@example.com",
  "_intent": "execute_action",
  "_intent_confidence": 0.85,
  "_validated_by_rag": true,
  "_attempts_count": 1
}
```

**Lifecycle**:
- **Creación**: Primer mensaje del usuario → `persist_inbound()`
- **Actualización**: Cada respuesta del orchestrator → `persist_outbound()`
- **Reset**: Al completar acción (`fsm_state = completed`) o timeout (30 min)
- **Carga**: SIEMPRE al inicio de `decide()` vía `load_state()`

**Costo**: ~0 (queries indexadas < 10ms)

---

### Capa 2: Short-Term Memory (Daily Context)

**Propósito**: Recordar interacciones recientes del mismo día/semana

**Storage**:
- Redis Sorted Sets (cache 24h)
- PostgreSQL `pulpo.conversation_summaries` (permanente)

**Schema SQL** (nueva tabla):
```sql
CREATE TABLE pulpo.conversation_summaries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    user_phone text NOT NULL,

    -- Resumen generado por LLM
    summary_text text NOT NULL,
    outcome text NOT NULL CHECK (outcome IN ('success', 'failed', 'abandoned', 'escalated')),
    sentiment text CHECK (sentiment IN ('positive', 'neutral', 'negative', 'angry')),

    -- Key facts extraídos
    key_facts jsonb DEFAULT '[]'::jsonb,

    -- Metadata
    message_count int,
    duration_seconds int,
    llm_cost_usd decimal(10,4) DEFAULT 0,  -- Para tracking

    created_at timestamptz DEFAULT NOW(),
    updated_at timestamptz DEFAULT NOW()
);

-- Índices críticos
CREATE INDEX idx_summaries_workspace_phone
    ON pulpo.conversation_summaries(workspace_id, user_phone, created_at DESC);

CREATE INDEX idx_summaries_conversation
    ON pulpo.conversation_summaries(conversation_id);

CREATE INDEX idx_summaries_outcome
    ON pulpo.conversation_summaries(workspace_id, outcome, created_at DESC);

-- RLS Policy
ALTER TABLE pulpo.conversation_summaries ENABLE ROW LEVEL SECURITY;

CREATE POLICY summaries_workspace_isolation
    ON pulpo.conversation_summaries
    FOR ALL
    USING (workspace_id::text = current_setting('app.workspace_id', true));
```

**Redis Structure**:
```
Key: daily_context:{workspace_id}:{user_phone}:{YYYY-MM-DD}
Type: Sorted Set
Members: conversation_id (score = unix_timestamp)
TTL: 24 hours

Ejemplo:
ZADD daily_context:550e8400:+5491112345678:2025-10-09
     1728518400 "conv-abc-123"
     1728522000 "conv-def-456"
```

**Cuándo Cargar**:
```python
async def should_load_short_term_memory(
    user_phone: str,
    workspace_id: str
) -> bool:
    # Check Redis first (fast)
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"daily_context:{workspace_id}:{user_phone}:{today}"

    count = await redis.zcard(key)
    if count > 0:
        return True  # Ya interactuó hoy

    # Fallback: check PostgreSQL (si Redis se reinició)
    last_interaction = await db.fetchval("""
        SELECT MAX(created_at)
        FROM pulpo.conversations
        WHERE workspace_id = $1 AND user_phone = $2
    """, workspace_id, user_phone)

    if not last_interaction:
        return False  # Cliente nuevo

    hours_since = (datetime.now() - last_interaction).total_seconds() / 3600
    return hours_since < 8  # Cargamos si < 8 horas
```

**Prompt Addition** (si se carga):
```python
# En orchestrator_service.py, dentro de _handle_greet() o _handle_answer()
if short_term_context:
    usr += f"""

CONTEXTO RECIENTE:
El cliente ya interactuó contigo hoy. Última vez hace {time_since_str}:
"{short_term_context['summary_text']}"
Resultado: {short_term_context['outcome']}

NO vuelvas a saludar formalmente. Continuá la conversación naturalmente.
"""
```

**Costo**:
- LLM summarization: ~200 tokens → $0.0001 por conversación (Ollama = $0)
- Storage PostgreSQL: ~1KB por summary → $0.00001
- Redis: Despreciable (TTL 24h)

---

### Capa 3: Long-Term Memory (Client Profile)

**Propósito**: Perfil persistente del cliente across conversaciones

**Storage**: PostgreSQL `pulpo.client_profiles`

**Schema SQL** (nueva tabla):
```sql
CREATE TABLE pulpo.client_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    user_phone text NOT NULL,

    -- Identificación
    name text,
    email text,

    -- Métricas de engagement
    total_interactions int DEFAULT 1,
    first_seen timestamptz DEFAULT NOW(),
    last_seen timestamptz DEFAULT NOW(),

    -- Preferencias (auto-extraídas)
    preferences jsonb DEFAULT '{}'::jsonb,
    -- Ejemplo: {"preferred_staff": "María", "preferred_time": "tarde", "services": ["corte", "barba"]}

    -- Lead scoring
    lead_score int DEFAULT 50 CHECK (lead_score >= 0 AND lead_score <= 100),
    segment text CHECK (segment IN ('new', 'warm', 'hot', 'cold', 'churned')),

    -- Business metrics
    lifetime_value decimal(10,2) DEFAULT 0,
    avg_sentiment decimal(3,2),  -- -1.0 (angry) to 1.0 (very positive)

    -- Auto-generated notes
    notes text,  -- LLM-generated summary

    created_at timestamptz DEFAULT NOW(),
    updated_at timestamptz DEFAULT NOW(),

    UNIQUE(workspace_id, user_phone)
);

-- Índices
CREATE INDEX idx_profiles_workspace_phone
    ON pulpo.client_profiles(workspace_id, user_phone);

CREATE INDEX idx_profiles_segment
    ON pulpo.client_profiles(workspace_id, segment, last_seen DESC);

CREATE INDEX idx_profiles_score
    ON pulpo.client_profiles(workspace_id, lead_score DESC);

-- RLS Policy
ALTER TABLE pulpo.client_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY profiles_workspace_isolation
    ON pulpo.client_profiles
    FOR ALL
    USING (workspace_id::text = current_setting('app.workspace_id', true));
```

**Cuándo Cargar**:
```python
async def should_load_long_term_memory(
    user_phone: str,
    workspace_id: str,
    plan: str
) -> bool:
    # Solo planes Premium
    if plan not in ('premium', 'enterprise'):
        return False

    profile = await db.fetchrow("""
        SELECT total_interactions, last_seen
        FROM pulpo.client_profiles
        WHERE workspace_id = $1 AND user_phone = $2
    """, workspace_id, user_phone)

    if not profile:
        return False  # Cliente nuevo (aún no tiene perfil)

    # Solo si es cliente recurrente (>3 interacciones)
    if profile['total_interactions'] < 3:
        return False

    # Y última interacción < 90 días
    days_since = (datetime.now() - profile['last_seen']).days
    return days_since < 90
```

**Prompt Addition** (si se carga):
```python
if long_term_profile:
    usr += f"""

PERFIL DEL CLIENTE:
{long_term_profile['name']} - Cliente desde {first_seen_str}
Total de interacciones: {long_term_profile['total_interactions']}
Preferencias: {json.dumps(long_term_profile['preferences'], ensure_ascii=False)}
Segmento: {long_term_profile['segment']} (score: {long_term_profile['lead_score']}/100)

Personalizá la conversación usando esta información.
"""
```

**Costo**:
- Profile update (LLM): ~150 tokens → $0.0001 por conversación
- Storage: ~2KB por cliente → $0.00002

---

## 3. Protecciones Production

### 3.1 Rate Limiting Distribuido (Redis)

**Requisitos**:
- Multi-tenant (límites por workspace)
- Distribuido (múltiples instancias del orchestrator)
- Ventanas deslizantes (sliding window)
- Respuestas progresivas (soft → hard block)

**Redis Keys Structure**:
```
rate:{workspace_id}:{user_phone}:min    → Sorted Set (score=timestamp, TTL=60s)
rate:{workspace_id}:{user_phone}:hour   → Sorted Set (score=timestamp, TTL=3600s)
rate:{workspace_id}:{user_phone}:day    → Counter (TTL=86400s)
```

**Límites por Plan** (configurables en `workspace.settings`):
```json
{
  "basic": {
    "msg_per_min": 5,
    "msg_per_hour": 50,
    "msg_per_day": 200,
    "concurrent_conversations": 10
  },
  "pro": {
    "msg_per_min": 10,
    "msg_per_hour": 120,
    "msg_per_day": 500,
    "concurrent_conversations": 50
  },
  "premium": {
    "msg_per_min": 20,
    "msg_per_hour": 300,
    "msg_per_day": 1000,
    "concurrent_conversations": 200
  }
}
```

**Implementación** (archivo nuevo: `shared/rate_limit.py`):
```python
# services/shared/rate_limit.py
import redis.asyncio as redis
import time
from typing import Tuple, Optional

class RateLimitService:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url, decode_responses=True)

    async def check_rate(
        self,
        workspace_id: str,
        user_phone: str,
        limits: dict
    ) -> Tuple[bool, Optional[str], int]:
        """
        Returns: (allow, reason, retry_after_seconds)
        """
        now = time.time()

        # 1. Check per-minute limit (sliding window)
        key_min = f"rate:{workspace_id}:{user_phone}:min"

        # Remove old entries
        await self.redis.zremrangebyscore(key_min, 0, now - 60)

        # Count current window
        count_min = await self.redis.zcard(key_min)

        if count_min >= limits['msg_per_min']:
            return (False, "Dame un segundo para procesar bien tus mensajes 😊", 10)

        # 2. Check per-hour limit
        key_hour = f"rate:{workspace_id}:{user_phone}:hour"
        await self.redis.zremrangebyscore(key_hour, 0, now - 3600)
        count_hour = await self.redis.zcard(key_hour)

        if count_hour >= limits['msg_per_hour']:
            return (False, "Llegaste al límite de mensajes por hora. Probá de nuevo en un rato.", 600)

        # 3. Check per-day limit
        key_day = f"rate:{workspace_id}:{user_phone}:day"
        count_day = await self.redis.get(key_day)
        count_day = int(count_day) if count_day else 0

        if count_day >= limits['msg_per_day']:
            return (False, "Llegaste al límite diario de mensajes. Volvé mañana!", 3600)

        # 4. All checks passed - register this request
        pipe = self.redis.pipeline()

        # Add to minute window
        pipe.zadd(key_min, {str(now): now})
        pipe.expire(key_min, 60)

        # Add to hour window
        pipe.zadd(key_hour, {str(now): now})
        pipe.expire(key_hour, 3600)

        # Increment day counter
        pipe.incr(key_day)
        pipe.expire(key_day, 86400)

        await pipe.execute()

        return (True, None, 0)

    async def log_abuse(self, workspace_id: str, user_phone: str, reason: str):
        """Log rate limit violations for analysis"""
        key = f"abuse:{workspace_id}:{user_phone}"

        await self.redis.hincrby(key, "total_blocks", 1)
        await self.redis.hset(key, "last_block_at", int(time.time()))

        # Store reason in list (keep last 10)
        reasons_key = f"abuse:{workspace_id}:{user_phone}:reasons"
        await self.redis.lpush(reasons_key, f"{time.time()}:{reason}")
        await self.redis.ltrim(reasons_key, 0, 9)
        await self.redis.expire(reasons_key, 86400 * 7)  # 7 days
```

**Integración en Orchestrator** (`orchestrator_app.py`):
```python
# En el endpoint /orchestrator/decide
from shared.rate_limit import RateLimitService

rate_limiter = RateLimitService(os.getenv("REDIS_URL"))

@app.post("/orchestrator/decide")
async def decide(request: DecideRequest, x_workspace_id: str = Header(...)):
    # 1. Load workspace limits
    workspace = await get_workspace(x_workspace_id)
    limits = workspace['settings'].get('rate_limits', DEFAULT_LIMITS)

    # 2. Check rate limit
    user_phone = extract_phone_from_conversation(request.conversation_id)
    allow, reason, retry_after = await rate_limiter.check_rate(
        x_workspace_id,
        user_phone,
        limits
    )

    if not allow:
        # Log abuse
        await rate_limiter.log_abuse(x_workspace_id, user_phone, reason)

        # Return rate limit response (no procesar)
        return DecideResponse(
            assistant=reason,
            next_action="rate_limited",
            tool_calls=[],
            slots=request.slots,
            end=False
        )

    # 3. Proceed normally
    with orchestrator_service.set_request_context({...}):
        response = await orchestrator_service.decide(snapshot)
    ...
```

---

### 3.2 Session Timeout y Cleanup

**Estrategia**:
- **Timeout de inactividad**: 30 min sin mensajes → `fsm_state = abandoned`
- **Timeout absoluto**: Conversación activa > 2 horas → `fsm_state = escalated` (forzar humano)
- **Cleanup job**: Cada hora, procesar timeouts

**Redis Keys**:
```
session:{conversation_id}:last_activity → timestamp, TTL=30min
session:{conversation_id}:created_at → timestamp, TTL=2h
```

**Batch Job** (Celery task: `tasks/cleanup_sessions.py`):
```python
@celery.task
async def cleanup_abandoned_sessions():
    """
    Corre cada hora. Marca conversaciones abandonadas.
    """
    # 1. Find conversations active pero sin actividad reciente
    abandoned = await db.fetch("""
        SELECT c.id, c.workspace_id, c.conversation_id
        FROM pulpo.conversations c
        JOIN pulpo.dialogue_states ds ON ds.conversation_id = c.id
        WHERE ds.fsm_state = 'active'
          AND c.updated_at < NOW() - INTERVAL '30 minutes'
    """)

    for conv in abandoned:
        await db.execute("""
            UPDATE pulpo.dialogue_states
            SET fsm_state = 'abandoned', updated_at = NOW()
            WHERE conversation_id = $1
        """, conv['conversation_id'])

        logger.info(f"Marked conversation {conv['conversation_id']} as abandoned (timeout)")

    # 2. Find zombies (activas > 2 horas) → escalar
    zombies = await db.fetch("""
        SELECT c.id, c.workspace_id, c.conversation_id
        FROM pulpo.conversations c
        JOIN pulpo.dialogue_states ds ON ds.conversation_id = c.id
        WHERE ds.fsm_state = 'active'
          AND c.created_at < NOW() - INTERVAL '2 hours'
    """)

    for conv in zombies:
        await db.execute("""
            UPDATE pulpo.dialogue_states
            SET fsm_state = 'escalated', next_action = 'ASK_HUMAN', updated_at = NOW()
            WHERE conversation_id = $1
        """, conv['conversation_id'])

        # Trigger alert to workspace admin
        await send_escalation_alert(conv['workspace_id'], conv['conversation_id'])

        logger.warning(f"Escalated zombie conversation {conv['conversation_id']} (>2h active)")
```

---

### 3.3 Off-Topic Detection

**Cuándo evaluar**:
- Usuario envía mensaje > 100 caracteres SIN keywords de vertical
- Ya hubo 1 intento off-topic (`slots['_off_topic_count'] > 0`)
- Plan Premium (tienen budget para LLM extra)

**Implementación** (en `PolicyEngine`):
```python
# En services/orchestrator_service.py, PolicyEngine class

async def detect_off_topic(
    self,
    user_input: str,
    vertical: str,
    llm_client
) -> dict:
    """
    Returns: {
        "is_off_topic": bool,
        "category": str,
        "confidence": float,
        "suggested_response": str
    }
    """
    prompt = f"""
Vertical del negocio: {vertical}

Usuario dice: "{user_input}"

Clasifica el mensaje:
- is_off_topic: true si NO está relacionado al negocio
- category: service_inquiry | pricing | scheduling | complaint | personal_chat | spam | harassment
- confidence: 0.0-1.0
- suggested_response: Mensaje para redirigir (solo si off_topic)

JSON: {{...}}
"""

    result = await llm_client.generate_json(
        "Eres un clasificador de mensajes para asistente de negocio.",
        prompt
    )

    return result or {
        "is_off_topic": False,
        "category": "service_inquiry",
        "confidence": 0.5,
        "suggested_response": ""
    }
```

**Uso en `enforce_policy()`**:
```python
# Dentro de enforce_policy(), antes de SLOT_FILL

# Check off-topic si hay señales
if (
    len(snapshot.user_input) > 100 and
    not self._has_business_keywords(snapshot.user_input, snapshot.vertical) and
    snapshot.slots.get("_off_topic_count", 0) > 0
):
    off_topic_result = await self.detect_off_topic(
        snapshot.user_input,
        snapshot.vertical,
        orchestrator.llm_client
    )

    if off_topic_result["is_off_topic"] and off_topic_result["confidence"] > 0.7:
        count = snapshot.slots.get("_off_topic_count", 0) + 1
        snapshot.slots["_off_topic_count"] = count

        if count >= 3:
            # Hard redirect
            return NextStep(
                next_action=NextAction.ANSWER,
                args={"force_response": "Disculpa, pero solo puedo ayudarte con temas del negocio. ¿Necesitás agendar algo hoy?"},
                reason="Off-topic detectado 3+ veces"
            )
        else:
            # Soft redirect
            return NextStep(
                next_action=NextAction.ANSWER,
                args={"force_response": off_topic_result["suggested_response"]},
                reason="Off-topic detectado, redirigiendo"
            )
```

---

## 4. Batch Jobs

### Job 1: Daily Summarization

**Schedule**: 02:00 AM cada día
**Executor**: Celery Beat
**Target**: Conversaciones completadas del día D-1

**Task** (`tasks/summarize_conversations.py`):
```python
from celery import Celery
from services.orchestrator_service import LLMClient
import asyncio

celery = Celery('pulpo', broker=os.getenv('CELERY_BROKER_URL'))

@celery.task
def summarize_daily_conversations():
    asyncio.run(_summarize_daily_conversations())

async def _summarize_daily_conversations():
    llm = LLMClient()

    # 1. Get completed conversations from yesterday
    conversations = await db.fetch("""
        SELECT
            c.id,
            c.workspace_id,
            c.user_phone,
            ds.slots,
            ds.meta,
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'sender', sender,
                        'content', content
                    ) ORDER BY created_at
                )
                FROM pulpo.messages m
                WHERE m.conversation_id = c.id
            ) as messages
        FROM pulpo.conversations c
        JOIN pulpo.dialogue_states ds ON ds.conversation_id = c.id
        WHERE c.created_at::date = CURRENT_DATE - 1
          AND ds.fsm_state = 'completed'
          AND NOT EXISTS (
            SELECT 1 FROM pulpo.conversation_summaries cs
            WHERE cs.conversation_id = c.id
          )
    """)

    logger.info(f"Found {len(conversations)} conversations to summarize")

    for conv in conversations:
        try:
            # 2. Build dialogue text
            dialogue = "\n".join([
                f"{msg['sender']}: {msg['content']}"
                for msg in (conv['messages'] or [])
            ])

            # 3. Generate summary with LLM
            prompt = f"""
Conversación completa:
{dialogue}

Resume la conversación en 2-3 oraciones capturando:
1. Qué quería el cliente
2. Qué se hizo (acción ejecutada o por qué no se completó)
3. Preferencias o notas importantes mencionadas

Clasifica el resultado y sentimiento.

JSON:
{{
  "summary": str (2-3 oraciones),
  "outcome": "success|failed|abandoned|escalated",
  "sentiment": "positive|neutral|negative|angry",
  "key_facts": [str] (máximo 5 facts importantes)
}}
"""

            summary = await llm.generate_json(
                "Eres un asistente que resume conversaciones de negocio.",
                prompt
            )

            if not summary:
                logger.error(f"Failed to generate summary for {conv['id']}")
                continue

            # 4. Save to database
            await db.execute("""
                INSERT INTO pulpo.conversation_summaries (
                    conversation_id,
                    workspace_id,
                    user_phone,
                    summary_text,
                    outcome,
                    sentiment,
                    key_facts,
                    message_count,
                    duration_seconds
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
                conv['id'],
                conv['workspace_id'],
                conv['user_phone'],
                summary['summary'],
                summary['outcome'],
                summary['sentiment'],
                json.dumps(summary['key_facts']),
                len(conv['messages'] or []),
                0  # TODO: calculate duration
            )

            logger.info(f"Summarized conversation {conv['id']}")

        except Exception as e:
            logger.error(f"Error summarizing conversation {conv['id']}: {e}")
            continue

    await llm.close()
```

**Celery Beat Config** (`celerybeat-schedule.py`):
```python
from celery.schedules import crontab

celery.conf.beat_schedule = {
    'summarize-daily-conversations': {
        'task': 'tasks.summarize_conversations.summarize_daily_conversations',
        'schedule': crontab(hour=2, minute=0),  # 02:00 AM
    },
}
```

---

### Job 2: Profile Update

**Schedule**: 03:00 AM cada día (después de summarization)
**Target**: Clientes con nuevas summaries del día anterior

**Task** (`tasks/update_profiles.py`):
```python
@celery.task
def update_client_profiles():
    asyncio.run(_update_client_profiles())

async def _update_client_profiles():
    # 1. Get new summaries from yesterday
    summaries = await db.fetch("""
        SELECT
            workspace_id,
            user_phone,
            summary_text,
            outcome,
            sentiment,
            key_facts,
            created_at
        FROM pulpo.conversation_summaries
        WHERE created_at::date = CURRENT_DATE - 1
        ORDER BY workspace_id, user_phone, created_at
    """)

    # 2. Group by (workspace, user_phone)
    grouped = {}
    for s in summaries:
        key = (s['workspace_id'], s['user_phone'])
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(s)

    logger.info(f"Updating profiles for {len(grouped)} clients")

    # 3. Update each profile
    for (workspace_id, user_phone), user_summaries in grouped.items():
        try:
            # Get or create profile
            profile = await db.fetchrow("""
                INSERT INTO pulpo.client_profiles (
                    workspace_id, user_phone, total_interactions, first_seen, last_seen
                )
                VALUES ($1, $2, 0, NOW(), NOW())
                ON CONFLICT (workspace_id, user_phone)
                DO UPDATE SET updated_at = NOW()
                RETURNING *
            """, workspace_id, user_phone)

            # Update metrics
            total_interactions = profile['total_interactions'] + len(user_summaries)

            # Calculate avg sentiment
            sentiments = {'positive': 1.0, 'neutral': 0.0, 'negative': -0.5, 'angry': -1.0}
            avg_sentiment = sum(sentiments.get(s['sentiment'], 0) for s in user_summaries) / len(user_summaries)

            # Merge key_facts into preferences
            all_facts = []
            for s in user_summaries:
                all_facts.extend(s['key_facts'] or [])

            # Extract preferences from facts (simple keyword matching)
            preferences = profile['preferences'] or {}
            for fact in all_facts:
                fact_lower = fact.lower()

                # Detect preferred staff
                if 'con' in fact_lower or 'atendió' in fact_lower:
                    # Extract name (heuristic)
                    for name in ['María', 'Juan', 'Carlos', 'Ana']:
                        if name.lower() in fact_lower:
                            preferences['preferred_staff'] = name

                # Detect preferred time
                if any(w in fact_lower for w in ['mañana', 'tarde', 'noche']):
                    if 'mañana' in fact_lower:
                        preferences['preferred_time'] = 'mañana'
                    elif 'tarde' in fact_lower:
                        preferences['preferred_time'] = 'tarde'
                    elif 'noche' in fact_lower:
                        preferences['preferred_time'] = 'noche'

            # Calculate lead score
            lead_score = calculate_lead_score(
                total_interactions,
                avg_sentiment,
                user_summaries[-1]['outcome'],  # Last outcome
                (datetime.now() - profile['last_seen']).days
            )

            # Classify segment
            segment = classify_segment(lead_score, total_interactions)

            # Update profile
            await db.execute("""
                UPDATE pulpo.client_profiles
                SET
                    total_interactions = $3,
                    last_seen = $4,
                    preferences = $5,
                    avg_sentiment = $6,
                    lead_score = $7,
                    segment = $8,
                    updated_at = NOW()
                WHERE workspace_id = $1 AND user_phone = $2
            """,
                workspace_id,
                user_phone,
                total_interactions,
                user_summaries[-1]['created_at'],
                json.dumps(preferences),
                avg_sentiment,
                lead_score,
                segment
            )

            logger.info(f"Updated profile for {user_phone} (score={lead_score}, segment={segment})")

        except Exception as e:
            logger.error(f"Error updating profile {workspace_id}/{user_phone}: {e}")


def calculate_lead_score(interactions: int, sentiment: float, last_outcome: str, days_since_last: int) -> int:
    """
    Lead scoring formula
    Returns: 0-100
    """
    # Recency score (0-30 points)
    if days_since_last == 0:
        recency = 30
    elif days_since_last < 7:
        recency = 25
    elif days_since_last < 30:
        recency = 15
    elif days_since_last < 90:
        recency = 5
    else:
        recency = 0

    # Frequency score (0-30 points)
    if interactions >= 10:
        frequency = 30
    elif interactions >= 5:
        frequency = 20
    elif interactions >= 3:
        frequency = 10
    else:
        frequency = 5

    # Engagement score (0-25 points)
    if last_outcome == 'success':
        engagement = 25
    elif last_outcome == 'escalated':
        engagement = 15
    elif last_outcome == 'failed':
        engagement = 5
    else:  # abandoned
        engagement = 0

    # Sentiment score (0-15 points)
    sentiment_score = max(0, min(15, int((sentiment + 1) * 7.5)))  # Map -1..1 to 0..15

    total = recency + frequency + engagement + sentiment_score
    return min(100, max(0, total))


def classify_segment(score: int, interactions: int) -> str:
    """Classify client segment based on score and interactions"""
    if interactions == 1:
        return 'new'
    elif score >= 70:
        return 'hot'
    elif score >= 50:
        return 'warm'
    elif score >= 30:
        return 'cold'
    else:
        return 'churned'
```

---

### Job 3: Abuse Analysis (Weekly)

**Schedule**: Lunes 08:00 AM
**Output**: Report por email/Slack a workspace admins

**Task** (`tasks/abuse_analysis.py`):
```python
@celery.task
def weekly_abuse_analysis():
    asyncio.run(_weekly_abuse_analysis())

async def _weekly_abuse_analysis():
    # 1. Query abuse logs from Redis
    workspaces = await db.fetch("SELECT id FROM pulpo.workspaces WHERE is_active = true")

    report = []

    for ws in workspaces:
        ws_id = ws['id']

        # Get all abuse keys for this workspace
        pattern = f"abuse:{ws_id}:*"
        keys = await redis.keys(pattern)

        if not keys:
            continue

        abusers = []
        for key in keys:
            user_phone = key.split(':')[-1]

            abuse_data = await redis.hgetall(key)
            if not abuse_data:
                continue

            total_blocks = int(abuse_data.get('total_blocks', 0))
            last_block_at = int(abuse_data.get('last_block_at', 0))

            if total_blocks >= 5:  # Only report serious abusers
                abusers.append({
                    'user_phone': user_phone,
                    'total_blocks': total_blocks,
                    'last_block_at': datetime.fromtimestamp(last_block_at)
                })

        if abusers:
            report.append({
                'workspace_id': ws_id,
                'workspace_name': await get_workspace_name(ws_id),
                'abusers': sorted(abusers, key=lambda x: x['total_blocks'], reverse=True)[:10]
            })

    # 2. Generate report
    if report:
        html = generate_abuse_report_html(report)

        # Send to Slack/Email
        for ws_report in report:
            await send_abuse_alert(ws_report['workspace_id'], html)

        logger.info(f"Sent abuse report to {len(report)} workspaces")
    else:
        logger.info("No abuse to report this week")
```

---

## 5. Roadmap de Implementación

### Sprint 1 (Esta Semana)

**Objetivo**: Arreglar bugs + protecciones básicas

- [x] Arreglar bug de workspace (usar 003 para tests)
- [x] Arreglar saludo repetido (policy engine + prompts explícitos)
- [ ] Implementar `RateLimitService` con Redis
- [ ] Agregar métricas básicas (Prometheus counters)
- [ ] Actualizar tests para workspace correcto
- [ ] Probar flujo end-to-end con conversación real

**Entregables**:
- `shared/rate_limit.py` implementado
- Tests pasando con workspace 003
- Documentación actualizada

---

### Sprint 2 (Próxima Semana)

**Objetivo**: Short-term memory (summaries)

- [ ] Migración SQL: tabla `conversation_summaries`
- [ ] Batch job: `tasks/summarize_conversations.py`
- [ ] Celery Beat configurado (schedule 02:00 AM)
- [ ] Función `load_short_term_memory()` en orchestrator
- [ ] Integrar short-term context en prompts (solo si < 8h)
- [ ] Dashboard admin: ver summaries por cliente

**Entregables**:
- Schema SQL aplicado en desarrollo
- Batch job corriendo en cron local
- Primeras summaries generadas

---

### Sprint 3 (Semana 3)

**Objetivo**: Long-term memory (profiles)

- [ ] Migración SQL: tabla `client_profiles`
- [ ] Batch job: `tasks/update_profiles.py`
- [ ] Lead scoring algorithm implementado
- [ ] Función `load_long_term_memory()` en orchestrator
- [ ] Integrar profiles en prompts (solo plan Premium)
- [ ] API endpoint: `GET /admin/profiles/{workspace_id}` (para dashboard)

**Entregables**:
- Profiles actualizándose diariamente
- Lead scoring funcionando
- Dashboard con segmentos de clientes

---

### Sprint 4 (Semana 4)

**Objetivo**: Limpieza y operaciones

- [ ] Session timeout automático (batch job cada hora)
- [ ] Off-topic detection implementado (LLM-based)
- [ ] Abuse analysis semanal (Celery task)
- [ ] Runbook de operaciones (cómo investigar issues)
- [ ] Alertas automáticas (Slack/email) para escalations
- [ ] Documentación de métricas (Grafana dashboards)

**Entregables**:
- Sistema autocontenido (no requiere intervención manual)
- Alertas configuradas
- Docs de troubleshooting

---

## 6. Costos Reales (Setup Actual: Ollama Local)

### CAPEX (Ya Pagado)
```
GPU: NVIDIA RTX 4090 / A100          ~$1,500 - $10,000
Servidor: Dell/HP PowerEdge           ~$500 - $2,000
Cooling: Rack + ventilación           ~$200 - $500

Total CAPEX: ~$2,200 - $12,500 (one-time)
Amortización: 3 años → $60-350/mes
```

### OPEX (Mensual)
```
Electricidad:
  - GPU 24/7 (350W) @ $0.15/kWh     ~$37/mes
  - Servidor (200W)                  ~$21/mes

Mantenimiento:
  - Cooling                          ~$10/mes
  - Limpieza/reemplazos              ~$20/mes

Total OPEX: ~$88/mes
```

### Costo por Conversación
```
Hardware amortizado: ~$200/mes (midpoint)
OPEX: ~$88/mes

Total: ~$288/mes

Con 10,000 conversaciones/mes: $0.029 por conversación
Con 50,000 conversaciones/mes: $0.006 por conversación
Con 100,000 conversaciones/mes: $0.003 por conversación
```

**Límite**: Depende de GPU
- RTX 4090: ~5-10 requests simultáneos
- A100 40GB: ~15-25 requests simultáneos
- A100 80GB: ~30-50 requests simultáneos

---

### Plan de Migración a APIs Pagas

**Trigger**: Cuando concurrencia > capacidad GPU O revenue > $5,000/mes

**Costos API** (estimados con tu arquitectura):
```
GPT-4o: $2.50/1M tokens input, $10/1M tokens output

Conversación promedio (10 mensajes, con tu sistema de slots):
  - Input: ~1,200 tokens (system prompt + slots + user input)
  - Output: ~150 tokens (JSON response)

Costo por conversación:
  = (1,200 * $2.50 / 1,000,000) + (150 * $10 / 1,000,000)
  = $0.003 + $0.0015
  = $0.0045 por conversación

Con summaries (batch, GPT-3.5-turbo @ $0.50/1M):
  - Promedio 500 tokens input + 100 output
  = $0.0003 por summary

Total: ~$0.005 por conversación (con summary incluido)
```

**Estrategia Híbrida** (fase intermedia):
```
Tier 1 - Ollama (hasta saturar GPU):
  - Workspaces Basic/Pro
  - Conversaciones simples
  - Costo: $0.003/conversación (amortizado)

Tier 2 - API fallback:
  - Overflow cuando GPU saturada
  - Workspaces Premium
  - Conversaciones complejas
  - Costo: $0.005/conversación

Breakeven: Cuando API cost < (nueva GPU cost / expected lifetime)
  Nueva A100: $10,000 / 3 años = $278/mes
  API equivalente: $278 / $0.005 = 55,600 conversaciones/mes

  → Si estás haciendo >60k convos/mes, API es más barato que comprar GPU
```

---

## 7. Anexo: Referencias de Implementación

### Archivos Clave

**Orchestrator**:
- `services/orchestrator_service.py` - Core logic
- `services/orchestrator_app.py` - FastAPI endpoints
- `services/vertical_manager.py` - Vertical configs

**Tools**:
- `services/servicios_tools.py` - Tools para vertical servicios
- `services/mcp_client.py` - MCP integration layer

**Database**:
- `database/migrations/002_n8n_workflow_functions.sql` - Funciones actuales
- `database/init/00_schema_normalized.sql` - Schema base

**Nuevos archivos a crear**:
- `shared/rate_limit.py` - Rate limiting service
- `tasks/summarize_conversations.py` - Batch job summaries
- `tasks/update_profiles.py` - Batch job profiles
- `tasks/cleanup_sessions.py` - Session timeouts
- `tasks/abuse_analysis.py` - Weekly abuse report

---

### Tablas SQL Involucradas

**Existentes**:
- `pulpo.workspaces` - Tenants
- `pulpo.conversations` - Conversaciones
- `pulpo.messages` - Mensajes
- `pulpo.dialogue_states` - Estado (Capa 1: Working Memory)

**Nuevas** (a crear en sprints):
- `pulpo.conversation_summaries` - Capa 2: Short-term memory
- `pulpo.client_profiles` - Capa 3: Long-term memory

---

### Configuración Redis

**Conexión**:
```bash
# docker-compose.yml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

**ENV vars**:
```bash
REDIS_URL=redis://redis:6379
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1
```

---

### Métricas Prometheus

**Counter**: `rate_limit_exceeded_total{workspace, plan, window}`
**Histogram**: `context_load_duration_seconds{layer, plan}`
**Gauge**: `active_conversations{workspace}`

**Endpoint**: `http://orchestrator:8005/metrics`

---

## Conclusión

Esta arquitectura balancea:
- ✅ **Performance**: Solo cargar contexto cuando aporta valor
- ✅ **Costo**: Usar hardware local (Ollama) hasta saturar
- ✅ **Escalabilidad**: Redis distribuido + batch jobs asíncronos
- ✅ **Multi-tenancy**: RLS en PostgreSQL + prefijos en Redis
- ✅ **Observabilidad**: Métricas + logs + alertas

**Próximo paso inmediato**: Implementar rate limiting (Sprint 1, tarea #1)
