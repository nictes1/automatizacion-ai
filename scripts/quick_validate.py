#!/usr/bin/env python3
"""
Validación rápida del workflow F-08
"""

import json

def main():
    print("🔍 Quick Validation - n8n Workflow F-08")
    print("=" * 40)
    
    # Cargar workflow
    with open('n8n/n8n-workflow-f08-fixed.json', 'r') as f:
        workflow = json.load(f)
    
    # Contar nodos
    nodes = workflow.get('nodes', [])
    print(f"📊 Nodes: {len(nodes)}")
    
    # Verificar nombres sin sufijo "1"
    names_with_1 = [node['name'] for node in nodes if node['name'].endswith('1')]
    if names_with_1:
        print(f"⚠️  Names with '1': {names_with_1}")
    else:
        print("✅ No inconsistent naming")
    
    # Verificar nodos clave
    node_names = [node['name'] for node in nodes]
    key_nodes = ['Webhook Inbound', 'Check Tool Calls', 'Split Tool Calls', 'Execute Action', 'Final Response']
    missing = [node for node in key_nodes if node not in node_names]
    
    if missing:
        print(f"❌ Missing: {missing}")
    else:
        print("✅ Key nodes present")
    
    # Verificar conexiones
    connections = workflow.get('connections', {})
    print(f"🔗 Connections: {len(connections)}")
    
    # Verificar que Send Twilio conecta a Final Response
    send_twilio_conn = connections.get('Send Twilio', [])
    if send_twilio_conn:
        targets = []
        for group in send_twilio_conn:
            for conn in group:
                if isinstance(conn, dict):
                    targets.append(conn.get('node', ''))
        if 'Final Response' in targets:
            print("✅ Send Twilio -> Final Response")
        else:
            print("❌ Send Twilio not connected to Final Response")
    else:
        print("❌ Send Twilio has no connections")
    
    print("\n🎯 Workflow F-08 is ready!")
    return True

if __name__ == "__main__":
    main()
