#!/usr/bin/env python3
"""
Script final para validar el workflow n8n F-08
"""

import json

def load_workflow(file_path: str):
    """Cargar workflow desde archivo JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    """Función principal"""
    print("🔍 Final Validation - n8n Workflow F-08")
    print("=" * 50)
    
    try:
        workflow = load_workflow('n8n/n8n-workflow-f08-fixed.json')
        print("✅ Workflow loaded successfully")
    except Exception as e:
        print(f"❌ Error loading workflow: {e}")
        return False
    
    # Obtener nombres de nodos
    node_names = set()
    for node in workflow.get('nodes', []):
        node_name = node.get('name', '')
        if node_name:
            node_names.add(node_name)
    
    print(f"📊 Found {len(node_names)} nodes")
    
    # Verificar conexiones
    connections = workflow.get('connections', {})
    all_connected_nodes = set()
    
    print("\n🔗 Checking connections...")
    for source_node, connections_list in connections.items():
        all_connected_nodes.add(source_node)
        print(f"   {source_node} -> ", end="")
        
        for connection_group in connections_list:
            for connection in connection_group:
                if isinstance(connection, dict):
                    target_node = connection.get('node', '')
                    if target_node:
                        all_connected_nodes.add(target_node)
                        print(f"{target_node} ", end="")
        print()
    
    # Verificar nodos huérfanos
    orphaned_nodes = node_names - all_connected_nodes
    if orphaned_nodes:
        print(f"\n⚠️  Orphaned nodes: {', '.join(orphaned_nodes)}")
    else:
        print("\n✅ All nodes are connected")
    
    # Verificar nombres inconsistentes
    inconsistent_names = [name for name in node_names if name.endswith('1')]
    if inconsistent_names:
        print(f"⚠️  Inconsistent naming: {', '.join(inconsistent_names)}")
    else:
        print("✅ All node names are consistent")
    
    # Verificar que hay nodos clave
    key_nodes = ['Webhook Inbound', 'Check Tool Calls', 'Split Tool Calls', 'Execute Action', 'Final Response']
    missing_nodes = [node for node in key_nodes if node not in node_names]
    
    if missing_nodes:
        print(f"❌ Missing key nodes: {', '.join(missing_nodes)}")
    else:
        print("✅ All key nodes present")
    
    # Resumen final
    print("\n" + "=" * 50)
    if not orphaned_nodes and not inconsistent_names and not missing_nodes:
        print("🎉 Workflow F-08 is ready for deployment!")
        print("\n📋 Key features validated:")
        print("   • All nodes properly connected")
        print("   • Consistent naming (no '1' suffixes)")
        print("   • Key workflow components present")
        print("   • Tool call handling implemented")
        return True
    else:
        print("⚠️  Workflow needs fixes before deployment")
        return False

if __name__ == "__main__":
    main()
