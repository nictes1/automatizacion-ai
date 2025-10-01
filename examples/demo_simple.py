#!/usr/bin/env python3
"""
Demo simplificada del sistema Slot Filling + RAG
Sin dependencias externas para demostración
"""

import asyncio
import json
import time
from typing import List, Dict, Any

class MockRAGSystem:
    """Sistema RAG simulado para la demo"""
    
    def __init__(self):
        self.menu_data = [
            {
                "content": "Pizza Margherita - $3.500 - Pizza clásica con salsa de tomate, mozzarella fresca y albahaca",
                "metadata": {
                    "type": "menu_item",
                    "nombre": "Pizza Margherita",
                    "precio": "$3.500",
                    "descripcion": "Pizza clásica con salsa de tomate, mozzarella fresca y albahaca",
                    "categoria": "PIZZAS"
                }
            },
            {
                "content": "Pizza Napolitana - $4.000 - Pizza con salsa de tomate, mozzarella, anchoas y aceitunas",
                "metadata": {
                    "type": "menu_item",
                    "nombre": "Pizza Napolitana",
                    "precio": "$4.000",
                    "descripcion": "Pizza con salsa de tomate, mozzarella, anchoas y aceitunas",
                    "categoria": "PIZZAS"
                }
            },
            {
                "content": "Empanadas de Carne - $800 - Empanadas caseras rellenas de carne molida con cebolla y especias",
                "metadata": {
                    "type": "menu_item",
                    "nombre": "Empanadas de Carne",
                    "precio": "$800",
                    "descripcion": "Empanadas caseras rellenas de carne molida con cebolla y especias",
                    "categoria": "EMPANADAS"
                }
            },
            {
                "content": "Coca Cola - $800 - Bebida gaseosa de 500ml",
                "metadata": {
                    "type": "menu_item",
                    "nombre": "Coca Cola",
                    "precio": "$800",
                    "descripcion": "Bebida gaseosa de 500ml",
                    "categoria": "BEBIDAS"
                }
            }
        ]
    
    async def search_similar(self, query: str, workspace_id: str = None, limit: int = 10, similarity_threshold: float = 0.7):
        """Búsqueda simulada"""
        query_lower = query.lower()
        results = []
        
        for item in self.menu_data:
            content = item['content'].lower()
            metadata = item['metadata']
            
            # Simular relevancia
            if any(word in content for word in query_lower.split()):
                results.append(item)
        
        return results[:limit]

class SimpleSlotFillingDemo:
    """Demo simplificada del sistema de slot filling"""
    
    def __init__(self):
        self.rag_system = MockRAGSystem()
        self.current_state = "START"
        self.slots = {}
    
    async def demo_conversation_flow(self):
        """Demo del flujo completo de conversación"""
        print("🎯 Demo: Slot Filling + RAG para Gastronomía")
        print("=" * 60)
        
        # Simular conversación
        conversation_messages = [
            "Hola, quiero hacer un pedido",
            "quiero una pizza",
            "una margherita",
            "sí, quiero una coca cola",
            "retiro",
            "efectivo"
        ]
        
        print(f"\n📋 Flujo de conversación:")
        print("-" * 40)
        
        for i, user_message in enumerate(conversation_messages):
            print(f"\n👤 Usuario: {user_message}")
            
            # Procesar mensaje
            response = await self._process_message(user_message)
            
            print(f"🤖 Asistente: {response}")
            
            # Mostrar estado actual
            print(f"📊 Estado: {self.current_state}")
            filled_slots = {name: value for name, value in self.slots.items() if value}
            if filled_slots:
                print(f"🎯 Slots llenos: {filled_slots}")
            
            time.sleep(1)  # Pausa para efecto visual
        
        # Mostrar resultado final
        print(f"\n✅ Pedido completado!")
        print(f"📋 Resumen final:")
        for name, value in self.slots.items():
            if value:
                print(f"   {name}: {value}")
    
    async def _process_message(self, user_message: str) -> str:
        """Procesar mensaje del usuario"""
        
        # Detectar intención
        intent = self._detect_intent(user_message)
        
        # Actualizar slots
        self._update_slots(intent, user_message)
        
        # Determinar siguiente estado
        self._determine_next_state(intent)
        
        # Generar respuesta
        return self._generate_response()
    
    def _detect_intent(self, user_message: str) -> str:
        """Detectar intención del usuario"""
        user_lower = user_message.lower()
        
        if any(word in user_lower for word in ['hola', 'buenas']):
            return 'saludo'
        elif any(word in user_lower for word in ['quiero', 'necesito', 'pedido']):
            return 'pedido'
        elif any(word in user_lower for word in ['pizza', 'margherita', 'napolitana']):
            return 'seleccion_item'
        elif any(word in user_lower for word in ['coca', 'bebida']):
            return 'agregar_extra'
        elif any(word in user_lower for word in ['retiro', 'delivery']):
            return 'metodo_entrega'
        elif any(word in user_lower for word in ['efectivo', 'tarjeta', 'qr']):
            return 'metodo_pago'
        elif any(word in user_lower for word in ['sí', 'si', 'ok']):
            return 'confirmacion'
        else:
            return 'informacion'
    
    def _update_slots(self, intent: str, user_message: str):
        """Actualizar slots según la intención"""
        
        if intent == 'pedido':
            if 'pizza' in user_message.lower():
                self.slots['categoria'] = 'pizzas'
        
        elif intent == 'seleccion_item':
            if 'margherita' in user_message.lower():
                self.slots['items'] = [{'name': 'Pizza Margherita', 'price': 3500, 'quantity': 1}]
        
        elif intent == 'agregar_extra':
            if 'coca' in user_message.lower():
                self.slots['extras'] = [{'name': 'Coca Cola', 'price': 800, 'quantity': 1}]
        
        elif intent == 'metodo_entrega':
            if 'retiro' in user_message.lower():
                self.slots['metodo_entrega'] = 'retiro'
            elif 'delivery' in user_message.lower():
                self.slots['metodo_entrega'] = 'delivery'
        
        elif intent == 'metodo_pago':
            if 'efectivo' in user_message.lower():
                self.slots['metodo_pago'] = 'efectivo'
    
    def _determine_next_state(self, intent: str):
        """Determinar siguiente estado"""
        if self.current_state == 'START':
            self.current_state = 'PEDIR_CATEGORIA'
        elif self.current_state == 'PEDIR_CATEGORIA' and self.slots.get('categoria'):
            self.current_state = 'ARMAR_ITEMS'
        elif self.current_state == 'ARMAR_ITEMS' and self.slots.get('items'):
            self.current_state = 'UPSELL'
        elif self.current_state == 'UPSELL' and intent in ['agregar_extra', 'confirmacion']:
            self.current_state = 'ENTREGA'
        elif self.current_state == 'ENTREGA' and self.slots.get('metodo_entrega'):
            self.current_state = 'PAGO'
        elif self.current_state == 'PAGO' and self.slots.get('metodo_pago'):
            self.current_state = 'CONFIRMAR'
    
    def _generate_response(self) -> str:
        """Generar respuesta basada en el estado actual"""
        if self.current_state == 'START':
            return "¡Hola! ¿En qué te puedo ayudar? ¿Querés hacer un pedido?"
        
        elif self.current_state == 'PEDIR_CATEGORIA':
            return "¿De qué categoría querés pedir? Tenemos pizzas, empanadas, pastas y más."
        
        elif self.current_state == 'ARMAR_ITEMS':
            categoria = self.slots.get('categoria', '')
            return f"Perfecto, {categoria}. Decime qué querés específicamente."
        
        elif self.current_state == 'UPSELL':
            return "¿Querés agregar alguna bebida o postre?"
        
        elif self.current_state == 'ENTREGA':
            return "¿Retirás por el local o querés delivery?"
        
        elif self.current_state == 'PAGO':
            return "¿Cómo pagás? (efectivo/QR/tarjeta)"
        
        elif self.current_state == 'CONFIRMAR':
            # Generar resumen
            items = self.slots.get('items', [])
            extras = self.slots.get('extras', [])
            metodo_entrega = self.slots.get('metodo_entrega', '')
            metodo_pago = self.slots.get('metodo_pago', '')
            
            total = sum(item['price'] * item['quantity'] for item in items + extras)
            
            resumen = f"Pedido confirmado:\n"
            for item in items:
                resumen += f"- {item['name']} x{item['quantity']} (${item['price']})\n"
            for extra in extras:
                resumen += f"- {extra['name']} x{extra['quantity']} (${extra['price']})\n"
            resumen += f"Total: ${total}\n"
            resumen += f"Entrega: {metodo_entrega}\n"
            resumen += f"Pago: {metodo_pago}\n"
            resumen += f"Tiempo estimado: 30 minutos"
            
            return resumen
        
        else:
            return "¿En qué más te puedo ayudar?"
    
    async def demo_rag_integration(self):
        """Demo de integración con RAG"""
        print(f"\n🔍 Demo: Integración RAG como herramienta")
        print("=" * 50)
        
        # Simular búsqueda en menú
        queries = [
            "pizzas",
            "pizza margherita",
            "bebidas",
            "menos de $4000"
        ]
        
        for query in queries:
            print(f"\n🔍 Búsqueda: '{query}'")
            
            # Usar RAG como herramienta
            results = await self.rag_system.search_similar(query)
            
            print(f"📋 Resultados encontrados: {len(results)}")
            for i, result in enumerate(results[:3]):
                metadata = result.get('metadata', {})
                print(f"  {i+1}. {metadata.get('nombre', '')} - {metadata.get('precio', '')}")
                print(f"     {metadata.get('descripcion', '')[:60]}...")
    
    async def demo_debounce_concept(self):
        """Demo del concepto de debounce"""
        print(f"\n⏱️ Demo: Concepto de Debounce")
        print("=" * 40)
        
        print("📨 Simulando mensajes rápidos del usuario:")
        messages = [
            "Hola",
            "quiero hacer",
            "un pedido",
            "de pizzas"
        ]
        
        for i, message in enumerate(messages):
            print(f"  {i+1}. {message}")
            time.sleep(0.5)  # Simular mensajes rápidos
        
        print(f"\n🔄 Sistema de debounce:")
        print("  - Acumula mensajes durante 10 segundos")
        print("  - Procesa el texto agregado: 'Hola quiero hacer un pedido de pizzas'")
        print("  - Evita spam y mejora la experiencia")
        
        print(f"\n📤 Resultado final:")
        print("  Texto procesado: 'Hola quiero hacer un pedido de pizzas'")
        print("  Intención detectada: pedido")
        print("  Slots extraídos: categoria=pizzas")

async def main():
    """Función principal de la demo"""
    print("🚀 Demo Completa: Slot Filling + RAG + Debounce")
    print("=" * 70)
    
    demo = SimpleSlotFillingDemo()
    
    # Ejecutar demos
    await demo.demo_conversation_flow()
    await demo.demo_rag_integration()
    await demo.demo_debounce_concept()
    
    print(f"\n✅ Demo completada!")
    print(f"\n💡 Conclusiones:")
    print("- El slot filling guía al usuario paso a paso")
    print("- El RAG proporciona información precisa del menú")
    print("- El debounce evita spam y mejora la experiencia")
    print("- El sistema es escalable y multitenant")
    
    print(f"\n🎯 Próximos pasos:")
    print("1. Configurar servicios (PostgreSQL, Redis, Weaviate)")
    print("2. Implementar integración con Twilio")
    print("3. Desplegar en producción")
    print("4. Configurar múltiples workspaces")

if __name__ == "__main__":
    asyncio.run(main())
