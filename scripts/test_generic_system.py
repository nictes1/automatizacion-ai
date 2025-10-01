#!/usr/bin/env python3
"""
Script de Prueba del Sistema Genérico Multi-Vertical
Prueba la API genérica de documentos con diferentes verticales
"""

import os
import sys
import asyncio
import json
import requests
from pathlib import Path
from typing import Dict, Any, List
import logging

# Agregar el directorio raíz al path
sys.path.append(str(Path(__file__).parent.parent))

from core.search.hybrid_search import hybrid_search_engine, search_documents
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración
API_BASE_URL = "http://localhost:8002"
WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"  # Workspace de semilla

class GenericSystemTester:
    """Tester para el sistema genérico multi-vertical"""
    
    def __init__(self):
        self.api_base = API_BASE_URL
        self.workspace_id = WORKSPACE_ID
        self.session = requests.Session()
    
    def test_api_health(self) -> bool:
        """Prueba la salud de la API"""
        try:
            response = self.session.get(f"{self.api_base}/health")
            if response.status_code == 200:
                logger.info("✅ API está funcionando correctamente")
                return True
            else:
                logger.error(f"❌ API no responde correctamente: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Error conectando a la API: {e}")
            return False
    
    def test_verticals_config(self) -> bool:
        """Prueba la configuración de verticales"""
        try:
            response = self.session.get(f"{self.api_base}/verticals")
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Verticales soportados: {list(data['verticals'].keys())}")
                return True
            else:
                logger.error(f"❌ Error obteniendo verticales: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Error en test de verticales: {e}")
            return False
    
    def create_test_documents(self) -> Dict[str, str]:
        """Crea documentos de prueba para diferentes verticales"""
        
        # Documento de menú gastronómico
        menu_content = """
MENÚ RESTAURANTE EL PULPO

EMPANADAS
- Empanada de carne picante - $1.200
- Empanada de jamón y queso - $1.200
- Empanada de humita - $1.100
- Empanada de pollo - $1.150

PIZZAS
- Pizza Margherita (chica/mediana/grande) - $3.500/$4.500/$5.500
- Pizza Fugazza (chica/mediana/grande) - $3.200/$4.200/$5.200
- Pizza Napolitana (chica/mediana/grande) - $3.800/$4.800/$5.800

BEBIDAS
- Coca Cola 500ml - $800
- Agua mineral 500ml - $600
- Cerveza Quilmes 473ml - $1.000

POSTRES
- Flan casero - $800
- Tiramisú - $1.200
- Helado 3 bochas - $900

PROMOCIONES
- Docena de empanadas: 10% descuento
- Pizza + 2 empanadas: 15% descuento
- Combo familiar (2 pizzas + 6 empanadas + 4 bebidas): 20% descuento
"""
        
        # Documento de propiedades inmobiliarias
        properties_content = """
PROPIEDADES DISPONIBLES - INMOBILIARIA MAR DEL PLATA

VENTA
- Departamento 2 ambientes, Centro, $85.000 USD
  Características: 60m², balcón, cocina integrada, baño completo
  Amenities: Ascensor, portero, cochera opcional
  
- Casa 3 dormitorios, Playa Grande, $120.000 USD
  Características: 120m², jardín, garaje, 2 baños
  Amenities: Piscina comunitaria, seguridad 24hs
  
- Departamento 1 ambiente, Puerto, $65.000 USD
  Características: 45m², vista al mar, cocina americana
  Amenities: Ascensor, portero, terraza común

ALQUILER
- Departamento 2 ambientes, Centro, $800 USD/mes
  Características: 65m², amueblado, balcón
  Incluye: Expensas, servicios básicos
  
- Casa 4 dormitorios, Playa Grande, $1.500 USD/mes
  Características: 150m², jardín, piscina privada
  Incluye: Servicios, mantenimiento jardín

POLÍTICAS
- Comisión venta: 3% sobre precio de venta
- Comisión alquiler: 1 mes de alquiler
- Documentación requerida: DNI, recibo de sueldo, garantía
"""
        
        # Documento de servicios
        services_content = """
SERVICIOS PROFESIONALES - CONSULTORÍA TECNOLÓGICA

SERVICIOS DE DESARROLLO
- Desarrollo web personalizado - $150/hora
  Incluye: Diseño, programación, testing, deploy
  Tiempo estimado: 2-8 semanas según complejidad
  
- Desarrollo de aplicaciones móviles - $180/hora
  Incluye: iOS, Android, backend, testing
  Tiempo estimado: 4-12 semanas según funcionalidades
  
- Consultoría tecnológica - $200/hora
  Incluye: Análisis, arquitectura, recomendaciones
  Tiempo estimado: 1-4 semanas según proyecto

HORARIOS DE ATENCIÓN
- Lunes a Viernes: 9:00 - 18:00
- Sábados: 9:00 - 13:00
- Domingos: Cerrado
- Consultas de emergencia: 24/7 (recargo 50%)

POLÍTICAS DE SERVICIO
- Pago: 50% adelanto, 50% al finalizar
- Cancelaciones: 48hs de anticipación
- Modificaciones: Sin costo hasta 50% del proyecto
- Garantía: 90 días post entrega
"""
        
        return {
            "gastronomia_menu": menu_content,
            "inmobiliaria_properties": properties_content,
            "servicios_services": services_content
        }
    
    def upload_document(self, content: str, filename: str, vertical: str, document_type: str) -> Dict[str, Any]:
        """Sube un documento a la API"""
        try:
            # Crear archivo temporal
            temp_file = Path(f"temp_{filename}")
            temp_file.write_text(content, encoding='utf-8')
            
            # Preparar datos para upload
            files = {'file': (filename, open(temp_file, 'rb'), 'text/plain')}
            params = {
                'workspace_id': self.workspace_id,
                'vertical': vertical,
                'document_type': document_type
            }
            
            # Subir archivo
            response = self.session.post(
                f"{self.api_base}/documents/upload",
                files=files,
                params=params
            )
            
            # Limpiar archivo temporal
            temp_file.unlink()
            files['file'][1].close()
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Documento subido: {filename} ({vertical}/{document_type})")
                return data
            else:
                logger.error(f"❌ Error subiendo {filename}: {response.status_code} - {response.text}")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Error en upload de {filename}: {e}")
            return {}
    
    def test_document_upload(self) -> Dict[str, str]:
        """Prueba la subida de documentos para diferentes verticales"""
        logger.info("📤 Probando subida de documentos...")
        
        documents = self.create_test_documents()
        uploaded_docs = {}
        
        # Subir menú gastronómico
        result = self.upload_document(
            documents["gastronomia_menu"],
            "menu_restaurante.txt",
            "gastronomia",
            "menu"
        )
        if result:
            uploaded_docs["gastronomia_menu"] = result.get("document_id", "")
        
        # Subir propiedades inmobiliarias
        result = self.upload_document(
            documents["inmobiliaria_properties"],
            "propiedades_mdp.txt",
            "inmobiliaria",
            "properties"
        )
        if result:
            uploaded_docs["inmobiliaria_properties"] = result.get("document_id", "")
        
        # Subir servicios
        result = self.upload_document(
            documents["servicios_services"],
            "servicios_consultoria.txt",
            "servicios",
            "services"
        )
        if result:
            uploaded_docs["servicios_services"] = result.get("document_id", "")
        
        return uploaded_docs
    
    def test_document_listing(self) -> bool:
        """Prueba el listado de documentos"""
        try:
            response = self.session.get(
                f"{self.api_base}/documents",
                params={'workspace_id': self.workspace_id}
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Documentos listados: {len(data)} encontrados")
                
                # Mostrar resumen por vertical
                verticals = {}
                for doc in data:
                    vertical = doc.get('vertical', 'unknown')
                    if vertical not in verticals:
                        verticals[vertical] = 0
                    verticals[vertical] += 1
                
                for vertical, count in verticals.items():
                    logger.info(f"  - {vertical}: {count} documentos")
                
                return True
            else:
                logger.error(f"❌ Error listando documentos: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en test de listado: {e}")
            return False
    
    def test_search_functionality(self) -> bool:
        """Prueba la funcionalidad de búsqueda"""
        logger.info("🔍 Probando funcionalidad de búsqueda...")
        
        # Queries de prueba por vertical
        test_queries = [
            {
                "query": "empanadas de carne",
                "vertical": "gastronomia",
                "expected_keywords": ["empanada", "carne", "picante"]
            },
            {
                "query": "departamento 2 ambientes centro",
                "vertical": "inmobiliaria",
                "expected_keywords": ["departamento", "2 ambientes", "centro"]
            },
            {
                "query": "desarrollo web personalizado",
                "vertical": "servicios",
                "expected_keywords": ["desarrollo", "web", "personalizado"]
            }
        ]
        
        success_count = 0
        
        for test in test_queries:
            try:
                # Búsqueda normal
                response = self.session.post(
                    f"{self.api_base}/documents/search",
                    json={
                        "query": test["query"],
                        "workspace_id": self.workspace_id,
                        "vertical": test["vertical"],
                        "limit": 5
                    }
                )
                
                if response.status_code == 200:
                    results = response.json()
                    if results:
                        logger.info(f"✅ Búsqueda '{test['query']}' ({test['vertical']}): {len(results)} resultados")
                        success_count += 1
                    else:
                        logger.warning(f"⚠️ Búsqueda '{test['query']}' sin resultados")
                else:
                    logger.error(f"❌ Error en búsqueda '{test['query']}': {response.status_code}")
                
                # Búsqueda híbrida
                response = self.session.post(
                    f"{self.api_base}/documents/hybrid-search",
                    json={
                        "query": test["query"],
                        "workspace_id": self.workspace_id,
                        "vertical": test["vertical"],
                        "limit": 5,
                        "search_type": "hybrid"
                    }
                )
                
                if response.status_code == 200:
                    results = response.json()
                    if results:
                        logger.info(f"✅ Búsqueda híbrida '{test['query']}': {len(results)} resultados")
                    else:
                        logger.warning(f"⚠️ Búsqueda híbrida '{test['query']}' sin resultados")
                else:
                    logger.error(f"❌ Error en búsqueda híbrida '{test['query']}': {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Error en test de búsqueda '{test['query']}': {e}")
        
        return success_count > 0
    
    def test_statistics(self) -> bool:
        """Prueba las estadísticas del sistema"""
        try:
            response = self.session.get(
                f"{self.api_base}/documents/stats",
                params={'workspace_id': self.workspace_id}
            )
            
            if response.status_code == 200:
                stats = response.json()
                logger.info("✅ Estadísticas obtenidas:")
                logger.info(f"  - Total archivos: {stats.get('total_files', 0)}")
                logger.info(f"  - Total chunks: {stats.get('total_chunks', 0)}")
                logger.info(f"  - Total embeddings: {stats.get('total_embeddings', 0)}")
                logger.info(f"  - Verticales: {stats.get('total_verticals', 0)}")
                return True
            else:
                logger.error(f"❌ Error obteniendo estadísticas: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error en test de estadísticas: {e}")
            return False
    
    async def test_hybrid_search_direct(self) -> bool:
        """Prueba la búsqueda híbrida directamente"""
        try:
            logger.info("🔍 Probando búsqueda híbrida directa...")
            
            # Probar diferentes tipos de búsqueda
            search_types = ["bm25", "vector", "hybrid"]
            
            for search_type in search_types:
                results = await search_documents(
                    query="empanadas de carne",
                    workspace_id=self.workspace_id,
                    limit=3,
                    search_type=search_type
                )
                
                if results:
                    logger.info(f"✅ Búsqueda {search_type}: {len(results)} resultados")
                    for i, result in enumerate(results[:2]):  # Mostrar solo los primeros 2
                        logger.info(f"  {i+1}. {result.get('filename', 'N/A')} - Score: {result.get('similarity', 0):.3f}")
                else:
                    logger.warning(f"⚠️ Búsqueda {search_type} sin resultados")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en test de búsqueda híbrida directa: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Ejecuta todas las pruebas"""
        logger.info("🚀 Iniciando pruebas del sistema genérico...")
        
        tests = [
            ("Health Check", self.test_api_health),
            ("Configuración de Verticales", self.test_verticals_config),
            ("Subida de Documentos", lambda: bool(self.test_document_upload())),
            ("Listado de Documentos", self.test_document_listing),
            ("Funcionalidad de Búsqueda", self.test_search_functionality),
            ("Estadísticas", self.test_statistics),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            logger.info(f"\n📋 Ejecutando: {test_name}")
            try:
                if asyncio.iscoroutinefunction(test_func):
                    result = asyncio.run(test_func())
                else:
                    result = test_func()
                
                if result:
                    passed += 1
                    logger.info(f"✅ {test_name}: PASÓ")
                else:
                    logger.error(f"❌ {test_name}: FALLÓ")
            except Exception as e:
                logger.error(f"❌ {test_name}: ERROR - {e}")
        
        # Prueba adicional de búsqueda híbrida directa
        logger.info(f"\n📋 Ejecutando: Búsqueda Híbrida Directa")
        try:
            result = asyncio.run(self.test_hybrid_search_direct())
            if result:
                passed += 1
                logger.info(f"✅ Búsqueda Híbrida Directa: PASÓ")
            else:
                logger.error(f"❌ Búsqueda Híbrida Directa: FALLÓ")
            total += 1
        except Exception as e:
            logger.error(f"❌ Búsqueda Híbrida Directa: ERROR - {e}")
            total += 1
        
        # Resumen final
        logger.info(f"\n📊 RESUMEN DE PRUEBAS:")
        logger.info(f"✅ Pasaron: {passed}/{total}")
        logger.info(f"❌ Fallaron: {total - passed}/{total}")
        logger.info(f"📈 Porcentaje de éxito: {(passed/total)*100:.1f}%")
        
        return passed == total

def main():
    """Función principal"""
    tester = GenericSystemTester()
    
    # Verificar que la API esté corriendo
    if not tester.test_api_health():
        logger.error("❌ La API no está disponible. Asegúrate de que esté corriendo en http://localhost:8002")
        return False
    
    # Ejecutar todas las pruebas
    success = tester.run_all_tests()
    
    if success:
        logger.info("\n🎉 ¡Todas las pruebas pasaron! El sistema genérico está funcionando correctamente.")
    else:
        logger.error("\n💥 Algunas pruebas fallaron. Revisa los logs para más detalles.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
