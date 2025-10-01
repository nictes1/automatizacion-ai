-- sql/10_vertical_packs_seed.sql
-- Datos de ejemplo para Vertical Packs

SET search_path = public, pulpo;

-- Contexto de workspace DEV
SELECT pulpo.set_ws_context('00000000-0000-0000-0000-000000000001');

-- 1. Vertical Pack: GASTRONOMÍA
INSERT INTO pulpo.vertical_packs (
  workspace_id, vertical, role_prompt, intents_json, slots_config, 
  tools_config, policies_config, handoff_rules, rag_sources
) VALUES (
  '00000000-0000-0000-0000-000000000001',
  'gastronomia',
  'Sos un asistente del restaurante "El Local de Prueba". Sé cordial, directo y orientado a cerrar pedidos. Siempre confirma los detalles antes de procesar. Si no sabés algo, ofrecé contactar con el equipo.',
  '{
    "take_order": {
      "description": "Tomar pedido de comida",
      "synonyms": ["pedir", "ordenar", "comprar", "quiero", "necesito"]
    },
    "menu_question": {
      "description": "Pregunta sobre el menú",
      "synonyms": ["menú", "carta", "qué tienen", "platos", "bebidas"]
    },
    "hours_location": {
      "description": "Consultar horarios y ubicación",
      "synonyms": ["horarios", "ubicación", "dirección", "cuándo abren", "dónde están"]
    },
    "delivery_info": {
      "description": "Información de delivery",
      "synonyms": ["delivery", "envío", "domicilio", "entrega", "zona"]
    },
    "reservation": {
      "description": "Hacer reserva",
      "synonyms": ["reserva", "reservar", "mesa", "turno", "cita"]
    }
  }'::jsonb,
  '{
    "take_order": {
      "required": ["product", "quantity", "pickup_or_delivery", "name", "phone"],
      "optional": ["special_instructions", "address"],
      "validators": {
        "product": "menu_item_exists",
        "quantity": "positive_integer",
        "pickup_or_delivery": "pickup_or_delivery_choice",
        "phone": "valid_phone"
      },
      "confirm": true
    },
    "reservation": {
      "required": ["date", "time", "party_size", "name", "phone"],
      "optional": ["special_requests"],
      "validators": {
        "date": "future_date",
        "time": "business_hours",
        "party_size": "positive_integer_max_12"
      },
      "confirm": true
    }
  }'::jsonb,
  '{
    "MenuRAG": {
      "description": "Buscar información del menú",
      "parameters": ["query"],
      "vertical": "gastronomia"
    },
    "OrderBuilder": {
      "description": "Construir pedido",
      "parameters": ["items", "customer_info"],
      "vertical": "gastronomia"
    },
    "PaymentLink": {
      "description": "Generar link de pago",
      "parameters": ["amount", "order_id"],
      "vertical": "gastronomia"
    },
    "DeliveryETA": {
      "description": "Calcular tiempo de entrega",
      "parameters": ["address", "order_items"],
      "vertical": "gastronomia"
    }
  }'::jsonb,
  '{
    "business_hours_required": true,
    "max_ticket_without_human": 100000,
    "delivery_zones": ["CABA", "GBA"],
    "max_party_size": 12,
    "lead_time_minutes": 15
  }'::jsonb,
  '{
    "customer_requests_human": true,
    "low_confidence_threshold": 0.7,
    "high_amount_threshold": 100000,
    "complaint_keywords": ["queja", "reclamo", "malo", "terrible"],
    "escalation_keywords": ["gerente", "supervisor", "dueño"]
  }'::jsonb,
  '{
    "vector_index": "tenant_00000000-0000-0000-0000-000000000001_gastronomia",
    "faq_sources": ["menu", "horarios", "delivery", "reservas"]
  }'::jsonb
)
ON CONFLICT (workspace_id, vertical) DO UPDATE SET
  role_prompt = EXCLUDED.role_prompt,
  intents_json = EXCLUDED.intents_json,
  slots_config = EXCLUDED.slots_config,
  tools_config = EXCLUDED.tools_config,
  policies_config = EXCLUDED.policies_config,
  handoff_rules = EXCLUDED.handoff_rules,
  rag_sources = EXCLUDED.rag_sources,
  updated_at = now();

-- 2. Vertical Pack: E-COMMERCE
INSERT INTO pulpo.vertical_packs (
  workspace_id, vertical, role_prompt, intents_json, slots_config, 
  tools_config, policies_config, handoff_rules, rag_sources
) VALUES (
  '00000000-0000-0000-0000-000000000001',
  'ecommerce',
  'Sos un asistente de ventas de la tienda online. Ayudá a los clientes a encontrar productos, resolver dudas y completar compras. Sé proactivo en sugerir productos relacionados.',
  '{
    "product_search": {
      "description": "Buscar productos",
      "synonyms": ["buscar", "producto", "encontrar", "tienen", "venden"]
    },
    "product_info": {
      "description": "Información de producto específico",
      "synonyms": ["precio", "stock", "características", "especificaciones"]
    },
    "add_to_cart": {
      "description": "Agregar al carrito",
      "synonyms": ["agregar", "carrito", "comprar", "añadir"]
    },
    "checkout": {
      "description": "Proceso de compra",
      "synonyms": ["comprar", "pagar", "checkout", "finalizar"]
    },
    "order_status": {
      "description": "Estado del pedido",
      "synonyms": ["pedido", "envío", "seguimiento", "estado"]
    }
  }'::jsonb,
  '{
    "product_search": {
      "required": ["search_query"],
      "optional": ["category", "price_range", "brand"],
      "validators": {
        "search_query": "non_empty_string",
        "price_range": "valid_price_range"
      },
      "confirm": false
    },
    "add_to_cart": {
      "required": ["product_id", "quantity"],
      "optional": ["variant", "size", "color"],
      "validators": {
        "product_id": "valid_product_id",
        "quantity": "positive_integer"
      },
      "confirm": true
    },
    "checkout": {
      "required": ["cart_items", "shipping_address", "payment_method"],
      "optional": ["coupon_code", "special_instructions"],
      "validators": {
        "shipping_address": "valid_address",
        "payment_method": "valid_payment_method"
      },
      "confirm": true
    }
  }'::jsonb,
  '{
    "CatalogSearch": {
      "description": "Buscar en catálogo",
      "parameters": ["query", "filters"],
      "vertical": "ecommerce"
    },
    "CartOps": {
      "description": "Operaciones de carrito",
      "parameters": ["action", "items"],
      "vertical": "ecommerce"
    },
    "ShippingETA": {
      "description": "Calcular envío",
      "parameters": ["address", "items"],
      "vertical": "ecommerce"
    },
    "OrderTracker": {
      "description": "Seguimiento de pedidos",
      "parameters": ["order_id"],
      "vertical": "ecommerce"
    }
  }'::jsonb,
  '{
    "business_hours_required": false,
    "max_ticket_without_human": 500000,
    "shipping_zones": ["Argentina"],
    "max_cart_items": 50,
    "lead_time_hours": 24
  }'::jsonb,
  '{
    "customer_requests_human": true,
    "low_confidence_threshold": 0.7,
    "high_amount_threshold": 500000,
    "complaint_keywords": ["defectuoso", "malo", "no funciona", "devolución"],
    "escalation_keywords": ["gerente", "supervisor", "dueño"]
  }'::jsonb,
  '{
    "vector_index": "tenant_00000000-0000-0000-0000-000000000001_ecommerce",
    "faq_sources": ["productos", "envios", "devoluciones", "pagos"]
  }'::jsonb
)
ON CONFLICT (workspace_id, vertical) DO UPDATE SET
  role_prompt = EXCLUDED.role_prompt,
  intents_json = EXCLUDED.intents_json,
  slots_config = EXCLUDED.slots_config,
  tools_config = EXCLUDED.tools_config,
  policies_config = EXCLUDED.policies_config,
  handoff_rules = EXCLUDED.handoff_rules,
  rag_sources = EXCLUDED.rag_sources,
  updated_at = now();

-- 3. Vertical Pack: INMOBILIARIA
INSERT INTO pulpo.vertical_packs (
  workspace_id, vertical, role_prompt, intents_json, slots_config, 
  tools_config, policies_config, handoff_rules, rag_sources
) VALUES (
  '00000000-0000-0000-0000-000000000001',
  'inmobiliaria',
  'Sos un asistente inmobiliario profesional. Ayudá a los clientes a encontrar propiedades, agendar visitas y resolver consultas. Sé detallado en las descripciones y proactivo en el seguimiento.',
  '{
    "property_search": {
      "description": "Buscar propiedades",
      "synonyms": ["buscar", "propiedad", "casa", "departamento", "alquiler", "venta"]
    },
    "property_info": {
      "description": "Información de propiedad específica",
      "synonyms": ["precio", "características", "ubicación", "metros", "ambientes"]
    },
    "schedule_visit": {
      "description": "Agendar visita",
      "synonyms": ["visita", "ver", "recorrer", "agendar", "turno"]
    },
    "lead_qualification": {
      "description": "Calificar lead",
      "synonyms": ["presupuesto", "necesidades", "requisitos", "calificar"]
    }
  }'::jsonb,
  '{
    "property_search": {
      "required": ["operation", "property_type", "zone", "budget"],
      "optional": ["bedrooms", "bathrooms", "amenities"],
      "validators": {
        "operation": "valid_operation",
        "property_type": "valid_property_type",
        "budget": "positive_number"
      },
      "confirm": false
    },
    "schedule_visit": {
      "required": ["property_id", "preferred_date", "preferred_time", "name", "phone"],
      "optional": ["special_requests"],
      "validators": {
        "property_id": "valid_property_id",
        "preferred_date": "future_date",
        "preferred_time": "business_hours",
        "phone": "valid_phone"
      },
      "confirm": true
    },
    "lead_qualification": {
      "required": ["operation", "budget_range", "timeline", "name", "phone"],
      "optional": ["current_situation", "preferences"],
      "validators": {
        "operation": "valid_operation",
        "budget_range": "valid_budget_range",
        "timeline": "valid_timeline"
      },
      "confirm": true
    }
  }'::jsonb,
  '{
    "PropertySearch": {
      "description": "Buscar propiedades",
      "parameters": ["filters", "criteria"],
      "vertical": "inmobiliaria"
    },
    "ScheduleVisit": {
      "description": "Agendar visita",
      "parameters": ["property_id", "datetime", "contact_info"],
      "vertical": "inmobiliaria"
    },
    "LeadQualify": {
      "description": "Calificar lead",
      "parameters": ["criteria", "contact_info"],
      "vertical": "inmobiliaria"
    }
  }'::jsonb,
  '{
    "business_hours_required": true,
    "max_ticket_without_human": 2000000,
    "service_zones": ["CABA", "GBA", "Zona Norte"],
    "max_visit_party": 4,
    "lead_time_hours": 2
  }'::jsonb,
  '{
    "customer_requests_human": true,
    "low_confidence_threshold": 0.7,
    "high_amount_threshold": 2000000,
    "complaint_keywords": ["malo", "caro", "no me sirve", "problema"],
    "escalation_keywords": ["gerente", "supervisor", "dueño"]
  }'::jsonb,
  '{
    "vector_index": "tenant_00000000-0000-0000-0000-000000000001_inmobiliaria",
    "faq_sources": ["propiedades", "procesos", "financiacion", "documentacion"]
  }'::jsonb
)
ON CONFLICT (workspace_id, vertical) DO UPDATE SET
  role_prompt = EXCLUDED.role_prompt,
  intents_json = EXCLUDED.intents_json,
  slots_config = EXCLUDED.slots_config,
  tools_config = EXCLUDED.tools_config,
  policies_config = EXCLUDED.policies_config,
  handoff_rules = EXCLUDED.handoff_rules,
  rag_sources = EXCLUDED.rag_sources,
  updated_at = now();

-- 4. Herramientas disponibles
INSERT INTO pulpo.available_tools (workspace_id, tool_name, tool_config) VALUES
-- Gastronomía
('00000000-0000-0000-0000-000000000001', 'MenuRAG', '{"description": "Buscar en menú", "vertical": "gastronomia", "endpoint": "/api/tools/menu-search"}'),
('00000000-0000-0000-0000-000000000001', 'OrderBuilder', '{"description": "Construir pedido", "vertical": "gastronomia", "endpoint": "/api/tools/order-builder"}'),
('00000000-0000-0000-0000-000000000001', 'PaymentLink', '{"description": "Link de pago", "vertical": "gastronomia", "endpoint": "/api/tools/payment-link"}'),
('00000000-0000-0000-0000-000000000001', 'DeliveryETA', '{"description": "Tiempo de entrega", "vertical": "gastronomia", "endpoint": "/api/tools/delivery-eta"}'),

-- E-commerce
('00000000-0000-0000-0000-000000000001', 'CatalogSearch', '{"description": "Buscar catálogo", "vertical": "ecommerce", "endpoint": "/api/tools/catalog-search"}'),
('00000000-0000-0000-0000-000000000001', 'CartOps', '{"description": "Operaciones carrito", "vertical": "ecommerce", "endpoint": "/api/tools/cart-ops"}'),
('00000000-0000-0000-0000-000000000001', 'OrderTracker', '{"description": "Seguimiento pedidos", "vertical": "ecommerce", "endpoint": "/api/tools/order-tracker"}'),

-- Inmobiliaria
('00000000-0000-0000-0000-000000000001', 'PropertySearch', '{"description": "Buscar propiedades", "vertical": "inmobiliaria", "endpoint": "/api/tools/property-search"}'),
('00000000-0000-0000-0000-000000000001', 'ScheduleVisit', '{"description": "Agendar visita", "vertical": "inmobiliaria", "endpoint": "/api/tools/schedule-visit"}'),
('00000000-0000-0000-0000-000000000001', 'LeadQualify', '{"description": "Calificar lead", "vertical": "inmobiliaria", "endpoint": "/api/tools/lead-qualify"}'),

-- Herramientas generales
('00000000-0000-0000-0000-000000000001', 'RAGSearch', '{"description": "Búsqueda RAG", "vertical": "all", "endpoint": "/api/tools/rag-search"}'),
('00000000-0000-0000-0000-000000000001', 'FAQSearch', '{"description": "Buscar FAQs", "vertical": "all", "endpoint": "/api/tools/faq-search"}')
ON CONFLICT (workspace_id, tool_name) DO UPDATE SET
  tool_config = EXCLUDED.tool_config;
