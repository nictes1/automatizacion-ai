#!/usr/bin/env python3
"""
Script para validar el workflow n8n F-08
Verifica que no haya referencias cruzadas ni nodos fantasma
"""

import json
import re
from typing import Dict, List, Set, Tuple

def load_workflow(file_path: str) -> Dict:
    """Cargar workflow desde archivo JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_node_references(workflow: Dict) -> Dict[str, List[str]]:
    """Extraer todas las referencias a nodos en el workflow"""
    references = {}
    
    for node_data in workflow.get('nodes', []):
        node_name = node_data.get('name', '')
        references[node_name] = []
        
        # Buscar referencias en parámetros
        for param_name, param_value in node_data.get('parameters', {}).items():
            if isinstance(param_value, str):
                # Buscar patrones como $('Node Name')
                matches = re.findall(r"\$\(['\"]([^'\"]+)['\"]\)", param_value)
                references[node_name].extend(matches)
    
    return references

def get_node_names(workflow: Dict) -> Set[str]:
    """Obtener todos los nombres de nodos en el workflow"""
    node_names = set()
    
    for node_data in workflow.get('nodes', []):
        node_name = node_data.get('name', '')
        if node_name:
            node_names.add(node_name)
    
    return node_names

def get_connection_targets(workflow: Dict) -> Set[str]:
    """Obtener todos los nodos que son targets de conexiones"""
    targets = set()
    
    connections = workflow.get('connections', {})
    for source_node, connections_list in connections.items():
        for connection_group in connections_list:
            for connection in connection_group:
                if isinstance(connection, dict):
                    target_node = connection.get('node', '')
                    if target_node:
                        targets.add(target_node)
    
    return targets

def validate_workflow(workflow: Dict) -> Tuple[bool, List[str]]:
    """Validar el workflow y retornar errores encontrados"""
    errors = []
    
    # 1. Obtener información del workflow
    node_names = get_node_names(workflow)
    connection_targets = get_connection_targets(workflow)
    references = extract_node_references(workflow)
    
    # 2. Verificar que todos los nodos referenciados existen
    for node_name, refs in references.items():
        for ref in refs:
            if ref not in node_names:
                errors.append(f"Node '{node_name}' references non-existent node '{ref}'")
    
    # 3. Verificar que todos los nodos conectados existen
    for target in connection_targets:
        if target not in node_names:
            errors.append(f"Connection target '{target}' does not exist")
    
    # 4. Verificar que no hay nodos huérfanos (sin conexiones)
    all_connected_nodes = set()
    connections = workflow.get('connections', {})
    
    for source_node, connections_list in connections.items():
        all_connected_nodes.add(source_node)
        for connection_group in connections_list:
            for connection in connection_group:
                target_node = connection.get('node', '')
                if target_node:
                    all_connected_nodes.add(target_node)
    
    orphaned_nodes = node_names - all_connected_nodes
    if orphaned_nodes:
        errors.append(f"Orphaned nodes (no connections): {', '.join(orphaned_nodes)}")
    
    # 5. Verificar nombres consistentes (sin sufijos "1")
    inconsistent_names = [name for name in node_names if name.endswith('1')]
    if inconsistent_names:
        errors.append(f"Nodes with inconsistent naming (ending in '1'): {', '.join(inconsistent_names)}")
    
    # 6. Verificar que el webhook tiene conexión de salida
    webhook_nodes = [name for name in node_names if 'webhook' in name.lower()]
    if webhook_nodes:
        webhook_connected = any(webhook in all_connected_nodes for webhook in webhook_nodes)
        if not webhook_connected:
            errors.append("Webhook nodes are not connected to the workflow")
    
    # 7. Verificar que hay un nodo Final Response
    final_response_nodes = [name for name in node_names if 'final' in name.lower() and 'response' in name.lower()]
    if not final_response_nodes:
        errors.append("No 'Final Response' node found")
    
    return len(errors) == 0, errors

def check_specific_issues(workflow: Dict) -> List[str]:
    """Verificar problemas específicos del workflow F-08"""
    issues = []
    
    # Verificar que Check Tool Calls tiene ambas ramas conectadas
    connections = workflow.get('connections', {})
    check_tool_calls_connections = connections.get('Check Tool Calls', [])
    
    if len(check_tool_calls_connections) < 2:
        issues.append("Check Tool Calls should have both TRUE and FALSE branches connected")
    
    # Verificar que Split Tool Calls tiene bucle de continuación
    split_connections = connections.get('Split Tool Calls', [])
    if len(split_connections) < 2:
        issues.append("Split Tool Calls should have both main output and loop back connection")
    
    # Verificar que Execute Action tiene bucle de continuación
    execute_connections = connections.get('Execute Action', [])
    if len(execute_connections) < 2:
        issues.append("Execute Action should have both main output and loop back connection")
    
    return issues

def main():
    """Función principal de validación"""
    print("🔍 Validating n8n Workflow F-08")
    print("=" * 50)
    
    # Cargar workflow
    try:
        workflow = load_workflow('n8n/n8n-workflow-f08-fixed.json')
        print("✅ Workflow loaded successfully")
    except Exception as e:
        print(f"❌ Error loading workflow: {e}")
        return False
    
    # Validar workflow
    is_valid, errors = validate_workflow(workflow)
    
    if is_valid:
        print("✅ Workflow structure is valid")
    else:
        print("❌ Workflow has structural issues:")
        for error in errors:
            print(f"   • {error}")
    
    # Verificar problemas específicos
    specific_issues = check_specific_issues(workflow)
    
    if specific_issues:
        print("\n⚠️  Specific F-08 issues found:")
        for issue in specific_issues:
            print(f"   • {issue}")
    else:
        print("\n✅ No specific F-08 issues found")
    
    # Resumen
    print("\n" + "=" * 50)
    if is_valid and not specific_issues:
        print("🎉 Workflow F-08 is ready for deployment!")
        return True
    else:
        print("⚠️  Workflow needs fixes before deployment")
        return False

if __name__ == "__main__":
    main()
