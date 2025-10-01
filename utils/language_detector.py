#!/usr/bin/env python3
"""
Detector de Idioma Profesional
Usa múltiples métodos para detectar idioma con alta precisión
"""

import logging
from typing import Optional, Dict, Any, Tuple
import re

# Dependencias para detección de idioma
try:
    import langdetect
    from langdetect import detect, detect_langs, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

try:
    import fasttext
    FASTTEXT_AVAILABLE = True
except ImportError:
    FASTTEXT_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

logger = logging.getLogger(__name__)

class LanguageDetector:
    """Detector de idioma profesional con múltiples métodos"""
    
    def __init__(self):
        self._check_dependencies()
        self._load_models()
        
        # Palabras comunes por idioma (fallback)
        self.language_words = {
            'es': {
                'articles': ['el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas'],
                'prepositions': ['de', 'del', 'en', 'con', 'por', 'para', 'sobre', 'entre'],
                'conjunctions': ['y', 'o', 'pero', 'aunque', 'porque', 'que'],
                'common': ['es', 'son', 'está', 'están', 'tiene', 'tienen', 'puede', 'pueden']
            },
            'en': {
                'articles': ['the', 'a', 'an'],
                'prepositions': ['of', 'in', 'on', 'at', 'by', 'for', 'with', 'from'],
                'conjunctions': ['and', 'or', 'but', 'although', 'because', 'that'],
                'common': ['is', 'are', 'was', 'were', 'has', 'have', 'can', 'will']
            },
            'fr': {
                'articles': ['le', 'la', 'les', 'un', 'une', 'des'],
                'prepositions': ['de', 'du', 'dans', 'sur', 'avec', 'pour', 'par'],
                'conjunctions': ['et', 'ou', 'mais', 'bien', 'que', 'car'],
                'common': ['est', 'sont', 'était', 'étaient', 'a', 'ont', 'peut', 'peuvent']
            },
            'pt': {
                'articles': ['o', 'a', 'os', 'as', 'um', 'uma', 'uns', 'umas'],
                'prepositions': ['de', 'do', 'da', 'em', 'com', 'por', 'para', 'sobre'],
                'conjunctions': ['e', 'ou', 'mas', 'embora', 'porque', 'que'],
                'common': ['é', 'são', 'está', 'estão', 'tem', 'têm', 'pode', 'podem']
            }
        }
    
    def _check_dependencies(self):
        """Verifica qué dependencias están disponibles"""
        logger.info("🔍 Verificando dependencias de detección de idioma...")
        logger.info(f"  langdetect: {'✅' if LANGDETECT_AVAILABLE else '❌'}")
        logger.info(f"  fasttext: {'✅' if FASTTEXT_AVAILABLE else '❌'}")
        logger.info(f"  spacy: {'✅' if SPACY_AVAILABLE else '❌'}")
    
    def _load_models(self):
        """Carga modelos de detección de idioma"""
        self.fasttext_model = None
        
        if FASTTEXT_AVAILABLE:
            try:
                # Intentar cargar modelo preentrenado
                self.fasttext_model = fasttext.load_model('lid.176.bin')
                logger.info("✅ Modelo FastText cargado")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo cargar modelo FastText: {e}")
                self.fasttext_model = None
    
    def detect_language(self, text: str, min_confidence: float = 0.7) -> Tuple[str, float]:
        """
        Detecta el idioma del texto usando múltiples métodos
        
        Args:
            text: Texto a analizar
            min_confidence: Confianza mínima requerida
            
        Returns:
            Tuple[idioma, confianza]
        """
        if not text or len(text.strip()) < 10:
            return 'unknown', 0.0
        
        # Limpiar texto
        clean_text = self._clean_text(text)
        
        if len(clean_text) < 10:
            return 'unknown', 0.0
        
        # Intentar diferentes métodos
        results = []
        
        # 1. LangDetect (más preciso para textos largos)
        if LANGDETECT_AVAILABLE:
            result = self._detect_with_langdetect(clean_text)
            if result:
                results.append(result)
        
        # 2. FastText (bueno para textos cortos)
        if self.fasttext_model:
            result = self._detect_with_fasttext(clean_text)
            if result:
                results.append(result)
        
        # 3. Análisis de palabras (fallback)
        result = self._detect_with_word_analysis(clean_text)
        if result:
            results.append(result)
        
        # Combinar resultados
        if results:
            final_language, final_confidence = self._combine_results(results)
            
            # Verificar confianza mínima
            if final_confidence >= min_confidence:
                return final_language, final_confidence
            else:
                logger.warning(f"Confianza baja ({final_confidence:.2f}) para idioma {final_language}")
                return final_language, final_confidence
        
        return 'unknown', 0.0
    
    def _clean_text(self, text: str) -> str:
        """Limpia el texto para análisis"""
        # Remover caracteres especiales y números
        clean = re.sub(r'[^\w\s]', ' ', text)
        clean = re.sub(r'\d+', '', clean)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip().lower()
    
    def _detect_with_langdetect(self, text: str) -> Optional[Tuple[str, float]]:
        """Detecta idioma usando langdetect"""
        try:
            # Detectar idioma principal
            language = detect(text)
            
            # Obtener confianza
            languages = detect_langs(text)
            confidence = languages[0].prob if languages else 0.0
            
            return language, confidence
        except LangDetectException as e:
            logger.warning(f"Error en langdetect: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error inesperado en langdetect: {e}")
            return None
    
    def _detect_with_fasttext(self, text: str) -> Optional[Tuple[str, float]]:
        """Detecta idioma usando FastText"""
        try:
            # FastText requiere texto con salto de línea
            text_with_newline = text + '\n'
            predictions = self.fasttext_model.predict(text_with_newline, k=1)
            
            if predictions and len(predictions) > 0:
                language_label = predictions[0][0]
                confidence = predictions[1][0] if len(predictions) > 1 else 0.0
                
                # Convertir etiqueta (ej: '__label__es' -> 'es')
                language = language_label.replace('__label__', '')
                
                return language, confidence
        except Exception as e:
            logger.warning(f"Error en FastText: {e}")
        
        return None
    
    def _detect_with_word_analysis(self, text: str) -> Optional[Tuple[str, float]]:
        """Detecta idioma analizando palabras comunes"""
        words = text.split()
        if len(words) < 5:
            return None
        
        language_scores = {}
        
        for lang, word_categories in self.language_words.items():
            score = 0
            total_words = len(words)
            
            for category, word_list in word_categories.items():
                matches = sum(1 for word in words if word in word_list)
                score += matches / total_words
            
            language_scores[lang] = score
        
        if language_scores:
            best_language = max(language_scores, key=language_scores.get)
            best_score = language_scores[best_language]
            
            # Convertir score a confianza (0-1)
            confidence = min(best_score * 10, 1.0)  # Escalar score
            
            return best_language, confidence
        
        return None
    
    def _combine_results(self, results: list) -> Tuple[str, float]:
        """Combina resultados de diferentes métodos"""
        if not results:
            return 'unknown', 0.0
        
        # Si solo hay un resultado, usarlo
        if len(results) == 1:
            return results[0]
        
        # Contar votos por idioma
        language_votes = {}
        total_confidence = 0
        
        for language, confidence in results:
            if language not in language_votes:
                language_votes[language] = {'count': 0, 'confidence': 0}
            
            language_votes[language]['count'] += 1
            language_votes[language]['confidence'] += confidence
            total_confidence += confidence
        
        # Encontrar idioma con más votos
        best_language = max(language_votes, key=lambda x: language_votes[x]['count'])
        best_confidence = language_votes[best_language]['confidence'] / language_votes[best_language]['count']
        
        return best_language, best_confidence
    
    def get_supported_languages(self) -> list:
        """Retorna lista de idiomas soportados"""
        return ['es', 'en', 'fr', 'pt', 'de', 'it', 'ru', 'zh', 'ja', 'ko']
    
    def is_supported_language(self, language: str) -> bool:
        """Verifica si un idioma está soportado"""
        return language in self.get_supported_languages()
    
    def get_language_name(self, language_code: str) -> str:
        """Convierte código de idioma a nombre"""
        language_names = {
            'es': 'Español',
            'en': 'Inglés',
            'fr': 'Francés',
            'pt': 'Portugués',
            'de': 'Alemán',
            'it': 'Italiano',
            'ru': 'Ruso',
            'zh': 'Chino',
            'ja': 'Japonés',
            'ko': 'Coreano'
        }
        return language_names.get(language_code, language_code)

# Función de utilidad para instalar dependencias
def install_language_detection_dependencies():
    """Instala dependencias para detección de idioma"""
    import subprocess
    import sys
    
    dependencies = [
        "langdetect",
        "fasttext",
        "spacy"
    ]
    
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"✅ {dep} instalado")
        except subprocess.CalledProcessError:
            print(f"❌ Error instalando {dep}")

if __name__ == "__main__":
    # Prueba del detector
    detector = LanguageDetector()
    
    test_texts = [
        "Hola, este es un texto en español para probar la detección de idioma.",
        "Hello, this is an English text to test language detection.",
        "Bonjour, ceci est un texte français pour tester la détection de langue.",
        "Olá, este é um texto em português para testar a detecção de idioma."
    ]
    
    print("🧪 Probando detector de idioma...")
    for text in test_texts:
        language, confidence = detector.detect_language(text)
        language_name = detector.get_language_name(language)
        print(f"  '{text[:50]}...' -> {language_name} ({confidence:.2f})")

