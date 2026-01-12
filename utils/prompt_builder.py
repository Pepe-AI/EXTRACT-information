"""
utils/prompt_builder.py - Constructor de prompts para extracción de escrituras

VERSIÓN CORREGIDA - ESTRUCTURA ESTRICTA
=======================================

PROBLEMA ANTERIOR:
==================
El LLM agregaba campos extra como:
- "representante_legal" (debe ir dentro de "representante")
- "documento" (estructura completa no solicitada)
- "gestora_negocios", "inmueble", "firmas", etc.

SOLUCIÓN:
=========
1. Prompts MUY ESTRICTOS que enfatizan NO agregar campos
2. JSON de ejemplo EXACTO sin variaciones
3. Lista explícita de campos prohibidos
4. Función limpiar_json_extra() para eliminar campos no permitidos
"""

import json
from typing import Tuple, Dict, Any, Optional, List


# =============================================================================
# CONSTANTES
# =============================================================================

NO_ENCONTRADO = "NO SE ENCONTRÓ DATO"

# Campos permitidos en cada nivel (para validación y limpieza)
CAMPOS_RAIZ_PERMITIDOS = {
    "notario", "numero_escritura", "fecha_documento", "tipo_titular",
    "titulares", "adquirientes", "monto_operacion", "tipo_moneda", "valor_catastral"
}

# NUEVO: Campos permitidos dentro de cada objeto notario
CAMPOS_NOTARIO_PERMITIDOS = {
    "nombre",           # Nombre del notario
    "numero_notario",   # Número de notaría (2-3 dígitos)
    "municipio",        # Municipio donde ejerce
    "escritura",        # Número de escritura (4-7 dígitos)
    "fecha_documento"   # Fecha del documento
}

CAMPOS_TITULAR_PERMITIDOS = {
    "nombre", "actua_por", "representante"
}

CAMPOS_REPRESENTANTE_PERMITIDOS = {
    "nombre", "en_calidad", "escritura", "bis", "fecha_poder"
}

CAMPOS_ADQUIRIENTE_PERMITIDOS = {
    "nombre", "estado_civil", "tipo_sociedad", "edad", "rfc", "curp"
}


# =============================================================================
# EJEMPLOS JSON EXACTOS
# =============================================================================

# NUEVA ESTRUCTURA DE NOTARIO:
# ============================
# notario ahora es un ARRAY con UN objeto que contiene:
# - nombre: Nombre del notario
# - numero_notario: 2-3 dígitos (ej: "45", "123")
# - municipio: Municipio de la notaría
# - escritura: 4-7 dígitos (ej: "2307", "1234567")
# - fecha_documento: Fecha del documento

EJEMPLO_JSON_EMPRESA = {
    "notario": [
        {
            "nombre": "RIGOBERTO OCHOA TORRES",
            "numero_notario": "45",           # 2-3 dígitos
            "municipio": "Tepic, Nayarit",
            "escritura": "2397",              # 4-7 dígitos
            "fecha_documento": "5 de mayo de 2023"
        }
    ],
    "numero_escritura": 2397,
    "fecha_documento": "5 de mayo de 2023",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "Instituto Nacional del Suelo Sustentable (INSUS)",
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

EJEMPLO_JSON_EMPRESA_2 = {
    "notario": [
        {
            "nombre": "FERNANDO CASTRO RUBIO",
            "numero_notario": "123",          # 2-3 dígitos
            "municipio": "Guadalajara, Jalisco",
            "escritura": "2736",              # 4-7 dígitos
            "fecha_documento": "13 de marzo de 2024"
        }
    ],
    "numero_escritura": 2736,
    "fecha_documento": "13 de marzo de 2024",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "KUBBOX ARQUITECTURA, SOCIEDAD ANONIMA DE CAPITAL VARIABLE",
            "actua_por": "apoderado",
            "representante": {
                "nombre": "ROSA HERLINDA DURAN GEBBIA",
                "en_calidad": "apoderado",
                "escritura": "21695",
                "bis": False,
                "fecha_poder": "14 de octubre de 2021"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "BEATRIZ PICHARDO MENDOZA",
            "estado_civil": "casada",
            "tipo_sociedad": "separación de bienes",
            "edad": None,
            "rfc": False,
            "curp": False
        }
    ],
    "monto_operacion": "$3,100,000.00",
    "tipo_moneda": "MXN",
    "valor_catastral": None
}

EJEMPLO_JSON_PERSONA = {
    "notario": [
        {
            "nombre": "María López Hernández",
            "numero_notario": "78",           # 2-3 dígitos
            "municipio": "Ciudad de México",
            "escritura": "5432",              # 4-7 dígitos
            "fecha_documento": "20 de junio de 2024"
        }
    ],
    "numero_escritura": 5432,
    "fecha_documento": "20 de junio de 2024",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "Juan Carlos Pérez García",
            "actua_por": "derecho propio",
            "representante": None
        }
    ],
    "adquirientes": [
        {
            "nombre": "Ana María Rodríguez López",
            "estado_civil": "soltera",
            "tipo_sociedad": None,
            "edad": 35,
            "rfc": "ROLA890515ABC",
            "curp": False
        }
    ],
    "monto_operacion": "$1,200,000.00",
    "tipo_moneda": "MXN",
    "valor_catastral": "$950,000.00"
}


# =============================================================================
# SYSTEM PROMPT ESTRICTO
# =============================================================================

SYSTEM_PROMPT_ESTRICTO = """Eres un extractor de datos de escrituras públicas mexicanas.

REGLAS ABSOLUTAS QUE DEBES SEGUIR:

1. Responde ÚNICAMENTE con un objeto JSON válido
2. NO agregues campos que no estén en la plantilla
3. NO crees estructuras anidadas adicionales como "documento", "inmueble", "firmas"
4. USA EXACTAMENTE los nombres de campos que te indico
5. Si no encuentras un dato, usa null o "NO SE ENCONTRÓ DATO"

ESTRUCTURA ESPECIAL - CAMPO "notario":
======================================
El campo "notario" es un ARRAY con UN objeto que tiene 5 campos:
- nombre: Nombre completo del notario
- numero_notario: Número de la notaría (2-3 dígitos, ej: "45", "123")
- municipio: Municipio donde ejerce el notario
- escritura: Número de escritura (4-7 dígitos, ej: "2307", "18226")
- fecha_documento: Fecha del documento

CAMPOS PROHIBIDOS (NUNCA LOS USES):
- representante_legal (el representante va DENTRO del objeto "representante")
- gestora_negocios
- documento
- inmueble
- firmas
- partes
- vendedor
- comprador
- jurisdiccion
- domicilio_notificaciones
- impuestos

El JSON debe tener EXACTAMENTE 9 campos en la raíz, no más."""

# Alias para compatibilidad
SYSTEM_PROMPT_EXTRACCION = SYSTEM_PROMPT_ESTRICTO


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
    Construye el prompt de extracción con estructura ESTRICTA.
    
    Args:
        document_text: Texto del documento a procesar
        tipo_titular: "empresa" o "persona" (de clasificación previa)
        nombre_titular: Nombre del titular identificado
        nombre_representante: Nombre del representante identificado
        include_examples: Si incluir ejemplos
        
    Returns:
        Tupla (system_prompt, user_prompt)
    """
    
    if tipo_titular == "empresa":
        return _build_prompt_empresa(
            document_text, nombre_titular, nombre_representante, include_examples
        )
    elif tipo_titular == "persona":
        return _build_prompt_persona(
            document_text, nombre_titular, nombre_representante, include_examples
        )
    else:
        return _build_prompt_generico(document_text, include_examples)


def _build_prompt_empresa(
    document_text: str,
    nombre_titular: str = None,
    nombre_representante: str = None,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Prompt ESTRICTO para extracción de EMPRESA/INSTITUCIÓN.
    
    IMPORTANTE: Las empresas/instituciones SIEMPRE deben tener representante.
    """
    
    user_prompt = """
╔══════════════════════════════════════════════════════════════════╗
║                    EXTRACCIÓN DE ESCRITURA                       ║
║                    TIPO: EMPRESA/INSTITUCIÓN                     ║
╚══════════════════════════════════════════════════════════════════╝

⚠️ INSTRUCCIONES CRÍTICAS - LEE CON ATENCIÓN:
==============================================
1. Extrae SOLO los 9 campos que aparecen en la plantilla
2. NO inventes campos adicionales
3. NO crees estructuras como "documento", "inmueble", "firmas", "partes"
4. El "representante" es un OBJETO con 5 campos, NO un campo string separado
5. EMPRESA = SIEMPRE tiene representante (es obligatorio)

"""

    # Agregar información confirmada si existe
    if nombre_titular or nombre_representante:
        user_prompt += """
✅ INFORMACIÓN YA IDENTIFICADA (ÚSALA):
=======================================
"""
        if nombre_titular:
            user_prompt += f"• Titular (empresa/institución): {nombre_titular}\n"
        if nombre_representante:
            user_prompt += f"• Representante (persona física que firma): {nombre_representante}\n"
        user_prompt += "\n"

    # Plantilla EXACTA
    user_prompt += """
📋 PLANTILLA JSON - USA EXACTAMENTE ESTA ESTRUCTURA:
====================================================

{
    "notario": [
        {
            "nombre": "NOMBRE COMPLETO DEL NOTARIO",
            "numero_notario": "45",
            "municipio": "CIUDAD, ESTADO",
            "escritura": "1234",
            "fecha_documento": "día de mes de año"
        }
    ],
    "numero_escritura": 1234,
    "fecha_documento": "día de mes de año",
    "tipo_titular": "empresa",
    "titulares": [
        {
            "nombre": "RAZÓN SOCIAL DE LA EMPRESA O INSTITUCIÓN",
            "actua_por": "representación",
            "representante": {
                "nombre": "NOMBRE DE LA PERSONA QUE FIRMA",
                "en_calidad": "apoderado/representante legal/etc",
                "escritura": "número de escritura del poder o NO SE ENCONTRÓ DATO",
                "bis": false,
                "fecha_poder": "fecha del poder o NO SE ENCONTRÓ DATO"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "NOMBRE DEL COMPRADOR",
            "estado_civil": "soltero/casado/etc",
            "tipo_sociedad": null,
            "edad": null,
            "rfc": "RFC123..." o false,
            "curp": "CURP123..." o false
        }
    ],
    "monto_operacion": "$X,XXX.XX",
    "tipo_moneda": "MXN",
    "valor_catastral": "$X,XXX.XX" o null
}

⚠️ IMPORTANTE SOBRE EL CAMPO "notario":
========================================
- Es un ARRAY con UN objeto
- numero_notario: Solo 2-3 dígitos (ej: "45", "123")
- escritura: Solo 4-7 dígitos (ej: "2307", "18226")
- fecha_documento: La misma fecha que el campo "fecha_documento" de raíz

"""

    if include_examples:
        user_prompt += f"""
📌 EJEMPLO 1 - INSTITUCIÓN GUBERNAMENTAL:
=========================================

```json
{json.dumps(EJEMPLO_JSON_EMPRESA, indent=4, ensure_ascii=False)}
```

📌 EJEMPLO 2 - SOCIEDAD ANÓNIMA:
================================

```json
{json.dumps(EJEMPLO_JSON_EMPRESA_2, indent=4, ensure_ascii=False)}
```

"""

    user_prompt += """
❌ ERRORES COMUNES QUE DEBES EVITAR:
====================================

ERROR 1 - Campo "representante_legal" separado:
-----------------------------------------------
❌ INCORRECTO:
{
    "titulares": [{
        "nombre": "Instituto...",
        "representante": null,
        "representante_legal": "Ernesto..."
    }]
}

✅ CORRECTO:
{
    "titulares": [{
        "nombre": "Instituto...",
        "representante": {
            "nombre": "Ernesto...",
            "en_calidad": "...",
            "escritura": "...",
            "bis": false,
            "fecha_poder": "..."
        }
    }]
}

ERROR 2 - Agregar estructura "documento":
-----------------------------------------
❌ INCORRECTO:
{
    "notario": "...",
    "documento": {
        "inmueble": {...},
        "firmas": {...}
    }
}

✅ CORRECTO:
{
    "notario": "...",
    "numero_escritura": 123,
    ... (solo 9 campos en raíz)
}

"""

    user_prompt += f"""
📄 DOCUMENTO A ANALIZAR:
========================

{document_text}

══════════════════════════════════════════════════════════════════
🎯 RESPONDE SOLO CON EL JSON.
🚫 NO AGREGUES TEXTO ANTES NI DESPUÉS DEL JSON.
🚫 NO AGREGUES CAMPOS QUE NO ESTÉN EN LA PLANTILLA.
══════════════════════════════════════════════════════════════════
"""

    return SYSTEM_PROMPT_ESTRICTO, user_prompt


def _build_prompt_persona(
    document_text: str,
    nombre_titular: str = None,
    nombre_representante: str = None,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Prompt ESTRICTO para extracción de PERSONA FÍSICA.
    
    IMPORTANTE: Para persona física, el representante es OPCIONAL.
    - Si actúa por derecho propio → representante: null
    - Si tiene apoderado → representante: {objeto}
    """
    
    user_prompt = """
╔══════════════════════════════════════════════════════════════════╗
║                    EXTRACCIÓN DE ESCRITURA                       ║
║                    TIPO: PERSONA FÍSICA                          ║
╚══════════════════════════════════════════════════════════════════╝

⚠️ INSTRUCCIONES CRÍTICAS:
==========================
1. Extrae SOLO los 9 campos de la plantilla
2. NO inventes campos adicionales
3. Para PERSONA FÍSICA, "representante" puede ser:
   - null (si actúa por derecho propio)
   - un objeto (si tiene apoderado)
4. NO crees estructuras como "documento", "inmueble", "firmas"

"""

    if nombre_titular:
        user_prompt += f"""
✅ INFORMACIÓN YA IDENTIFICADA:
===============================
• Titular (persona física): {nombre_titular}
"""
        if nombre_representante:
            user_prompt += f"• Representante/Apoderado: {nombre_representante}\n"
        user_prompt += "\n"

    user_prompt += """
📋 PLANTILLA - PERSONA SIN APODERADO (actúa por derecho propio):
================================================================

{
    "notario": [
        {
            "nombre": "NOMBRE DEL NOTARIO",
            "numero_notario": "45",
            "municipio": "CIUDAD, ESTADO",
            "escritura": "1234",
            "fecha_documento": "día de mes de año"
        }
    ],
    "numero_escritura": 1234,
    "fecha_documento": "día de mes de año",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "NOMBRE DE LA PERSONA",
            "actua_por": "derecho propio",
            "representante": null
        }
    ],
    "adquirientes": [
        {
            "nombre": "NOMBRE DEL COMPRADOR",
            "estado_civil": "soltero/casado/etc",
            "tipo_sociedad": null,
            "edad": null,
            "rfc": false,
            "curp": false
        }
    ],
    "monto_operacion": "$X,XXX.XX",
    "tipo_moneda": "MXN",
    "valor_catastral": null
}

📋 PLANTILLA - PERSONA CON APODERADO:
=====================================

{
    "notario": [
        {
            "nombre": "NOMBRE DEL NOTARIO",
            "numero_notario": "78",
            "municipio": "CIUDAD, ESTADO",
            "escritura": "5432",
            "fecha_documento": "día de mes de año"
        }
    ],
    "numero_escritura": 1234,
    "fecha_documento": "día de mes de año",
    "tipo_titular": "persona",
    "titulares": [
        {
            "nombre": "NOMBRE DE LA PERSONA",
            "actua_por": "representación",
            "representante": {
                "nombre": "NOMBRE DEL APODERADO",
                "en_calidad": "apoderado",
                "escritura": "número",
                "bis": false,
                "fecha_poder": "fecha"
            }
        }
    ],
    "adquirientes": [...],
    "monto_operacion": "$X,XXX.XX",
    "tipo_moneda": "MXN",
    "valor_catastral": null
}

⚠️ IMPORTANTE SOBRE EL CAMPO "notario":
========================================
- Es un ARRAY con UN objeto
- numero_notario: Solo 2-3 dígitos (ej: "45", "78")
- escritura: Solo 4-7 dígitos (ej: "5432", "12345")
- fecha_documento: La misma fecha que el campo "fecha_documento" de raíz

"""

    if include_examples:
        user_prompt += f"""
📌 EJEMPLO - PERSONA SIN APODERADO:
===================================

```json
{json.dumps(EJEMPLO_JSON_PERSONA, indent=4, ensure_ascii=False)}
```

"""

    user_prompt += f"""
📄 DOCUMENTO A ANALIZAR:
========================

{document_text}

══════════════════════════════════════════════════════════════════
🎯 RESPONDE SOLO CON EL JSON.
🚫 NO AGREGUES CAMPOS QUE NO ESTÉN EN LA PLANTILLA.
══════════════════════════════════════════════════════════════════
"""

    return SYSTEM_PROMPT_ESTRICTO, user_prompt


def _build_prompt_generico(
    document_text: str,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Prompt genérico cuando no hay clasificación previa.
    """
    
    user_prompt = """
╔══════════════════════════════════════════════════════════════════╗
║                    EXTRACCIÓN DE ESCRITURA                       ║
╚══════════════════════════════════════════════════════════════════╝

INSTRUCCIONES:
==============
1. Determina si el titular es EMPRESA o PERSONA
2. Extrae SOLO los 9 campos de la plantilla
3. NO agregues campos adicionales

PLANTILLA JSON (9 campos obligatorios):
=======================================

{
    "notario": [
        {
            "nombre": "NOMBRE DEL NOTARIO",
            "numero_notario": "45",
            "municipio": "CIUDAD, ESTADO",
            "escritura": "1234",
            "fecha_documento": "día de mes de año"
        }
    ],
    "numero_escritura": 1234,
    "fecha_documento": "fecha",
    "tipo_titular": "empresa" o "persona",
    "titulares": [
        {
            "nombre": "NOMBRE",
            "actua_por": "representación" o "derecho propio",
            "representante": null o {nombre, en_calidad, escritura, bis, fecha_poder}
        }
    ],
    "adquirientes": [
        {
            "nombre": "NOMBRE",
            "estado_civil": "estado",
            "tipo_sociedad": null,
            "edad": null,
            "rfc": false,
            "curp": false
        }
    ],
    "monto_operacion": "$X,XXX.XX",
    "tipo_moneda": "MXN",
    "valor_catastral": null
}

REGLAS:
- Si es EMPRESA → representante es OBLIGATORIO (objeto)
- Si es PERSONA → representante es OPCIONAL (null o objeto)
- "notario" es un ARRAY con un objeto que tiene 5 campos

"""

    user_prompt += f"""
DOCUMENTO:
==========

{document_text}

══════════════════════════════════════════════════════════════════
RESPONDE SOLO CON EL JSON. NO AGREGUES CAMPOS EXTRA.
══════════════════════════════════════════════════════════════════
"""

    return SYSTEM_PROMPT_ESTRICTO, user_prompt


# =============================================================================
# PROMPT DE VALIDACIÓN/RETRY
# =============================================================================

def build_validation_prompt(
    json_anterior: Dict,
    error_validacion: str,
    document_text: str,
    tipo_titular: str = None,
    nombre_titular: str = None,
    nombre_representante: str = None,
    datos_regex: Dict = None
) -> Tuple[str, str]:
    """
    Prompt para corregir una extracción fallida.
    
    Mantiene el tipo_titular clasificado y proporciona
    feedback específico de los errores.
    """
    
    # Limpiar el JSON anterior de campos extra
    json_limpio = limpiar_json_extra(json_anterior) if json_anterior else {}
    
    system_prompt = """Eres un corrector de JSON para escrituras públicas.

REGLAS ESTRICTAS:
1. Corrige los errores señalados
2. NO agregues campos nuevos
3. Usa SOLO los 9 campos de la plantilla
4. El "representante" debe ser un OBJETO con 5 campos, NO un string separado
5. El "notario" debe ser un ARRAY con UN objeto que tiene 5 campos
6. NO crees estructuras como "documento", "inmueble", "firmas\""""

    user_prompt = f"""
⚠️ TU JSON ANTERIOR TIENE ERRORES. CORRÍGELOS.

TIPO DE TITULAR CONFIRMADO: {tipo_titular.upper() if tipo_titular else 'NO ESPECIFICADO'}
(NO cambies el tipo_titular)

"""

    # Analizar errores específicos
    if json_anterior:
        errores = _detectar_errores_estructura(json_anterior)
        if errores:
            user_prompt += "❌ ERRORES DETECTADOS:\n"
            user_prompt += "=" * 40 + "\n"
            for error in errores:
                user_prompt += f"• {error}\n"
            user_prompt += "\n"
    
    if error_validacion:
        user_prompt += f"Error de validación Pydantic:\n{error_validacion[:300]}\n\n"

    user_prompt += f"""
📋 ESTRUCTURA CORRECTA QUE DEBES USAR:
======================================

{{
    "notario": [
        {{
            "nombre": "NOMBRE DEL NOTARIO",
            "numero_notario": "45",
            "municipio": "CIUDAD, ESTADO",
            "escritura": "1234",
            "fecha_documento": "día de mes de año"
        }}
    ],
    "numero_escritura": 1234,
    "fecha_documento": "...",
    "tipo_titular": "{tipo_titular or 'empresa'}",
    "titulares": [
        {{
            "nombre": "...",
            "actua_por": "...",
            "representante": {{
                "nombre": "...",
                "en_calidad": "...",
                "escritura": "...",
                "bis": false,
                "fecha_poder": "..."
            }}
        }}
    ],
    "adquirientes": [
        {{
            "nombre": "...",
            "estado_civil": "...",
            "tipo_sociedad": null,
            "edad": null,
            "rfc": false,
            "curp": false
        }}
    ],
    "monto_operacion": "...",
    "tipo_moneda": "MXN",
    "valor_catastral": null
}}

⚠️ RECUERDA: "notario" es un ARRAY con UN objeto de 5 campos:
   - nombre, numero_notario (2-3 dígitos), municipio, escritura (4-7 dígitos), fecha_documento

"""

    if json_limpio:
        user_prompt += f"""
📄 TU JSON ANTERIOR (parcialmente limpiado):
============================================

```json
{json.dumps(json_limpio, indent=2, ensure_ascii=False)}
```

"""

    user_prompt += f"""
📄 FRAGMENTO DEL DOCUMENTO ORIGINAL:
====================================

{document_text[:1500]}

══════════════════════════════════════════════════════════════════
🎯 DEVUELVE EL JSON CORREGIDO.
🚫 NO AGREGUES CAMPOS QUE NO ESTÉN EN LA PLANTILLA.
══════════════════════════════════════════════════════════════════
"""

    return system_prompt, user_prompt


def _detectar_errores_estructura(json_data: Dict) -> List[str]:
    """
    Detecta errores específicos en la estructura del JSON.
    
    ACTUALIZADO: Ahora detecta errores en la estructura de notario.
    """
    errores = []
    
    # Detectar campos extra en raíz
    campos_extra_raiz = set(json_data.keys()) - CAMPOS_RAIZ_PERMITIDOS
    if campos_extra_raiz:
        errores.append(f"Campos NO permitidos en raíz: {', '.join(campos_extra_raiz)}")
    
    # Detectar errores en notario
    notario = json_data.get("notario")
    if notario is not None:
        if isinstance(notario, str):
            errores.append("'notario' debe ser un ARRAY con un objeto, no un string")
        elif isinstance(notario, dict):
            errores.append("'notario' debe ser un ARRAY con un objeto, no un objeto directo")
        elif isinstance(notario, list):
            if len(notario) == 0:
                errores.append("'notario' está vacío, debe tener UN objeto")
            elif len(notario) > 0:
                notario_obj = notario[0]
                if isinstance(notario_obj, dict):
                    # Verificar campos del objeto notario
                    campos_extra_notario = set(notario_obj.keys()) - CAMPOS_NOTARIO_PERMITIDOS
                    if campos_extra_notario:
                        errores.append(f"notario[0] tiene campos extra: {', '.join(campos_extra_notario)}")
                    
                    # Verificar campos faltantes
                    campos_faltantes = CAMPOS_NOTARIO_PERMITIDOS - set(notario_obj.keys())
                    if campos_faltantes:
                        errores.append(f"notario[0] le faltan campos: {', '.join(campos_faltantes)}")
                elif isinstance(notario_obj, str):
                    errores.append("notario[0] debe ser un OBJETO con 5 campos, no un string")
    
    # Detectar problemas en titulares
    for i, titular in enumerate(json_data.get("titulares", [])):
        if isinstance(titular, dict):
            campos_extra = set(titular.keys()) - CAMPOS_TITULAR_PERMITIDOS
            if campos_extra:
                errores.append(f"titulares[{i}] tiene campos extra: {', '.join(campos_extra)}")
            
            if "representante_legal" in titular:
                errores.append(f"titulares[{i}]: 'representante_legal' debe ir DENTRO de 'representante'")
            
            if titular.get("representante") is None and "representante_legal" in titular:
                errores.append(f"titulares[{i}]: Mueve 'representante_legal' dentro del objeto 'representante'")
    
    # Detectar problemas en adquirientes
    for i, adq in enumerate(json_data.get("adquirientes", [])):
        if isinstance(adq, dict):
            campos_extra = set(adq.keys()) - CAMPOS_ADQUIRIENTE_PERMITIDOS
            if campos_extra:
                errores.append(f"adquirientes[{i}] tiene campos extra: {', '.join(campos_extra)}")
    
    # Detectar "documento" como campo
    if "documento" in json_data:
        errores.append("Campo 'documento' NO está permitido - extrae los datos directamente en los 9 campos")
    
    return errores


# =============================================================================
# LIMPIEZA DE JSON (POST-PROCESAMIENTO)
# =============================================================================

def limpiar_json_extra(json_data: Dict) -> Dict:
    """
    Elimina campos no permitidos del JSON y normaliza la estructura.
    
    Esta función es la ÚLTIMA LÍNEA DE DEFENSA para asegurar
    que el JSON tenga exactamente la estructura esperada.
    
    PROCESO:
    ========
    1. Filtra solo campos permitidos en raíz
    2. NUEVO: Normaliza notario a array de objetos
    3. Limpia cada titular (solo 3 campos)
    4. Convierte representante_legal → representante objeto
    5. Limpia cada adquiriente (solo 6 campos)
    6. Recupera datos de "documento" si existe
    
    NUEVA ESTRUCTURA DE NOTARIO:
    ============================
    notario: [
        {
            "nombre": "...",
            "numero_notario": "XX",      # 2-3 dígitos
            "municipio": "...",
            "escritura": "XXXX",         # 4-7 dígitos
            "fecha_documento": "..."
        }
    ]
    
    Args:
        json_data: JSON potencialmente con campos extra
        
    Returns:
        JSON limpio con solo campos permitidos
    """
    
    if not json_data:
        return {}
    
    resultado = {}
    
    # 1. Copiar solo campos permitidos de la raíz
    for campo in CAMPOS_RAIZ_PERMITIDOS:
        if campo in json_data:
            resultado[campo] = json_data[campo]
    
    # 2. NUEVO: Normalizar y limpiar notario
    resultado["notario"] = _limpiar_notario(json_data, resultado)
    
    # 3. Limpiar titulares
    if "titulares" in resultado and isinstance(resultado["titulares"], list):
        titulares_limpios = []
        for titular in resultado["titulares"]:
            if isinstance(titular, dict):
                titular_limpio = {}
                
                # Copiar solo campos permitidos
                for campo in CAMPOS_TITULAR_PERMITIDOS:
                    if campo in titular:
                        titular_limpio[campo] = titular[campo]
                
                # Caso especial: representante_legal como campo separado
                if titular_limpio.get("representante") is None:
                    # Buscar representante_legal
                    rep_legal = titular.get("representante_legal")
                    if rep_legal:
                        titular_limpio["representante"] = {
                            "nombre": rep_legal if isinstance(rep_legal, str) else str(rep_legal),
                            "en_calidad": titular.get("en_calidad", NO_ENCONTRADO),
                            "escritura": titular.get("escritura", NO_ENCONTRADO),
                            "bis": titular.get("bis", False),
                            "fecha_poder": titular.get("fecha_poder", NO_ENCONTRADO)
                        }
                
                # Limpiar objeto representante si existe
                if isinstance(titular_limpio.get("representante"), dict):
                    rep = titular_limpio["representante"]
                    rep_limpio = {}
                    for campo in CAMPOS_REPRESENTANTE_PERMITIDOS:
                        if campo in rep:
                            rep_limpio[campo] = rep[campo]
                        else:
                            # Valores por defecto
                            if campo == "bis":
                                rep_limpio[campo] = False
                            else:
                                rep_limpio[campo] = NO_ENCONTRADO
                    titular_limpio["representante"] = rep_limpio
                
                # Asegurar campos mínimos
                if "nombre" not in titular_limpio:
                    titular_limpio["nombre"] = NO_ENCONTRADO
                if "actua_por" not in titular_limpio:
                    titular_limpio["actua_por"] = NO_ENCONTRADO
                if "representante" not in titular_limpio:
                    titular_limpio["representante"] = None
                
                titulares_limpios.append(titular_limpio)
        
        resultado["titulares"] = titulares_limpios
    
    # 4. Limpiar adquirientes
    if "adquirientes" in resultado and isinstance(resultado["adquirientes"], list):
        adquirientes_limpios = []
        for adq in resultado["adquirientes"]:
            if isinstance(adq, dict):
                adq_limpio = {}
                for campo in CAMPOS_ADQUIRIENTE_PERMITIDOS:
                    if campo in adq:
                        adq_limpio[campo] = adq[campo]
                    else:
                        # Valores por defecto
                        if campo in ["rfc", "curp"]:
                            adq_limpio[campo] = False
                        else:
                            adq_limpio[campo] = None
                adquirientes_limpios.append(adq_limpio)
        resultado["adquirientes"] = adquirientes_limpios
    
    # 5. Recuperar datos del campo "documento" si existe
    if "documento" in json_data and isinstance(json_data["documento"], dict):
        doc = json_data["documento"]
        
        # Recuperar fecha
        if not resultado.get("fecha_documento") or resultado.get("fecha_documento") == NO_ENCONTRADO:
            if "fecha_documento" in doc:
                resultado["fecha_documento"] = doc["fecha_documento"]
            elif "fecha" in doc:
                resultado["fecha_documento"] = doc["fecha"]
        
        # Recuperar monto
        if not resultado.get("monto_operacion") or resultado.get("monto_operacion") == NO_ENCONTRADO:
            if "monto_operacion" in doc:
                monto = doc["monto_operacion"]
                if isinstance(monto, (int, float)):
                    resultado["monto_operacion"] = f"${monto:,.2f}"
                else:
                    resultado["monto_operacion"] = str(monto)
        
        # Recuperar notario del documento si no existe en resultado
        if not resultado.get("notario") or len(resultado["notario"]) == 0:
            if "notario" in doc:
                resultado["notario"] = _limpiar_notario(doc, resultado)
    
    return resultado


def _limpiar_notario(json_data: Dict, resultado: Dict) -> List[Dict]:
    """
    Normaliza y limpia el campo notario.
    
    CASOS QUE MANEJA:
    =================
    1. notario es STRING (formato antiguo)
       → Convertir a array con objeto: [{nombre: "...", ...}]
    
    2. notario es ARRAY de objetos (formato correcto)
       → Limpiar cada objeto, mantener solo campos permitidos
    
    3. notario es OBJETO sin array
       → Envolver en array y limpiar
    
    4. notario no existe o es None
       → Retornar array con objeto vacío/defaults
    
    Args:
        json_data: JSON original
        resultado: JSON resultado parcial (para obtener escritura, fecha)
        
    Returns:
        Array con un objeto notario limpio
    """
    
    notario_raw = json_data.get("notario")
    
    # Caso 1: notario es STRING (formato antiguo)
    if isinstance(notario_raw, str):
        # Convertir a nuevo formato
        return [
            {
                "nombre": notario_raw if notario_raw != NO_ENCONTRADO else NO_ENCONTRADO,
                "numero_notario": NO_ENCONTRADO,
                "municipio": NO_ENCONTRADO,
                "escritura": str(resultado.get("numero_escritura", NO_ENCONTRADO)),
                "fecha_documento": resultado.get("fecha_documento", NO_ENCONTRADO)
            }
        ]
    
    # Caso 2: notario es ARRAY de objetos
    if isinstance(notario_raw, list):
        notarios_limpios = []
        for notario_obj in notario_raw[:1]:  # Solo el primer notario (máximo 1)
            if isinstance(notario_obj, dict):
                notario_limpio = _limpiar_objeto_notario(notario_obj, resultado)
                notarios_limpios.append(notario_limpio)
        
        # Si el array estaba vacío, crear objeto con defaults
        if len(notarios_limpios) == 0:
            notarios_limpios.append(_crear_notario_vacio(resultado))
        
        return notarios_limpios
    
    # Caso 3: notario es OBJETO sin array
    if isinstance(notario_raw, dict):
        return [_limpiar_objeto_notario(notario_raw, resultado)]
    
    # Caso 4: notario no existe o es None
    return [_crear_notario_vacio(resultado)]


def _limpiar_objeto_notario(notario_obj: Dict, resultado: Dict) -> Dict:
    """
    Limpia un objeto notario individual.
    
    Filtra solo los campos permitidos y asegura valores por defecto.
    
    CAMPOS PERMITIDOS:
    ==================
    - nombre: Nombre del notario
    - numero_notario: 2-3 dígitos
    - municipio: Municipio de la notaría
    - escritura: 4-7 dígitos
    - fecha_documento: Fecha del documento
    """
    
    notario_limpio = {}
    
    for campo in CAMPOS_NOTARIO_PERMITIDOS:
        if campo in notario_obj:
            valor = notario_obj[campo]
            # Convertir números a string para numero_notario y escritura
            if campo in ["numero_notario", "escritura"] and isinstance(valor, int):
                valor = str(valor)
            notario_limpio[campo] = valor
        else:
            # Valores por defecto
            if campo == "escritura":
                notario_limpio[campo] = str(resultado.get("numero_escritura", NO_ENCONTRADO))
            elif campo == "fecha_documento":
                notario_limpio[campo] = resultado.get("fecha_documento", NO_ENCONTRADO)
            else:
                notario_limpio[campo] = NO_ENCONTRADO
    
    return notario_limpio


def _crear_notario_vacio(resultado: Dict) -> Dict:
    """
    Crea un objeto notario con valores por defecto.
    
    Usa los datos disponibles en resultado para escritura y fecha.
    """
    return {
        "nombre": NO_ENCONTRADO,
        "numero_notario": NO_ENCONTRADO,
        "municipio": NO_ENCONTRADO,
        "escritura": str(resultado.get("numero_escritura", NO_ENCONTRADO)),
        "fecha_documento": resultado.get("fecha_documento", NO_ENCONTRADO)
    }


# =============================================================================
# UTILIDADES
# =============================================================================

def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """
    Estima el número de tokens en un texto.
    
    La estimación es aproximada: ~4 caracteres por token en español.
    """
    return int(len(text) / chars_per_token)


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DEL CONSTRUCTOR DE PROMPTS (ESTRICTO)")
    print("=" * 60)
    
    # Prueba 1: Limpieza de JSON con notario como STRING (formato antiguo)
    print("\n📋 Prueba 1: Conversión de notario STRING → ARRAY")
    
    json_malo = {
        "notario": "RIGOBERTO OCHOA TORRES",  # STRING (formato antiguo)
        "numero_escritura": 2307,
        "fecha_documento": "5 de mayo de 2023",
        "tipo_titular": "empresa",
        "titulares": [
            {
                "nombre": "Instituto Nacional...",
                "actua_por": "representación",
                "representante": None,
                "representante_legal": "Ernesto Padilla Aceves"  # Campo extra a convertir
            }
        ],
        "adquirientes": [
            {
                "nombre": "Angelita Pérez Soto",
                "estado_civil": "casada",
                "gestora_negocios": "María..."  # Campo extra a eliminar
            }
        ]
    }
    
    print("\n❌ JSON original (notario como string):")
    print(f"   notario: {json_malo['notario']}")
    
    json_limpio = limpiar_json_extra(json_malo)
    
    print("\n✅ JSON limpio (notario como array):")
    print(json.dumps(json_limpio["notario"], indent=2, ensure_ascii=False))
    
    # Verificaciones
    assert isinstance(json_limpio["notario"], list), "notario debería ser array"
    assert len(json_limpio["notario"]) == 1, "notario debería tener 1 elemento"
    assert json_limpio["notario"][0]["nombre"] == "RIGOBERTO OCHOA TORRES"
    assert json_limpio["notario"][0]["escritura"] == "2307"
    assert json_limpio["notario"][0]["fecha_documento"] == "5 de mayo de 2023"
    print("   ✅ notario convertido correctamente a array")
    
    # Prueba 2: notario ya como ARRAY (formato correcto)
    print("\n📋 Prueba 2: notario ya como ARRAY (sin cambios)")
    
    json_con_array = {
        "notario": [
            {
                "nombre": "FERNANDO CASTRO RUBIO",
                "numero_notario": "45",
                "municipio": "Guadalajara",
                "escritura": "2736",
                "fecha_documento": "13 de marzo de 2024",
                "campo_extra": "eliminar"  # Campo extra a eliminar
            }
        ],
        "numero_escritura": 2736,
        "tipo_titular": "empresa",
        "titulares": [],
        "adquirientes": []
    }
    
    json_limpio2 = limpiar_json_extra(json_con_array)
    
    assert json_limpio2["notario"][0]["nombre"] == "FERNANDO CASTRO RUBIO"
    assert "campo_extra" not in json_limpio2["notario"][0]
    print("   ✅ notario array limpiado correctamente")
    
    # Prueba 3: Verificar representante_legal → representante
    print("\n📋 Prueba 3: Conversión representante_legal → representante")
    assert json_limpio["titulares"][0]["representante"] is not None
    assert json_limpio["titulares"][0]["representante"]["nombre"] == "Ernesto Padilla Aceves"
    print("   ✅ representante_legal convertido a objeto representante")
    
    # Prueba 4: Verificar eliminación de campos extra
    print("\n📋 Prueba 4: Eliminación de campos extra")
    assert "gestora_negocios" not in json_limpio["adquirientes"][0]
    print("   ✅ Campo gestora_negocios eliminado")
    
    # Mostrar JSON final
    print("\n" + "=" * 60)
    print("JSON FINAL LIMPIO:")
    print("=" * 60)
    print(json.dumps(json_limpio, indent=2, ensure_ascii=False))
    
    print("\n✅ Todas las pruebas pasaron correctamente")
