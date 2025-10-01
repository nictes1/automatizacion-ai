# Ejemplo de Uso - Ingestion Service

## 🔐 Autenticación y Headers

Todos los endpoints ahora requieren el header `X-Workspace-Id` para seguridad multitenant:

```bash
# Header obligatorio para todos los endpoints
X-Workspace-Id: tu-workspace-uuid
```

## 📤 Upload de Archivo

```bash
curl -X POST "http://localhost:8007/files" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000" \
  -F "file=@menu_restaurante.pdf"
```

**Response:**
```json
{
  "file_id": "456e7890-e89b-12d3-a456-426614174001",
  "filename": "menu_restaurante.pdf",
  "status": "uploaded",
  "message": "Archivo subido exitosamente, procesamiento iniciado"
}
```

## 📋 Listar Archivos

```bash
curl -X GET "http://localhost:8007/files?limit=10&offset=0" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000"
```

**Response:**
```json
[
  {
    "file_id": "456e7890-e89b-12d3-a456-426614174001",
    "filename": "menu_restaurante.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 2048576,
    "status": "processed",
    "created_at": "2024-01-15T10:30:00Z",
    "processed_at": "2024-01-15T10:31:30Z",
    "error_message": null
  }
]
```

## 🔍 Obtener Info de Archivo

```bash
curl -X GET "http://localhost:8007/files/456e7890-e89b-12d3-a456-426614174001" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000"
```

## 🔄 Re-procesar Archivo

```bash
curl -X POST "http://localhost:8007/files/456e7890-e89b-12d3-a456-426614174001/reingest" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000"
```

## 🗑️ Eliminar Archivo (Purga Completa)

```bash
curl -X DELETE "http://localhost:8007/files/456e7890-e89b-12d3-a456-426614174001" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000"
```

**Response:**
```json
{
  "message": "Archivo y datos asociados eliminados exitosamente"
}
```

## 🧪 Test Endpoint

```bash
curl -X POST "http://localhost:8007/files/test"
```

**Response:**
```json
{
  "test": "success",
  "file_id": "789e0123-e89b-12d3-a456-426614174002",
  "filename": "test_menu.txt",
  "status": "uploaded"
}
```

## 🔧 Ejemplo con Python

```python
import httpx
import asyncio

async def upload_file_example():
    workspace_id = "123e4567-e89b-12d3-a456-426614174000"
    
    async with httpx.AsyncClient() as client:
        # Upload archivo
        with open("menu.pdf", "rb") as f:
            response = await client.post(
                "http://localhost:8007/files",
                headers={"X-Workspace-Id": workspace_id},
                files={"file": ("menu.pdf", f, "application/pdf")}
            )
        
        file_data = response.json()
        file_id = file_data["file_id"]
        print(f"Archivo subido: {file_id}")
        
        # Verificar estado
        response = await client.get(
            f"http://localhost:8007/files/{file_id}",
            headers={"X-Workspace-Id": workspace_id}
        )
        
        file_info = response.json()
        print(f"Estado: {file_info['status']}")

# Ejecutar
asyncio.run(upload_file_example())
```

## 🚨 Errores Comunes

### 1. Header Faltante
```bash
curl -X POST "http://localhost:8007/files" -F "file=@test.pdf"
# Error: 422 Unprocessable Entity
# "X-Workspace-Id header is required"
```

### 2. Workspace No Válido
```bash
curl -X GET "http://localhost:8007/files" \
  -H "X-Workspace-Id: invalid-uuid"
# Error: 422 Unprocessable Entity
# "Invalid workspace ID format. Must be a valid UUID v4"
```

### 3. Archivo Demasiado Grande
```bash
curl -X POST "http://localhost:8007/files" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000" \
  -F "file=@huge_file.pdf"
# Error: 413 Payload Too Large
# "Archivo demasiado grande. Máximo permitido: 10485760 bytes"
```

### 4. Tipo MIME No Permitido
```bash
curl -X POST "http://localhost:8007/files" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000" \
  -F "file=@malicious.exe"
# Error: 415 Unsupported Media Type
# "Tipo MIME no permitido: application/x-msdownload. Tipos permitidos: application/pdf, text/plain, ..."
```

### 5. Archivo No Encontrado
```bash
curl -X GET "http://localhost:8007/files/nonexistent-id" \
  -H "X-Workspace-Id: 123e4567-e89b-12d3-a456-426614174000"
# Error: 404 Not Found
# "Archivo no encontrado"
```

## 📊 Estados de Archivo

- `uploaded`: Archivo subido, procesamiento pendiente
- `duplicate`: Archivo duplicado, reutilizando existente
- `processing`: Procesamiento en curso
- `processed`: Procesamiento completado exitosamente
- `failed`: Error en el procesamiento

## 🔒 Seguridad

- **Multitenant**: Cada workspace está completamente aislado
- **Headers obligatorios**: No se puede manipular workspace desde el body
- **Validación UUID v4**: Formato estricto para workspace_id
- **Límites de tamaño**: Máximo 10MB por archivo (configurable)
- **Allow-list MIME**: Solo tipos de archivo permitidos
- **RLS automático**: Todas las queries incluyen contexto de workspace
- **Purga completa**: DELETE elimina todos los datos asociados
- **Limpieza automática**: Archivos duplicados se eliminan del disco

## 🚀 Performance

- **Streaming real**: Archivos se procesan por chunks de 1MB
- **Embeddings en lotes**: 16 chunks por lote para mejor performance
- **DB no bloqueante**: Operaciones de base de datos en threads separados
- **Deduplicación**: Archivos duplicados se reutilizan automáticamente
