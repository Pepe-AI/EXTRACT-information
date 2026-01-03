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
    process_deepseek_response
)

from .prompt_builder import (
    build_extraction_prompt,
    build_validation_prompt,
    estimate_tokens
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
    'estimate_tokens'
]
