# 🔄 Flujo de Procesamiento de Archivos para RAG

## 📋 Resumen

Este documento explica cómo el sistema procesa diferentes tipos de archivos para convertirlos en embeddings y hacerlos disponibles para RAG.

## 🎯 **Punto Clave: Los Embeddings Solo Funcionan con Texto**

Los embeddings **solo pueden procesar texto**. No pueden manejar directamente:
- ❌ Imágenes
- ❌ Audio
- ❌ Video
- ❌ Archivos binarios

Por eso, **todo debe convertirse a texto primero**.

## 🔄 Flujo de Procesamiento por Tipo de Archivo

### 1. **📄 Documentos de Texto** (PDF, DOCX, TXT, MD, etc.)

```
Archivo → Tika Server → Texto Extraído → Chunking → Embeddings → Base Vectorial
```

**Ejemplo:**
- **Entrada**: `documento.pdf`
- **Tika Server**: Extrae texto del PDF
- **Resultado**: "Este es el contenido del documento..."
- **Chunking**: Divide en pedazos de 1000 tokens
- **Embeddings**: Convierte cada chunk a vector
- **Almacenamiento**: Guarda en PostgreSQL + pgvector

### 2. **🖼️ Imágenes** (PNG, JPG, TIFF, BMP)

```
Imagen → Tika Server + OCR → Texto Extraído → Chunking → Embeddings → Base Vectorial
```

**Ejemplo:**
- **Entrada**: `foto_menu.jpg`
- **Tika Server + OCR**: Extrae texto de la imagen
- **Resultado**: "Pizza Margherita - $15.000\nHamburguesa - $12.000..."
- **Chunking**: Divide en pedazos
- **Embeddings**: Convierte a vectores
- **Almacenamiento**: Guarda en base vectorial

### 3. **🎵 Audio** (MP3, WAV, FLAC, etc.)

```
Audio → Whisper → Transcripción → Chunking → Embeddings → Base Vectorial
```

**Ejemplo:**
- **Entrada**: `reunion.mp3`
- **Whisper**: Transcribe el audio
- **Resultado**: "Hola, bienvenidos a la reunión. Hoy vamos a discutir..."
- **Chunking**: Divide en pedazos
- **Embeddings**: Convierte a vectores
- **Almacenamiento**: Guarda en base vectorial

### 4. **🎥 Video** (MP4, AVI, MOV, etc.)

```
Video → FFmpeg (Extraer Audio) → Whisper → Transcripción → Chunking → Embeddings → Base Vectorial
```

**Ejemplo:**
- **Entrada**: `presentacion.mp4`
- **FFmpeg**: Extrae el audio del video
- **Whisper**: Transcribe el audio extraído
- **Resultado**: "Buenos días, en esta presentación vamos a mostrar..."
- **Chunking**: Divide en pedazos
- **Embeddings**: Convierte a vectores
- **Almacenamiento**: Guarda en base vectorial

## 🛠️ Herramientas Utilizadas

### **Apache Tika Server**
- **Para**: Documentos, imágenes con OCR
- **Función**: Extrae texto de múltiples formatos
- **Ventaja**: Muy robusto, maneja casos edge

### **Whisper (OpenAI)**
- **Para**: Audio y video
- **Función**: Transcripción de audio a texto
- **Ventaja**: Multilingüe, muy preciso

### **FFmpeg**
- **Para**: Video
- **Función**: Extrae audio de video
- **Ventaja**: Soporta muchos formatos

### **Ollama + nomic-embed-text**
- **Para**: Todos los tipos
- **Función**: Genera embeddings del texto
- **Ventaja**: Local, privado, multilingüe

## 📊 Ejemplo Completo: Procesando un Video

```python
# 1. Usuario sube video
video_file = "reunion_equipo.mp4"

# 2. Sistema detecta tipo
extension = ".mp4"  # Es video

# 3. FFmpeg extrae audio
audio_file = ffmpeg_extract_audio(video_file)
# Resultado: "reunion_equipo.wav"

# 4. Whisper transcribe
text = whisper.transcribe(audio_file, language="es")
# Resultado: "Hola equipo, hoy vamos a revisar los objetivos del trimestre..."

# 5. Chunking
chunks = chunk_text(text, size=1000, overlap=200)
# Resultado: [
#   "Hola equipo, hoy vamos a revisar los objetivos del trimestre...",
#   "Los objetivos del trimestre incluyen aumentar las ventas...",
#   ...
# ]

# 6. Embeddings
embeddings = ollama.generate_embeddings(chunks)
# Resultado: [
#   [0.1, 0.2, 0.3, ...],  # Vector para chunk 1
#   [0.4, 0.5, 0.6, ...],  # Vector para chunk 2
#   ...
# ]

# 7. Almacenamiento
save_to_database(video_file, text, chunks, embeddings)
```

## 🔍 Búsqueda RAG

Una vez procesados, todos los archivos se pueden buscar de la misma manera:

```python
# Usuario hace pregunta
query = "¿Cuáles son los objetivos del trimestre?"

# 1. Generar embedding de la pregunta
query_embedding = ollama.generate_embedding(query)

# 2. Buscar en base vectorial
results = semantic_search(query_embedding, limit=5)

# 3. Retornar contexto relevante
# El sistema puede encontrar:
# - Texto del video de la reunión
# - Documentos PDF con objetivos
# - Imágenes de presentaciones
# - Audio de otras reuniones
```

## 🌍 Soporte Multilingüe

### **Embeddings Multilingües**
- **nomic-embed-text** soporta múltiples idiomas
- Los embeddings funcionan entre idiomas
- Puedes buscar en español y encontrar contenido en inglés

### **Transcripción Multilingüe**
- **Whisper** detecta automáticamente el idioma
- Soporta 99 idiomas
- Muy preciso en español e inglés

### **OCR Multilingüe**
- **Tika** con OCR puede extraer texto en múltiples idiomas
- Funciona bien con documentos en español

## ⚡ Optimizaciones

### **Procesamiento en Lote**
```python
# Procesar múltiples archivos
files = ["doc1.pdf", "audio1.mp3", "video1.mp4"]
for file in files:
    process_file(file)  # Procesamiento paralelo
```

### **Caché de Embeddings**
```python
# Evitar reprocesar archivos idénticos
if file_hash_exists(sha256):
    return existing_embeddings
```

### **Chunking Inteligente**
```python
# Chunking por tipo de contenido
if is_code_file(file):
    chunk_by_functions()  # Por funciones
elif is_document(file):
    chunk_by_paragraphs()  # Por párrafos
elif is_audio(file):
    chunk_by_time()  # Por tiempo
```

## 🚨 Limitaciones y Consideraciones

### **Tamaño de Archivos**
- **Audio**: Máximo 25MB (límite de Whisper)
- **Video**: Depende del audio extraído
- **Documentos**: Sin límite práctico

### **Calidad de Transcripción**
- **Audio claro**: Muy buena calidad
- **Audio con ruido**: Calidad reducida
- **Múltiples hablantes**: Puede confundir

### **Tiempo de Procesamiento**
- **Documentos**: Rápido (segundos)
- **Audio**: Medio (minutos)
- **Video**: Lento (depende de duración)

## 🔮 Próximas Mejoras

1. **Procesamiento de Imágenes Avanzado**
   - Descripción de imágenes con IA
   - Extracción de tablas y gráficos

2. **Procesamiento de Video Mejorado**
   - Extracción de subtítulos
   - Análisis de escenas

3. **Optimizaciones de Rendimiento**
   - Procesamiento en GPU
   - Caché inteligente
   - Compresión de embeddings

---

**Conclusión**: El sistema convierte cualquier tipo de archivo a texto, luego a embeddings, permitiendo búsqueda semántica unificada en todos los contenidos.


