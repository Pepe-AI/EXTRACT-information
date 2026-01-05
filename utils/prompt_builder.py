"""
utils/prompt_builder.py - Constructor de prompts para extracción de escrituras

ESTRATEGIA "DIVIDE Y VENCERÁS":
===============================
En lugar de un prompt genérico que maneje ambos casos (empresa/persona),
creamos prompts ESPECÍFICOS para cada tipo:

1. FASE 1: Clasificación
   - Prompt simple que SOLO detecta si es empresa o persona
   - Respuesta rápida (~2-5 segundos)
   - Alta precisión porque es tarea simple

2. FASE 2: Extracción
   - Si es EMPRESA → build_prompt_empresa()
   - Si es PERSONA → build_prompt_persona()
   - Cada prompt tiene la plantilla JSON EXACTA para ese tipo

¿Por qué esto reduce la variabilidad?
=====================================
1. El LLM no tiene que "decidir" la estructura - se la damos exacta
2. Menos ambigüedad = menos espacio para variación
3. Ejemplos específicos para cada caso
4. Validación más estricta porque sabemos qué esperar
"""

import json
from typing import Tuple, Dict, Any


# =============================================================================
# CONSTANTES
# =============================================================================

NO_ENCONTRADO = "NO SE ENCONTRÓ DATO"


# =============================================================================
# PROMPTS DE CLASIFICACIÓN (FASE 1)
# =============================================================================

SYSTEM_PROMPT_CLASIFICACION = """Eres un clasificador de documentos legales mexicanos.
Tu ÚNICA tarea es determinar si el VENDEDOR/ENAJENANTE es una EMPRESA o una PERSONA FÍSICA.

REGLAS SIMPLES:
- Si ves "S.A.", "S.A. de C.V.", "S. de R.L.", "SOCIEDAD", "CAPITAL VARIABLE" → EMPRESA
- Si el vendedor es solo un nombre de persona sin denominación social → PERSONA

Responde ÚNICAMENTE con la palabra "empresa" o "persona", nada más."""


def build_classification_prompt(document_text: str) -> Tuple[str, str]:
    """
    Construye el prompt para FASE 1: Clasificación.
    
    Este prompt es intencionalmente SIMPLE para maximizar precisión.
    
    Args:
        document_text: Texto del documento (primeros 3000 chars son suficientes)
        
    Returns:
        Tuple (system_prompt, user_prompt)
    """
    # Solo necesitamos el inicio del documento para clasificar
    texto_corto = document_text[:3000]
    
    user_prompt = f"""Analiza este fragmento y determina si el VENDEDOR es EMPRESA o PERSONA:

{texto_corto}

Responde solo con una palabra: "empresa" o "persona"."""

    return SYSTEM_PROMPT_CLASIFICACION, user_prompt


# =============================================================================
# PROMPTS PARA EMPRESA (FASE 2)
# =============================================================================

SYSTEM_PROMPT_EMPRESA = """Eres un extractor de datos de escrituras públicas mexicanas.
El documento que analizarás es de tipo EMPRESA (sociedad mercantil).

IMPORTANTE:
- El vendedor es una EMPRESA (S.A., S.A. de C.V., etc.)
- DEBE tener un representante legal
- Usa la plantilla JSON que te proporciono EXACTAMENTE
- No inventes campos, usa solo los de la plantilla
- Si no encuentras un dato, usa null o "NO SE ENCONTRÓ DATO"

Responde SOLO con el JSON, sin explicaciones."""


PLANTILLA_JSON_EMPRESA = {
    "notario": "NOMBRE_DEL_NOTARIO",
    "numero_escritura": 0,
    "fecha_documento": "DD de MES de AAAA",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "RAZÓN_SOCIAL_DE_LA_EMPRESA",
            "actua_por": "representante legal",
            "representante": {
                "nombre": "NOMBRE_DEL_REPRESENTANTE",
                "en_calidad": "apoderado legal",
                "escritura": "NÚMERO_ESCRITURA_DEL_PODER",
                "bis": False,
                "fecha_poder": "FECHA_DEL_PODER"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "NOMBRE_DEL_COMPRADOR",
            "estado_civil": "casado/soltero/etc",
            "tipo_sociedad": "sociedad conyugal o null",
            "edad": None,
            "rfc": "RFC_O_false",
            "curp": "CURP_O_false"
        }
    ],
    "monto_operacion": "$XXX,XXX.XX",
    "tipo_moneda": "MXN",
    "valor_catastral": None
}


EJEMPLO_EMPRESA = {
    "notario": "GUILLERMO LOZA RAMÍREZ",
    "numero_escritura": 18226,
    "fecha_documento": "22 de marzo de 2024",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "DESARROLLO TURISTICO LOS COCOS, SOCIEDAD ANÓNIMA DE CAPITAL VARIABLE",
            "actua_por": "representante legal",
            "representante": {
                "nombre": "HECTOR RAMÓN FLORES IBARRA",
                "en_calidad": "apoderado general",
                "escritura": "5058",
                "bis": False,
                "fecha_poder": "21 de noviembre de 1990"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "ANTONIO QUINTERO FLORES",
            "estado_civil": "casado",
            "tipo_sociedad": "sociedad legal",
            "edad": 57,
            "rfc": "QUFA670718TK2",
            "curp": "QUFA670718HJCNLN04"
        },
        {
            "nombre": "SILVIA SÁNCHEZ SÁNCHEZ",
            "estado_civil": "casada",
            "tipo_sociedad": "sociedad legal",
            "edad": 56,
            "rfc": "SASS680104FB7",
            "curp": "SASS680104MJCNNL03"
        }
    ],
    "monto_operacion": "$600,000.00",
    "tipo_moneda": "MXN",
    "valor_catastral": "$870,000.00"
}


def build_prompt_empresa(document_text: str) -> Tuple[str, str]:
    """
    Construye el prompt para extracción de documentos de EMPRESA.
    
    Este prompt:
    1. Le dice al modelo que es una EMPRESA (ya clasificada)
    2. Proporciona la plantilla JSON EXACTA
    3. Incluye un ejemplo completo
    4. Especifica claramente cada campo
    
    Returns:
        Tuple (system_prompt, user_prompt)
    """
    
    user_prompt = f"""
========================================
TIPO DE DOCUMENTO: EMPRESA (S.A. de C.V.)
========================================

Este documento es de una EMPRESA que vende a través de un representante legal.

========================================
PLANTILLA JSON A LLENAR:
========================================

```json
{json.dumps(PLANTILLA_JSON_EMPRESA, indent=2, ensure_ascii=False)}
```

========================================
EJEMPLO DE RESULTADO CORRECTO:
========================================

```json
{json.dumps(EJEMPLO_EMPRESA, indent=2, ensure_ascii=False)}
```

========================================
INSTRUCCIONES ESPECÍFICAS PARA EMPRESA:
========================================

1. "tipo_titular" SIEMPRE es "empresa"
2. El "nombre" del titular es la RAZÓN SOCIAL completa (con S.A. de C.V.)
3. "representante" es OBLIGATORIO para empresas
4. Busca la escritura del poder del representante
5. Si hay múltiples compradores, agrégalos todos a "adquirientes"

========================================
DOCUMENTO A ANALIZAR:
========================================

{document_text}

========================================
TU RESPUESTA (solo JSON):
========================================
"""

    return SYSTEM_PROMPT_EMPRESA, user_prompt


# =============================================================================
# PROMPTS PARA PERSONA FÍSICA (FASE 2)
# =============================================================================

SYSTEM_PROMPT_PERSONA = """Eres un extractor de datos de escrituras públicas mexicanas.
El documento que analizarás es de tipo PERSONA FÍSICA.

IMPORTANTE:
- El vendedor es una PERSONA FÍSICA (no empresa)
- El representante es OPCIONAL:
  * Si actúa por "derecho propio" → representante es null
  * Si actúa mediante apoderado → incluye los datos del representante
- Usa la plantilla JSON que te proporciono EXACTAMENTE
- No inventes campos, usa solo los de la plantilla
- Si no encuentras un dato, usa null o "NO SE ENCONTRÓ DATO"

Responde SOLO con el JSON, sin explicaciones."""


PLANTILLA_JSON_PERSONA = {
    "notario": "NOMBRE_DEL_NOTARIO",
    "numero_escritura": 0,
    "fecha_documento": "DD de MES de AAAA",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "NOMBRE_DEL_VENDEDOR",
            "actua_por": "derecho propio O representación",
            "representante": "OBJETO_CON_DATOS o null SI NO TIENE"
        }
    ],
    "adquirientes": [
        {
            "nombre": "NOMBRE_DEL_COMPRADOR",
            "estado_civil": "casado/soltero/etc",
            "tipo_sociedad": "sociedad conyugal o null",
            "edad": None,
            "rfc": "RFC_O_false",
            "curp": "CURP_O_false"
        }
    ],
    "monto_operacion": "$XXX,XXX.XX",
    "tipo_moneda": "MXN",
    "valor_catastral": None
}


EJEMPLO_PERSONA = {
    "notario": "María López Hernández",
    "numero_escritura": 5432,
    "fecha_documento": "15 de mayo de 2024",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "Juan Carlos Pérez García",
            "actua_por": "derecho propio",
            "representante": None  # Actúa por sí mismo, sin representante
        }
    ],
    "adquirientes": [
        {
            "nombre": "Ana María Rodríguez López",
            "estado_civil": "soltera",
            "tipo_sociedad": None,
            "edad": 35,
            "rfc": "ROLA890515ABC",
            "curp": "ROLA890515MDFRPN01"
        }
    ],
    "monto_operacion": "$1,200,000.00",
    "tipo_moneda": "MXN",
    "valor_catastral": "$950,000.00"
}

# Ejemplo alternativo: Persona física CON representante
EJEMPLO_PERSONA_CON_REPRESENTANTE = {
    "notario": "Roberto Sánchez Mora",
    "numero_escritura": 7891,
    "fecha_documento": "20 de junio de 2024",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "María Elena Gutiérrez Flores",
            "actua_por": "representación",  # Actúa mediante apoderado
            "representante": {
                "nombre": "Pedro Martínez Ruiz",
                "en_calidad": "apoderado general",
                "escritura": "3456",
                "bis": False,
                "fecha_poder": "10 de enero de 2023"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "Carlos López Mendoza",
            "estado_civil": "casado",
            "tipo_sociedad": "sociedad conyugal",
            "edad": 42,
            "rfc": "LOMC820315XYZ",
            "curp": False
        }
    ],
    "monto_operacion": "$2,500,000.00",
    "tipo_moneda": "MXN",
    "valor_catastral": None
}


def build_prompt_persona(document_text: str) -> Tuple[str, str]:
    """
    Construye el prompt para extracción de documentos de PERSONA FÍSICA.
    
    Este prompt:
    1. Le dice al modelo que es PERSONA FÍSICA (ya clasificada)
    2. Aclara que el representante es OPCIONAL
    3. Incluye DOS ejemplos: con y sin representante
    
    Returns:
        Tuple (system_prompt, user_prompt)
    """
    
    user_prompt = f"""
========================================
TIPO DE DOCUMENTO: PERSONA FÍSICA
========================================

Este documento es de una PERSONA FÍSICA.

========================================
PLANTILLA JSON A LLENAR:
========================================

```json
{json.dumps(PLANTILLA_JSON_PERSONA, indent=2, ensure_ascii=False)}
```

========================================
EJEMPLO 1 - PERSONA SIN REPRESENTANTE (actúa por derecho propio):
========================================

```json
{json.dumps(EJEMPLO_PERSONA, indent=2, ensure_ascii=False)}
```

========================================
EJEMPLO 2 - PERSONA CON REPRESENTANTE (actúa mediante apoderado):
========================================

```json
{json.dumps(EJEMPLO_PERSONA_CON_REPRESENTANTE, indent=2, ensure_ascii=False)}
```

========================================
INSTRUCCIONES ESPECÍFICAS PARA PERSONA:
========================================

1. "tipo_titular" SIEMPRE es "persona"
2. El representante es OPCIONAL para personas físicas:
   - Si el vendedor actúa "por derecho propio" → "representante": null
   - Si el vendedor actúa mediante apoderado → incluir objeto "representante" con sus datos
3. Busca frases como:
   - "por su propio derecho" → representante es null
   - "representado por", "mediante apoderado" → incluir representante
4. Si hay múltiples vendedores, agrégalos todos a "titulares"
5. Si hay múltiples compradores, agrégalos todos a "adquirientes"

========================================
DOCUMENTO A ANALIZAR:
========================================

{document_text}

========================================
TU RESPUESTA (solo JSON):
========================================
"""

    return SYSTEM_PROMPT_PERSONA, user_prompt


# =============================================================================
# FUNCIÓN PRINCIPAL DE CONSTRUCCIÓN DE PROMPT
# =============================================================================

def build_extraction_prompt(
    document_text: str,
    tipo_titular: str = None,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Construye el prompt de extracción según el tipo de titular.
    
    ESTRATEGIA DIVIDE Y VENCERÁS:
    =============================
    Si tipo_titular está definido:
        - "empresa" → usa build_prompt_empresa()
        - "persona" → usa build_prompt_persona()
    
    Si tipo_titular es None:
        - Usa prompt genérico (menos preciso, pero funciona)
    
    Args:
        document_text: Texto del documento a procesar
        tipo_titular: "empresa", "persona", o None
        include_examples: Si incluir ejemplos (default True)
        
    Returns:
        Tuple (system_prompt, user_prompt)
    """
    
    # Si sabemos el tipo, usar prompt específico
    if tipo_titular == "empresa":
        return build_prompt_empresa(document_text)
    elif tipo_titular == "persona":
        return build_prompt_persona(document_text)
    
    # Fallback: prompt genérico (menos preciso)
    return _build_prompt_generico(document_text, include_examples)


def _build_prompt_generico(document_text: str, include_examples: bool = True) -> Tuple[str, str]:
    """
    Prompt genérico (fallback si no se pudo clasificar).
    
    Este prompt es menos preciso porque tiene que manejar ambos casos.
    Se usa solo si la clasificación falló.
    """
    
    system_prompt = """Eres un extractor de datos de escrituras públicas mexicanas.

REGLAS:
1. Determina si el vendedor es EMPRESA o PERSONA
2. Si es empresa, DEBE tener representante
3. Si es persona, representante es null
4. Usa la estructura JSON que te proporciono

Responde SOLO con JSON."""

    plantilla = {
        "notario": "",
        "numero_escritura": 0,
        "fecha_documento": "",
        "tipo_titular": "empresa o persona",
        "titulares": [
            {
                "nombre": "",
                "actua_por": "",
                "representante": "objeto o null"
            }
        ],
        "adquirientes": [
            {
                "nombre": "",
                "estado_civil": "",
                "tipo_sociedad": None,
                "edad": None,
                "rfc": False,
                "curp": False
            }
        ],
        "monto_operacion": "",
        "tipo_moneda": "MXN",
        "valor_catastral": None
    }
    
    user_prompt = f"""
PLANTILLA JSON:
```json
{json.dumps(plantilla, indent=2, ensure_ascii=False)}
```

DOCUMENTO:
{document_text}

Responde SOLO con el JSON completo:"""

    return system_prompt, user_prompt


# =============================================================================
# PROMPT DE VALIDACIÓN (PARA RETRY)
# =============================================================================

def build_validation_prompt(
    json_anterior: Dict,
    error_validacion: str,
    document_text: str,
    tipo_titular: str = None,
    datos_regex: Dict = None
) -> Tuple[str, str]:
    """
    Construye prompt para corregir extracción fallida.
    
    MEJORA: Ahora usa análisis inteligente del feedback y respeta
    el tipo_titular clasificado en FASE 1.
    
    Args:
        json_anterior: JSON del intento anterior
        error_validacion: Error de Pydantic o mensaje
        document_text: Texto del documento (truncado)
        tipo_titular: Tipo clasificado ("empresa" o "persona") - IMPORTANTE
        datos_regex: Datos extraídos por regex (para dar pistas)
    
    Returns:
        Tuple (system_prompt, user_prompt)
    """
    from models.escritura import generar_feedback_error, formatear_feedback_para_prompt
    
    # Generar análisis inteligente
    analisis = generar_feedback_error(
        error_validacion=error_validacion,
        json_anterior=json_anterior,
        tipo_titular=tipo_titular
    )
    
    # System prompt específico según tipo
    if tipo_titular == "empresa":
        system_prompt = """Eres un corrector de datos JSON para escrituras de EMPRESAS.

REGLAS PARA EMPRESA:
1. tipo_titular SIEMPRE es "empresa" (NO lo cambies)
2. representante es OBLIGATORIO (toda empresa tiene uno)
3. numero_escritura es INTEGER (sin comillas)
4. Mantén los datos correctos, corrige solo los errores

El representante debe ser un OBJETO con:
- nombre: Nombre del apoderado
- en_calidad: "apoderado legal", "representante legal", etc.
- escritura: Número de escritura del poder
- bis: true o false
- fecha_poder: Fecha del poder"""

    else:  # persona
        system_prompt = """Eres un corrector de datos JSON para escrituras de PERSONAS FÍSICAS.

REGLAS PARA PERSONA:
1. tipo_titular SIEMPRE es "persona" (NO lo cambies)
2. representante es OPCIONAL:
   - Si actúa "por derecho propio" → null
   - Si tiene apoderado → incluir objeto representante
3. numero_escritura es INTEGER (sin comillas)
4. Mantén los datos correctos, corrige solo los errores"""

    # Formatear feedback
    feedback_texto = formatear_feedback_para_prompt(analisis)
    
    # Agregar datos de regex como pistas si están disponibles
    pistas_regex = ""
    if datos_regex:
        pistas = []
        if datos_regex.get("numero_escritura"):
            pistas.append(f"- numero_escritura: {datos_regex['numero_escritura']}")
        if datos_regex.get("monto_operacion"):
            pistas.append(f"- monto_operacion: {datos_regex['monto_operacion']}")
        if datos_regex.get("fecha_documento"):
            pistas.append(f"- fecha_documento: {datos_regex['fecha_documento']}")
        if datos_regex.get("notario"):
            pistas.append(f"- notario: {datos_regex['notario']}")
        
        if pistas:
            pistas_regex = "\n\n💡 PISTAS (datos extraídos por regex, úsalos):\n" + "\n".join(pistas)
    
    # User prompt
    user_prompt = f"""
{feedback_texto}
{pistas_regex}

========================================
DOCUMENTO ORIGINAL (fragmento):
========================================

{document_text[:1500]}

========================================
PLANTILLA DE REFERENCIA ({tipo_titular.upper() if tipo_titular else 'GENERAL'}):
========================================

"""
    
    # Agregar plantilla según tipo
    if tipo_titular == "empresa":
        user_prompt += f"""```json
{json.dumps(PLANTILLA_JSON_EMPRESA, indent=2, ensure_ascii=False)}
```"""
    else:
        user_prompt += f"""```json
{json.dumps(PLANTILLA_JSON_PERSONA, indent=2, ensure_ascii=False)}
```"""
    
    user_prompt += """

========================================
TU JSON CORREGIDO:
========================================

Corrige los problemas identificados y devuelve el JSON completo.
"""

    return system_prompt, user_prompt


# =============================================================================
# UTILIDADES
# =============================================================================

def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """Estima el número de tokens en un texto."""
    return int(len(text) / chars_per_token)


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DE PROMPTS ESPECÍFICOS")
    print("=" * 60)
    
    doc_sample = "ESCRITURA 18226... DESARROLLO TURISTICO LOS COCOS S.A. de C.V..."
    
    # Probar prompt de empresa
    system, user = build_extraction_prompt(doc_sample, tipo_titular="empresa")
    print("\n📋 PROMPT EMPRESA:")
    print(f"   System: {len(system)} chars")
    print(f"   User: {len(user)} chars")
    print(f"   Tokens estimados: ~{estimate_tokens(system + user)}")
    
    # Probar prompt de persona
    system, user = build_extraction_prompt(doc_sample, tipo_titular="persona")
    print("\n📋 PROMPT PERSONA:")
    print(f"   System: {len(system)} chars")
    print(f"   User: {len(user)} chars")
    print(f"   Tokens estimados: ~{estimate_tokens(system + user)}")
