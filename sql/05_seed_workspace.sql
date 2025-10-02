-- =====================================================
-- SEED WORKSPACE COMPLETO
-- =====================================================
-- Crear workspace de prueba con datos reales
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- WORKSPACE DE PRUEBA
-- =====================================================

-- Crear workspace
INSERT INTO pulpo.workspaces (id, name, domain, plan, settings, created_at, updated_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    'Restaurante El Pulpo',
    'elpulpo.com',
    'premium',
    '{"vertical": "gastronomia", "timezone": "America/Bogota", "language": "es"}',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Crear usuario admin
INSERT INTO pulpo.users (id, email, name, role, created_at, updated_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440001',
    'admin@elpulpo.com',
    'Administrador El Pulpo',
    'admin',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- Asociar usuario al workspace
INSERT INTO pulpo.workspace_members (workspace_id, user_id, role, created_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440001',
    'admin',
    NOW()
) ON CONFLICT (workspace_id, user_id) DO NOTHING;

-- =====================================================
-- CANAL WHATSAPP
-- =====================================================

-- Crear canal WhatsApp
INSERT INTO pulpo.channels (id, workspace_id, type, name, config, is_active, created_at, updated_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440002',
    '550e8400-e29b-41d4-a716-446655440000',
    'whatsapp',
    'WhatsApp El Pulpo',
    '{"phone": "+573001234567", "webhook_url": "https://elpulpo.com/webhook/whatsapp", "sandbox": true}',
    true,
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- CONTACTOS DE PRUEBA
-- =====================================================

-- Crear contactos de prueba
INSERT INTO pulpo.contacts (id, workspace_id, channel_id, external_id, name, phone, email, metadata, created_at, updated_at)
VALUES 
(
    '550e8400-e29b-41d4-a716-446655440003',
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440002',
    'whatsapp:+573001111111',
    'Juan Pérez',
    '+573001111111',
    'juan@email.com',
    '{"preferences": {"language": "es", "notifications": true}}',
    NOW(),
    NOW()
),
(
    '550e8400-e29b-41d4-a716-446655440004',
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440002',
    'whatsapp:+573002222222',
    'María García',
    '+573002222222',
    'maria@email.com',
    '{"preferences": {"language": "es", "notifications": true}}',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- CONVERSACIONES DE PRUEBA
-- =====================================================

-- Crear conversaciones de prueba
INSERT INTO pulpo.conversations (id, workspace_id, channel_id, contact_id, status, metadata, created_at, updated_at)
VALUES 
(
    '550e8400-e29b-41d4-a716-446655440005',
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440002',
    '550e8400-e29b-41d4-a716-446655440003',
    'active',
    '{"vertical": "gastronomia", "language": "es"}',
    NOW(),
    NOW()
),
(
    '550e8400-e29b-41d4-a716-446655440006',
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440002',
    '550e8400-e29b-41d4-a716-446655440004',
    'active',
    '{"vertical": "gastronomia", "language": "es"}',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- MENSAJES DE PRUEBA
-- =====================================================

-- Crear mensajes de prueba
INSERT INTO pulpo.messages (id, workspace_id, conversation_id, sender, content, message_type, metadata, created_at)
VALUES 
(
    '550e8400-e29b-41d4-a716-446655440007',
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440005',
    'user',
    'Hola, quiero saber qué platos de pescado tienen',
    'text',
    '{"intent": "consultar_menu", "entities": {"plato": "pescado"}}',
    NOW() - INTERVAL '5 minutes'
),
(
    '550e8400-e29b-41d4-a716-446655440008',
    '550e8400-e29b-41d4-a716-446655440000',
    '550e8400-e29b-41d4-a716-446655440005',
    'assistant',
    '¡Hola! Te puedo ayudar con los platos de pescado que tenemos:\n\n🐟 Pescado a la plancha con arroz y ensalada - $25.000\n🐟 Ceviche de pescado fresco - $15.000\n\n¿Te interesa alguno en particular?',
    'text',
    '{"intent": "responder_consulta", "entities": {}}',
    NOW() - INTERVAL '4 minutes'
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- CONFIGURACIÓN DE VERTICAL
-- =====================================================

-- Crear configuración de vertical gastronomía
INSERT INTO pulpo.vertical_configs (id, workspace_id, vertical, config, created_at, updated_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440009',
    '550e8400-e29b-41d4-a716-446655440000',
    'gastronomia',
    '{
        "system_prompt": "Eres un asistente de restaurante inteligente. Responde de manera amigable y profesional a las consultas de los clientes sobre el menú, reservas y pedidos.",
        "intents": ["consultar_menu", "hacer_reserva", "hacer_pedido", "consultar_horarios", "consultar_precios"],
        "entities": ["plato", "cantidad", "fecha", "hora", "personas"],
        "actions": ["search_menu", "create_reservation", "create_order", "get_hours", "get_prices"],
        "language": "es"
    }',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- DOCUMENTOS DE PRUEBA
-- =====================================================

-- Crear documentos de prueba
INSERT INTO pulpo.documents (id, workspace_id, title, content, document_type, metadata, created_at, updated_at)
VALUES (
    '550e8400-e29b-41d4-a716-446655440010',
    '550e8400-e29b-41d4-a716-446655440000',
    'Menú Restaurante El Pulpo',
    'MENÚ RESTAURANTE "EL PULPO"

ENTRADAS
- Ceviche de pescado fresco con cebolla morada y cilantro - $15.000
- Empanadas de mariscos (6 unidades) - $12.000
- Ensalada de palta con tomate y aceite de oliva - $8.000

PLATOS PRINCIPALES
- Pescado a la plancha con arroz y ensalada - $25.000
- Paella de mariscos para 2 personas - $45.000
- Lomo de res con papas fritas - $28.000
- Pollo a la parrilla con vegetales - $22.000

POSTRES
- Flan de caramelo - $6.000
- Torta de chocolate - $8.000
- Helado de vainilla - $4.000

BEBIDAS
- Agua mineral - $3.000
- Jugo de naranja natural - $5.000
- Cerveza nacional - $4.000
- Vino tinto de la casa - $15.000

HORARIOS
Lunes a Viernes: 12:00 - 15:00 y 19:00 - 23:00
Sábados y Domingos: 12:00 - 24:00

RESERVAS
Teléfono: +57 1 234-5678
WhatsApp: +57 300 123-4567
Email: reservas@elpulpo.com

UBICACIÓN
Calle 123 #45-67, Bogotá, Colombia',
    'menu',
    '{"vertical": "gastronomia", "language": "es", "category": "menu"}',
    NOW(),
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- CHUNKS Y EMBEDDINGS
-- =====================================================

-- Crear chunks del documento
INSERT INTO pulpo.document_chunks (id, document_id, content, chunk_index, metadata, created_at)
VALUES 
(
    '550e8400-e29b-41d4-a716-446655440011',
    '550e8400-e29b-41d4-a716-446655440010',
    'ENTRADAS
- Ceviche de pescado fresco con cebolla morada y cilantro - $15.000
- Empanadas de mariscos (6 unidades) - $12.000
- Ensalada de palta con tomate y aceite de oliva - $8.000',
    0,
    '{"category": "entradas", "type": "menu_section"}',
    NOW()
),
(
    '550e8400-e29b-41d4-a716-446655440012',
    '550e8400-e29b-41d4-a716-446655440010',
    'PLATOS PRINCIPALES
- Pescado a la plancha con arroz y ensalada - $25.000
- Paella de mariscos para 2 personas - $45.000
- Lomo de res con papas fritas - $28.000
- Pollo a la parrilla con vegetales - $22.000',
    1,
    '{"category": "platos_principales", "type": "menu_section"}',
    NOW()
),
(
    '550e8400-e29b-41d4-a716-446655440013',
    '550e8400-e29b-41d4-a716-446655440010',
    'HORARIOS
Lunes a Viernes: 12:00 - 15:00 y 19:00 - 23:00
Sábados y Domingos: 12:00 - 24:00',
    2,
    '{"category": "horarios", "type": "info"}',
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- EMBEDDINGS (MOCK)
-- =====================================================

-- Crear embeddings mock para los chunks (1536 dimensiones para compatibilidad con OpenAI)
-- Nota: En producción, estos embeddings serán generados por el modelo real
-- Por ahora, usamos embeddings vacíos/mock
INSERT INTO pulpo.document_embeddings (id, chunk_id, model, created_at)
VALUES
(
    '550e8400-e29b-41d4-a716-446655440014',
    '550e8400-e29b-41d4-a716-446655440011',
    'nomic-embed-text',
    NOW()
),
(
    '550e8400-e29b-41d4-a716-446655440015',
    '550e8400-e29b-41d4-a716-446655440012',
    'nomic-embed-text',
    NOW()
),
(
    '550e8400-e29b-41d4-a716-446655440016',
    '550e8400-e29b-41d4-a716-446655440013',
    'nomic-embed-text',
    NOW()
) ON CONFLICT (id) DO NOTHING;

-- =====================================================
-- CONFIGURACIÓN DE RLS
-- =====================================================

-- Nota: RLS está configurado y las políticas están activas
-- No se requiere configuración adicional para el workspace de prueba

-- =====================================================
-- VERIFICACIÓN
-- =====================================================

-- Verificar que todo se creó correctamente
SELECT 
    'Workspaces' as table_name, 
    COUNT(*) as count 
FROM pulpo.workspaces 
WHERE id = '550e8400-e29b-41d4-a716-446655440000'

UNION ALL

SELECT 
    'Channels' as table_name, 
    COUNT(*) as count 
FROM pulpo.channels 
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'

UNION ALL

SELECT 
    'Contacts' as table_name, 
    COUNT(*) as count 
FROM pulpo.contacts 
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'

UNION ALL

SELECT 
    'Conversations' as table_name, 
    COUNT(*) as count 
FROM pulpo.conversations 
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'

UNION ALL

SELECT 
    'Documents' as table_name, 
    COUNT(*) as count 
FROM pulpo.documents 
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'

UNION ALL

SELECT 
    'Chunks' as table_name, 
    COUNT(*) as count 
FROM pulpo.document_chunks 
WHERE document_id = '550e8400-e29b-41d4-a716-446655440010'

UNION ALL

SELECT 
    'Embeddings' as table_name, 
    COUNT(*) as count 
FROM pulpo.document_embeddings 
WHERE chunk_id IN (
    SELECT id FROM pulpo.document_chunks 
    WHERE document_id = '550e8400-e29b-41d4-a716-446655440010'
);
