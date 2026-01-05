"""
models/__init__.py - Exporta los modelos del paquete
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
    
    # Respuesta de extracción
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
    formatear_feedback_para_prompt,
    analizar_json_parcial,
)

__all__ = [
    'EscrituraPublica',
    'Titular',
    'Adquiriente',
    'Representante',
    'EscrituraPublicaFlexible',
    'TitularFlexible',
    'AdquirienteFlexible',
    'RepresentanteFlexible',
    'ExtractionResponse',
    'TipoTitular',
    'NO_ENCONTRADO',
    'get_campos_obligatorios',
    'get_campos_no_obligatorios',
    'validar_json_flexible',
    'generar_feedback_error',
    'formatear_feedback_para_prompt',
    'analizar_json_parcial',
]
