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

NO_ENCONTRADO = None  # Valor por defecto cuando no se encuentra un dato

# Campos permitidos en cada nivel (para validación y limpieza)
CAMPOS_RAIZ_PERMITIDOS = {
    "numero_escritura", "fecha_documento", "numero_notaria",
    "municipio", "nombre_notario", "tipo_titular",
    "titulares", "adquirientes", "monto_operacion", "valor_catastral", "curps"
}

CAMPOS_TITULAR_PERMITIDOS = {
    "nombre", "tipo", "actua_por", "representante"
}

CAMPOS_REPRESENTANTE_PERMITIDOS = {
    "nombre", "en_calidad", "escritura", "bis", "fecha_poder"
}

CAMPOS_ADQUIRIENTE_PERMITIDOS = {
    "nombre", "tipo", "actua_por", "estado_civil", "tipo_sociedad", "edad", "rfc", "curp", "representante"
}


# =============================================================================
# FUNCIONES DE RECUPERACIÓN Y NORMALIZACIÓN
# =============================================================================

def _recuperar_datos_estructura_alternativa(json_data: dict) -> dict:
    """
    Recupera datos de estructuras alternativas que el LLM puede generar.
    
    PROBLEMA QUE RESUELVE:
    ======================
    El LLM a veces genera estructuras como:
    
        {
            "Documento": {
                "Partes": {
                    "Vendedor": "Instituto Nacional...",
                    "Comprador": "ANGELBERTA PÉREZ SOTO"
                },
                "Fecha": "05/05/2023",
                "Escritura": {"Numero": "2307"}
            }
        }
    
    En lugar de la estructura esperada con "titulares" y "adquirientes".
    
    CÓMO FUNCIONA:
    ==============
    1. Detecta si existe el campo "Documento" (estructura alternativa)
    2. Extrae los datos anidados y los mapea a la estructura esperada
    3. También busca campos alternativos en raíz ("vendedor", "comprador")
    
    Args:
        json_data: JSON original del LLM
        
    Returns:
        JSON con datos recuperados en la estructura correcta
        
    Ejemplo:
        >>> entrada = {"Documento": {"Partes": {"Vendedor": "INSUS"}}}
        >>> salida = _recuperar_datos_estructura_alternativa(entrada)
        >>> print(salida.get("titulares"))
        [{"nombre": "INSUS", "actua_por": None, "representante": None}]
    """
    
    # Si ya tiene la estructura correcta, retornar sin cambios
    if "titulares" in json_data and json_data["titulares"]:
        return json_data
    
    resultado = dict(json_data)  # Copia para no modificar original
    
    # =========================================================================
    # ESTRATEGIA 1: Buscar estructura "Documento"
    # =========================================================================
    
    documento = json_data.get("Documento") or json_data.get("documento")
    
    if documento and isinstance(documento, dict):
        print("   🔄 Recuperando datos de estructura 'Documento'...")
        
        # Extraer "Partes" (Vendedor/Comprador)
        partes = documento.get("Partes") or documento.get("partes") or {}
        
        # -----------------------------------------------------------------
        # Recuperar VENDEDOR → titulares
        # -----------------------------------------------------------------
        vendedor = (
            partes.get("Vendedor") or 
            partes.get("vendedor") or
            documento.get("Vendedor") or
            documento.get("vendedor")
        )
        
        if vendedor and not resultado.get("titulares"):
            if isinstance(vendedor, str):
                resultado["titulares"] = [{
                    "nombre": vendedor,
                    "actua_por": NO_ENCONTRADO,
                    "representante": None
                }]
            elif isinstance(vendedor, dict):
                nombre_vendedor = (
                    vendedor.get("nombre") or 
                    vendedor.get("Nombre") or
                    vendedor.get("razon_social") or
                    str(vendedor)
                )
                resultado["titulares"] = [{
                    "nombre": nombre_vendedor,
                    "actua_por": vendedor.get("actua_por", NO_ENCONTRADO),
                    "representante": vendedor.get("representante")
                }]
            
            print(f"      ✅ Recuperado vendedor: {resultado['titulares'][0]['nombre'][:50]}...")
        
        # -----------------------------------------------------------------
        # Recuperar COMPRADOR → adquirientes
        # -----------------------------------------------------------------
        comprador = (
            partes.get("Comprador") or 
            partes.get("comprador") or
            documento.get("Comprador") or
            documento.get("comprador")
        )
        
        if comprador and not resultado.get("adquirientes"):
            if isinstance(comprador, str):
                resultado["adquirientes"] = [{
                    "nombre": comprador,
                    "estado_civil": NO_ENCONTRADO,
                    "tipo_sociedad": None,
                    "edad": None,
                    "rfc": False,
                    "curp": False
                }]
            elif isinstance(comprador, dict):
                nombre_comprador = (
                    comprador.get("nombre") or 
                    comprador.get("Nombre") or
                    str(comprador)
                )
                resultado["adquirientes"] = [{
                    "nombre": nombre_comprador,
                    "estado_civil": comprador.get("estado_civil", NO_ENCONTRADO),
                    "tipo_sociedad": comprador.get("tipo_sociedad"),
                    "edad": comprador.get("edad"),
                    "rfc": comprador.get("rfc", False),
                    "curp": comprador.get("curp", False)
                }]
            
            print(f"      ✅ Recuperado comprador: {resultado['adquirientes'][0]['nombre'][:50]}...")
        
        # -----------------------------------------------------------------
        # Recuperar otros campos del documento
        # -----------------------------------------------------------------
        
        # Fecha
        if not resultado.get("fecha_documento") or resultado.get("fecha_documento") == NO_ENCONTRADO:
            fecha = (
                documento.get("Fecha") or 
                documento.get("fecha") or
                documento.get("fecha_documento")
            )
            if fecha:
                resultado["fecha_documento"] = fecha
                print(f"      ✅ Recuperada fecha: {fecha}")
        
        # Escritura
        escritura_obj = documento.get("Escritura") or documento.get("escritura") or {}
        if isinstance(escritura_obj, dict):
            numero_esc = escritura_obj.get("Numero") or escritura_obj.get("numero")
            if numero_esc and not resultado.get("numero_escritura"):
                try:
                    resultado["numero_escritura"] = int(str(numero_esc).replace(",", ""))
                    print(f"      ✅ Recuperado numero_escritura: {resultado['numero_escritura']}")
                except ValueError:
                    pass
        
        # Monto
        monto = (
            documento.get("Consideraciones") or
            documento.get("Precio") or
            documento.get("precio") or
            documento.get("Monto") or
            documento.get("monto") or
            documento.get("monto_operacion")
        )
        if monto and (not resultado.get("monto_operacion") or resultado.get("monto_operacion") == NO_ENCONTRADO):
            if isinstance(monto, str):
                resultado["monto_operacion"] = monto
            elif isinstance(monto, (int, float)):
                resultado["monto_operacion"] = f"${monto:,.2f}"
            print(f"      ✅ Recuperado monto: {resultado.get('monto_operacion')}")
    
    # =========================================================================
    # ESTRATEGIA 2: Buscar campos alternativos en raíz
    # =========================================================================
    
    MAPEO_ALTERNATIVOS = {
        # Titulares
        "vendedor": "titulares",
        "vendedores": "titulares",
        "transmitente": "titulares",
        "transmitentes": "titulares",
        "enajenante": "titulares",
        "enajenantes": "titulares",
        "propietario": "titulares",
        "propietarios": "titulares",
        
        # Adquirientes
        "comprador": "adquirientes",
        "compradores": "adquirientes",
        "adquirente": "adquirientes",
        "adquirentes": "adquirientes",
        "beneficiario": "adquirientes",
        "beneficiarios": "adquirientes",
    }
    
    for campo_alt, campo_correcto in MAPEO_ALTERNATIVOS.items():
        if campo_alt in json_data and not resultado.get(campo_correcto):
            valor = json_data[campo_alt]
            
            if isinstance(valor, str):
                if campo_correcto == "titulares":
                    resultado[campo_correcto] = [{
                        "nombre": valor,
                        "actua_por": NO_ENCONTRADO,
                        "representante": None
                    }]
                else:
                    resultado[campo_correcto] = [{
                        "nombre": valor,
                        "estado_civil": NO_ENCONTRADO,
                        "tipo_sociedad": None,
                        "edad": None,
                        "rfc": False,
                        "curp": False
                    }]
            elif isinstance(valor, list):
                resultado[campo_correcto] = valor
            elif isinstance(valor, dict):
                resultado[campo_correcto] = [valor]
            
            print(f"   🔄 Mapeado '{campo_alt}' → '{campo_correcto}'")
    
    return resultado


def _normalizar_valores_null(json_data: dict) -> dict:
    """
    Convierte valores `null` a valores válidos según el tipo esperado.
    
    PROBLEMA QUE RESUELVE:
    ======================
    El LLM genera JSON con valores `null` donde Pydantic espera strings:
    
        {
            "adquirientes": [{
                "estado_civil": null,    ← Error: espera str
                "rfc": null              ← Debería ser False
            }]
        }
    
    Error de Pydantic:
    "Input should be a valid string [type=string_type, input_value=None]"
    
    CÓMO FUNCIONA:
    ==============
    1. Recorre recursivamente el JSON (porque hay estructuras anidadas)
    2. Para campos string obligatorios: null → "NO SE ENCONTRÓ DATO"
    3. Para campos boolean (rfc, curp, bis): null → False
    
    Args:
        json_data: JSON con posibles valores null
        
    Returns:
        JSON con valores normalizados
    """
    
    if not json_data:
        return json_data
    
    # Campos que DEBEN ser string (no pueden ser null)
    CAMPOS_STRING_OBLIGATORIOS = {
        "fecha_documento",
        "tipo_titular",
        "monto_operacion",
        "nombre",
        "actua_por",
        "en_calidad",
        "fecha_poder",
        "estado_civil",
        "municipio",
    }
    
    # Campos que deben ser boolean (null → False)
    CAMPOS_BOOLEAN = {"rfc", "curp", "bis"}
    
    def normalizar_recursivo(obj, campo_padre=None):
        """Normaliza valores null de forma recursiva."""
        
        if obj is None:
            return obj
        
        if isinstance(obj, dict):
            resultado_dict = {}
            for key, value in obj.items():
                if value is None:
                    if key in CAMPOS_STRING_OBLIGATORIOS:
                        resultado_dict[key] = NO_ENCONTRADO
                    elif key in CAMPOS_BOOLEAN:
                        resultado_dict[key] = False
                    else:
                        resultado_dict[key] = None
                elif isinstance(value, (dict, list)):
                    resultado_dict[key] = normalizar_recursivo(value, key)
                else:
                    resultado_dict[key] = value
            return resultado_dict
        
        elif isinstance(obj, list):
            return [normalizar_recursivo(item, campo_padre) for item in obj]
        
        else:
            return obj
    
    return normalizar_recursivo(json_data)


# =============================================================================
# EJEMPLOS JSON EXACTOS
# =============================================================================

EJEMPLO_JSON_EMPRESA = {
    "numero_escritura": 2397,
    "fecha_documento": "5 de mayo de 2023",
    "numero_notaria": "45",
    "municipio": "Tepic, Nayarit",
    "nombre_notario": "RIGOBERTO OCHOA TORRES",
    "tipo_titular": None,  # DEPRECATED: usar campo 'tipo' individual
    "titulares": [
        {
            "nombre": "Instituto Nacional del Suelo Sustentable (INSUS)",
            "tipo": "empresa",
            "actua_por": "representación",
            "representante": {
                "nombre": "Ernesto Padilla Aceves",
                "en_calidad": "Representante Regional",
                "escritura": None,
                "bis": False,
                "fecha_poder": "5 de mayo de 2023"
            }
        }
    ],
    "adquirientes": [
        {
            "nombre": "Angelita Pérez Soto",
            "tipo": "persona",
            "actua_por": "derecho propio",
            "estado_civil": "casada",
            "tipo_sociedad": None,
            "edad": None,
            "rfc": False,
            "curp": False,
            "representante": None
        }
    ],
    "monto_operacion": "$8,654.00",
    "valor_catastral": None,
    "curps": []
}

EJEMPLO_JSON_EMPRESA_2 = {
    "numero_escritura": 2736,
    "fecha_documento": "13 de marzo de 2024",
    "numero_notaria": "123",
    "municipio": "Guadalajara, Jalisco",
    "nombre_notario": "FERNANDO CASTRO RUBIO",
    "tipo_titular": None,  # DEPRECATED: usar campo 'tipo' individual
    "titulares": [
        {
            "nombre": "KUBBOX ARQUITECTURA, SOCIEDAD ANONIMA DE CAPITAL VARIABLE",
            "tipo": "empresa",
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
            "tipo": "persona",
            "actua_por": "derecho propio",
            "estado_civil": "casada",
            "tipo_sociedad": "separación de bienes",
            "edad": None,
            "rfc": False,
            "curp": False,
            "representante": None
        }
    ],
    "monto_operacion": "$3,100,000.00",
    "valor_catastral": None,
    "curps": []
}

EJEMPLO_JSON_PERSONA = {
    "numero_escritura": 5432,
    "fecha_documento": "20 de junio de 2024",
    "numero_notaria": "78",
    "municipio": "Ciudad de México",
    "nombre_notario": "María López Hernández",
    "tipo_titular": None,  # DEPRECATED: usar campo 'tipo' individual
    "titulares": [
        {
            "nombre": "Juan Carlos Pérez García",
            "tipo": "persona",
            "actua_por": "derecho propio",
            "representante": None
        }
    ],
    "adquirientes": [
        {
            "nombre": "Ana María Rodríguez López",
            "tipo": "persona",
            "actua_por": "derecho propio",
            "estado_civil": "soltera",
            "tipo_sociedad": None,
            "edad": 35,
            "rfc": "ROLA890515ABC",
            "curp": False,
            "representante": None
        }
    ],
    "monto_operacion": "$1,200,000.00",
    "valor_catastral": "$950,000.00",
    "curps": []
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
5. Si no encuentras un dato, usa null (NUNCA uses strings como "NO SE ENCONTRÓ DATO" o "N/A")

CAMPOS PROHIBIDOS (NUNCA LOS USES):
- representante_legal (el representante va DENTRO del objeto "representante")
- notario (como array u objeto)
- rfcs (como array)
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

El JSON debe tener EXACTAMENTE los campos especificados en la plantilla."""

# Alias para compatibilidad
SYSTEM_PROMPT_EXTRACCION = SYSTEM_PROMPT_ESTRICTO


# =============================================================================
# FUNCIONES PRINCIPALES
# =============================================================================

def build_extraction_prompt(
    document_text: str,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Construye el prompt de extracción genérico sin clasificación previa.

    El LLM determinará el tipo de cada titular/adquiriente individualmente.

    Args:
        document_text: Texto del documento a procesar
        include_examples: Si incluir ejemplos

    Returns:
        Tupla (system_prompt, user_prompt)
    """
    return _build_prompt_generico(document_text, include_examples)


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

INSTRUCCIONES IMPORTANTES:
=========================

1. NOMBRE DEL NOTARIO:
   - Busca en el ENCABEZADO frases como "ante mí", "Notario Público", "Titular de la Notaría"
   - Extrae el nombre completo en MAYÚSCULAS sin títulos (Lic., Dr., etc.)
   - Ejemplo correcto: "RIGOBERTO OCHOA TORRES"
   - Si NO lo encuentras, usa null (NUNCA uses placeholders como "NOMBRE DEL NOTARIO")

2. CAMPO "tipo" EN TITULARES Y ADQUIRIENTES:
   - Cada titular/adquiriente DEBE tener campo "tipo": "empresa" o "persona"
   - Si es EMPRESA/INSTITUCIÓN (S.A., S.C., Instituto, Gobierno, etc.):
     * tipo: "empresa"
     * DEBE tener representante (persona física que firma)
   - Si es PERSONA FÍSICA (actúa por sí misma):
     * tipo: "persona"
     * representante es OPCIONAL (solo si tiene apoderado)

3. VALORES POR DEFECTO:
   - Si NO encuentras un dato, usa null
   - NUNCA uses strings como "NO SE ENCONTRÓ DATO", "N/A", "NOMBRE DEL NOTARIO", etc.

PLANTILLA JSON (campos obligatorios):
======================================

{
    "numero_escritura": 1234,
    "fecha_documento": "fecha",
    "numero_notaria": "45",
    "municipio": "CIUDAD, ESTADO",
    "nombre_notario": null,  // Extraer del encabezado (ej: "RIGOBERTO OCHOA TORRES")
    "tipo_titular": null,  // DEPRECATED: ignorar
    "titulares": [
        {
            "nombre": "NOMBRE",
            "tipo": "empresa" o "persona",
            "actua_por": "representación" o "derecho propio",
            "representante": null o {nombre, en_calidad, escritura, bis, fecha_poder}
        }
    ],
    "adquirientes": [
        {
            "nombre": "NOMBRE",
            "tipo": "empresa" o "persona",
            "actua_por": "derecho propio" o "representación",
            "estado_civil": false,  // false si no existe
            "tipo_sociedad": false,  // false si no existe
            "edad": false,           // false si no existe
            "rfc": false,            // false si no existe
            "curp": false,           // false si no existe
            "representante": null o {objeto}
        }
    ],
    "monto_operacion": "$X,XXX.XX",
    "valor_catastral": null,
    "curps": []
}

REGLAS IMPORTANTES:
===================
1. TITULARES: Solo necesitan nombre, tipo, actua_por, representante
2. ADQUIRIENTES: Además de lo anterior, incluyen estado_civil, tipo_sociedad, edad, rfc, curp
3. Si titular/adquiriente es EMPRESA → representante es OBLIGATORIO
4. Si titular/adquiriente es PERSONA → representante es OPCIONAL
5. Para campos estado_civil, tipo_sociedad, edad, rfc, curp en adquirientes:
   - Si NO existen en el documento → usa "false"
   - Si SÍ existen → extrae el valor

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
3. Usa SOLO los campos de la plantilla
4. El "representante" debe ser un OBJETO con 5 campos, NO un string separado
5. NO crees estructuras como "documento", "inmueble", "firmas"
6. NO uses campos prohibidos como "notario" (array), "rfcs" (lista), "tipo_moneda\""""

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
    "numero_escritura": 1234,
    "fecha_documento": "...",
    "numero_notaria": "45",
    "municipio": "CIUDAD, ESTADO",
    "nombre_notario": null,  // Extraer del encabezado (ej: "RIGOBERTO OCHOA TORRES")
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
            "actua_por": "...",
            "estado_civil": "...",
            "tipo_sociedad": null,
            "edad": null,
            "rfc": false,
            "curp": false,
            "representante": null
        }}
    ],
    "monto_operacion": "...",
    "valor_catastral": null,
    "curps": []
}}

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
    """
    errores = []

    # Detectar campos extra en raíz
    campos_extra_raiz = set(json_data.keys()) - CAMPOS_RAIZ_PERMITIDOS
    if campos_extra_raiz:
        errores.append(f"Campos NO permitidos en raíz: {', '.join(campos_extra_raiz)}")

    # Detectar campo "notario" prohibido
    if "notario" in json_data:
        errores.append("Campo 'notario' (como array u objeto) ya NO se usa - usa numero_notaria, nombre_notario, municipio")

    # Detectar campo "rfcs" prohibido
    if "rfcs" in json_data:
        errores.append("Campo 'rfcs' (como lista) ya NO se usa")

    # Detectar campo "tipo_moneda" prohibido
    if "tipo_moneda" in json_data:
        errores.append("Campo 'tipo_moneda' ya NO se usa")
    
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
    0. Recuperar datos de estructuras alternativas (Documento, vendedor, etc.)
    0b. Normalizar valores null a valores válidos
    1. Filtra solo campos permitidos en raíz (elimina notario, rfcs, tipo_moneda)
    2. Limpia cada titular (solo 3 campos)
    3. Convierte representante_legal → representante objeto
    4. Limpia cada adquiriente
    5. Recupera datos de "documento" si existe
    
    Args:
        json_data: JSON potencialmente con campos extra
        
    Returns:
        JSON limpio con solo campos permitidos
    """
    
    if not json_data:
        return {}
    
    # =========================================================================
    # PASO 0: Recuperar datos de estructuras alternativas del LLM
    # =========================================================================
    # Si el LLM generó estructuras como "Documento", "vendedor", etc.
    # las convertimos a la estructura esperada antes de limpiar
    json_data = _recuperar_datos_estructura_alternativa(json_data)
    
    # =========================================================================
    # PASO 0b: Normalizar valores null a valores válidos
    # =========================================================================
    # Convierte null → "NO SE ENCONTRÓ DATO" para campos string
    # Convierte null → False para campos boolean (rfc, curp, bis)
    json_data = _normalizar_valores_null(json_data)
    
    resultado = {}

    # 1. Copiar solo campos permitidos de la raíz
    for campo in CAMPOS_RAIZ_PERMITIDOS:
        if campo in json_data:
            resultado[campo] = json_data[campo]

    # 2. Extraer datos del campo "notario" prohibido (si existe) y migrarlos
    if "notario" in json_data:
        notario = json_data["notario"]
        # Si notario es array con un objeto
        if isinstance(notario, list) and len(notario) > 0 and isinstance(notario[0], dict):
            notario_obj = notario[0]
            if "nombre" in notario_obj and "nombre_notario" not in resultado:
                resultado["nombre_notario"] = notario_obj["nombre"]
            if "numero_notario" in notario_obj and "numero_notaria" not in resultado:
                resultado["numero_notaria"] = str(notario_obj["numero_notario"])
            if "municipio" in notario_obj and "municipio" not in resultado:
                resultado["municipio"] = notario_obj["municipio"]
    
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
                        # Limpiar representante recursivamente
                        if campo == "representante" and isinstance(adq[campo], dict):
                            rep_limpio = {}
                            for rep_campo in CAMPOS_REPRESENTANTE_PERMITIDOS:
                                if rep_campo in adq[campo]:
                                    rep_limpio[rep_campo] = adq[campo][rep_campo]
                            adq_limpio[campo] = rep_limpio if rep_limpio else None
                        else:
                            adq_limpio[campo] = adq[campo]
                    else:
                        # Valores por defecto
                        if campo == "actua_por":
                            adq_limpio[campo] = None
                        elif campo == "representante":
                            adq_limpio[campo] = None
                        elif campo in ["rfc", "curp"]:
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

    # Prueba 1: Limpieza de JSON con campo notario prohibido (array antiguo)
    print("\nPrueba 1: Migracion de notario array a campos individuales")

    json_malo = {
        "notario": [  # Campo prohibido - debe migrarse
            {
                "nombre": "RIGOBERTO OCHOA TORRES",
                "numero_notario": "45",
                "municipio": "Tepic, Nayarit"
            }
        ],
        "numero_escritura": 2307,
        "fecha_documento": "5 de mayo de 2023",
        "tipo_titular": "empresa",
        "titulares": [
            {
                "nombre": "Instituto Nacional...",
                "actua_por": "representacion",
                "representante": None,
                "representante_legal": "Ernesto Padilla Aceves"  # Campo extra a convertir
            }
        ],
        "adquirientes": [
            {
                "nombre": "Angelita Perez Soto",
                "estado_civil": "casada",
                "gestora_negocios": "Maria..."  # Campo extra a eliminar
            }
        ]
    }

    print("\nJSON original con campo 'notario' prohibido")

    json_limpio = limpiar_json_extra(json_malo)

    print("\nJSON limpio con campos migrados:")
    print(f"  numero_notaria: {json_limpio.get('numero_notaria')}")
    print(f"  nombre_notario: {json_limpio.get('nombre_notario')}")
    print(f"  municipio: {json_limpio.get('municipio')}")

    # Verificaciones
    assert "notario" not in json_limpio, "notario no deberia estar en el JSON limpio"
    assert json_limpio["nombre_notario"] == "RIGOBERTO OCHOA TORRES"
    assert json_limpio["numero_notaria"] == "45"
    assert json_limpio["municipio"] == "Tepic, Nayarit"
    print("  OK - Campos migrados correctamente")

    # Prueba 2: JSON con campos prohibidos (rfcs, tipo_moneda)
    print("\nPrueba 2: Eliminacion de campos prohibidos (rfcs, tipo_moneda)")

    json_con_prohibidos = {
        "numero_escritura": 2736,
        "numero_notaria": "45",
        "nombre_notario": "FERNANDO CASTRO RUBIO",
        "municipio": "Guadalajara",
        "tipo_titular": "empresa",
        "rfcs": ["RFC123", "RFC456"],  # Campo prohibido
        "tipo_moneda": "MXN",  # Campo prohibido
        "titulares": [],
        "adquirientes": []
    }

    json_limpio2 = limpiar_json_extra(json_con_prohibidos)

    assert "rfcs" not in json_limpio2, "rfcs no deberia estar en el JSON limpio"
    assert "tipo_moneda" not in json_limpio2, "tipo_moneda no deberia estar en el JSON limpio"
    print("  OK - Campos prohibidos eliminados correctamente")

    # Prueba 3: Verificar representante_legal -> representante
    print("\nPrueba 3: Conversion representante_legal -> representante")
    assert json_limpio["titulares"][0]["representante"] is not None
    assert json_limpio["titulares"][0]["representante"]["nombre"] == "Ernesto Padilla Aceves"
    print("  OK - representante_legal convertido a objeto representante")

    # Prueba 4: Verificar eliminacion de campos extra
    print("\nPrueba 4: Eliminacion de campos extra")
    assert "gestora_negocios" not in json_limpio["adquirientes"][0]
    print("  OK - Campo gestora_negocios eliminado")

    # Mostrar JSON final
    print("\n" + "=" * 60)
    print("JSON FINAL LIMPIO:")
    print("=" * 60)
    print(json.dumps(json_limpio, indent=2, ensure_ascii=False))

    print("\nTodas las pruebas pasaron correctamente")
