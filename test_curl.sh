#!/bin/bash

# Test 1: Saludo inicial
echo "=== TEST 1: Saludo inicial ==="
curl -X POST http://localhost:8005/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "x-workspace-id: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "conversation_id": "test-001",
    "vertical": "servicios",
    "user_input": "Hola, ¿qué servicios ofrecen?",
    "greeted": false,
    "slots": {},
    "objective": ""
  }' 2>/dev/null | jq .

echo ""
echo "=== TEST 2: Pregunta por servicios específicos ==="
curl -X POST http://localhost:8005/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "x-workspace-id: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "conversation_id": "test-001",
    "vertical": "servicios",
    "user_input": "¿Cuánto sale un corte de pelo?",
    "greeted": true,
    "slots": {"greeted": true},
    "objective": "consultar_servicios"
  }' 2>/dev/null | jq .

echo ""
echo "=== TEST 3: Consultar disponibilidad ==="
curl -X POST http://localhost:8005/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "x-workspace-id: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "conversation_id": "test-001",
    "vertical": "servicios",
    "user_input": "Quiero un turno para corte mañana",
    "greeted": true,
    "slots": {"greeted": true, "service_type": "Corte"},
    "objective": "agendar_turno"
  }' 2>/dev/null | jq .

echo ""
echo "=== TEST 4: Consultar promociones ==="
curl -X POST http://localhost:8005/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "x-workspace-id: 550e8400-e29b-41d4-a716-446655440000" \
  -d '{
    "conversation_id": "test-001",
    "vertical": "servicios",
    "user_input": "¿Tienen alguna promoción?",
    "greeted": true,
    "slots": {"greeted": true},
    "objective": "consultar_promociones"
  }' 2>/dev/null | jq .
