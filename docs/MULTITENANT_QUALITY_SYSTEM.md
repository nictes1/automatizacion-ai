# 🏢 Sistema Multitenant con Control de Calidad

## 📋 Resumen

Hemos implementado un sistema robusto de ingesta de archivos con:
- ✅ **Autenticación JWT multitenant**
- ✅ **Control de calidad estricto**
- ✅ **Detección de idioma profesional**
- ✅ **Procesador híbrido inteligente**
- ✅ **Límites configurables por workspace**

## 🔐 **Autenticación Multitenant**

### **Cómo Funciona:**

1. **Token JWT**: Cada request debe incluir un token JWT válido
2. **Workspace Isolation**: Cada token está asociado a un workspace específico
3. **Permisos Granulares**: Control de acceso por funcionalidad
4. **RLS en Base de Datos**: Aislamiento automático por workspace

### **Estructura del Token:**
```json
{
  "user_id": "user_001",
  "workspace_id": "00000000-0000-0000-0000-000000000001",
  "permissions": ["file:ingest", "workspace:read", "workspace:admin"],
  "iat": 1640995200,
  "exp": 1641081600
}
```

### **Permisos Disponibles:**
- `file:ingest` - Subir y procesar archivos
- `file:delete` - Eliminar archivos
- `workspace:read` - Leer datos del workspace
- `workspace:admin` - Administrar workspace

## 🎯 **Control de Calidad Estricto**

### **Límites Configurables:**

| Límite | Valor por Defecto | Descripción |
|--------|-------------------|-------------|
| **Tamaño de archivo** | 50 MB | Máximo tamaño por archivo |
| **Páginas PDF** | 100 páginas | Máximo páginas en PDF |
| **Duración audio** | 30 minutos | Máximo duración de audio |
| **Duración video** | 60 minutos | Máximo duración de video |
| **Texto mínimo** | 50 caracteres | Mínimo texto extraído |
| **Texto máximo** | 1M caracteres | Máximo texto extraído |
| **Confianza mínima** | 0.7 | Mínima confianza de calidad |

### **Validaciones de Calidad:**

1. **Validación de Archivo:**
   - ✅ Tamaño dentro de límites
   - ✅ Tipo de archivo soportado
   - ✅ Estructura válida

2. **Validación de Extracción:**
   - ✅ Texto extraído suficiente
   - ✅ Proporción de caracteres alfabéticos
   - ✅ Detección de idioma confiable

3. **Métricas de Calidad:**
   - 📊 Score de confianza (0-1)
   - 🌍 Idioma detectado
   - ⏱️ Tiempo de procesamiento
   - 🔧 Procesador utilizado

## 🌍 **Detección de Idioma Profesional**

### **Métodos Utilizados:**

1. **LangDetect**: Para textos largos (más preciso)
2. **FastText**: Para textos cortos (más rápido)
3. **Análisis de Palabras**: Fallback confiable

### **Idiomas Soportados:**
- 🇪🇸 Español (es)
- 🇺🇸 Inglés (en)
- 🇫🇷 Francés (fr)
- 🇵🇹 Portugués (pt)
- 🇩🇪 Alemán (de)
- 🇮🇹 Italiano (it)
- 🇷🇺 Ruso (ru)
- 🇨🇳 Chino (zh)
- 🇯🇵 Japonés (ja)
- 🇰🇷 Coreano (ko)

## 🔧 **Procesador Híbrido Inteligente**

### **Selección Automática por Tipo:**

| Tipo de Archivo | Procesador | Razón |
|-----------------|------------|-------|
| **PDFs con tablas** | pdfplumber | Excelente para tablas |
| **PDFs científicos** | Unstructured | Preserva estructura |
| **PDFs simples** | PyMuPDF | Muy rápido |
| **Documentos Office** | Tika | Amplio soporte |
| **Imágenes** | Tika + OCR | OCR integrado |
| **Audio** | Whisper | Transcripción precisa |
| **Video** | FFmpeg + Whisper | Extrae audio y transcribe |

### **Fallback Inteligente:**
Si el procesador principal falla, automáticamente usa Tika como respaldo.

## 🚀 **API Multitenant**

### **Endpoints Principales:**

#### **1. Ingesta de Archivos**
```bash
POST /ingest
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "file_path": "/path/to/file.pdf",
  "title": "Documento de prueba",
  "language": "es",
  "quality_threshold": 0.8
}
```

#### **2. Subida Directa**
```bash
POST /ingest/upload
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data

file: <archivo>
title: "Documento de prueba"
quality_threshold: 0.8
```

#### **3. Estadísticas del Workspace**
```bash
GET /workspace/stats
Authorization: Bearer <jwt_token>
```

#### **4. Listar Archivos**
```bash
GET /workspace/files?limit=50&offset=0
Authorization: Bearer <jwt_token>
```

#### **5. Eliminar Archivo**
```bash
DELETE /workspace/files/{file_id}
Authorization: Bearer <jwt_token>
```

#### **6. Configurar Límites (Admin)**
```bash
POST /workspace/quality/limits
Authorization: Bearer <jwt_token>

{
  "max_file_size_mb": 100,
  "max_pages_pdf": 200,
  "min_confidence": 0.8
}
```

## 🔧 **Configuración**

### **Variables de Entorno:**
```bash
# Base de datos
DATABASE_URL=postgresql://user:pass@host:5432/db

# Servicios
TIKA_URL=http://localhost:9998
OLLAMA_URL=http://localhost:11434

# Autenticación
JWT_SECRET=your-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Servidor
SERVER_ADDR=:8080
```

### **Generar Tokens de Prueba:**
```bash
python scripts/generate_jwt_token.py
```

## 🧪 **Pruebas del Sistema**

### **1. Verificar Salud del Servicio:**
```bash
curl http://localhost:8080/health
```

### **2. Generar Token:**
```bash
python scripts/generate_jwt_token.py
```

### **3. Probar Ingesta:**
```bash
# Con archivo local
curl -X POST http://localhost:8080/ingest \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "/path/to/document.pdf",
    "title": "Documento de prueba",
    "quality_threshold": 0.8
  }'

# Con archivo subido
curl -X POST http://localhost:8080/ingest/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf" \
  -F "title=Documento de prueba" \
  -F "quality_threshold=0.8"
```

### **4. Verificar Estadísticas:**
```bash
curl -H "Authorization: Bearer <token>" \
  http://localhost:8080/workspace/stats
```

## 📊 **Métricas de Calidad**

### **Estadísticas Disponibles:**
```json
{
  "total_processed": 150,
  "high_quality": 120,
  "medium_quality": 25,
  "low_quality": 3,
  "failed": 2,
  "high_quality_rate": 0.80,
  "medium_quality_rate": 0.17,
  "low_quality_rate": 0.02,
  "failure_rate": 0.01
}
```

### **Métricas por Archivo:**
```json
{
  "confidence_score": 0.95,
  "language": "es",
  "language_confidence": 0.98,
  "processor_used": "pdfplumber",
  "is_high_quality": true,
  "quality_issues": [],
  "extraction_time": 2.5
}
```

## 🚨 **Manejo de Errores**

### **Errores Comunes:**

1. **401 Unauthorized**: Token inválido o expirado
2. **403 Forbidden**: Permisos insuficientes
3. **400 Bad Request**: Archivo no cumple límites de calidad
4. **404 Not Found**: Archivo o workspace no encontrado
5. **500 Internal Server Error**: Error del servidor

### **Logs Detallados:**
```bash
# Ver logs del servicio
tail -f logs/multitenant_ingestor.log

# Ver logs de calidad
grep "quality" logs/multitenant_ingestor.log
```

## 🔮 **Próximas Mejoras**

1. **Dashboard de Calidad**: Interfaz web para monitoreo
2. **Alertas Automáticas**: Notificaciones por calidad baja
3. **A/B Testing**: Comparar procesadores automáticamente
4. **Machine Learning**: Mejorar detección de calidad
5. **Integración con n8n**: Workflow automatizado

## 🎯 **Ventajas del Sistema**

### **vs. Sistema Anterior:**

| Aspecto | Anterior | Nuevo |
|---------|----------|-------|
| **Autenticación** | ❌ Sin autenticación | ✅ JWT multitenant |
| **Idioma** | ❌ Detección básica | ✅ Detección profesional |
| **Procesamiento** | ❌ Solo Tika | ✅ Híbrido inteligente |
| **Límites** | ❌ Sin límites | ✅ Límites configurables |
| **Aislamiento** | ❌ Básico | ✅ RLS estricto |

### **Beneficios Clave:**

1. **🔒 Seguridad**: Aislamiento completo por workspace
2. **🎯 Calidad**: Control estricto de calidad de extracción
3. **🌍 Multilingüe**: Detección profesional de idiomas
4. **⚡ Eficiencia**: Procesador híbrido optimizado
5. **📊 Monitoreo**: Métricas detalladas de calidad
6. **🔧 Configurabilidad**: Límites ajustables por workspace

---

**Conclusión**: El sistema ahora garantiza que "si entra calidad, sale calidad" en cada paso del proceso, con autenticación robusta y control granular por workspace.

**Fecha**: Enero 2025  
**Versión**: 2.0  
**Estado**: ✅ Implementado  
**Próximo**: Integración con n8n y pruebas en producción
