-- =====================================================
-- SEED MENU ITEMS - Catálogo de Gastronomía
-- =====================================================
-- Populate menu_items for testing crear_pedido action

-- Empanadas
INSERT INTO pulpo.menu_items (workspace_id, sku, nombre, descripcion, precio, categoria, disponible)
VALUES
  ('550e8400-e29b-41d4-a716-446655440000', 'EMP-001', 'Empanada de Carne', 'Empanada criolla rellena de carne picada con cebolla, huevo y aceitunas', 2.50, 'Empanadas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'EMP-002', 'Empanada de Pollo', 'Empanada rellena de pollo desmenuzado con verduras', 2.50, 'Empanadas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'EMP-003', 'Empanada de Jamón y Queso', 'Empanada rellena de jamón cocido y queso muzzarella', 2.50, 'Empanadas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'EMP-004', 'Empanada de Verdura', 'Empanada rellena de espinaca, acelga y queso ricota', 2.30, 'Empanadas', true);

-- Platos principales
INSERT INTO pulpo.menu_items (workspace_id, sku, nombre, descripcion, precio, categoria, disponible)
VALUES
  ('550e8400-e29b-41d4-a716-446655440000', 'PLATO-001', 'Milanesa con Papas Fritas', 'Milanesa de carne o pollo con guarnición de papas fritas', 12.50, 'Platos Principales', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'PLATO-002', 'Bife de Chorizo', 'Bife de chorizo 300g con ensalada o papas', 18.00, 'Platos Principales', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'PLATO-003', 'Pollo al Horno', 'Presa de pollo al horno con verduras asadas', 11.50, 'Platos Principales', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'PLATO-004', 'Pescado a la Plancha', 'Filete de merluza a la plancha con limón y ensalada', 14.00, 'Platos Principales', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'PLATO-005', 'Ravioles de Ricota', 'Ravioles caseros con salsa a elección: tuco, crema, mixta', 10.50, 'Platos Principales', true);

-- Pizzas
INSERT INTO pulpo.menu_items (workspace_id, sku, nombre, descripcion, precio, categoria, disponible)
VALUES
  ('550e8400-e29b-41d4-a716-446655440000', 'PIZZA-001', 'Pizza Muzzarella', 'Pizza con muzzarella y aceitunas', 9.00, 'Pizzas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'PIZZA-002', 'Pizza Napolitana', 'Pizza con muzzarella, tomate y ajo', 10.00, 'Pizzas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'PIZZA-003', 'Pizza Jamón y Morrones', 'Pizza con muzzarella, jamón cocido y morrones', 11.50, 'Pizzas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'PIZZA-004', 'Pizza Fugazzeta', 'Pizza rellena de muzzarella con cebolla', 10.50, 'Pizzas', true);

-- Bebidas
INSERT INTO pulpo.menu_items (workspace_id, sku, nombre, descripcion, precio, categoria, disponible)
VALUES
  ('550e8400-e29b-41d4-a716-446655440000', 'BEB-001', 'Coca Cola 1.5L', 'Gaseosa Coca Cola 1.5 litros', 2.50, 'Bebidas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'BEB-002', 'Agua Mineral 500ml', 'Agua mineral sin gas', 1.50, 'Bebidas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'BEB-003', 'Cerveza Quilmes 1L', 'Cerveza Quilmes litro', 3.50, 'Bebidas', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'BEB-004', 'Jugo Natural Naranja', 'Jugo de naranja exprimido', 3.00, 'Bebidas', true);

-- Postres
INSERT INTO pulpo.menu_items (workspace_id, sku, nombre, descripcion, precio, categoria, disponible)
VALUES
  ('550e8400-e29b-41d4-a716-446655440000', 'POST-001', 'Flan Casero con Dulce de Leche', 'Flan casero con dulce de leche y crema', 4.50, 'Postres', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'POST-002', 'Helado 2 Bochas', 'Helado artesanal a elección', 4.00, 'Postres', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'POST-003', 'Tiramisú', 'Tiramisú casero', 5.50, 'Postres', true),
  ('550e8400-e29b-41d4-a716-446655440000', 'POST-004', 'Ensalada de Frutas', 'Ensalada de frutas de estación', 4.00, 'Postres', true);
