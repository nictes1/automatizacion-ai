#!/usr/bin/env python3
"""
Script simple para validar el workflow n8n F-08
"""

import json
import re

def load_workflow(file_path: str):
    """Cargar workflow desde archivo JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def validate_workflow(workflow):
    """Validar el workflow"""
    errors = []
    
    # Obtener nombres de nodos
    node_names = set()
    for node in workflow.get('nodes', []):
        node_name = node.get('name', '')
        if node_name:
            node_names.add(node_name)
    
    print(f"📊 Found {len(node_names)} nodes:")
    for name in sorted(node_names):
        print(f"   • {name}")
    
    # Verificar referencias en parámetros
    print("\n🔍 Checking node references...")
    
    for node in workflow.get('nodes', []):
        node_name = node.get('name', '')
        parameters = node.get('parameters', {})
        
        # Buscar referencias en parámetros
        for param_name, param_value in parameters.items():
            if isinstance(param_value, str):
                # Buscar patrones como $('Node Name')
                matches = re.findall(r"\$\(['\"]([^'\"]+)['\"]\)", param_value)
                for match in matches:
                    if match not in node_names:
                        errors.append(f"Node '{node_name}' references non-existent node '{match}'")
    
    # Verificar conexiones
    print("\n🔗 Checking connections...")
    
    connections = workflow.get('connections', {})
    all_connected_nodes = set()
    
    for source_node, connections_list in connections.items():
        all_connected_nodes.add(source_node)
        for connection_group in connections_list:
            for connection in connection_group:
                if isinstance(connection, dict):
                    target_node = connection.get('node', '')
                    if target_node:
                        all_connected_nodes.add(target_node)
                        if target_node not in node_names:
                            errors.append(f"Connection target '{target_node}' does not exist")
    
    # Verificar nodos huérfanos
    orphaned_nodes = node_names - all_connected_nodes
    if orphaned_nodes:
        errors.append(f"Orphaned nodes: {', '.join(orphaned_nodes)}")
    
    # Verificar nombres inconsistentes
    inconsistent_names = [name for name in node_names if name.endswith('1')]
    if inconsistent_names:
        errors.append(f"Nodes with inconsistent naming: {', '.join(inconsistent_names)}")
    
    return errors

def main():
    """Función principal"""
    print("🔍 Validating n8n Workflow F-08")
    print("=" * 50)
    
    try:
        workflow = load_workflow('n8n/n8n-workflow-f08-fixed.json')
        print("✅ Workflow loaded successfully")
    except Exception as e:
        print(f"❌ Error loading workflow: {e}")
        return False
    
    errors = validate_workflow(workflow)
    
    if errors:
        print("\n❌ Issues found:")
        for error in errors:
            print(f"   • {error}")
        return False
    else:
        print("\n✅ Workflow validation passed!")
        return True

if __name__ == "__main__":
    main()
