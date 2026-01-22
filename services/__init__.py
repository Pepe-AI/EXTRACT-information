"""
services - Servicios externos para el sistema de extracción
"""

from .gemini_service import GeminiFallbackService, get_gemini_fallback_service

__all__ = [
    'GeminiFallbackService',
    'get_gemini_fallback_service',
]
