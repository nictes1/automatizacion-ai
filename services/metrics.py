"""
Métricas Prometheus para RAG Service
Métricas de latencia, errores, cache y requests por workspace
"""
from prometheus_client import Counter, Histogram, Gauge

# Contadores de requests
rag_requests = Counter(
    "rag_requests_total",
    "Total de requests al RAG",
    ["endpoint", "workspace", "status"]
)

# Contadores de errores
rag_errors = Counter(
    "rag_errors_total",
    "Total de errores en RAG",
    ["endpoint", "workspace"]
)

# Histograma de latencia
rag_latency = Histogram(
    "rag_request_latency_seconds",
    "Latencia de requests al RAG",
    ["endpoint", "workspace"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1, 2, 5)
)

# Métricas de cache de embeddings
emb_cache_hits = Counter(
    "rag_embeddings_cache_hits_total", 
    "Embeddings cache hits", 
    ["workspace"]
)

emb_cache_miss = Counter(
    "rag_embeddings_cache_miss_total", 
    "Embeddings cache misses", 
    ["workspace"]
)

# Métricas de documentos
documents_total = Gauge(
    "rag_documents_total",
    "Total de documentos por workspace",
    ["workspace", "status"]  # status: active, deleted, needs_ocr
)

chunks_total = Gauge(
    "rag_chunks_total",
    "Total de chunks por workspace",
    ["workspace", "status"]  # status: active, deleted
)

# Métricas de OCR
ocr_jobs_total = Counter(
    "rag_ocr_jobs_total",
    "Total de jobs de OCR",
    ["workspace", "status"]  # status: pending, processing, completed, failed
)

ocr_processing_time = Histogram(
    "rag_ocr_processing_seconds",
    "Tiempo de procesamiento OCR",
    ["workspace"],
    buckets=(1, 5, 10, 30, 60, 120, 300)
)

# Métricas de versionado
document_versions_total = Gauge(
    "rag_document_versions_total",
    "Total de versiones por documento",
    ["workspace"]
)

# Métricas de purga
purge_operations_total = Counter(
    "rag_purge_operations_total",
    "Total de operaciones de purga",
    ["workspace"]
)

purged_documents_total = Counter(
    "rag_purged_documents_total",
    "Total de documentos purgados",
    ["workspace"]
)

# Métricas de jobs (Sprint 3)
jobs_running = Gauge(
    "rag_jobs_running",
    "Cantidad de jobs en ejecución",
    ["job_type"]
)

job_retries_total = Counter(
    "rag_job_retries_total",
    "Reintentos realizados por job_type",
    ["job_type"]
)

dlq_total = Gauge(
    "rag_dlq_total",
    "Jobs en DLQ por job_type",
    ["job_type"]
)

job_duration_seconds = Histogram(
    "rag_job_duration_seconds",
    "Duración de ejecución de jobs",
    ["job_type", "status"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600)
)

jobs_processed_total = Counter(
    "rag_jobs_processed_total",
    "Total de jobs procesados",
    ["job_type", "status"]
)
