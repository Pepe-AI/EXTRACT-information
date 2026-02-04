"""
utils/gemini_prompts.py - Prompts especializados para Gemini

ARQUITECTURA MODULAR:
====================
- build_gemini_prompt_critico() → Campos críticos (titular/adquiriente)
- build_gemini_prompt_expandido() → + municipio, monto, poder
- build_gemini_prompt_completo() → Todos los campos <90%

Permite escalar gradualmente agregando campos según se validen.
"""

from typing import Dict, Any


def build_gemini_prompt_critico(document_text: str) -> str:
    """
    Prompt Gemini para campos CRÍTICOS que DeepSeek falla consistentemente.

    VERSIÓN 1 - CAMPOS EXTRAÍDOS:
    =============================
    - titular.nombre (VENDEDOR)
    - titular.tipo (empresa/persona)
    - titular.representante.nombre
    - titular.representante.en_calidad
    - adquiriente.nombre (COMPRADOR)
    - adquiriente.tipo (empresa/persona)
    - adquiriente.representante (si existe)

    PROBLEMA QUE RESUELVE:
    =====================
    DeepSeek invierte titular ↔ adquiriente en ~90% de casos.
    Gemini tiene mejor comprensión semántica de "vendedor vs comprador".

    Args:
        document_text: Texto OCR del documento

    Returns:
        str: Prompt optimizado para Gemini
    """

    # FIX 2026-01-26: NO truncar el texto. Gemini 2.5 Flash soporta 1M tokens
    # Antes: texto_truncado = document_text[:5000]
    texto_truncado = document_text  # Enviar texto completo

    prompt = f"""Eres un extractor especializado de escrituras públicas mexicanas.

Tu ÚNICA tarea es identificar correctamente QUIÉN VENDE y QUIÉN COMPRA.

⚠️ REGLA CRÍTICA - NO CONFUNDAS:
================================

TITULAR = VENDEDOR (quien transmite/enajena/vende el inmueble)
ADQUIRIENTE = COMPRADOR (quien adquiere/compra el inmueble)

INSTRUCCIONES:
==============

1. Busca palabras clave para identificar roles:

   VENDEDOR (titular):
   - "vende"
   - "transmite"
   - "enajena"
   - "es propietario"
   - "primera parte"
   - "comparece y expone que es dueño"

   COMPRADOR (adquiriente):
   - "adquiere"
   - "compra"
   - "segunda parte"
   - "manifiesta su interés en adquirir"

2. Para EMPRESAS/INSTITUCIONES:
   - tipo: "empresa"
   - Identifica el REPRESENTANTE (persona física que firma)
   - Busca: "representado por", "en su calidad de", "apoderado"
   - Extrae: nombre del representante y en_calidad (cargo)

3. Para PERSONAS:
   - tipo: "persona"
   - Si actúa por derecho propio → representante: null
   - Si tiene apoderado/gestor → extraer nombre y en_calidad

⚠️ REGLA CRÍTICA - REPRESENTANTE:
==================================

Cada titular/adquiriente puede tener MÁXIMO UN representante.

REGLAS:
- Si tipo = "empresa" → representante es OBLIGATORIO
- Si tipo = "persona" → representante es OPCIONAL (puede ser null)

Si el documento menciona varios representantes, toma SOLO EL PRIMERO.

FORMATO CORRECTO:
{{
  "representante": {{
    "nombre": "NOMBRE COMPLETO DEL REPRESENTANTE",
    "en_calidad": "apoderado legal"
  }}
}}

O si no tiene representante:
{{
  "representante": null
}}

⚠️ CAMPOS EXCLUSIVOS POR TIPO DE ENTIDAD:
==========================================

TITULAR (vendedor):
- nombre
- tipo
- representante

ADQUIRIENTE (comprador):
- nombre
- tipo
- representante
- estado_civil (casado/soltero/divorciado/viudo) - SI APARECE
- rfc - SI APARECE
- curp - SI APARECE
- edad - SI APARECE
- tipo_sociedad (separación de bienes/sociedad conyugal) - SI APARECE

PLANTILLA DE RESPUESTA (JSON):
==============================

{{
  "titular": {{
    "nombre": "NOMBRE COMPLETO DEL VENDEDOR",
    "tipo": "empresa" o "persona",
    "representante": null o {{
      "nombre": "NOMBRE DEL REPRESENTANTE",
      "en_calidad": "apoderado legal"
    }}
  }},
  "adquiriente": {{
    "nombre": "NOMBRE COMPLETO DEL COMPRADOR",
    "tipo": "empresa" o "persona",
    "estado_civil": "..." o false,
    "rfc": "..." o false,
    "curp": "..." o false,
    "edad": X o false,
    "tipo_sociedad": "..." o false,
    "representante": null o {{
      "nombre": "NOMBRE DEL REPRESENTANTE",
      "en_calidad": "gestor de negocios"
    }}
  }}
}}

EJEMPLO CORRECTO:
=================

Documento: "Comparece el INSTITUTO NACIONAL DEL SUELO SUSTENTABLE (INSUS),
representado por ERNESTO PADILLA ACEVES en su calidad de Representante Regional,
quien manifiesta que VENDE a la señora ANGELBERTA PÉREZ SOTO, casada, quien ADQUIERE..."

JSON correcto:
{{
  "titular": {{
    "nombre": "INSTITUTO NACIONAL DEL SUELO SUSTENTABLE (INSUS)",
    "tipo": "empresa",
    "representante": {{
      "nombre": "ERNESTO PADILLA ACEVES",
      "en_calidad": "Representante Regional"
    }}
  }},
  "adquiriente": {{
    "nombre": "ANGELBERTA PÉREZ SOTO",
    "tipo": "persona",
    "estado_civil": "casada",
    "rfc": false,
    "curp": false,
    "edad": false,
    "tipo_sociedad": false,
    "representante": null
  }}
}}

REGLAS IMPORTANTES:
===================
- Extrae nombres COMPLETOS (sin títulos como Lic., Dr., Ing.)
- Si es EMPRESA → representante es OBLIGATORIO (objeto)
- Si es PERSONA sin apoderado → representante: null
- Si el documento menciona MÚLTIPLES representantes → toma SOLO EL PRIMERO
- TITULAR: SOLO extrae nombre, tipo, representante (NO rfc, curp, edad, estado_civil, tipo_sociedad)
- ADQUIRIENTE: Extrae rfc, curp, edad, estado_civil, tipo_sociedad SOLO SI APARECEN (sino usa false)
- Usa null para representante, usa false para campos que no existan (NO uses "N/A" o "NO ENCONTRADO")

DOCUMENTO A EXTRAER:
===================

{texto_truncado}

═══════════════════════════════════════════════════════════════
RESPONDE ÚNICAMENTE CON EL JSON. NO AGREGUES EXPLICACIONES.
═══════════════════════════════════════════════════════════════
"""

    return prompt


def build_gemini_prompt_expandido(document_text: str) -> str:
    """
    Prompt Gemini EXPANDIDO - Agrega campos numéricos.

    VERSIÓN 2 - CAMPOS ADICIONALES:
    ===============================
    + municipio (ubicación del inmueble)
    + monto_operacion (precio de venta)
    + representante.escritura (número del poder)
    + representante.fecha_poder (fecha del poder)

    Args:
        document_text: Texto OCR del documento

    Returns:
        str: Prompt expandido para Gemini
    """

    # FIX 2026-01-26: NO truncar el texto. Gemini 2.5 Flash soporta 1M tokens (~4M caracteres)
    # Los RFC/CURP/edad están al FINAL del documento (sección FE NOTARIAL)
    # Antes: texto_truncado = document_text[:6000]
    texto_truncado = document_text  # Enviar texto completo

    prompt = f"""Eres un extractor especializado de escrituras públicas mexicanas.

Extrae los siguientes campos del documento:

═══════════════════════════════════════════════════════════════
1. TITULAR y ADQUIRIENTE (CRÍTICO)
═══════════════════════════════════════════════════════════════

⚠️ NO CONFUNDAS:
- TITULAR = VENDEDOR (vende/transmite/enajena)
- ADQUIRIENTE = COMPRADOR (adquiere/compra)

⚠️ CAMPOS POR TIPO DE ENTIDAD:
- TITULAR: nombre, tipo, representante
- ADQUIRIENTE: nombre, tipo, representante, estado_civil, rfc, curp, edad, tipo_sociedad

⚠️ REGLA MÚLTIPLES ADQUIRIENTES:
- Si detectas MÚLTIPLES ADQUIRIENTES (ejemplo: "ANTONIO QUINTERO FLORES y SILVIA SÁNCHEZ SÁNCHEZ")
- NO los concatenes en un solo objeto
- Crea un objeto SEPARADO para cada adquiriente en el array "adquirientes"
- Extrae el RFC, CURP y edad de CADA PERSONA por separado
- Busca en la sección "FE NOTARIAL" o "COMPARECIENTES" donde se listan los RFC/CURP de cada persona
- Asigna el RFC/CURP correcto a cada persona (busca el RFC/CURP cerca del nombre de cada persona)

⚠️ REGLA REPRESENTANTE:
- Cada titular/adquiriente puede tener MÁXIMO UN representante
- Si tipo = "empresa" → representante es OBLIGATORIO
- Si tipo = "persona" → representante es OPCIONAL (puede ser null)
- Si hay varios representantes mencionados → toma SOLO EL PRIMERO

⚠️ CAMPOS EXCLUSIVOS DE ADQUIRIENTE:
- estado_civil, rfc, curp, edad, tipo_sociedad → SOLO extraer para ADQUIRIENTE
- Si NO aparecen en el documento → usa false (NO null)

═══════════════════════════════════════════════════════════════
2. MUNICIPIO DEL INMUEBLE
═══════════════════════════════════════════════════════════════

Busca el municipio donde está UBICADO EL INMUEBLE, NO el municipio de la notaría.

Patrones:
- "inmueble ubicado en el municipio de X"
- "predio situado en X"
- "bien inmueble que se encuentra en X"

═══════════════════════════════════════════════════════════════
3. MONTO DE LA OPERACIÓN
═══════════════════════════════════════════════════════════════

Busca el PRECIO DE VENTA (no impuestos ni pagos parciales).

Patrones:
- "precio de la operación"
- "por la cantidad de $X"
- "suma de $X"
- "monto total de $X"

Formato: "$1,234,567.89"

═══════════════════════════════════════════════════════════════
4. DATOS DEL PODER (si el titular tiene representante)
═══════════════════════════════════════════════════════════════

Busca:
- Número de escritura del poder
- Fecha del poder

Patrones:
- "instrumento número X de fecha Y"
- "escritura X otorgada el Y"
- "poder otorgado mediante escritura X del Y"

PLANTILLA DE RESPUESTA (JSON):
==============================

{{
  "titular": {{
    "nombre": "NOMBRE VENDEDOR",
    "tipo": "empresa" o "persona",
    "representante": null o {{
      "nombre": "NOMBRE REPRESENTANTE",
      "en_calidad": "cargo",
      "escritura": "12345",
      "fecha_poder": "15/4/2020"
    }}
  }},
  "adquirientes": [
    {{
      "nombre": "NOMBRE COMPRADOR 1",
      "tipo": "empresa" o "persona",
      "estado_civil": "..." o false,
      "rfc": "..." o false,
      "curp": "..." o false,
      "edad": X o false,
      "tipo_sociedad": "..." o false,
      "representante": null o {{
        "nombre": "NOMBRE REPRESENTANTE",
        "en_calidad": "cargo",
        "escritura": null,
        "fecha_poder": null
      }}
    }}
  ],
  "municipio": "NOMBRE MUNICIPIO" o null,
  "monto_operacion": "$X,XXX.XX" o null
}}

REGLAS IMPORTANTES:
===================
- Extrae nombres COMPLETOS (sin títulos como Lic., Dr., Ing.)
- Si es EMPRESA → representante es OBLIGATORIO (objeto)
- Si es PERSONA sin apoderado → representante: null
- Si hay MÚLTIPLES representantes mencionados → toma SOLO EL PRIMERO
- TITULAR: SOLO extrae nombre, tipo, representante (NO rfc, curp, edad, estado_civil, tipo_sociedad)
- ADQUIRIENTES: SIEMPRE retorna como ARRAY (incluso si es solo 1 persona)
- Si hay MÚLTIPLES ADQUIRIENTES (ejemplo: "ANTONIO y SILVIA") → crea un objeto separado para CADA UNO
- Extrae rfc, curp, edad, estado_civil, tipo_sociedad de CADA adquiriente SOLO SI APARECEN (sino usa false)
- Usa null para representante/municipio/monto, usa false para campos de adquiriente que no existan
- Municipio del INMUEBLE, NO de la notaría
- Monto de VENTA, NO impuestos

DOCUMENTO A EXTRAER:
===================

{texto_truncado}

RESPONDE ÚNICAMENTE CON EL JSON. NO AGREGUES TEXTO EXTRA.
"""

    return prompt


def build_gemini_prompt_completo(document_text: str) -> str:
    """
    Prompt Gemini COMPLETO - Todos los campos <90%.

    VERSIÓN 3 - CAMPOS ADICIONALES:
    ===============================
    + adquiriente.estado_civil
    + adquiriente.rfc
    + adquiriente.curp

    Args:
        document_text: Texto OCR del documento

    Returns:
        str: Prompt completo para Gemini
    """

    # FIX 2026-01-26: NO truncar el texto. Gemini 2.5 Flash soporta 1M tokens
    # Antes: texto_truncado = document_text[:7000]
    texto_truncado = document_text  # Enviar texto completo

    prompt = f"""Eres un extractor experto de escrituras públicas mexicanas.

Extrae TODOS los siguientes campos del documento:

╔══════════════════════════════════════════════════════════════════╗
║  CAMPOS CRÍTICOS                                                 ║
╚══════════════════════════════════════════════════════════════════╝

1. TITULAR (VENDEDOR):
   - Nombre completo
   - Tipo (empresa/persona)
   - Representante (si existe): nombre, en_calidad, escritura, fecha_poder
   ⚠️ NO EXTRAER: rfc, curp, edad, estado_civil, tipo_sociedad

2. ADQUIRIENTE (COMPRADOR):
   - Nombre completo
   - Tipo (empresa/persona)
   - Estado civil (casado/soltero/divorciado/viudo) - SI APARECE
   - RFC - SI APARECE
   - CURP - SI APARECE
   - Edad - SI APARECE
   - Tipo de sociedad (separación de bienes/sociedad conyugal) - SI APARECE
   - Representante (si existe)

3. UBICACIÓN:
   - Municipio donde está ubicado el INMUEBLE (no la notaría)

4. MONTO:
   - Monto de la operación (precio de venta, no impuestos)

⚠️ REGLAS:
==========

- TITULAR = VENDEDOR (vende/transmite/enajena)
- ADQUIRIENTE = COMPRADOR (adquiere/compra)
- EMPRESA → DEBE tener representante
- PERSONA → representante solo si lo menciona el documento
- TITULAR: SOLO nombre, tipo, representante (NO rfc, curp, edad, estado_civil, tipo_sociedad)
- ADQUIRIENTE: Incluye rfc, curp, edad, estado_civil, tipo_sociedad → false si no aparecen
- Municipio del INMUEBLE, NO de la notaría
- Monto de VENTA, NO impuestos

PLANTILLA JSON:
===============

{{
  "titular": {{
    "nombre": "...",
    "tipo": "empresa" o "persona",
    "representante": null o {{
      "nombre": "...",
      "en_calidad": "...",
      "escritura": "...",
      "fecha_poder": "..."
    }}
  }},
  "adquiriente": {{
    "nombre": "...",
    "tipo": "empresa" o "persona",
    "estado_civil": "..." o false,
    "rfc": "..." o false,
    "curp": "..." o false,
    "edad": X o false,
    "tipo_sociedad": "..." o false,
    "representante": null o {{...}}
  }},
  "municipio": "..." o null,
  "monto_operacion": "$X,XXX.XX" o null
}}

DOCUMENTO:
==========

{texto_truncado}

RESPONDE SOLO CON JSON.
"""

    return prompt


def parse_gemini_response(response_text: str) -> Dict[str, Any]:
    """
    Parsea la respuesta de Gemini y extrae el JSON.

    Gemini puede devolver:
    1. JSON puro
    2. JSON en bloque markdown ```json ... ```
    3. JSON con texto adicional

    Args:
        response_text: Respuesta cruda de Gemini

    Returns:
        Dict con el JSON parseado
    """
    import json
    import re

    if not response_text:
        return {}

    # Intentar extraer JSON de bloque markdown
    json_block_pattern = re.compile(r'```(?:json)?\s*([\s\S]*?)```', re.IGNORECASE)
    match = json_block_pattern.search(response_text)

    if match:
        json_str = match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️ Error parseando JSON del bloque: {e}")

    # Intentar parsear respuesta directa
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        pass

    # Buscar JSON en el texto (objeto {...})
    json_pattern = re.compile(r'\{[\s\S]*\}')
    match = json_pattern.search(response_text)

    if match:
        json_str = match.group()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️ Error parseando JSON extraído: {e}")

            # Intentar reparar JSON incompleto
            try:
                # Si no termina con } o ], intentar cerrar
                if not json_str.endswith('}') and not json_str.endswith(']'):
                    open_braces = json_str.count('{') - json_str.count('}')
                    open_brackets = json_str.count('[') - json_str.count(']')

                    json_reparado = json_str
                    for _ in range(open_brackets):
                        json_reparado += ']'
                    for _ in range(open_braces):
                        json_reparado += '}'

                    print(f"   🔧 Intentando reparar JSON...")
                    return json.loads(json_reparado)
            except:
                pass

    print(f"⚠️ No se pudo extraer JSON de la respuesta de Gemini")
    return {}
