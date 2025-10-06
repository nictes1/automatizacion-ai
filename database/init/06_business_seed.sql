-- =====================================================
-- BUSINESS CATALOG SEED DATA
-- =====================================================
-- Datos de ejemplo para catálogos de negocio
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- SERVICIOS - PELUQUERÍA
-- =====================================================

-- Workspace ID para peluquería (debe existir en workspaces)
DO $$
DECLARE
  v_workspace_id uuid := '550e8400-e29b-41d4-a716-446655440000';
BEGIN
  -- Staff
  INSERT INTO pulpo.staff (workspace_id, name, email, phone, role, is_active, google_calendar_id, skills)
  VALUES
    (v_workspace_id, 'María García', 'maria.garcia@peluqueriaestilo.com', '+5491123456789', 'Peluquera Senior', true, 'maria.garcia@gmail.com',
     '["corte", "coloración", "brushing"]'::jsonb),
    (v_workspace_id, 'Juan Pérez', 'juan.perez@peluqueriaestilo.com', '+5491198765432', 'Peluquero', true, 'juan.perez@gmail.com',
     '["corte", "barba"]'::jsonb),
    (v_workspace_id, 'Ana López', 'ana.lopez@peluqueriaestilo.com', '+5491187654321', 'Estilista', true, 'ana.lopez@gmail.com',
     '["coloración", "mechas", "tratamientos"]'::jsonb),
    (v_workspace_id, 'Carlos Martínez', 'carlos.martinez@peluqueriaestilo.com', '+5491156781234', 'Barbero', true, 'carlos.martinez@gmail.com',
     '["corte", "barba", "afeitado"]'::jsonb)
  ON CONFLICT (workspace_id, email) DO NOTHING;

  -- Service Types
  INSERT INTO pulpo.service_types (workspace_id, name, description, category, price, currency, duration_minutes, is_active, requires_staff)
  VALUES
    (v_workspace_id, 'Corte de Cabello', 'Corte de cabello con lavado incluido', 'hair', 2500, 'ARS', 45, true, true),
    (v_workspace_id, 'Coloración Completa', 'Aplicación de color en todo el cabello', 'hair', 6500, 'ARS', 120, true, true),
    (v_workspace_id, 'Mechas/Reflejos', 'Mechas o reflejos parciales', 'hair', 5000, 'ARS', 90, true, true),
    (v_workspace_id, 'Brushing', 'Secado y peinado profesional', 'hair', 1800, 'ARS', 30, true, true),
    (v_workspace_id, 'Tratamiento Capilar', 'Tratamiento nutritivo o reparador', 'hair', 3500, 'ARS', 45, true, true),
    (v_workspace_id, 'Corte y Barba', 'Corte de cabello y arreglo de barba', 'hair', 3000, 'ARS', 60, true, true),
    (v_workspace_id, 'Barba Completa', 'Diseño y arreglo completo de barba', 'hair', 1500, 'ARS', 30, true, true),
    (v_workspace_id, 'Manicura', 'Manicura básica con esmaltado', 'nails', 1200, 'ARS', 45, true, true),
    (v_workspace_id, 'Pedicura', 'Pedicura completa con esmaltado', 'nails', 1500, 'ARS', 60, true, true),
    (v_workspace_id, 'Manicura Semipermanente', 'Manicura con esmaltado semipermanente', 'nails', 2000, 'ARS', 60, true, true)
  ON CONFLICT (workspace_id, name) DO UPDATE
  SET price = EXCLUDED.price,
      duration_minutes = EXCLUDED.duration_minutes;

  -- Asignar servicios a staff
  INSERT INTO pulpo.staff_services (workspace_id, staff_id, service_type_id)
  SELECT
    v_workspace_id,
    s.id,
    st.id
  FROM pulpo.staff s
  CROSS JOIN pulpo.service_types st
  WHERE s.workspace_id = v_workspace_id
    AND st.workspace_id = v_workspace_id
    AND (
      -- María: corte, coloración, brushing
      (s.name = 'María García' AND st.name IN ('Corte de Cabello', 'Coloración Completa', 'Brushing', 'Tratamiento Capilar')) OR
      -- Juan: corte, barba
      (s.name = 'Juan Pérez' AND st.name IN ('Corte de Cabello', 'Corte y Barba', 'Barba Completa')) OR
      -- Ana: coloración, mechas, tratamientos
      (s.name = 'Ana López' AND st.name IN ('Coloración Completa', 'Mechas/Reflejos', 'Tratamiento Capilar', 'Brushing')) OR
      -- Carlos: corte, barba
      (s.name = 'Carlos Martínez' AND st.name IN ('Corte de Cabello', 'Corte y Barba', 'Barba Completa'))
    )
  ON CONFLICT (staff_id, service_type_id) DO NOTHING;

END $$;

-- =====================================================
-- GASTRONOMÍA - RESTAURANTE
-- =====================================================

DO $$
DECLARE
  v_workspace_id uuid := '550e8400-e29b-41d4-a716-446655440001';
BEGIN
  -- Menu Items
  INSERT INTO pulpo.menu_items (workspace_id, sku, nombre, descripcion, precio, categoria, disponible)
  VALUES
    -- Pizzas
    (v_workspace_id, 'PIZZA-001', 'Pizza Margherita', 'Salsa de tomate napolitana con mozzarella y albahaca fresca', 3500, 'pizzas', true),
    (v_workspace_id, 'PIZZA-002', 'Pizza Napolitana', 'Mozzarella napolitana con tomate en rodajas y orégano', 3800, 'pizzas', true),
    (v_workspace_id, 'PIZZA-003', 'Pizza Fugazzeta', 'Cebolla salteada con abundante mozzarella', 4200, 'pizzas', true),
    (v_workspace_id, 'PIZZA-004', 'Pizza Calabresa', 'Mozzarella con longaniza calabresa y aceitunas', 4500, 'pizzas', true),
    (v_workspace_id, 'PIZZA-005', 'Pizza Cuatro Quesos', 'Mozzarella, roquefort, parmesano y provolone', 4800, 'pizzas', true),

    -- Hamburguesas
    (v_workspace_id, 'BURGER-001', 'Hamburguesa Clásica', 'Medallón de carne con lechuga, tomate y cebolla', 2800, 'hamburguesas', true),
    (v_workspace_id, 'BURGER-002', 'Hamburguesa Completa', 'Con jamón, queso, huevo y panceta', 3500, 'hamburguesas', true),
    (v_workspace_id, 'BURGER-003', 'Hamburguesa BBQ', 'Con salsa barbacoa, cebolla caramelizada y cheddar', 3800, 'hamburguesas', true),

    -- Pastas
    (v_workspace_id, 'PASTA-001', 'Ravioles de Ricota', 'Con salsa a elección (tuco, fileto o crema)', 3200, 'pastas', true),
    (v_workspace_id, 'PASTA-002', 'Sorrentinos de Jamón y Queso', 'Con salsa a elección', 3400, 'pastas', true),
    (v_workspace_id, 'PASTA-003', 'Ñoquis de Papa', 'Con salsa a elección', 2800, 'pastas', true),
    (v_workspace_id, 'PASTA-004', 'Tallarines con Salsa Bolognesa', 'Tallarines caseros con salsa bolognesa', 3000, 'pastas', true),

    -- Ensaladas
    (v_workspace_id, 'ENS-001', 'Ensalada César', 'Lechuga romana, parmesano, croutons y aderezo césar', 2500, 'ensaladas', true),
    (v_workspace_id, 'ENS-002', 'Ensalada Mixta', 'Lechuga, tomate, cebolla, zanahoria y huevo', 2200, 'ensaladas', true),
    (v_workspace_id, 'ENS-003', 'Ensalada Caprese', 'Tomate, mozzarella de búfala y albahaca', 2800, 'ensaladas', true),

    -- Bebidas
    (v_workspace_id, 'BEB-001', 'Coca Cola 500ml', 'Gaseosa', 800, 'bebidas', true),
    (v_workspace_id, 'BEB-002', 'Agua Mineral 500ml', 'Agua sin gas', 600, 'bebidas', true),
    (v_workspace_id, 'BEB-003', 'Cerveza Quilmes 1L', 'Cerveza rubia', 1500, 'bebidas', true),
    (v_workspace_id, 'BEB-004', 'Fernet con Coca 1L', 'Fernet Branca con Coca Cola', 2000, 'bebidas', true),

    -- Postres
    (v_workspace_id, 'POST-001', 'Flan Casero', 'Con dulce de leche o crema', 1200, 'postres', true),
    (v_workspace_id, 'POST-002', 'Helado 2 Bochas', 'Sabor a elección', 1000, 'postres', true),
    (v_workspace_id, 'POST-003', 'Tiramisu', 'Postre italiano con mascarpone y café', 1500, 'postres', true)
  ON CONFLICT (workspace_id, sku) DO UPDATE
  SET precio = EXCLUDED.precio,
      disponible = EXCLUDED.disponible;

END $$;

-- =====================================================
-- INMOBILIARIA (Ejemplo básico)
-- =====================================================

DO $$
DECLARE
  v_workspace_id uuid := '550e8400-e29b-41d4-a716-446655440002';
BEGIN
  -- Staff (Asesores)
  INSERT INTO pulpo.staff (workspace_id, name, email, phone, role, is_active, google_calendar_id, skills)
  VALUES
    (v_workspace_id, 'Roberto Sánchez', 'roberto.sanchez@inmobiliaria.com', '+5491145678901', 'Asesor Senior', true, 'roberto.sanchez@gmail.com',
     '["ventas", "alquileres", "tasaciones"]'::jsonb),
    (v_workspace_id, 'Laura Fernández', 'laura.fernandez@inmobiliaria.com', '+5491198765432', 'Asesora', true, 'laura.fernandez@gmail.com',
     '["ventas", "alquileres"]'::jsonb)
  ON CONFLICT (workspace_id, email) DO NOTHING;

END $$;

RAISE NOTICE 'Business catalog seed data loaded successfully';
