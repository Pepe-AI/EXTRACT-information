"""
utils/__init__.py - Exporta utilidades del paquete

Contiene:
- text_processing: Limpieza de texto OCR y procesamiento de respuestas
- prompt_builder: Construcción de prompts para DeepSeek
- clasificador: Clasificación de documentos (Fase 1 del sistema híbrido)
"""

from .text_processing import (
    extract_think_block,
    extract_json_from_response,
    clean_ocr_text,
    truncate_text,
    format_for_prompt,
    process_deepseek_response
)

from .prompt_builder import (
    build_extraction_prompt,
    build_validation_prompt,
    estimate_tokens
)

from .clasificador import (
    clasificar_documento,
    ResultadoClasificacion,
    detectar_tipo_por_nombre,
    validar_representante_no_es_institucion,
)

__all__ = [
    # text_processing
    'extract_think_block',
    'extract_json_from_response',
    'clean_ocr_text',
    'truncate_text',
    'format_for_prompt',
    'process_deepseek_response',
    
    # prompt_builder
    'build_extraction_prompt',
    'build_validation_prompt',
    'estimate_tokens',
    
    # clasificador (NUEVO)
    'clasificar_documento',
    'ResultadoClasificacion',
    'detectar_tipo_por_nombre',
    'validar_representante_no_es_institucion',
]
