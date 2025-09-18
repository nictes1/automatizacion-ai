# Pulpo – Infraestructura Local (Dev)

Este README documenta cómo levantar la infraestructura completa de **Pulpo** en tu PC servidor (gabinete) usando **Docker Compose**.

---

## 1. Requisitos

- **Ubuntu 22.04+**
- **Docker + Docker Compose**
- **NVIDIA Drivers + CUDA** instalados
- **NVIDIA Container Toolkit** configurado:

```bash
sudo apt install -y nvidia-container-toolkit
sudo systemctl restart docker
docker info | grep -i nvidia   # debe mostrar "Default Runtime: nvidia"
```

---

## 2. Estructura de carpetas

```
pulpo/
 ├── docker-compose.yml
 ├── scripts/
 │   ├── up.sh
 │   ├── verify.sh
 │   ├── check_gpu.sh
 │   └── down.sh
 └── sql/
     ├── 01_core_up.sql
     ├── 02_seed_dev.sql
     └── 03_fn_persist_inbound.sql
```

---

## 3. Levantar servicios

```bash
cd ~/workspace/nictes1/pulpo

# Resetear todo
docker compose down -v

# Levantar stack completo
docker compose up -d

# Ver estado
docker compose ps
```

Deberías ver: `db (healthy)`, `redis`, `ollama`, `n8n`.

---

## 4. Inicializar Base de Datos

### 4.1 Crear schema y extensiones
```bash
docker compose exec -T db psql -U pulpo -d pulpo -f /docker-entrypoint-initdb.d/01_core_up.sql
```

### 4.2 Cargar seed de desarrollo
```bash
cat sql/02_seed_dev.sql | docker compose exec -T db psql -U pulpo -d pulpo
```

### 4.3 Instalar funciones extra
```bash
docker compose exec -T db psql -U pulpo -d pulpo -f /docker-entrypoint-initdb.d/03_fn_persist_inbound.sql
```

### 4.4 Verificar
```bash
docker compose exec db psql -U pulpo -d pulpo -c "\dx"         # extensiones
docker compose exec db psql -U pulpo -d pulpo -c "\dt pulpo.*" # tablas
docker compose exec db psql -U pulpo -d pulpo -c "SELECT count(*) FROM pulpo.messages;"
```

---

## 5. Verificar servicios

### 5.1 n8n
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.100.4:5678
# debe devolver 200
```

### 5.2 Ollama
```bash
curl -s http://192.168.100.4:11434/api/tags
```

Si no hay modelos, descargarlos:
```bash
docker compose exec ollama ollama pull llama3.1:8b
docker compose exec ollama ollama pull qwen2.5:7b-instruct
docker compose exec ollama ollama pull nomic-embed-text
```

Verificar:
```bash
docker compose exec ollama ollama list
```

### 5.3 Probar generación
```bash
printf "Hola, ¿quién sos?" | docker compose exec -T ollama ollama run llama3.1:8b
```

### 5.4 Probar embeddings
```bash
curl -s http://192.168.100.4:11434/api/embeddings   -d '{"model":"nomic-embed-text","input":"hola mundo"}'
```

---

## 6. Monitoreo GPU

- Ver procesos en GPU:
  ```bash
  nvidia-smi
  ```

- Monitoreo en vivo:
  ```bash
  watch -n 2 nvidia-smi
  ```

Si Ollama está usando la GPU, vas a ver sus procesos consumiendo VRAM.

---

## 7. Scripts Automáticos

### 7.1 Levantar e inicializar
```bash
chmod +x scripts/up.sh
SERVER_IP=192.168.100.4 ./scripts/up.sh
```

### 7.2 Verificación completa
```bash
SERVER_IP=192.168.100.4 ./scripts/verify.sh
```

### 7.3 Chequear GPU
```bash
./scripts/check_gpu.sh
```

### 7.4 Bajar todo
```bash
./scripts/down.sh
```

---

