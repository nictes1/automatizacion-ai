# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PulpoAI is a multitenant SaaS platform that automates conversational customer service through messaging channels (WhatsApp, voice, Telegram, Instagram DM). It uses AI agents orchestrated by n8n, specialized by vertical industries (gastronomy, real estate, e-commerce, services).

### Core Value Proposition
- Replace traditional bots with intelligent conversational AI
- Execute business actions based on subscription tier (Start/Pro/Max)
- Provide RAG-based contextual responses from business documents
- Enable human takeover from dashboard when needed

## Architecture

### Microservices Structure
The system follows a microservices architecture with clear separation of concerns:

1. **Orchestrator Service** (`services/orchestrator_service.py`)
   - Policy-based deterministic orchestration with LLM support
   - Manages conversation flow using state machine pattern (`NextAction` enum)
   - Handles slot filling, context retrieval, and action execution decisions
   - Uses idempotency keys for reliable message processing

2. **Actions Service** (`services/actions_service_v2.py`)
   - Executes business actions (create_order, reserve_table, schedule_visit, etc.)
   - Provides idempotent action execution with request tracking
   - Vertical-specific action implementations (gastronomy, real estate, services)

3. **RAG Service** (`services/rag_service.py`)
   - Semantic search using pgvector embeddings
   - Ollama integration for embedding generation (nomic-embed-text model)
   - Fallback to text search when embeddings unavailable

### Shared Libraries (`shared/`)
All microservices use common libraries:
- `shared/database/` - PostgreSQL client with workspace context and RLS support
- `shared/auth/` - JWT authentication and authorization middleware
- `shared/monitoring/` - Structured logging and Prometheus metrics
- `shared/utils/` - Common helpers, validators, formatters

### Vertical Configuration
Verticals are configured via `services/vertical_manager.py`:
- **Gastronomía**: Menu queries, reservations, orders, delivery
- **Inmobiliaria**: Property search, visit scheduling, financing info
- **Servicios**: Appointment booking, service info, pricing

Each vertical has:
- Custom system prompts
- Specific intents and entities
- Dedicated actions

### Data Isolation (Multitenant)
- All tables use Row-Level Security (RLS) with `workspace_id` filtering
- Database queries must set workspace context: `SELECT set_config('app.workspace_id', workspace_id, true)`
- Redis keys include workspace prefix
- RAG searches filtered by workspace

## Development Commands

### Starting Services

```bash
# Start basic services only (PostgreSQL, Redis, Ollama)
docker-compose -f docker-compose.simple.yml up -d

# Start all services including microservices and n8n
docker-compose up -d

# Start full stack with monitoring (Prometheus, Grafana)
docker-compose -f docker-compose.full.yml up -d
```

### Service Verification

```bash
# Check all services status
docker-compose ps

# PostgreSQL connection test
docker exec pulpo-postgres psql -U pulpo -d pulpo -c "SELECT version();"

# Redis ping test
docker exec pulpo-redis redis-cli ping

# Ollama models check
curl http://localhost:11434/api/tags

# Check service health endpoints
curl http://localhost:8007/rag/health        # RAG service
curl http://localhost:8006/actions/health    # Actions service
curl http://localhost:8005/orchestrator/health  # Orchestrator service
```

### Database Operations

```bash
# Connect to PostgreSQL
docker exec -it pulpo-postgres psql -U pulpo -d pulpo

# View database schema
docker exec pulpo-postgres psql -U pulpo -d pulpo -c "\dt pulpo.*"

# Run migrations (init scripts run automatically on first start)
# Manual migration files are in: database/init/
# - 01_schema.sql: Core tables, extensions (pgvector, uuid-ossp)
# - 02_functions.sql: Stored procedures and triggers
# - 03_rls.sql: Row-Level Security policies
# - 04_seed.sql: Development seed data
```

### Testing

```bash
# End-to-end system test
python scripts/test_end_to_end.py

# Test individual services
python scripts/test_real_services.py

# Test complete system (orchestrator + actions + RAG)
python scripts/test_complete_system.py

# Test RAG search
python scripts/test_rag_search.py

# Test business action (e.g., create order)
python scripts/test_crear_pedido.py

# Validate n8n workflow
python scripts/validate_workflow.py

# AI Client Simulated Tests (Recommended)
# Tests conversacionales realistas con múltiples escenarios
./scripts/run_ai_tests.sh
# O directamente:
python3 tests/test_ai_client_scenarios.py
```

### Ollama Model Management

```bash
# List available models
docker exec pulpo-ollama ollama list

# Pull required models
docker exec pulpo-ollama ollama pull qwen2.5:14b    # Orchestrator (production)
docker exec pulpo-ollama ollama pull llama3.1:8b    # AI Client simulation
docker exec pulpo-ollama ollama pull nomic-embed-text  # RAG embeddings

# Test generation
echo "Hola, ¿cómo estás?" | docker exec -i pulpo-ollama ollama run llama3.1:8b

# Test embeddings
curl http://localhost:11434/api/embeddings -d '{"model":"nomic-embed-text","prompt":"test query"}'
```

### Document Ingestion & Embeddings

```bash
# Generate embeddings for existing documents
python scripts/generate_embeddings.py

# The ingestion service handles: PDF, DOCX, XLSX, PPTX, images (OCR)
# Documents are chunked and embedded automatically
```

## Key Design Patterns

### Request Context Management
All services use `contextvars.ContextVar` for thread-safe, async-safe request context:
```python
from services.orchestrator_service import REQUEST_CONTEXT, RequestContext

with RequestContext({"x-workspace-id": workspace_id}):
    # Workspace context is automatically available
    result = await process_request()
```

### Idempotency
All action executions use stable idempotency keys:
```python
key = stable_idempotency_key(conversation_id, payload, vertical)
# SHA-256 hash of canonical JSON: {vertical}:{conversation_id}:{sorted_payload}
```

### Conversation Flow State Machine
The orchestrator uses explicit state transitions:
- `GREET` → Initial greeting
- `SLOT_FILL` → Collect missing information
- `RETRIEVE_CONTEXT` → RAG search
- `EXECUTE_ACTION` → Business action
- `ANSWER` → Generate response
- `ASK_HUMAN` → Escalate to human

### Database Schema Pattern
Tables follow multitenant structure:
```sql
CREATE TABLE pulpo.{table_name} (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id),
  -- other fields
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- RLS Policy
ALTER TABLE pulpo.{table_name} ENABLE ROW LEVEL SECURITY;
CREATE POLICY workspace_isolation ON pulpo.{table_name}
  USING (workspace_id::text = current_setting('app.workspace_id', true));
```

## Environment Configuration

Key environment variables (see `.env`):
```bash
# Database
DATABASE_URL=postgresql://pulpo:pulpo@postgres:5432/pulpo

# Redis
REDIS_URL=redis://redis:6379

# Ollama
OLLAMA_URL=http://ollama:11434

# JWT
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256

# Service URLs (for inter-service communication)
RAG_URL=http://rag:8007
ACTIONS_URL=http://actions:8006
ORCHESTRATOR_URL=http://orchestrator:8005

# n8n
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123
```

## Service Ports

- **5432**: PostgreSQL
- **6379**: Redis
- **11434**: Ollama
- **5678**: n8n
- **8005**: Orchestrator Service
- **8006**: Actions Service
- **8007**: RAG Service
- **8080**: pgAdmin
- **9090**: Prometheus
- **3000**: Grafana

## Common Development Workflows

### Adding a New Vertical
1. Add configuration in `services/vertical_manager.py`
2. Define system prompt, intents, entities, actions
3. Implement vertical-specific actions in `services/actions_service_v2.py`
4. Update seed data in `database/init/04_seed.sql` if needed

### Adding a New Action
1. Define action in vertical config (`vertical_manager.py`)
2. Implement action method in `ActionExecutor` class (`actions_service_v2.py`)
3. Add validation and business logic
4. Return `ActionResponse` with success status and data
5. Test with `scripts/test_*.py`

### Modifying Database Schema
1. Create new migration file in `database/init/`
2. Use sequential numbering (05_*, 06_*, etc.)
3. Include both UP and DOWN migrations
4. Test migration before applying to production
5. Update RLS policies if new workspace-scoped table

### Debugging Conversation Flow
1. Check orchestrator logs: `docker logs pulpo-orchestrator -f`
2. Inspect conversation state in database:
   ```sql
   SELECT * FROM pulpo.conversations WHERE id = 'conversation-id';
   SELECT * FROM pulpo.messages WHERE conversation_id = 'conversation-id' ORDER BY created_at;
   ```
3. Review tool calls and actions:
   ```sql
   SELECT * FROM pulpo.tool_calls WHERE conversation_id = 'conversation-id';
   ```

## Important Implementation Notes

- **Never bypass workspace isolation**: Always set `app.workspace_id` config before queries
- **Use connection pooling**: All services use `SimpleConnectionPool` or async pools
- **Handle Ollama failures gracefully**: RAG service falls back to text search if embeddings fail
- **Metrics collection**: All services expose Prometheus metrics at `/metrics`
- **Structured logging**: Use `logger.info(msg, extra={...})` for searchable logs
- **API authentication**: All endpoints require JWT in `Authorization` header except `/health`

## Testing Philosophy

- **Unit tests**: Test individual action implementations
- **Integration tests**: Test service-to-service communication
- **End-to-end tests**: Simulate full WhatsApp message flow
- **Smoke tests**: Verify all services are responding (`scripts/smoke_test.sh`)

## Monitoring & Observability

### Metrics Available
- Request latency (`{service}_request_duration_seconds`)
- Request count (`{service}_requests_total`)
- Database query performance (`{service}_db_query_duration_seconds`)
- Business metrics (conversations, messages, actions executed)
- RAG metrics (searches, embeddings generated, documents ingested)

### Log Locations
- Service logs: `docker logs pulpo-{service-name}`
- PostgreSQL logs: `docker logs pulpo-postgres`
- n8n execution logs: Via n8n UI at http://localhost:5678

### Access Dashboards
- **n8n**: http://localhost:5678 (admin/admin123)
- **Grafana**: http://localhost:3000 (admin/admin123)
- **pgAdmin**: http://localhost:8080 (admin@pulpo.ai/admin123)
- **Prometheus**: http://localhost:9090

## Reference Documentation

- Full system documentation: `LaBibliadePulpo.md` (comprehensive Spanish docs)
- Shared libraries guide: `shared/README.md`
- Database guide: `database/README.md`
- Scripts usage: `scripts/readme.md`
- Architecture diagrams: `docs/README.md`
