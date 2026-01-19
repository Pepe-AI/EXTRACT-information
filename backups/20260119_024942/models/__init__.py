"""
models/__init__.py - Exporta los modelos del paquete
"""

from .escritura import (
    # Modelos estrictos
    EscrituraPublica,
    Titular,
    Adquiriente,
    Representante,
    Notario,  # NUEVO - Modelo estricto de notario
    
    # Modelos flexibles
    EscrituraPublicaFlexible,
    TitularFlexible,
    AdquirienteFlexible,
    RepresentanteFlexible,
    NotarioFlexible,  # NUEVO - Modelo flexible de notario
    
    # Respuesta de extracción
    ExtractionResponse,
    
    # Enums y constantes
    TipoTitular,
    NO_ENCONTRADO,
    
    # Funciones auxiliares
    get_campos_obligatorios,
    get_campos_no_obligatorios,
    validar_json_flexible,
    generar_feedback_error,
    analizar_json_parcial,
)

__all__ = [
    # Modelos estrictos
    'EscrituraPublica',
    'Titular',
    'Adquiriente',
    'Representante',
    'Notario',  # NUEVO
    
    # Modelos flexibles
    'EscrituraPublicaFlexible',
    'TitularFlexible',
    'AdquirienteFlexible',
    'RepresentanteFlexible',
    'NotarioFlexible',  # NUEVO
    
    # Enums y constantes
    'TipoTitular',
    'NO_ENCONTRADO',
    
    # Funciones auxiliares
    'get_campos_obligatorios',
    'get_campos_no_obligatorios',
    'validar_json_flexible',
    'generar_feedback_error',
    'analizar_json_parcial',
]
