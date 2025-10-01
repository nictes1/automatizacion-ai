# 🔗 Integración con App Pulpo

## 📋 Resumen

El servicio de ingesta de archivos está diseñado para integrarse perfectamente con la app Pulpo. Los usuarios se autentican en la app principal y luego pueden subir archivos usando su token de sesión.

## 🔄 **Flujo de Integración**

### **1. Usuario se Loguea en App Pulpo**
```
Usuario → App Pulpo → Token JWT
```

### **2. Usuario Sube Archivo**
```
App Pulpo → Servicio Ingesta + Token JWT → Procesamiento
```

### **3. Respuesta a App Pulpo**
```
Servicio Ingesta → App Pulpo → file_id para referencia
```

## 🔐 **Autenticación**

### **Token JWT de Usuario**
La app Pulpo debe enviar el token JWT del usuario logueado en el header `Authorization`:

```http
Authorization: Bearer <jwt_token_del_usuario>
```

### **Estructura del Token**
```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "workspace_id": "00000000-0000-0000-0000-000000000001",
  "iat": 1640995200,
  "exp": 1641081600
}
```

### **Validación del Token**
El servicio:
1. ✅ Decodifica el token JWT
2. ✅ Verifica expiración
3. ✅ Busca el usuario en la base de datos
4. ✅ Verifica acceso al workspace
5. ✅ Obtiene permisos del usuario
6. ✅ Aplica límites del workspace

## 📡 **Endpoints para App Pulpo**

### **1. Subir Archivo (Recomendado)**
```http
POST /ingest/upload
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: <archivo>
title: "Título del documento" (opcional)
language: "es" (opcional)
quality_threshold: 0.8 (opcional)
```

**Respuesta:**
```json
{
  "file_id": "uuid-del-archivo",
  "document_id": "uuid-del-documento",
  "chunks_created": 15,
  "embeddings_generated": 15,
  "processing_time": 3.2,
  "quality_metrics": {
    "confidence_score": 0.95,
    "language": "es",
    "language_confidence": 0.98,
    "processor_used": "pdfplumber",
    "is_high_quality": true,
    "quality_issues": []
  },
  "status": "completed",
  "user_info": {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "user_name": "Juan Pérez",
    "user_email": "juan@empresa.com",
    "workspace_name": "Empresa ABC",
    "workspace_plan": "premium"
  }
}
```

### **2. Obtener Información del Usuario**
```http
GET /user/info
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "user_id": "00000000-0000-0000-0000-000000000001",
  "name": "Juan Pérez",
  "email": "juan@empresa.com",
  "role": "admin",
  "permissions": [
    "file:ingest",
    "file:delete",
    "workspace:read",
    "workspace:admin"
  ],
  "workspace": {
    "id": "00000000-0000-0000-0000-000000000001",
    "name": "Empresa ABC",
    "plan": "premium"
  }
}
```

### **3. Verificar Quota del Usuario**
```http
GET /user/quota
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "can_upload": true,
  "quota_message": "Quota disponible: 850 archivos restantes",
  "workspace_limits": {
    "max_file_size_mb": 200,
    "max_pages_pdf": 500,
    "max_audio_duration_minutes": 120,
    "max_video_duration_minutes": 240,
    "max_files_per_month": 10000,
    "quality_threshold": 0.8
  },
  "user_info": {
    "user_id": "00000000-0000-0000-0000-000000000001",
    "workspace_id": "00000000-0000-0000-0000-000000000001",
    "workspace_plan": "premium"
  }
}
```

### **4. Ver Estadísticas del Workspace**
```http
GET /workspace/stats
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "total_files": 150,
  "total_size": 2500000000,
  "files_by_status": {
    "processed": 140,
    "processing": 5,
    "failed": 5
  },
  "total_documents": 140,
  "total_chunks": 2100,
  "total_embeddings": 2100,
  "quality_stats": {
    "total_processed": 150,
    "high_quality": 120,
    "medium_quality": 25,
    "low_quality": 3,
    "failed": 2,
    "high_quality_rate": 0.80
  }
}
```

### **5. Listar Archivos del Usuario**
```http
GET /workspace/files?limit=50&offset=0
Authorization: Bearer <token>
```

### **6. Eliminar Archivo**
```http
DELETE /workspace/files/{file_id}
Authorization: Bearer <token>
```

## 🎯 **Límites por Plan**

| Plan | Tamaño Archivo | Páginas PDF | Audio | Video | Archivos/Mes | Calidad |
|------|----------------|-------------|-------|-------|--------------|---------|
| **Free** | 10 MB | 50 páginas | 10 min | 15 min | 100 | 0.6 |
| **Basic** | 50 MB | 100 páginas | 30 min | 60 min | 1,000 | 0.7 |
| **Premium** | 200 MB | 500 páginas | 120 min | 240 min | 10,000 | 0.8 |
| **Enterprise** | 1 GB | 2,000 páginas | 480 min | 960 min | 100,000 | 0.9 |

## 🔧 **Implementación en App Pulpo**

### **1. Configuración del Cliente**
```javascript
// Configuración del cliente HTTP
const FILE_INGESTOR_URL = 'http://localhost:8080';

// Función para hacer requests autenticados
async function authenticatedRequest(endpoint, options = {}) {
  const token = localStorage.getItem('userToken'); // Token del usuario logueado
  
  const response = await fetch(`${FILE_INGESTOR_URL}${endpoint}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      ...options.headers
    }
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }
  
  return response.json();
}
```

### **2. Subir Archivo**
```javascript
async function uploadFile(file, title = null, language = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);
  if (language) formData.append('language', language);
  
  try {
    const result = await authenticatedRequest('/ingest/upload', {
      method: 'POST',
      body: formData
    });
    
    console.log('Archivo procesado:', result);
    return result;
  } catch (error) {
    console.error('Error subiendo archivo:', error);
    throw error;
  }
}
```

### **3. Verificar Quota**
```javascript
async function checkUserQuota() {
  try {
    const quota = await authenticatedRequest('/user/quota');
    return quota;
  } catch (error) {
    console.error('Error verificando quota:', error);
    throw error;
  }
}
```

### **4. Obtener Estadísticas**
```javascript
async function getWorkspaceStats() {
  try {
    const stats = await authenticatedRequest('/workspace/stats');
    return stats;
  } catch (error) {
    console.error('Error obteniendo estadísticas:', error);
    throw error;
  }
}
```

## 🚨 **Manejo de Errores**

### **Errores Comunes:**

| Código | Error | Descripción | Solución |
|--------|-------|-------------|----------|
| **401** | Token inválido | Token expirado o malformado | Renovar token |
| **403** | Sin permisos | Usuario sin permisos | Verificar rol |
| **429** | Quota excedida | Límite mensual alcanzado | Esperar o upgrade |
| **400** | Archivo rechazado | No cumple límites de calidad | Verificar archivo |
| **413** | Archivo muy grande | Excede límite de tamaño | Comprimir o dividir |

### **Ejemplo de Manejo:**
```javascript
async function uploadFileWithErrorHandling(file) {
  try {
    const result = await uploadFile(file);
    return result;
  } catch (error) {
    if (error.message.includes('401')) {
      // Token expirado, redirigir a login
      window.location.href = '/login';
    } else if (error.message.includes('429')) {
      // Quota excedida, mostrar mensaje
      alert('Has alcanzado el límite mensual de archivos');
    } else if (error.message.includes('400')) {
      // Archivo rechazado, mostrar detalles
      alert('El archivo no cumple con los requisitos de calidad');
    } else {
      // Error genérico
      alert('Error procesando archivo: ' + error.message);
    }
    throw error;
  }
}
```

## 🧪 **Pruebas**

### **1. Generar Tokens de Prueba**
```bash
python scripts/generate_pulpo_user_tokens.py
```

### **2. Probar Subida de Archivo**
```bash
# Obtener token del script anterior
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."

# Subir archivo
curl -X POST http://localhost:8080/ingest/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@documento.pdf" \
  -F "title=Documento de prueba"
```

### **3. Verificar Quota**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/user/quota
```

## 🔮 **Próximas Mejoras**

1. **Webhook de Notificaciones**: Notificar a la app cuando termine el procesamiento
2. **Progreso en Tiempo Real**: WebSocket para mostrar progreso de procesamiento
3. **Batch Upload**: Subir múltiples archivos en una sola request
4. **Integración con n8n**: Workflow automatizado para procesamiento
5. **Dashboard de Calidad**: Interfaz web para monitorear calidad

## 📞 **Soporte**

Para problemas de integración:
1. Verificar logs del servicio: `tail -f logs/multitenant_ingestor.log`
2. Verificar token JWT: `python scripts/generate_pulpo_user_tokens.py`
3. Verificar salud del servicio: `curl http://localhost:8080/health`

---

**Conclusión**: El servicio está completamente preparado para integrarse con la app Pulpo, usando tokens de usuario existentes y aplicando límites por workspace automáticamente.

**Fecha**: Enero 2025  
**Versión**: 2.0  
**Estado**: ✅ Listo para integración  
**Próximo**: Implementar en app Pulpo


