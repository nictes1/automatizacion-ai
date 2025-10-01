# 🔧 Corrección del Nodo Intent Router

## 🐛 Problema Identificado

El nodo "Intent Router" en el workflow `n8n-flow-improved.json` estaba definido con un tipo de nodo que no existe en n8n:

```json
{
  "type": "n8n-nodes-base.openAi",  // ❌ Este tipo no existe
  "typeVersion": 1.3,
  "id": "intent-router",
  "name": "Intent Router"
}
```

Esto causaba que n8n mostrara el error: **"Install this node to use it"** y **"This node is not currently installed"**.

## 🔍 Análisis del Problema

### Causa Raíz
- El tipo `"n8n-nodes-base.openAi"` no es un nodo nativo de n8n
- En el workflow original se usa `"n8n-nodes-base.httpRequest"` para comunicarse con Ollama
- Los nodos LLM en n8n se implementan como HTTP requests a servicios externos

### Comparación con Workflow Original
En el workflow original (`n8n-flow.json`), el nodo LLM está definido como:

```json
{
  "parameters": {
    "method": "POST",
    "url": "http://ollama:11434/api/chat",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "{ ... }"
  },
  "type": "n8n-nodes-base.httpRequest",  // ✅ Tipo correcto
  "typeVersion": 4.2,
  "name": "LLM — Intent"
}
```

## ✅ Solución Implementada

### 1. Corrección del Nodo Intent Router
Se cambió de `openAi` a `httpRequest` con configuración para Ollama:

```json
{
  "parameters": {
    "method": "POST",
    "url": "http://ollama:11434/api/chat",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "{\n  \"model\": \"qwen2.5\",\n  \"format\": \"json\",\n  \"options\": { \"temperature\": 0.1 },\n  \"messages\": [\n    {\n      \"role\": \"system\",\n      \"content\": \"Eres un clasificador de intenciones...\"\n    },\n    {\n      \"role\": \"user\",\n      \"content\": \"{{ $json.user_text }}\"\n    }\n  ]\n}",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",  // ✅ Tipo corregido
  "typeVersion": 4.2,
  "id": "intent-router",
  "name": "Intent Router"
}
```

### 2. Corrección del Nodo Parse Intent
Se actualizó el código JavaScript para manejar la respuesta de Ollama:

```javascript
// Antes (OpenAI)
const routerResponse = $input.first().json.choices[0].message.content;

// Después (Ollama)
const routerResponse = $input.first().json.message?.content || $input.first().json.content || '{}';
```

### 3. Corrección del Nodo Generate Response
También se corrigió el nodo "Generate Response" que tenía el mismo problema:

```json
{
  "parameters": {
    "method": "POST",
    "url": "http://ollama:11434/api/chat",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "{\n  \"model\": \"qwen2.5\",\n  \"options\": { \"temperature\": 0.3 },\n  \"messages\": [ ... ]\n}",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",  // ✅ Corregido
  "typeVersion": 4.2,
  "id": "generate-response",
  "name": "Generate Response"
}
```

### 4. Corrección del Nodo Prepare Response
Se actualizó para manejar la respuesta de Ollama:

```javascript
// Antes
"value": "={{ $json.choices[0].message.content }}"

// Después
"value": "={{ $json.message?.content || $json.content || 'Error generando respuesta' }}"
```

## 🧪 Validación

### JSON Válido
```bash
python3 -m json.tool n8n-flow-improved.json
# ✅ JSON válido
```

### Conexiones Válidas
```bash
python3 scripts/validate-workflow-connections.py
# 🎉 ¡Todas las conexiones son válidas!
# ✅ El workflow está listo para importar en n8n
```

### Resultado de Validación
```
📊 Total de nodos encontrados: 28
🔗 Total de conexiones definidas: 26
✅ intent-router -> parse-intent
✅ generate-response -> prepare-response
🎉 ¡Todas las conexiones son válidas!
```

## 🔄 Cambios Realizados

| Nodo | Tipo Anterior | Tipo Corregido | Estado |
|------|---------------|----------------|---------|
| Intent Router | `n8n-nodes-base.openAi` | `n8n-nodes-base.httpRequest` | ✅ |
| Generate Response | `n8n-nodes-base.openAi` | `n8n-nodes-base.httpRequest` | ✅ |
| Parse Intent | Código OpenAI | Código Ollama | ✅ |
| Prepare Response | Código OpenAI | Código Ollama | ✅ |

## 🚀 Configuración de Ollama

El workflow ahora usa Ollama con el modelo `qwen2.5` para:

1. **Clasificación de intenciones** (Intent Router)
2. **Generación de respuestas** (Generate Response)

### Requisitos
- Ollama corriendo en `http://ollama:11434`
- Modelo `qwen2.5` descargado en Ollama
- Formato JSON habilitado para respuestas estructuradas

## 📋 Próximos Pasos

1. **Importar workflow**: El archivo está listo para importar en n8n
2. **Verificar Ollama**: Asegurar que Ollama esté corriendo y el modelo disponible
3. **Probar flujo**: Enviar mensajes de prueba
4. **Monitorear logs**: Revisar respuestas de Ollama

## 🔧 Comandos de Verificación

```bash
# Verificar que Ollama esté corriendo
curl http://localhost:11434/api/tags

# Verificar que el modelo esté disponible
curl http://localhost:11434/api/show -d '{"name": "qwen2.5"}'

# Validar workflow
python3 scripts/validate-workflow-connections.py
```

---

**Fecha**: Enero 2025  
**Estado**: ✅ Corregido y Validado  
**Problema**: Nodo Intent Router no existía  
**Solución**: Cambio a httpRequest con Ollama


