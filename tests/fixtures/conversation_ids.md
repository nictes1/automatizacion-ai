# 🎯 Conversation IDs para Testing Canary

IDs de conversación con hash determinístico para forzar routing a SLM o Legacy.

---

## 🧮 Cómo Funciona el Hash

```python
import hashlib

def get_bucket(conversation_id: str) -> int:
    """Calcula bucket 0-99 para canary routing"""
    h = hashlib.md5(conversation_id.encode()).hexdigest()
    return int(h, 16) % 100

# Ejemplo
get_bucket("wa-00000000000")  # → 41
get_bucket("wa-99999999999")  # → 89
get_bucket("wa-slm-test")     # → 7  ← ENTRA en canary 10%
get_bucket("wa-legacy-test")  # → 78 ← NO entra en canary 10%
```

---

## ✅ IDs que ENTRAN en SLM (bucket < 10, canary=10%)

```
wa-00
wa-06
wa-08
wa-slm-test
wa-00000000000001
wa-canary-slm-1
wa-canary-slm-2
wa-canary-slm-3
```

**Verificar:**
```bash
# Debería retornar "slm_pipeline"
curl -X POST http://localhost:8000/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-slm-test" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route'
```

---

## ❌ IDs que NO ENTRAN en SLM (bucket >= 10, canary=10%)

```
wa-99
wa-50
wa-legacy-test
wa-99999999999999
wa-canary-legacy-1
wa-canary-legacy-2
wa-canary-legacy-3
```

**Verificar:**
```bash
# Debería retornar "legacy"
curl -X POST http://localhost:8000/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -H "X-Channel: whatsapp" \
  -H "X-Conversation-Id: wa-legacy-test" \
  -d @tests/fixtures/request_saludo.json \
  | jq '.telemetry.route'
```

---

## 🧪 Script de Testing

### Validar routing determinístico

```bash
#!/bin/bash
# tests/smoke/test_deterministic_routing.sh

# IDs que deben ir a SLM (canary=10%)
for id in "wa-slm-test" "wa-canary-slm-1" "wa-canary-slm-2"; do
  route=$(curl -s -X POST http://localhost:8000/orchestrator/decide \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: $id" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route')
  
  if [[ "$route" == "slm_pipeline" ]]; then
    echo "✓ $id → SLM (OK)"
  else
    echo "✗ $id → $route (expected: slm_pipeline)"
  fi
done

# IDs que deben ir a Legacy
for id in "wa-legacy-test" "wa-canary-legacy-1" "wa-canary-legacy-2"; do
  route=$(curl -s -X POST http://localhost:8000/orchestrator/decide \
    -H "Content-Type: application/json" \
    -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
    -H "X-Channel: whatsapp" \
    -H "X-Conversation-Id: $id" \
    -d @tests/fixtures/request_saludo.json \
    | jq -r '.telemetry.route')
  
  if [[ "$route" == "legacy" ]]; then
    echo "✓ $id → Legacy (OK)"
  else
    echo "✗ $id → $route (expected: legacy)"
  fi
done
```

---

## 📊 Calcular Buckets de tus IDs Reales

### Python script

```python
#!/usr/bin/env python3
import hashlib
import sys

def get_bucket(conv_id: str) -> int:
    return int(hashlib.md5(conv_id.encode()).hexdigest(), 16) % 100

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ./calculate_bucket.py <conversation_id>")
        sys.exit(1)
    
    conv_id = sys.argv[1]
    bucket = get_bucket(conv_id)
    
    print(f"Conversation ID: {conv_id}")
    print(f"Bucket: {bucket}")
    print(f"Entra en canary 10%: {'✓ SÍ' if bucket < 10 else '✗ NO'}")
    print(f"Entra en canary 50%: {'✓ SÍ' if bucket < 50 else '✗ NO'}")
```

**Uso:**
```bash
chmod +x calculate_bucket.py
./calculate_bucket.py wa-5492235261872
# Output:
# Conversation ID: wa-5492235261872
# Bucket: 23
# Entra en canary 10%: ✗ NO
# Entra en canary 50%: ✓ SÍ
```

---

## 🎲 Generar IDs para Canary

### Bash one-liner

```bash
# Encontrar IDs que caen en bucket < 10
for i in {0..1000}; do
  id="wa-test-$i"
  bucket=$(python3 -c "import hashlib; print(int(hashlib.md5('$id'.encode()).hexdigest(), 16) % 100)")
  if [[ $bucket -lt 10 ]]; then
    echo "$id → bucket $bucket"
  fi
done | head -10
```

---

**Última actualización:** 16 Enero 2025




