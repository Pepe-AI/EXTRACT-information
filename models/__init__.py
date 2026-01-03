"""
models/__init__.py - Exporta los modelos del paquete

MODELOS:
========
- EscrituraPublica: Modelo ESTRICTO (campos obligatorios)
- EscrituraPublicaFlexible: Modelo FLEXIBLE (todo opcional)
- Titular, Adquiriente, Representante: Modelos anidados
"""

from .escritura import (
    # Modelos estrictos
    EscrituraPublica,
    Titular,
    Adquiriente,
    Representante,
    
    # Modelos flexibles
    EscrituraPublicaFlexible,
    TitularFlexible,
    AdquirienteFlexible,
    RepresentanteFlexible,
    
    # Respuesta
    ExtractionResponse,
    
    # Enums
    TipoTitular,
    
    # Constantes
    NO_ENCONTRADO,
    
    # Funciones
    get_campos_obligatorios,
    get_campos_no_obligatorios,
    validar_json_flexible,
    generar_feedback_error,
    analizar_json_parcial  # Nueva función
)

__all__ = [
    # Modelos estrictos
    'EscrituraPublica',
    'Titular',
    'Adquiriente',
    'Representante',
    
    # Modelos flexibles
    'EscrituraPublicaFlexible',
    'TitularFlexible',
    'AdquirienteFlexible',
    'RepresentanteFlexible',
    
    # Respuesta
    'ExtractionResponse',
    
    # Enums y constantes
    'TipoTitular',
    'NO_ENCONTRADO',
    
    # Funciones
    'get_campos_obligatorios',
    'get_campos_no_obligatorios',
    'validar_json_flexible',
    'generar_feedback_error',
    'analizar_json_parcial'
]
