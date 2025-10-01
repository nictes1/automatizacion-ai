# 📁 Tipos de Archivos Soportados para RAG

## 🎯 Objetivo
Definir los tipos de archivos que el sistema puede procesar para generar embeddings y mejorar las respuestas del LLM.

## 📋 Tipos de Archivos Soportados

### 📄 **Documentos de Texto**
| Extensión | Tipo | Descripción | Procesamiento |
|-----------|------|-------------|---------------|
| `.txt` | Texto plano | Documentos de texto simple | Extracción directa |
| `.md` | Markdown | Documentación en Markdown | Parseo de Markdown |
| `.rtf` | Rich Text Format | Texto enriquecido | Conversión a texto |

### 📊 **Documentos de Oficina**
| Extensión | Tipo | Descripción | Procesamiento |
|-----------|------|-------------|---------------|
| `.pdf` | PDF | Documentos PDF | Extracción de texto con PyPDF2/pdfplumber |
| `.docx` | Word | Documentos de Microsoft Word | Extracción con python-docx |
| `.doc` | Word Legacy | Documentos Word antiguos | Conversión con python-docx2txt |
| `.xlsx` | Excel | Hojas de cálculo Excel | Extracción con openpyxl |
| `.xls` | Excel Legacy | Excel antiguo | Conversión con xlrd |
| `.pptx` | PowerPoint | Presentaciones PowerPoint | Extracción con python-pptx |
| `.ppt` | PowerPoint Legacy | PowerPoint antiguo | Conversión con python-pptx |

### 🌐 **Archivos Web**
| Extensión | Tipo | Descripción | Procesamiento |
|-----------|------|-------------|---------------|
| `.html` | HTML | Páginas web | Extracción de texto con BeautifulSoup |
| `.xml` | XML | Documentos XML | Parseo XML |
| `.json` | JSON | Datos JSON | Extracción de texto estructurado |

### 📝 **Archivos de Código**
| Extensión | Tipo | Descripción | Procesamiento |
|-----------|------|-------------|---------------|
| `.py` | Python | Código Python | Extracción con comentarios |
| `.js` | JavaScript | Código JavaScript | Extracción con comentarios |
| `.ts` | TypeScript | Código TypeScript | Extracción con comentarios |
| `.java` | Java | Código Java | Extracción con comentarios |
| `.cpp` | C++ | Código C++ | Extracción con comentarios |
| `.c` | C | Código C | Extracción con comentarios |
| `.sql` | SQL | Consultas SQL | Extracción con comentarios |
| `.yaml` | YAML | Archivos YAML | Parseo YAML |
| `.yml` | YAML | Archivos YAML | Parseo YAML |

### 📋 **Archivos de Configuración**
| Extensión | Tipo | Descripción | Procesamiento |
|-----------|------|-------------|---------------|
| `.ini` | INI | Archivos de configuración | Parseo INI |
| `.cfg` | Config | Archivos de configuración | Extracción de texto |
| `.conf` | Config | Archivos de configuración | Extracción de texto |
| `.env` | Environment | Variables de entorno | Extracción de texto |

## 🚫 Tipos de Archivos NO Soportados

### ❌ **Archivos Binarios**
- Imágenes: `.jpg`, `.png`, `.gif`, `.bmp`, `.svg`
- Videos: `.mp4`, `.avi`, `.mov`, `.mkv`
- Audio: `.mp3`, `.wav`, `.flac`, `.aac`
- Archivos comprimidos: `.zip`, `.rar`, `.7z`, `.tar.gz`
- Ejecutables: `.exe`, `.dll`, `.so`, `.dylib`

### ❌ **Archivos Especializados**
- CAD: `.dwg`, `.dxf`, `.step`
- GIS: `.shp`, `.kml`, `.gpx`
- Bases de datos: `.db`, `.sqlite`, `.mdb`

## 🔧 Procesamiento por Tipo

### 📄 **Texto Simple**
```python
# .txt, .md, .rtf
def process_text_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    return content
```

### 📊 **Documentos de Oficina**
```python
# PDF
def process_pdf(file_path):
    import PyPDF2
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text

# Word
def process_docx(file_path):
    from docx import Document
    doc = Document(file_path)
    text = ""
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text
```

### 🌐 **Archivos Web**
```python
# HTML
def process_html(file_path):
    from bs4 import BeautifulSoup
    with open(file_path, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
        return soup.get_text()
```

## 📏 Límites y Restricciones

### 📊 **Tamaño de Archivo**
- **Máximo**: 50 MB por archivo
- **Recomendado**: < 10 MB para mejor rendimiento
- **Chunking**: Archivos grandes se dividen en chunks de 1000 tokens

### 📝 **Contenido de Texto**
- **Mínimo**: 100 caracteres
- **Máximo**: 1,000,000 caracteres por archivo
- **Encoding**: UTF-8 preferido

### 🔄 **Procesamiento**
- **Timeout**: 30 segundos por archivo
- **Retry**: 3 intentos en caso de error
- **Chunking**: 1000 tokens por chunk para embeddings

## 🎯 Casos de Uso por Vertical

### 🍽️ **Gastronomía**
- Menús en PDF/Word
- Recetas en Markdown
- Políticas de restaurante
- Manuales de procedimientos

### 🛒 **E-commerce**
- Catálogos de productos
- Manuales de usuario
- Políticas de devolución
- Guías de instalación

### 🏠 **Inmobiliaria**
- Fichas de propiedades
- Contratos tipo
- Reglamentos de consorcio
- Manuales de mantenimiento

## 🔧 Configuración del Sistema

### 📁 **Estructura de Directorios**
```
uploads/
├── raw/           # Archivos originales
├── processed/     # Archivos procesados
├── chunks/        # Chunks de texto
└── embeddings/    # Vectores generados
```

### 🗄️ **Base de Datos**
- Tabla `files` para metadatos
- Tabla `file_chunks` para chunks
- Tabla `embeddings` para vectores
- Índices vectoriales para búsqueda

---

**Fecha**: Enero 2025  
**Versión**: 1.0  
**Estado**: ✅ Definido  
**Próximo**: Implementación del sistema


