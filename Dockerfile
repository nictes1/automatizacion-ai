# Dockerfile para PulpoAI - Sistema de Agentes Conversacionales
FROM python:3.11-slim

# Metadatos
LABEL maintainer="PulpoAI Team <team@pulpo.ai>"
LABEL description="PulpoAI - Sistema de agentes conversacionales inteligentes"
LABEL version="1.0.0"

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Crear usuario no-root
RUN groupadd -r pulpo && useradd -r -g pulpo pulpo

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt pyproject.toml ./

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorios necesarios
RUN mkdir -p /app/logs /app/data /app/cache

# Cambiar ownership a usuario pulpo
RUN chown -R pulpo:pulpo /app

# Cambiar a usuario no-root
USER pulpo

# Exponer puerto
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/metrics/health || exit 1

# Comando por defecto
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
