# 🐙 Guía Docker - PulpoAI

## 📦 Único docker-compose.yml

Consolidamos todos los archivos en **uno solo**: `docker-compose.yml`

Este archivo incluye:
- ✅ PostgreSQL con pgvector
- ✅ Redis
- ✅ Ollama (LLM local)
- ✅ Microservicios (RAG, Orchestrator, Actions)
- ✅ n8n (Workflow Engine)
- ✅ Monitoring (Prometheus, Grafana)
- ✅ pgAdmin (DB management)

## 🚀 Comandos Útiles

### Iniciar todo el stack

```bash
docker-compose up -d
```

### Iniciar solo infraestructura básica (sin microservicios ni monitoring)

```bash
docker-compose up -d postgres redis ollama
```

### Iniciar infraestructura + microservicios (sin monitoring)

```bash
docker-compose up -d postgres redis ollama rag orchestrator actions n8n
```

### Ver logs de un servicio

```bash
docker-compose logs -f orchestrator
docker-compose logs -f ollama
```

### Detener todo

```bash
docker-compose down
```

### Detener y eliminar volúmenes (⚠️ BORRA DATOS)

```bash
docker-compose down -v
```

### Rebuild de un servicio

```bash
docker-compose up -d --build orchestrator
```

### Ver estado de servicios

```bash
docker-compose ps
```

## 🔍 Acceso a Servicios

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| PostgreSQL | `localhost:5432` | pulpo/pulpo |
| Redis | `localhost:6379` | - |
| Ollama | `http://localhost:11434` | - |
| Orchestrator | `http://localhost:8005` | - |
| Actions | `http://localhost:8006` | - |
| RAG | `http://localhost:8007` | - |
| n8n | `http://localhost:5678` | admin/admin123 |
| pgAdmin | `http://localhost:8080` | admin@pulpo.ai/admin123 |
| Prometheus | `http://localhost:9090` | - |
| Grafana | `http://localhost:3000` | admin/admin123 |

## 📊 Health Checks

Todos los servicios tienen endpoints de salud:

```bash
curl http://localhost:8005/health  # Orchestrator
curl http://localhost:8006/health  # Actions
curl http://localhost:8007/health  # RAG
curl http://localhost:5678/healthz # n8n
```

## 🛠️ Troubleshooting

### Ollama no tiene modelos

```bash
# Entrar al container
docker exec -it pulpo-ollama bash

# Descargar modelos
ollama pull qwen2.5:14b
ollama pull llama3.1:8b
ollama pull nomic-embed-text

# Verificar
ollama list
```

### Base de datos no inicializa

```bash
# Ver logs
docker-compose logs postgres

# Reiniciar desde cero
docker-compose down -v
docker-compose up -d postgres
```

### Microservicio no se conecta

```bash
# Verificar network
docker network inspect pulpo-network

# Ver logs del servicio
docker-compose logs -f orchestrator

# Rebuild
docker-compose up -d --build orchestrator
```

## 📝 Notas

- Los volúmenes persisten los datos entre reinicios
- Los init scripts de PostgreSQL (`database/init/*.sql`) se ejecutan automáticamente en el primer inicio
- Para desarrollo, los volumes están mapeados para hot-reload
- La red `pulpo-network` conecta todos los servicios
