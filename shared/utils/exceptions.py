#!/usr/bin/env python3
"""
PulpoAI Shared Utils Exceptions
Excepciones compartidas para utilidades
"""

class UtilsError(Exception):
    """Error base de utilidades"""
    pass

class ValidationError(UtilsError):
    """Error de validación"""
    pass

class FormatError(UtilsError):
    """Error de formateo"""
    pass

class HelperError(UtilsError):
    """Error de helper"""
    pass
