"""
services/__init__.py - Exporta servicios del paquete
"""

from .ollama_service import (
    OllamaConfig,
    OllamaService,
    get_ollama_service
)

from .azure_ocr_service import (
    AzureConfig,
    AzureOCRService,
    get_ocr_service
)

__all__ = [
    'OllamaConfig',
    'OllamaService',
    'get_ollama_service',
    'AzureConfig',
    'AzureOCRService',
    'get_ocr_service'
]
