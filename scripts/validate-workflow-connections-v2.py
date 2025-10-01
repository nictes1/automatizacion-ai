#!/usr/bin/env python3
"""
Script mejorado para validar las conexiones del workflow de n8n
Funciona tanto con IDs como con nombres de nodos
"""

import json
import sys

def validate_workflow_connections(workflow_file):
    """Valida que todas las conexiones del workflow sean correctas"""
    
    try:
        with open(workflow_file, 'r', encoding='utf-8') as f:
            workflow = json.load(f)
    except Exception as e:
        print(f"❌ Error leyendo archivo: {e}")
        return False
    
    # Obtener todos los nodos y crear mapeos
    nodes_by_id = {}
    nodes_by_name = {}
    
    for node in workflow.get('nodes', []):
        node_id = node.get('id')
        node_name = node.get('name')
        if node_id:
            nodes_by_id[node_id] = node_name
            if node_name:
                nodes_by_name[node_name] = node_id
    
    print(f"📊 Total de nodos encontrados: {len(nodes_by_id)}")
    
    # Obtener todas las conexiones
    connections = workflow.get('connections', {})
    
    print(f"🔗 Total de conexiones definidas: {len(connections)}")
    
    # Validar conexiones
    errors = []
    warnings = []
    valid_connections = 0
    
    for source_node, connection_data in connections.items():
        # Determinar si source_node es ID o nombre
        source_is_id = source_node in nodes_by_id
        source_is_name = source_node in nodes_by_name
        
        if not source_is_id and not source_is_name:
            errors.append(f"❌ Nodo fuente '{source_node}' no existe en la lista de nodos")
            continue
            
        # Obtener el nombre del nodo fuente para mostrar
        if source_is_id:
            source_name = nodes_by_id[source_node]
        else:
            source_name = source_node
            
        main_connections = connection_data.get('main', [])
        for i, connection_group in enumerate(main_connections):
            for j, connection in enumerate(connection_group):
                target_node = connection.get('node')
                if target_node:
                    # Determinar si target_node es ID o nombre
                    target_is_id = target_node in nodes_by_id
                    target_is_name = target_node in nodes_by_name
                    
                    if not target_is_id and not target_is_name:
                        errors.append(f"❌ Nodo destino '{target_node}' no existe (conectado desde '{source_name}')")
                    else:
                        # Obtener el nombre del nodo destino para mostrar
                        if target_is_id:
                            target_name = nodes_by_id[target_node]
                        else:
                            target_name = target_node
                        
                        print(f"✅ {source_name} -> {target_name}")
                        valid_connections += 1
    
    # Verificar nodos sin conexiones
    connected_nodes = set()
    
    # Agregar nodos fuente
    for source_node in connections.keys():
        if source_node in nodes_by_id:
            connected_nodes.add(source_node)
        elif source_node in nodes_by_name:
            connected_nodes.add(nodes_by_name[source_node])
    
    # Agregar nodos destino
    for connection_data in connections.values():
        main_connections = connection_data.get('main', [])
        for connection_group in main_connections:
            for connection in connection_group:
                target_node = connection.get('node')
                if target_node:
                    if target_node in nodes_by_id:
                        connected_nodes.add(target_node)
                    elif target_node in nodes_by_name:
                        connected_nodes.add(nodes_by_name[target_node])
    
    # Encontrar nodos desconectados
    for node_id, node_name in nodes_by_id.items():
        if node_id not in connected_nodes:
            warnings.append(f"⚠️  Nodo '{node_name}' ({node_id}) no tiene conexiones")
    
    print("\n" + "="*50)
    print("📋 RESUMEN DE VALIDACIÓN")
    print("="*50)
    
    if errors:
        print(f"\n❌ ERRORES ENCONTRADOS ({len(errors)}):")
        for error in errors:
            print(f"  {error}")
    
    if warnings:
        print(f"\n⚠️  ADVERTENCIAS ({len(warnings)}):")
        for warning in warnings:
            print(f"  {warning}")
    
    if not errors and not warnings:
        print(f"\n🎉 ¡Todas las conexiones son válidas!")
        print(f"✅ {valid_connections} conexiones validadas correctamente")
        print("✅ El workflow está listo para importar en n8n")
        return True
    else:
        if errors:
            print(f"\n❌ Se encontraron {len(errors)} errores que deben corregirse")
        if warnings:
            print(f"⚠️  Se encontraron {len(warnings)} advertencias")
        print("\n❌ El workflow tiene errores que deben corregirse")
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python3 validate-workflow-connections-v2.py <archivo_workflow.json>")
        sys.exit(1)
    
    workflow_file = sys.argv[1]
    print(f"🔍 Validando conexiones del workflow de n8n...")
    print(f"📁 Archivo: {workflow_file}")
    print()
    
    success = validate_workflow_connections(workflow_file)
    sys.exit(0 if success else 1)


