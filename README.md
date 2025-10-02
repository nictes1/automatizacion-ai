# PulpoAI - Sistema Multitenant de Agentes Conversacionales

## 🎯 **Visión**
Sistema SaaS multitenant que reemplaza bots tradicionales con IA conversacional inteligente, orquestado por n8n y especializado por verticales (gastronomía, inmobiliaria, servicios).

## 🏗️ **Arquitectura Actual**

### **Servicios Básicos (Funcionando)**
- **PostgreSQL + pgvector**: Base de datos principal con soporte para embeddings
- **Redis**: Cache y debounce de mensajes
- **Ollama**: LLM local para procesamiento de lenguaje natural

### **Estructura del Proyecto**
```
pulpo/
├── services/           # Microservicios principales
│   ├── orchestrator_service.py    # Orquestador de diálogo
│   ├── actions_service_v2.py     # Ejecución de acciones de negocio
│   ├── rag_service.py            # Búsqueda semántica
│   └── orchestrator_app.py       # FastAPI app del orquestador
├── shared/            # Librerías compartidas
│   ├── database/      # Cliente de base de datos
│   ├── auth/         # Autenticación JWT
│   ├── monitoring/    # Métricas y logging
│   └── utils/        # Utilidades comunes
├── database/          # Scripts SQL de inicialización
│   └── init/         # Migraciones y esquemas
├── n8n/              # Workflows de n8n
├── scripts/          # Scripts de deployment y testing
├── docs/             # Documentación
└── utils/            # Utilidades del sistema
```

## 🚀 **Cómo Empezar**

### **1. Levantar Servicios Básicos**
```bash
# Solo servicios básicos (recomendado para empezar)
docker-compose -f docker-compose.simple.yml up -d

# Verificar que estén funcionando
docker ps
```

### **2. Verificar Servicios**
```bash
# PostgreSQL
docker exec pulpo-postgres psql -U pulpo -d pulpo -c "SELECT version();"

# Redis
docker exec pulpo-redis redis-cli ping

# Ollama
curl http://localhost:11434/api/tags
```

### **3. Levantar Microservicios (Próximo Paso)**
```bash
# Cuando estén listos los servicios básicos
docker-compose up -d
```

## 📋 **Estado Actual**

### ✅ **Completado**
- [x] Limpieza de estructura del proyecto
- [x] Servicios básicos funcionando (PostgreSQL, Redis, Ollama)
- [x] Librerías compartidas creadas
- [x] Microservicios separados (Orchestrator, Actions, RAG)
- [x] Documentación base

### 🔄 **En Progreso**
- [ ] Testing de microservicios
- [ ] Integración con n8n
- [ ] Testing end-to-end

### 📝 **Próximos Pasos**
1. **Testing de Microservicios**: Verificar que cada servicio funcione independientemente
2. **Integración n8n**: Conectar workflows con los servicios
3. **Testing End-to-End**: Flujo completo desde WhatsApp hasta respuesta
4. **Primera Vertical**: Implementar flujo de gastronomía

## 🛠️ **Comandos Útiles**

```bash
# Ver logs de un servicio
docker logs pulpo-postgres

# Conectar a PostgreSQL
docker exec -it pulpo-postgres psql -U pulpo -d pulpo

# Conectar a Redis
docker exec -it pulpo-redis redis-cli

# Ver estado de todos los servicios
docker-compose ps
```

## 📚 **Documentación**
- [La Biblia de Pulpo v3](LaBibliadePulpo.md) - Documentación completa del sistema
- [Arquitectura](docs/README.md) - Diagramas y explicaciones técnicas
- [Scripts](scripts/README.md) - Guía de uso de scripts de deployment