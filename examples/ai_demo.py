#!/usr/bin/env python3
"""
Demo del sistema con AI - Mostrando la diferencia entre programación tradicional vs AI
"""

import asyncio
import json
from core.tools.vertical_tools import GastronomiaTools

async def demo_ai_vs_traditional():
    """Demo comparando enfoque tradicional vs AI"""
    
    print("🤖 DEMO: AI vs Programación Tradicional")
    print("=" * 50)
    
    # Crear instancia de tools
    tools = GastronomiaTools()
    
    # Ejemplo 1: Búsqueda inteligente
    print("\n📋 EJEMPLO 1: Búsqueda en Menú")
    print("-" * 30)
    
    queries = [
        "algo de carne",
        "empas",
        "gaseosa",
        "postre",
        "algo vegetariano"
    ]
    
    for query in queries:
        print(f"\n🔍 Usuario busca: '{query}'")
        
        # Búsqueda con AI
        result = await tools.search_menu({"query": query}, "demo-workspace")
        
        if result.get("items"):
            print("✅ AI encontró:")
            for item in result["items"][:2]:  # Mostrar solo los 2 primeros
                print(f"   - {item['name']} (${item['price']})")
                if item.get("match_reason"):
                    print(f"     Razón: {item['match_reason']}")
        else:
            print("❌ No se encontraron resultados")
    
    # Ejemplo 2: Upsell inteligente
    print("\n\n🛒 EJEMPLO 2: Upsell Inteligente")
    print("-" * 30)
    
    pedidos = [
        {
            "items": [{"name": "Empanada de carne", "price": 1200, "quantity": 6}],
            "current_total": 7200
        },
        {
            "items": [
                {"name": "Pizza Margherita", "price": 3500, "quantity": 1},
                {"name": "Empanada de jamón y queso", "price": 1200, "quantity": 2}
            ],
            "current_total": 5900
        },
        {
            "items": [{"name": "Coca Cola 500ml", "price": 800, "quantity": 1}],
            "current_total": 800
        }
    ]
    
    for i, pedido in enumerate(pedidos, 1):
        print(f"\n🍽️ Pedido {i}:")
        for item in pedido["items"]:
            print(f"   - {item['name']} x{item['quantity']}")
        print(f"   Total: ${pedido['current_total']}")
        
        # Upsell con AI
        result = await tools.suggest_upsell(pedido, "demo-workspace")
        
        if result.get("suggestions"):
            print("💡 AI sugiere:")
            for suggestion in result["suggestions"]:
                print(f"   - {suggestion['name']} (${suggestion['price']})")
                print(f"     {suggestion['reason']}")
        else:
            print("🤷 AI no sugiere nada adicional")

async def demo_conversacion_natural():
    """Demo de conversación natural con AI"""
    
    print("\n\n💬 DEMO: Conversación Natural")
    print("=" * 50)
    
    # Simular conversación
    conversaciones = [
        {
            "usuario": "Hola, quiero algo de carne",
            "contexto": "Usuario nuevo, sin items en pedido"
        },
        {
            "usuario": "Perfecto, 6 de carne",
            "contexto": "Usuario confirmó empanadas de carne"
        },
        {
            "usuario": "Sí, una coca",
            "contexto": "Usuario acepta sugerencia de bebida"
        },
        {
            "usuario": "No, ya está",
            "contexto": "Usuario rechaza más sugerencias"
        },
        {
            "usuario": "Delivery a San Martín 123",
            "contexto": "Usuario proporciona dirección"
        }
    ]
    
    tools = GastronomiaTools()
    pedido_actual = []
    
    for i, conv in enumerate(conversaciones, 1):
        print(f"\n🗣️ Turno {i}:")
        print(f"Usuario: '{conv['usuario']}'")
        print(f"Contexto: {conv['contexto']}")
        
        # Simular respuesta del orquestador
        if "carne" in conv["usuario"].lower():
            # Buscar empanadas de carne
            result = await tools.search_menu({"query": "empanada de carne"}, "demo-workspace")
            if result.get("items"):
                item = result["items"][0]
                pedido_actual.append({
                    "name": item["name"],
                    "price": item["price"],
                    "quantity": 6
                })
                print(f"🤖 Bot: 'Perfecto, 6 empanadas de carne. ¿Querés agregar algo más? Una bebida o postre?'")
        
        elif "coca" in conv["usuario"].lower():
            # Agregar coca
            pedido_actual.append({
                "name": "Coca Cola 500ml",
                "price": 800,
                "quantity": 1
            })
            print(f"🤖 Bot: 'Excelente, una Coca Cola. ¿Algo más o procedemos con la entrega?'")
        
        elif "ya está" in conv["usuario"].lower() or "no" in conv["usuario"].lower():
            print(f"🤖 Bot: 'Perfecto. ¿Retirás o querés delivery?'")
        
        elif "delivery" in conv["usuario"].lower():
            total = sum(item["price"] * item["quantity"] for item in pedido_actual)
            total += 1500  # delivery fee
            print(f"🤖 Bot: 'Listo! Pedido confirmado. Total: ${total} (incluye envío). Llega en 25-30 min.'")
    
    print(f"\n📋 Pedido final:")
    for item in pedido_actual:
        print(f"   - {item['name']} x{item['quantity']} (${item['price'] * item['quantity']})")

def demo_ventajas_ai():
    """Mostrar ventajas del enfoque AI"""
    
    print("\n\n🚀 VENTAJAS DEL ENFOQUE AI")
    print("=" * 50)
    
    ventajas = [
        {
            "aspecto": "Búsqueda",
            "tradicional": "if 'carne' in query: return empanadas_carne",
            "ai": "Entiende 'algo de carne', 'empas de carne', 'carne molida'"
        },
        {
            "aspecto": "Upsell",
            "tradicional": "if 'empanada' in items: suggest 'coca'",
            "ai": "Analiza contexto completo y sugiere lo más relevante"
        },
        {
            "aspecto": "Flexibilidad",
            "tradicional": "Reglas hardcodeadas, difícil de mantener",
            "ai": "Se adapta a nuevos productos sin cambiar código"
        },
        {
            "aspecto": "Experiencia",
            "tradicional": "Respuestas predecibles y robóticas",
            "ai": "Conversación natural y contextual"
        }
    ]
    
    for ventaja in ventajas:
        print(f"\n📊 {ventaja['aspecto'].upper()}:")
        print(f"   ❌ Tradicional: {ventaja['tradicional']}")
        print(f"   ✅ AI: {ventaja['ai']}")

async def main():
    """Función principal del demo"""
    try:
        await demo_ai_vs_traditional()
        await demo_conversacion_natural()
        demo_ventajas_ai()
        
        print("\n\n🎉 CONCLUSIÓN")
        print("=" * 50)
        print("✅ El sistema AI entiende lenguaje natural")
        print("✅ Se adapta a diferentes formas de expresarse")
        print("✅ Proporciona sugerencias contextuales inteligentes")
        print("✅ Mantiene conversaciones fluidas y naturales")
        print("✅ No requiere reglas hardcodeadas para cada caso")
        
    except Exception as e:
        print(f"❌ Error en demo: {e}")

if __name__ == "__main__":
    asyncio.run(main())

