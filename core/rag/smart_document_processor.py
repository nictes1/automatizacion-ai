#!/usr/bin/env python3
"""
Procesador inteligente de documentos usando LLM
Extrae información estructurada de menús, catálogos, etc.
"""

import json
import logging
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MenuItem:
    """Item del menú estructurado"""
    nombre: str
    precio: str
    descripcion: str
    categoria: str
    disponibilidad: str = "disponible"

@dataclass
class StructuredMenu:
    """Menú estructurado"""
    restaurante: str
    categorias: Dict[str, List[MenuItem]]
    horarios: str = ""
    contacto: str = ""
    delivery: str = ""

class SmartDocumentProcessor:
    """
    Procesador inteligente que usa LLM para extraer información estructurada
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "llama3.1:8b"):
        self.ollama_url = ollama_url
        self.model = model
    
    def extract_menu_structure(self, text: str) -> StructuredMenu:
        """
        Extraer estructura del menú usando LLM
        """
        try:
            prompt = f"""
Analiza el siguiente menú de restaurante y extrae la información estructurada en formato JSON.

MENÚ:
{text}

Extrae la información en este formato JSON:
{{
  "restaurante": "nombre del restaurante",
  "categorias": {{
    "Pizzas": [
      {{
        "nombre": "Pizza Margherita",
        "precio": "$3.500",
        "descripcion": "descripción del plato",
        "categoria": "Pizzas"
      }}
    ],
    "Pastas": [
      {{
        "nombre": "Ravioles de Ricotta",
        "precio": "$2.500", 
        "descripcion": "descripción del plato",
        "categoria": "Pastas"
      }}
    ]
  }},
  "horarios": "horarios de atención",
  "contacto": "información de contacto",
  "delivery": "información de delivery"
}}

IMPORTANTE:
- Cada item del menú debe ser un objeto separado
- Incluye solo la información que esté en el texto
- Mantén los precios exactos como aparecen
- Agrupa por categorías lógicas
- Responde SOLO con el JSON, sin texto adicional
"""

            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "stream": False
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("message", {}).get("content", "")
                
                # Limpiar el contenido para extraer solo el JSON
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                
                if json_start != -1 and json_end != -1:
                    json_str = content[json_start:json_end]
                    menu_data = json.loads(json_str)
                    
                    # Convertir a StructuredMenu
                    return self._parse_menu_data(menu_data)
                else:
                    logger.error("No se pudo extraer JSON del response del LLM")
                    return self._fallback_parsing(text)
            else:
                logger.error(f"Error en LLM: {response.status_code}")
                return self._fallback_parsing(text)
                
        except Exception as e:
            logger.error(f"Error extrayendo estructura del menú: {e}")
            return self._fallback_parsing(text)
    
    def _parse_menu_data(self, menu_data: Dict[str, Any]) -> StructuredMenu:
        """Convertir datos del LLM a StructuredMenu"""
        try:
            categorias = {}
            
            for categoria, items in menu_data.get("categorias", {}).items():
                menu_items = []
                for item in items:
                    menu_item = MenuItem(
                        nombre=item.get("nombre", ""),
                        precio=item.get("precio", ""),
                        descripcion=item.get("descripcion", ""),
                        categoria=categoria
                    )
                    menu_items.append(menu_item)
                categorias[categoria] = menu_items
            
            return StructuredMenu(
                restaurante=menu_data.get("restaurante", ""),
                categorias=categorias,
                horarios=menu_data.get("horarios", ""),
                contacto=menu_data.get("contacto", ""),
                delivery=menu_data.get("delivery", "")
            )
            
        except Exception as e:
            logger.error(f"Error parseando datos del menú: {e}")
            return self._fallback_parsing("")
    
    def _fallback_parsing(self, text: str) -> StructuredMenu:
        """Parsing de fallback si el LLM falla"""
        logger.warning("Usando parsing de fallback")
        return StructuredMenu(
            restaurante="Restaurante",
            categorias={"General": [MenuItem("Item", "Precio", "Descripción", "General")]},
            horarios="",
            contacto="",
            delivery=""
        )
    
    def create_searchable_chunks(self, structured_menu: StructuredMenu) -> List[Dict[str, Any]]:
        """
        Crear chunks específicos para búsqueda
        Cada item del menú será un chunk independiente
        """
        chunks = []
        
        # Chunk para información general del restaurante
        if structured_menu.restaurante or structured_menu.horarios or structured_menu.contacto:
            general_info = f"Restaurante: {structured_menu.restaurante}\n"
            if structured_menu.horarios:
                general_info += f"Horarios: {structured_menu.horarios}\n"
            if structured_menu.contacto:
                general_info += f"Contacto: {structured_menu.contacto}\n"
            if structured_menu.delivery:
                general_info += f"Delivery: {structured_menu.delivery}\n"
            
            chunks.append({
                "content": general_info.strip(),
                "metadata": {
                    "type": "restaurant_info",
                    "restaurante": structured_menu.restaurante,
                    "categoria": "informacion_general"
                }
            })
        
        # Chunk para cada item del menú
        for categoria, items in structured_menu.categorias.items():
            for item in items:
                item_content = f"{item.nombre} - {item.precio}"
                if item.descripcion:
                    item_content += f"\n{item.descripcion}"
                
                chunks.append({
                    "content": item_content,
                    "metadata": {
                        "type": "menu_item",
                        "nombre": item.nombre,
                        "precio": item.precio,
                        "descripcion": item.descripcion,
                        "categoria": categoria,
                        "restaurante": structured_menu.restaurante
                    }
                })
        
        return chunks
    
    def process_document(self, text: str, document_type: str = "menu") -> List[Dict[str, Any]]:
        """
        Procesar documento y devolver chunks estructurados
        """
        try:
            if document_type == "menu":
                structured_data = self.extract_menu_structure(text)
                return self.create_searchable_chunks(structured_data)
            else:
                # Para otros tipos de documentos, usar chunking tradicional
                return [{"content": text, "metadata": {"type": "general"}}]
                
        except Exception as e:
            logger.error(f"Error procesando documento: {e}")
            return [{"content": text, "metadata": {"type": "error"}}]

# Función de conveniencia
def process_menu_with_llm(text: str) -> List[Dict[str, Any]]:
    """Procesar menú usando LLM para extracción inteligente"""
    processor = SmartDocumentProcessor()
    return processor.process_document(text, "menu")
