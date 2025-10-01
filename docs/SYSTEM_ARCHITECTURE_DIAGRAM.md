# 🏗️ Diagrama de Arquitectura del Sistema PulpoAI

## 📊 **Vista General del Sistema**

```mermaid
graph TB
    subgraph "Frontend Layer"
        APP[App Pulpo<br/>Frontend]
    end
    
    subgraph "API Gateway Layer"
        API[API Gateway<br/>Load Balancer]
    end
    
    subgraph "Service Layer"
        N8N[n8n Workflow<br/>Conversación<br/>:5678]
        INGEST[File Ingestor<br/>Multitenant<br/>:8080]
        RAG[Worker RAG<br/>Búsqueda<br/>:8002]
    end
    
    subgraph "Processing Layer"
        TIKA[Tika Server<br/>Extracción<br/>:9998]
        OLLAMA[Ollama<br/>LLM + Embeddings<br/>:11434]
        PROCESSOR[Quality Processor<br/>Control Calidad]
    end
    
    subgraph "Data Layer"
        POSTGRES[(PostgreSQL<br/>RLS + pgvector<br/>:5432)]
        REDIS[(Redis<br/>Cache<br/>:6379)]
    end
    
    subgraph "Storage Layer"
        FILES[File Storage<br/>uploads/]
        BACKUPS[Backups<br/>backups/]
    end
    
    %% Connections
    APP --> API
    API --> N8N
    API --> INGEST
    API --> RAG
    
    N8N --> OLLAMA
    N8N --> POSTGRES
    N8N --> REDIS
    
    INGEST --> PROCESSOR
    INGEST --> POSTGRES
    INGEST --> REDIS
    
    RAG --> OLLAMA
    RAG --> POSTGRES
    RAG --> REDIS
    
    PROCESSOR --> TIKA
    PROCESSOR --> OLLAMA
    PROCESSOR --> POSTGRES
    
    TIKA --> FILES
    INGEST --> FILES
    RAG --> FILES
    
    POSTGRES --> BACKUPS
```

## 🔄 **Flujo de Datos Principal**

```mermaid
sequenceDiagram
    participant U as Usuario
    participant A as App Pulpo
    participant N as n8n Workflow
    participant O as Ollama
    participant P as PostgreSQL
    participant R as Redis
    
    U->>A: Mensaje
    A->>N: Webhook + Token
    N->>P: Validar Usuario
    N->>O: Generar Respuesta
    O->>N: Respuesta LLM
    N->>R: Cache Resultado
    N->>A: Respuesta
    A->>U: Mensaje Final
```

## 📁 **Flujo de Ingesta de Archivos**

```mermaid
sequenceDiagram
    participant U as Usuario
    participant A as App Pulpo
    participant I as File Ingestor
    participant Q as Quality Processor
    participant T as Tika Server
    participant O as Ollama
    participant P as PostgreSQL
    
    U->>A: Subir Archivo
    A->>I: POST /ingest/upload + Token
    I->>P: Validar Usuario/Quota
    I->>Q: Procesar Archivo
    Q->>T: Extraer Texto
    T->>Q: Texto + Metadatos
    Q->>O: Generar Embeddings
    O->>Q: Vectores
    Q->>P: Guardar Documento
    I->>A: file_id + Métricas
    A->>U: Confirmación
```

## 🔍 **Flujo de Búsqueda RAG**

```mermaid
sequenceDiagram
    participant U as Usuario
    participant A as App Pulpo
    participant R as Worker RAG
    participant O as Ollama
    participant P as PostgreSQL
    participant C as Redis Cache
    
    U->>A: Consulta
    A->>R: POST /rag/search
    R->>C: Verificar Cache
    alt Cache Hit
        C->>R: Resultado Cached
    else Cache Miss
        R->>O: Embedding Consulta
        O->>R: Vector Consulta
        R->>P: Búsqueda Vectorial
        P->>R: Documentos Similares
        R->>C: Guardar en Cache
    end
    R->>A: Resultados
    A->>U: Respuesta
```

## 🏢 **Arquitectura Multi-Tenant**

```mermaid
graph TB
    subgraph "Workspace 1"
        U1[Usuario 1]
        U2[Usuario 2]
        W1[Workspace 1<br/>Plan: Premium]
    end
    
    subgraph "Workspace 2"
        U3[Usuario 3]
        U4[Usuario 4]
        W2[Workspace 2<br/>Plan: Basic]
    end
    
    subgraph "Shared Services"
        DB[(PostgreSQL<br/>RLS Enabled)]
        CACHE[(Redis<br/>Namespaced)]
        STORAGE[File Storage<br/>Isolated]
    end
    
    U1 --> W1
    U2 --> W1
    U3 --> W2
    U4 --> W2
    
    W1 --> DB
    W2 --> DB
    
    W1 --> CACHE
    W2 --> CACHE
    
    W1 --> STORAGE
    W2 --> STORAGE
```

## 🔐 **Flujo de Autenticación**

```mermaid
sequenceDiagram
    participant U as Usuario
    participant A as App Pulpo
    participant S as File Ingestor
    participant V as Token Validator
    participant P as PostgreSQL
    
    U->>A: Login
    A->>P: Validar Credenciales
    P->>A: Usuario + Workspace
    A->>A: Generar JWT
    A->>U: Token JWT
    
    Note over U,S: Usuario sube archivo
    
    U->>A: Subir Archivo
    A->>S: POST + JWT Token
    S->>V: Validar Token
    V->>P: Verificar Usuario/Workspace
    P->>V: Datos Usuario
    V->>S: Usuario Validado
    S->>S: Procesar Archivo
    S->>A: Resultado
    A->>U: Confirmación
```

## 📊 **Métricas y Monitoreo**

```mermaid
graph TB
    subgraph "Application Metrics"
        QPS[Queries Per Second]
        LAT[Latency]
        ERR[Error Rate]
        QLT[Quality Score]
    end
    
    subgraph "System Metrics"
        CPU[CPU Usage]
        MEM[Memory Usage]
        DISK[Disk Usage]
        NET[Network I/O]
    end
    
    subgraph "Business Metrics"
        USERS[Active Users]
        FILES[Files Processed]
        SEARCH[Search Queries]
        CONV[Conversations]
    end
    
    subgraph "Monitoring Stack"
        PROM[Prometheus]
        GRAF[Grafana]
        ALERT[AlertManager]
        LOGS[ELK Stack]
    end
    
    QPS --> PROM
    LAT --> PROM
    ERR --> PROM
    QLT --> PROM
    
    CPU --> PROM
    MEM --> PROM
    DISK --> PROM
    NET --> PROM
    
    USERS --> PROM
    FILES --> PROM
    SEARCH --> PROM
    CONV --> PROM
    
    PROM --> GRAF
    PROM --> ALERT
    PROM --> LOGS
```

## 🚀 **Despliegue y Escalabilidad**

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Nginx/HAProxy]
    end
    
    subgraph "Application Tier"
        APP1[App Instance 1]
        APP2[App Instance 2]
        APP3[App Instance N]
    end
    
    subgraph "Service Tier"
        N8N1[n8n Instance 1]
        N8N2[n8n Instance 2]
        INGEST1[Ingestor 1]
        INGEST2[Ingestor 2]
    end
    
    subgraph "Data Tier"
        PG1[(PostgreSQL Primary)]
        PG2[(PostgreSQL Replica)]
        REDIS1[(Redis Master)]
        REDIS2[(Redis Slave)]
    end
    
    LB --> APP1
    LB --> APP2
    LB --> APP3
    
    APP1 --> N8N1
    APP1 --> INGEST1
    APP2 --> N8N2
    APP2 --> INGEST2
    
    N8N1 --> PG1
    N8N2 --> PG2
    INGEST1 --> PG1
    INGEST2 --> PG2
    
    PG1 --> PG2
    REDIS1 --> REDIS2
```

## 🔧 **Componentes por Capa**

### **Frontend Layer**
- **App Pulpo**: Interfaz de usuario principal
- **Responsabilidades**: UI/UX, autenticación, gestión de archivos

### **API Gateway Layer**
- **Load Balancer**: Distribución de carga
- **Responsabilidades**: Routing, rate limiting, SSL termination

### **Service Layer**
- **n8n Workflow**: Orquestación de conversaciones
- **File Ingestor**: Procesamiento de archivos multitenant
- **Worker RAG**: Búsqueda semántica

### **Processing Layer**
- **Tika Server**: Extracción de texto
- **Ollama**: LLM y embeddings
- **Quality Processor**: Control de calidad

### **Data Layer**
- **PostgreSQL**: Base de datos principal con RLS
- **Redis**: Cache y sesiones

### **Storage Layer**
- **File Storage**: Archivos subidos
- **Backups**: Respaldo de datos

## 📈 **Métricas de Rendimiento**

| Componente | QPS | Latencia | Disponibilidad |
|------------|-----|----------|----------------|
| **n8n Workflow** | 100 | 2s | 99.9% |
| **File Ingestor** | 50 | 5s | 99.5% |
| **Worker RAG** | 200 | 500ms | 99.9% |
| **PostgreSQL** | 1000 | 10ms | 99.99% |
| **Redis** | 10000 | 1ms | 99.99% |

## 🎯 **Puntos de Integración**

1. **App Pulpo ↔ n8n**: Webhooks para conversación
2. **App Pulpo ↔ File Ingestor**: API REST para archivos
3. **n8n ↔ Worker RAG**: Búsqueda semántica
4. **File Ingestor ↔ Worker RAG**: Sincronización de datos
5. **Todos ↔ PostgreSQL**: Persistencia de datos
6. **Todos ↔ Redis**: Cache compartido

---

**Nota**: Este diagrama representa la arquitectura actual del sistema PulpoAI v2.0, mostrando las interacciones entre componentes y los flujos de datos principales.


