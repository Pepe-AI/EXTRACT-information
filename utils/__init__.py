"""
utils/__init__.py - Exporta utilidades del paquete

Contiene:
- text_processing: Limpieza de texto OCR y procesamiento de respuestas
- prompt_builder: Construcción de prompts para DeepSeek
"""

from .text_processing import (
    extract_think_block,
    extract_json_from_response,
    clean_ocr_text,
    truncate_text,
    format_for_prompt,
    process_deepseek_response,
    # NUEVO: Funciones de extracción por regex
    extraer_monto_operacion,
    extraer_numero_escritura,
    extraer_fecha_documento,
    extraer_datos_con_regex,
    merge_extractions,
    #Nuevas funciones del plan Z
    extraer_numero_notaria,
    extraer_nombre_notario,
    extraer_rfc_todos,
    extraer_curp_todos,
    extraer_municipio,
    extraer_estado,
    extraer_todos_regex,
    validar_dato_en_texto,
)

from .prompt_builder import (
    build_extraction_prompt,
    build_validation_prompt,
    estimate_tokens,
    limpiar_json_extra,  # NUEVO: Limpieza de campos extra
)

__all__ = [
    # text_processing
    'extract_think_block',
    'extract_json_from_response',
    'clean_ocr_text',
    'truncate_text',
    'format_for_prompt',
    'process_deepseek_response',
    # NUEVO: Extracción por regex
    'extraer_monto_operacion',
    'extraer_numero_escritura',
    'extraer_fecha_documento',
    'extraer_datos_con_regex',
    'merge_extractions',
    
    # prompt_builder
    'build_extraction_prompt',
    'build_validation_prompt',
    'estimate_tokens',
    'limpiar_json_extra',  # NUEVO
]
