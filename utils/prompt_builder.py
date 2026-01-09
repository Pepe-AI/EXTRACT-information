"""
utils/prompt_builder.py - Constructor de prompts para extracción de escrituras

VERSIÓN MEJORADA - SISTEMA HÍBRIDO (Plan A + C)
===============================================

Este módulo construye los prompts que se envían a DeepSeek R1.
Ahora soporta el flujo de DOS FASES:

FASE 1: Clasificación (usa utils/clasificador.py)
- Determina si el titular es empresa o persona
- Identifica quién es titular y quién es representante

FASE 2: Extracción (usa este módulo)
- Construye prompt específico según la clasificación
- Incluye la clasificación como "información confirmada"
- El LLM ya sabe quién es quién, solo extrae detalles

MEJORAS RESPECTO A LA VERSIÓN ANTERIOR:
=======================================
1. Prompts específicos para EMPRESA vs PERSONA
2. Ejemplos de instituciones gubernamentales (no solo S.A. de C.V.)
3. Errores comunes documentados con ejemplos
4. Soporte para clasificación previa
"""

import json
from typing import Tuple, Dict, Any, Optional


# =============================================================================
# CONSTANTES
# =============================================================================

NO_ENCONTRADO = "NO SE ENCONTRÓ DATO"


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

SYSTEM_PROMPT_EXTRACCION = """Eres un extractor de datos especializado en documentos notariales mexicanos.

Tu tarea es analizar escrituras públicas y extraer información estructurada en formato JSON.

REGLAS FUNDAMENTALES:
1. Responde SOLO con JSON válido, sin texto adicional antes o después
2. Usa EXACTAMENTE los nombres de campos que se te indican
3. Si no encuentras un dato, usa null o "NO SE ENCONTRÓ DATO"
4. numero_escritura debe ser INTEGER (sin comillas)
5. El REPRESENTANTE siempre es una PERSONA FÍSICA (nunca una institución)

REGLA CRÍTICA PARA tipo_titular:
- "empresa" = Cualquier entidad que NO sea persona física:
  * Sociedades: S.A., S.A. de C.V., S. de R.L.
  * Instituciones: Instituto, Secretaría, Gobierno
  * Organismos: INFONAVIT, FOVISSSTE, INSS
  * Fideicomisos, Fondos, Asociaciones (A.C.)
  
- "persona" = SOLO personas físicas actuando por sí mismas"""


SYSTEM_PROMPT_EMPRESA = """Eres un extractor de datos de escrituras públicas mexicanas.
El documento que analizarás es de una EMPRESA o INSTITUCIÓN.

REGLAS PARA EMPRESA/INSTITUCIÓN:
1. tipo_titular SIEMPRE es "empresa"
2. El representante es OBLIGATORIO (quien firma por la entidad)
3. El representante es una PERSONA FÍSICA, nunca otra institución
4. numero_escritura es INTEGER (sin comillas)

Responde SOLO con el JSON, sin explicaciones."""


SYSTEM_PROMPT_PERSONA = """Eres un extractor de datos de escrituras públicas mexicanas.
El documento que analizarás es de una PERSONA FÍSICA.

REGLAS PARA PERSONA:
1. tipo_titular SIEMPRE es "persona"
2. El representante es OPCIONAL:
   - Si actúa "por derecho propio" → representante es null
   - Si tiene apoderado → incluir datos del representante
3. numero_escritura es INTEGER (sin comillas)

Responde SOLO con el JSON, sin explicaciones."""


# =============================================================================
# PLANTILLAS JSON
# =============================================================================

PLANTILLA_JSON_EMPRESA = {
    "notario": "NOMBRE_DEL_NOTARIO",
    "numero_escritura": 0,
    "fecha_documento": "DD de MES de AAAA",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "RAZÓN_SOCIAL_O_NOMBRE_DE_LA_INSTITUCIÓN",
            "actua_por": "representación",
            "representante": {
                "nombre": "NOMBRE_DE_LA_PERSONA_QUE_FIRMA",
                "en_calidad": "apoderado legal / representante / director",
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


PLANTILLA_JSON_PERSONA = {
    "notario": "NOMBRE_DEL_NOTARIO",
    "numero_escritura": 0,
    "fecha_documento": "DD de MES de AAAA",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "NOMBRE_DE_LA_PERSONA_FÍSICA",
            "actua_por": "derecho propio",
            "representante": None
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


# =============================================================================
# EJEMPLOS COMPLETOS
# =============================================================================

EJEMPLO_EMPRESA_SA = {
    "notario": "Lic. Roberto García Mendoza",
    "numero_escritura": 3125,
    "fecha_documento": "15 de mayo de 2024",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "Inmobiliaria del Norte S.A. de C.V.",
            "actua_por": "representación",
            "representante": {
                "nombre": "Juan Carlos Pérez López",
                "en_calidad": "apoderado legal",
                "escritura": "1234",
                "bis": False,
                "fecha_poder": "10 de enero de 2020"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "Carlos Rodríguez Martínez",
            "estado_civil": "casado",
            "tipo_sociedad": "sociedad conyugal",
            "edad": 45,
            "rfc": "ROMC790515ABC",
            "curp": "ROMC790515HDFRRL09"
        }
    ],
    "monto_operacion": "$1,500,000.00",
    "tipo_moneda": "MXN",
    "valor_catastral": "$800,000.00"
}


EJEMPLO_INSTITUCION_GOBIERNO = {
    "notario": "Lic. Rigoberto Ochoa Torres",
    "numero_escritura": 2397,
    "fecha_documento": "5 de mayo de 2023",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "Instituto Nacional del Suelo Sustentable (INSS)",
            "actua_por": "representación",
            "representante": {
                "nombre": "Ernesto Padilla Aceves",
                "en_calidad": "Representante Regional",
                "escritura": "NO SE ENCONTRÓ DATO",
                "bis": False,
                "fecha_poder": "5 de mayo de 2023"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "Angelita Pérez Soto",
            "estado_civil": "casada",
            "tipo_sociedad": None,
            "edad": None,
            "rfc": False,
            "curp": False
        }
    ],
    "monto_operacion": "$8,654.00",
    "tipo_moneda": "MXN",
    "valor_catastral": None
}


EJEMPLO_PERSONA_FISICA = {
    "notario": "Lic. María López Hernández",
    "numero_escritura": 5432,
    "fecha_documento": "20 de junio de 2024",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "Ana García López",
            "actua_por": "derecho propio",
            "representante": None
        }
    ],
    "adquirientes": [
        {
            "nombre": "Pedro Sánchez Ruiz",
            "estado_civil": "soltero",
            "tipo_sociedad": None,
            "edad": 35,
            "rfc": "SARP890101XYZ",
            "curp": False
        }
    ],
    "monto_operacion": "$500,000.00",
    "tipo_moneda": "MXN",
    "valor_catastral": "$300,000.00"
}


EJEMPLO_PERSONA_CON_APODERADO = {
    "notario": "Lic. Fernando Ruiz Castillo",
    "numero_escritura": 7891,
    "fecha_documento": "10 de julio de 2024",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "María Elena Gutiérrez Flores",
            "actua_por": "representación",
            "representante": {
                "nombre": "Roberto Martínez García",
                "en_calidad": "apoderado general",
                "escritura": "3456",
                "bis": False,
                "fecha_poder": "15 de marzo de 2022"
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


# =============================================================================
# ERRORES COMUNES
# =============================================================================

def _build_errores_comunes() -> str:
    """
    Lista de errores comunes que el LLM debe evitar.
    
    Estos errores fueron identificados en extracciones reales.
    """
    
    return """
========================================
⚠️ ERRORES QUE NO DEBES COMETER:
========================================

ERROR 1 - Poner tipo_titular dentro de cada titular:
❌ INCORRECTO:
{
  "titulares": [
    { "tipo_titular": "empresa", "nombre": "..." }
  ]
}

✅ CORRECTO:
{
  "tipo_titular": "empresa",
  "titulares": [
    { "nombre": "..." }
  ]
}

----------------------------------------

ERROR 2 - Confundir TITULAR con REPRESENTANTE:
Cuando una institución actúa a través de una persona:
- TITULAR = La institución/empresa (quien tiene el derecho)
- REPRESENTANTE = La persona física que firma

❌ INCORRECTO (al revés):
{
  "tipo_titular": "persona",
  "titulares": [
    {
      "nombre": "Ernesto Padilla",
      "representante": { "nombre": "Instituto Nacional..." }
    }
  ]
}

✅ CORRECTO:
{
  "tipo_titular": "empresa",
  "titulares": [
    {
      "nombre": "Instituto Nacional del Suelo Sustentable",
      "representante": { "nombre": "Ernesto Padilla Aceves" }
    }
  ]
}

----------------------------------------

ERROR 3 - Clasificar instituciones como "persona":
Las instituciones gubernamentales son "empresa", NO "persona"

❌ INCORRECTO:
{ "tipo_titular": "persona" }  // Para INSS, INFONAVIT, Secretarías, etc.

✅ CORRECTO:
{ "tipo_titular": "empresa" }  // Para cualquier institución u organismo

RECUERDA: tipo_titular="empresa" incluye:
- S.A., S.A. de C.V., S. de R.L.
- Instituto, Secretaría, Gobierno
- INFONAVIT, FOVISSSTE, INSS
- Fideicomisos, Fondos, A.C.

----------------------------------------

ERROR 4 - Poner institución como representante:
El representante siempre es una PERSONA FÍSICA

❌ INCORRECTO:
{
  "representante": { "nombre": "Instituto Nacional..." }
}

✅ CORRECTO:
{
  "representante": { "nombre": "Juan Pérez López" }
}

----------------------------------------

ERROR 5 - Usar nombres de campos incorrectos:
❌ INCORRECTO: "nombre_titular", "nombre_completo", "razon_social"
✅ CORRECTO: "nombre"

❌ INCORRECTO: "num_escritura", "no_escritura"
✅ CORRECTO: "numero_escritura"

----------------------------------------

ERROR 6 - numero_escritura como string:
❌ INCORRECTO: "numero_escritura": "3125"
✅ CORRECTO: "numero_escritura": 3125
"""


# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def build_extraction_prompt(
    document_text: str,
    tipo_titular: str = None,
    nombre_titular: str = None,
    nombre_representante: str = None,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Construye el prompt de extracción.
    
    MODO HÍBRIDO:
    =============
    Si se proporciona tipo_titular (de la Fase 1), construye un prompt
    específico que incluye la clasificación como "información confirmada".
    
    Si no se proporciona, construye un prompt genérico.
    
    Args:
        document_text: Texto del documento a procesar
        tipo_titular: "empresa" o "persona" (de clasificación previa)
        nombre_titular: Nombre del titular identificado (opcional)
        nombre_representante: Nombre del representante identificado (opcional)
        include_examples: Si incluir ejemplos en el prompt
        
    Returns:
        Tupla (system_prompt, user_prompt)
        
    Ejemplo:
        >>> system, user = build_extraction_prompt(
        ...     document_text=texto,
        ...     tipo_titular="empresa",
        ...     nombre_titular="Instituto Nacional del Suelo Sustentable"
        ... )
    """
    
    # Si tenemos clasificación previa, usar prompt específico
    if tipo_titular:
        return _build_prompt_con_clasificacion(
            document_text=document_text,
            tipo_titular=tipo_titular,
            nombre_titular=nombre_titular,
            nombre_representante=nombre_representante,
            include_examples=include_examples
        )
    
    # Sin clasificación, usar prompt genérico
    return _build_prompt_generico(document_text, include_examples)


def _build_prompt_con_clasificacion(
    document_text: str,
    tipo_titular: str,
    nombre_titular: str = None,
    nombre_representante: str = None,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Construye prompt específico con clasificación previa (FASE 2).
    
    Este prompt le dice al LLM exactamente quién es quién,
    para que no tenga que "adivinar" y se enfoque en extraer detalles.
    """
    
    # Seleccionar system prompt y plantilla según tipo
    if tipo_titular == "empresa":
        system_prompt = SYSTEM_PROMPT_EMPRESA
        plantilla = PLANTILLA_JSON_EMPRESA
        ejemplos = [EJEMPLO_EMPRESA_SA, EJEMPLO_INSTITUCION_GOBIERNO]
    else:
        system_prompt = SYSTEM_PROMPT_PERSONA
        plantilla = PLANTILLA_JSON_PERSONA
        ejemplos = [EJEMPLO_PERSONA_FISICA, EJEMPLO_PERSONA_CON_APODERADO]
    
    # Construir sección de información confirmada
    info_confirmada = f"""
========================================
📋 INFORMACIÓN YA CONFIRMADA (NO CAMBIAR)
========================================

Esta información fue verificada en una fase previa:

✅ Tipo de titular: {tipo_titular.upper()}"""

    if nombre_titular:
        info_confirmada += f"""
✅ Nombre del titular: {nombre_titular}"""
    
    if nombre_representante:
        info_confirmada += f"""
✅ Representante: {nombre_representante}"""
    elif tipo_titular == "empresa":
        info_confirmada += f"""
⚠️ Representante: Buscar en el documento (OBLIGATORIO para empresa)"""
    
    info_confirmada += """

USA ESTA INFORMACIÓN. No la cambies a menos que sea claramente incorrecta.
========================================
"""

    # Construir user prompt
    user_prompt = info_confirmada
    
    # Agregar plantilla
    user_prompt += f"""
========================================
PLANTILLA JSON A LLENAR ({tipo_titular.upper()}):
========================================

```json
{json.dumps(plantilla, indent=2, ensure_ascii=False)}
```
"""

    # Agregar ejemplos si se solicitan
    if include_examples:
        user_prompt += """
========================================
EJEMPLOS DE RESPUESTA CORRECTA:
========================================
"""
        for i, ejemplo in enumerate(ejemplos, 1):
            user_prompt += f"""
EJEMPLO {i}:
```json
{json.dumps(ejemplo, indent=2, ensure_ascii=False)}
```
"""

    # Agregar errores comunes
    user_prompt += _build_errores_comunes()
    
    # Agregar documento
    user_prompt += f"""
========================================
DOCUMENTO A ANALIZAR:
========================================

{document_text}

========================================
TU RESPUESTA (solo JSON válido):
========================================
"""

    return system_prompt, user_prompt


def _build_prompt_generico(
    document_text: str,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Construye prompt genérico sin clasificación previa.
    
    Se usa como fallback si la clasificación no está disponible.
    """
    
    user_prompt = f"""
========================================
INSTRUCCIONES DE EXTRACCIÓN
========================================

Analiza el siguiente documento notarial y extrae la información en formato JSON.

PASO 1 - Determina el tipo de titular:
- Si el vendedor es S.A., S.A. de C.V., Instituto, Secretaría, INFONAVIT, etc. → tipo_titular="empresa"
- Si el vendedor es una persona física actuando por sí misma → tipo_titular="persona"

PASO 2 - Identifica titular y representante:
- TITULAR: La entidad que vende (empresa/institución O persona física)
- REPRESENTANTE: La persona física que firma (si existe)

========================================
PLANTILLA JSON:
========================================

```json
{json.dumps(PLANTILLA_JSON_EMPRESA, indent=2, ensure_ascii=False)}
```
"""

    if include_examples:
        user_prompt += f"""
========================================
EJEMPLO - EMPRESA/INSTITUCIÓN:
========================================

```json
{json.dumps(EJEMPLO_INSTITUCION_GOBIERNO, indent=2, ensure_ascii=False)}
```

========================================
EJEMPLO - PERSONA FÍSICA:
========================================

```json
{json.dumps(EJEMPLO_PERSONA_FISICA, indent=2, ensure_ascii=False)}
```
"""

    user_prompt += _build_errores_comunes()
    
    user_prompt += f"""
========================================
DOCUMENTO A ANALIZAR:
========================================

{document_text}

========================================
TU RESPUESTA (solo JSON válido):
========================================
"""

    return SYSTEM_PROMPT_EXTRACCION, user_prompt


# =============================================================================
# PROMPT DE VALIDACIÓN (PARA RETRY)
# =============================================================================

def build_validation_prompt(
    json_anterior: Dict,
    error_validacion: str,
    document_text: str,
    tipo_titular: str = None,
    nombre_titular: str = None,
    nombre_representante: str = None
) -> Tuple[str, str]:
    """
    Construye prompt para corregir una extracción fallida (retry).
    
    Este prompt:
    1. Muestra el JSON anterior con sus errores
    2. Explica qué campos faltan o son incorrectos
    3. Mantiene la clasificación de la Fase 1
    4. Pide al LLM que corrija
    
    Args:
        json_anterior: JSON del intento anterior
        error_validacion: Error de Pydantic o mensaje de error
        document_text: Texto del documento (truncado para el prompt)
        tipo_titular: Tipo clasificado (mantener consistente)
        nombre_titular: Nombre del titular (de clasificación)
        nombre_representante: Nombre del representante (de clasificación)
        
    Returns:
        Tupla (system_prompt, user_prompt)
    """
    
    # System prompt de corrección
    if tipo_titular == "empresa":
        system_prompt = """Eres un corrector de datos JSON para escrituras de EMPRESAS/INSTITUCIONES.

REGLAS:
1. tipo_titular SIEMPRE es "empresa" (NO lo cambies)
2. El TITULAR es la empresa/institución, el REPRESENTANTE es quien firma
3. El representante es OBLIGATORIO y debe ser una PERSONA FÍSICA
4. numero_escritura es INTEGER (sin comillas)

Corrige los errores y devuelve el JSON completo."""
    else:
        system_prompt = """Eres un corrector de datos JSON para escrituras de PERSONAS FÍSICAS.

REGLAS:
1. tipo_titular SIEMPRE es "persona" (NO lo cambies)
2. El representante es OPCIONAL (null si actúa por derecho propio)
3. numero_escritura es INTEGER (sin comillas)

Corrige los errores y devuelve el JSON completo."""

    # Analizar errores del JSON anterior
    analisis = _analizar_errores_json(json_anterior, error_validacion, tipo_titular)
    
    # Construir user prompt
    user_prompt = f"""
========================================
⚠️ CORRECCIÓN REQUERIDA
========================================

Tu respuesta anterior tuvo errores. Corrígelos.

{analisis}

========================================
📋 INFORMACIÓN CONFIRMADA (NO CAMBIAR):
========================================
- Tipo de titular: {tipo_titular or 'No especificado'}"""
    
    if nombre_titular:
        user_prompt += f"""
- Nombre del titular: {nombre_titular}"""
    
    if nombre_representante:
        user_prompt += f"""
- Representante: {nombre_representante}"""

    user_prompt += f"""

========================================
TU JSON ANTERIOR (con errores):
========================================

```json
{json.dumps(json_anterior, indent=2, ensure_ascii=False) if json_anterior else "No se pudo parsear JSON"}
```

========================================
DOCUMENTO ORIGINAL (fragmento):
========================================

{document_text[:2000]}

========================================
TU JSON CORREGIDO:
========================================
"""

    return system_prompt, user_prompt


def _analizar_errores_json(
    json_anterior: Dict,
    error_validacion: str,
    tipo_titular: str = None
) -> str:
    """
    Analiza los errores del JSON anterior y genera feedback.
    """
    
    if not json_anterior:
        return "❌ No se pudo parsear el JSON. Asegúrate de devolver JSON válido."
    
    errores = []
    
    # Campos requeridos
    campos_requeridos = [
        "notario", "numero_escritura", "fecha_documento",
        "tipo_titular", "titulares", "adquirientes",
        "monto_operacion", "tipo_moneda"
    ]
    
    # Verificar campos faltantes
    for campo in campos_requeridos:
        if campo not in json_anterior or json_anterior[campo] is None:
            errores.append(f"❌ Campo faltante: {campo}")
        elif campo == "titulares" and len(json_anterior.get("titulares", [])) == 0:
            errores.append(f"❌ Campo vacío: titulares (debe tener al menos 1)")
        elif campo == "adquirientes" and len(json_anterior.get("adquirientes", [])) == 0:
            errores.append(f"❌ Campo vacío: adquirientes (debe tener al menos 1)")
    
    # Verificar tipo_titular
    tipo_json = json_anterior.get("tipo_titular", "")
    if tipo_titular and tipo_json != tipo_titular:
        errores.append(f"❌ tipo_titular incorrecto: dijiste '{tipo_json}', debe ser '{tipo_titular}'")
    
    # Verificar numero_escritura es int
    num_esc = json_anterior.get("numero_escritura")
    if isinstance(num_esc, str):
        errores.append(f"❌ numero_escritura es string ('{num_esc}'), debe ser integer (sin comillas)")
    
    # Verificar estructura de titulares
    for i, titular in enumerate(json_anterior.get("titulares", [])):
        if isinstance(titular, dict):
            # Verificar campo "nombre"
            if "nombre" not in titular:
                if "nombre_titular" in titular:
                    errores.append(f"❌ titulares[{i}]: usa 'nombre_titular', debe ser 'nombre'")
                elif "razon_social" in titular:
                    errores.append(f"❌ titulares[{i}]: usa 'razon_social', debe ser 'nombre'")
                else:
                    errores.append(f"❌ titulares[{i}]: falta campo 'nombre'")
            
            # Verificar tipo_titular dentro de titular (error común)
            if "tipo_titular" in titular:
                errores.append(f"❌ titulares[{i}]: tiene 'tipo_titular' adentro, debe ir en la RAÍZ")
            
            # Para empresa, verificar representante
            if tipo_titular == "empresa":
                rep = titular.get("representante")
                if rep is None:
                    errores.append(f"❌ titulares[{i}]: empresa debe tener representante")
                elif isinstance(rep, str):
                    errores.append(f"❌ titulares[{i}]: representante es string, debe ser objeto")
    
    # Parsear errores de Pydantic
    if error_validacion and "Field required" in error_validacion:
        import re
        matches = re.findall(r"'(\w+)'[^']*Field required", error_validacion)
        for campo in matches:
            if f"Campo faltante: {campo}" not in str(errores):
                errores.append(f"❌ Campo requerido por validación: {campo}")
    
    if not errores:
        errores.append("⚠️ Error de validación no específico. Revisa el formato general.")
    
    return "\n".join(errores)


# =============================================================================
# UTILIDADES
# =============================================================================

def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """
    Estima el número de tokens en un texto.
    
    Los LLMs tienen límite de contexto en tokens, no caracteres.
    Esta es una estimación aproximada (4 caracteres ≈ 1 token para español).
    
    Args:
        text: Texto a estimar
        chars_per_token: Caracteres por token (default 4 para español)
        
    Returns:
        Número estimado de tokens
    """
    return int(len(text) / chars_per_token)


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DEL CONSTRUCTOR DE PROMPTS")
    print("=" * 60)
    
    documento_prueba = """
    ESCRITURA NÚMERO 2397
    Ante mí, Licenciado Rigoberto Ochoa Torres, Notario Público,
    comparece el señor Ernesto Padilla Aceves en representación
    del Instituto Nacional del Suelo Sustentable (INSS)...
    """
    
    # Prueba 1: Prompt con clasificación (empresa)
    print("\n📋 Prueba 1: Prompt con clasificación EMPRESA")
    print("-" * 40)
    
    system, user = build_extraction_prompt(
        document_text=documento_prueba,
        tipo_titular="empresa",
        nombre_titular="Instituto Nacional del Suelo Sustentable",
        nombre_representante="Ernesto Padilla Aceves"
    )
    
    print(f"   System prompt: {len(system)} caracteres")
    print(f"   User prompt: {len(user)} caracteres")
    print(f"   Tokens estimados: ~{estimate_tokens(system + user)}")
    
    # Prueba 2: Prompt con clasificación (persona)
    print("\n📋 Prueba 2: Prompt con clasificación PERSONA")
    print("-" * 40)
    
    system, user = build_extraction_prompt(
        document_text=documento_prueba,
        tipo_titular="persona",
        nombre_titular="Juan Pérez López"
    )
    
    print(f"   System prompt: {len(system)} caracteres")
    print(f"   User prompt: {len(user)} caracteres")
    print(f"   Tokens estimados: ~{estimate_tokens(system + user)}")
    
    # Prueba 3: Prompt genérico (sin clasificación)
    print("\n📋 Prueba 3: Prompt genérico (sin clasificación)")
    print("-" * 40)
    
    system, user = build_extraction_prompt(
        document_text=documento_prueba,
        tipo_titular=None
    )
    
    print(f"   System prompt: {len(system)} caracteres")
    print(f"   User prompt: {len(user)} caracteres")
    print(f"   Tokens estimados: ~{estimate_tokens(system + user)}")
    
    print("\n" + "=" * 60)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 60)
