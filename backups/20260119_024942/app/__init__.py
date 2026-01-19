"""
app/__init__.py - Exporta componentes principales de la aplicación
"""

from .extractor import (
    EscrituraExtractor,
    ExtractionConfig,
    ExtractionResult,
    extract_escritura
)

__all__ = [
    'EscrituraExtractor',
    'ExtractionConfig',
    'ExtractionResult',
    'extract_escritura'
]
