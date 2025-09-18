# PulpoAI — Mini RAG + n8n + Worker (README)

> **Objetivo:** chatear con datos propios vía RAG. n8n recibe el mensaje, llama a un **worker FastAPI** (`/rag/search`) que consulta Postgres+pgvector con **RLS por workspace** y devuelve *chunks* relevantes.

---

## 0) Requisitos
- Docker & Docker Compose
- Postgres con pgvector (se levanta con Compose)
- n8n 1.80.x (evitar `latest`)
- Repo con:
  - `sql/` (migraciones)
  - `worker_min.py`
  - `docker-compose.yml`
  - `.env` (ver ejemplo más abajo)

---

## 1) Variables de entorno (`.env` de ejemplo)

```env
# ZONA HORARIA
TZ=America/Argentina/Buenos_Aires

# DB
POSTGRES_DB=pulpo
POSTGRES_USER=pulpo
POSTGRES_PASSWORD=pulpo
POSTGRES_PORT=5432

# REDIS
REDIS_PORT=6379

# OLLAMA (opcional)
OLLAMA_PORT=11434

# N8N
N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_PROTOCOL=http
WEBHOOK_URL=http://192.168.1.104:5678/
N8N_ENCRYPTION_KEY=<<TU_CLAVE_UNICA>>

# PGADMIN (opcional)
PGADMIN_EMAIL=admin@pulpo.local
PGADMIN_PASSWORD=pulpo
PGADMIN_PORT=5050

# QDRANT (si usás profile with-qdrant)
QDRANT_PORT=6333
```

> **Nota:** `N8N_ENCRYPTION_KEY` DEBE coincidir con el valor guardado en `/home/node/.n8n/config` dentro del contenedor n8n (ver Troubleshooting).

---

## 2) `docker-compose.yml` — puntos clave (resumen)

- **Todos** los servicios en la **misma red** (`pulpo-net`).
- n8n **fijar versión**: `n8nio/n8n:1.80.1`.
- **Worker** en Compose y **SIN** publicar el puerto si no es necesario (n8n lo llama por hostname `worker`).
- Postgres expone `5432`, monta `./sql/` para migraciones.

**Ejemplo de servicio `worker`:**
```yaml
  worker:
    image: python:3.11-slim
    container_name: pulpo-worker
    working_dir: /app
    volumes:
      - ./:/app:ro
    environment:
      DATABASE_URL: "postgresql://pulpo:pulpo@db:5432/pulpo"  # host = servicio 'db'
    command: >
      sh -lc "pip install --no-cache-dir fastapi uvicorn psycopg[binary] pydantic &&
              uvicorn worker_min:app --host 0.0.0.0 --port 8000"
    depends_on:
      db:
        condition: service_healthy
    # ports:
    #   - "8000:8000"   # opcional, útil para curl desde host; si choca, quitar o mapear a 18000
    networks: [pulpo-net]
```

> **¿Cómo encuentra `worker_min.py`?** Por el volumen `./:/app` + `working_dir: /app`. El comando `uvicorn worker_min:app` importa `/app/worker_min.py` y toma la variable `app`.

---

## 3) Boot de servicios

```bash
# Levantar DB/Redis/n8n (y opcionales)
docker compose up -d db redis n8n

# Aplicar migraciones RAG (si no se auto-ejecutaron)
docker exec -i pulpo-db psql -U pulpo -d pulpo < sql/07_rag_up.sql

# Levantar worker (tras DB healthy)
docker compose up -d worker

# Ver logs del worker (esperar "Uvicorn running on http://0.0.0.0:8000")
docker logs -f pulpo-worker
```

---

## 4) Carga de datos mínima (demo)

```bash
# Setear contexto de workspace (dev fijo)
docker exec -it pulpo-db psql -U pulpo -d pulpo -c "SELECT pulpo.set_ws_context('00000000-0000-0000-0000-000000000001');"

# Insertar documento dummy
docker exec -it pulpo-db psql -U pulpo -d pulpo -c "
INSERT INTO pulpo.documents (workspace_id, title, mime, hash, storage_url, size_bytes)
VALUES ('00000000-0000-0000-0000-000000000001','menu demo','pdf','demo-hash-001','file://storage/demo/menu.pdf',12345);"

# Insertar chunk y embedding placeholder
docker exec -it pulpo-db psql -U pulpo -d pulpo -c "
WITH d AS (SELECT id FROM pulpo.documents WHERE hash='demo-hash-001')
INSERT INTO pulpo.chunks (workspace_id, document_id, pos, text, meta)
SELECT '00000000-0000-0000-0000-000000000001', d.id, 0,
       'Menú: Pizzas (muzza, napolitana), Empanadas. NO hay ravioles. Horario: 20–24 hs.',
       jsonb_build_object('page',1)
FROM d
ON CONFLICT DO NOTHING;"

docker exec -it pulpo-db psql -U pulpo -d pulpo -c "
WITH c AS (SELECT id AS chunk_id, document_id FROM pulpo.chunks ORDER BY created_at DESC LIMIT 1)
INSERT INTO pulpo.chunk_embeddings (chunk_id, workspace_id, document_id, embedding)
SELECT chunk_id, '00000000-0000-0000-0000-000000000001', document_id,
       (SELECT ARRAY(SELECT 0.0::float4 FROM generate_series(1,1024))::vector)
FROM c ON CONFLICT (chunk_id) DO NOTHING;"
```

---

## 5) n8n — Nodo HTTP “RAG Search (worker)”

- **Method:** `POST`
- **URL:** `http://worker:8000/rag/search`
- **Headers:**
  - `Content-Type: application/json`
  - `X-Workspace-Id`: `{{$json.root.ws_id}}`
- **Body (JSON):**
```json
{ "top_k": 5, "vector_mode": "unit" }
```

### Disparo del flujo (webhook test n8n)
```bash
curl -s -X POST "http://<IP_DEL_SERVER>:5678/webhook-test/pulpo/twilio/wa/inbound"   -H "Content-Type: application/json"   -d '{"Body":"¿Tienen ravioles?","From":"whatsapp:+5491111111111","To":"whatsapp:+5491112345678","WaId":"5491111111111","SmsSid":"SM_TEST_1"}'
```

**Esperado:** el nodo devuelve `results[0].preview` con “NO hay ravioles…”. En `docker logs -f pulpo-worker` verás `POST /rag/search 200`.

---

## 6) Troubleshooting (casos reales y solución)

### 6.1 n8n en loop / error “Mismatching encryption keys”
- Causa: la clave en `/home/node/.n8n/config` **no coincide** con `N8N_ENCRYPTION_KEY`.
- Solución express:
  ```bash
  docker compose run --rm --no-deps --entrypoint sh n8n -lc 'cat /home/node/.n8n/config'
  # Copiá el valor de "encryptionKey"
  # Pégalo en tu .env -> N8N_ENCRYPTION_KEY=...
  docker compose up -d --no-deps --force-recreate n8n
  ```
- Consejo: fijar imagen `n8nio/n8n:1.80.1` y `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true`.

### 6.2 n8n no llega al worker (ECONNREFUSED / Executing…)
- Usá URL **interna**: `http://worker:8000/rag/search`.
- Asegurate que **n8n y worker** comparten la **red** (`pulpo-net`).
- Verificá el worker corriendo:
  ```bash
  docker logs -f pulpo-worker
  ```

### 6.3 Conflicto de puerto 8000 al crear `worker`
- Mensaje: `address already in use`.
- Causa: ya tenías `uvicorn` en host:8000.
- Solución: **no publicar** el puerto en el servicio worker (quitar `ports:`) o mapear `18000:8000`.

### 6.4 Probar desde dentro de n8n (BusyBox `wget`)
- BusyBox no tiene `--method=POST`. Usar `--post-data`:
  ```bash
  docker exec -it pulpo-n8n sh -lc   'wget -qO- --header="Content-Type: application/json"    --header="X-Workspace-Id: 00000000-0000-0000-0000-000000000001"    --post-data="{"top_k":1,"vector_mode":"unit"}"    http://worker:8000/rag/search'
  ```

### 6.5 Si el worker estuviera fuera de Docker (no recomendado)
- Obtener gateway del contenedor y usar `http://<GW>:8000`:
  ```bash
  docker exec -it pulpo-n8n sh -lc 'ip route | awk "/default/ {print \$3}"'
  # Ej: 172.25.0.1  -> URL: http://172.25.0.1:8000/rag/search
  ```
- Mejor: contenerizar el worker y llamar por hostname.

### 6.6 Healthchecks y estado
```bash
docker inspect -f '{{.State.Health.Status}}' pulpo-n8n
docker compose logs -f n8n
```

---

## 7) Aceptación (Golden path)
1. `docker compose up -d db redis n8n worker` → **todos healthy**.
2. Migraciones RAG aplicadas, datos demo insertados.
3. Desde n8n (Test step) en “RAG Search (worker)” retorna `results` con el preview esperado.
4. El webhook test responde **200** y el nodo muestra `score: 1` con “NO hay ravioles…”.

---

## 8) Registro Vivo (PulpoAI)
- **Fase:** 2 — RAG (Documentos y búsquedas)
- **Microflujo:** F-05 *RAG Search Handler (consulta → vector search → LLM con contexto)*
- **Estado:** ✅ validado (mínimo viable n8n→worker→DB)
- **Prioridad:** [P1]
- **Dependencias:** DB (pgvector), RLS activo, worker en `pulpo-net`, n8n 1.80.x
- **Notas de arquitectura:** llamadas intra-Compose por hostname; evitar `localhost`. Claves de n8n alineadas.

---

## 9) Próximos pasos (corto)
- F-04 Ingesta real (PDF → parse → chunks → embeddings).
- F-03 Persistir outbound + respuesta por canal (Twilio/WA).
- Prompting por vertical (menú/resto) y guardado de conversaciones.
