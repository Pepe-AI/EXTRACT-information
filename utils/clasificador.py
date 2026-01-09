"""
utils/clasificador.py - Clasificación ligera de documentos (Fase 1)

PROPÓSITO:
==========
Este módulo implementa la FASE 1 del sistema híbrido de extracción.
Antes de extraer todos los datos, primero clasificamos el documento para:

1. Determinar si el titular es EMPRESA/INSTITUCIÓN o PERSONA FÍSICA
2. Identificar quién es el TITULAR (la entidad que vende/transmite)
3. Identificar quién es el REPRESENTANTE (la persona física que firma)

¿POR QUÉ ES NECESARIO?
======================
Sin clasificación previa, el LLM a veces confunde:
- Pone a la persona física como titular cuando debería ser la institución
- Pone a la institución como representante cuando debería ser la persona

Con clasificación previa:
- El LLM ya sabe de antemano quién es quién
- Solo necesita extraer los detalles adicionales
- Reduce errores de confusión titular/representante

FLUJO:
======
1. Tomar los primeros ~3000 caracteres del documento
2. Enviar prompt corto a DeepSeek (solo para clasificar)
3. Validar la clasificación con patrones regex (código Python)
4. Devolver clasificación confirmada para usar en Fase 2
"""

import re
import json
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass


# =============================================================================
# CONSTANTES Y PATRONES
# =============================================================================

# Patrones que SIEMPRE indican empresa/institución (nunca una persona física)
PATRONES_EMPRESA = [
    # Sociedades mercantiles mexicanas
    (r'\bS\.?\s*A\.?\s*(?:DE\s*)?C\.?\s*V\.?\b', "S.A. de C.V."),
    (r'\bS\.?\s*A\.?\b(?!\s*(?:lud|nto|lvador))', "S.A."),  # Evita "Salud", "Santo", "Salvador"
    (r'\bS\.?\s*DE\s*R\.?\s*L\.?\b', "S. de R.L."),
    (r'\bS\.?\s*A\.?\s*B\.?\b', "S.A.B."),
    (r'\bS\.?\s*A\.?\s*P\.?\s*I\.?\b', "S.A.P.I."),
    (r'\bS\.?\s*C\.?\s*(?!ott)\b', "S.C."),  # Evita "Scott"
    
    # Asociaciones
    (r'\bA\.?\s*C\.?\b', "A.C."),
    (r'\bI\.?\s*A\.?\s*P\.?\b', "I.A.P."),
    
    # Instituciones gubernamentales (palabras clave)
    (r'\bINSTITUTO\s+(?:NACIONAL|ESTATAL|MUNICIPAL|FEDERAL)\b', "Instituto gubernamental"),
    (r'\bINSTITUTO\b', "Instituto"),
    (r'\bSECRETAR[IÍ]A\s+DE\b', "Secretaría"),
    (r'\bGOBIERNO\s+(?:DEL\s+)?(?:ESTADO|FEDERAL|MUNICIPAL)\b', "Gobierno"),
    (r'\bGOBIERNO\b', "Gobierno"),
    (r'\bMUNICIPIO\s+DE\b', "Municipio"),
    (r'\bAYUNTAMIENTO\b', "Ayuntamiento"),
    (r'\bDELEGACI[OÓ]N\b', "Delegación"),
    (r'\bALCALD[IÍ]A\b', "Alcaldía"),
    
    # Organismos públicos conocidos (acrónimos)
    (r'\bINFONAVIT\b', "INFONAVIT"),
    (r'\bFOVISSSTE\b', "FOVISSSTE"),
    (r'\bINSS\b', "INSS"),
    (r'\bFONHAPO\b', "FONHAPO"),
    (r'\bCONAVI\b', "CONAVI"),
    (r'\bSEDATU\b', "SEDATU"),
    (r'\bIMSS\b', "IMSS"),
    (r'\bISSSTE\b', "ISSSTE"),
    (r'\bCONADUPI\b', "CONADUPI"),
    (r'\bCONASAMI\b', "CONASAMI"),
    
    # Fideicomisos y fondos
    (r'\bFIDEICOMISO\b', "Fideicomiso"),
    (r'\bFONDO\s+(?:DE|NACIONAL|ESTATAL)\b', "Fondo"),
    
    # Palabras que sugieren entidad empresarial
    (r'\bDESARROLLOS?\s+(?:INMOBILIARIOS?|URBANOS?|TUR[IÍ]STICOS?)\b', "Desarrollos"),
    (r'\bINMOBILIARIA\b', "Inmobiliaria"),
    (r'\bCONSTRUCTORA\b', "Constructora"),
    (r'\bCORPORATIVO\b', "Corporativo"),
    (r'\bGRUPO\s+(?:FINANCIERO|INMOBILIARIO|INDUSTRIAL)\b', "Grupo empresarial"),
    (r'\bHOLDING\b', "Holding"),
    (r'\bCOMERCIALIZADORA\b', "Comercializadora"),
    (r'\bPROMOTORA\b', "Promotora"),
    (r'\bADMINISTRADORA\b', "Administradora"),
    (r'\bSOCIEDAD\s+(?:MERCANTIL|AN[OÓ]NIMA|CIVIL)\b', "Sociedad"),
    (r'\bORGANISMO\s+(?:P[UÚ]BLICO|DESCENTRALIZADO)\b', "Organismo público"),
    (r'\bENTIDAD\s+(?:P[UÚ]BLICA|FEDERATIVA)\b', "Entidad pública"),
    (r'\bDEPENDENCIA\b', "Dependencia"),
    (r'\bPATRONATO\b', "Patronato"),
    (r'\bFUNDACI[OÓ]N\b', "Fundación"),
    (r'\bASAMBLEA\b', "Asamblea"),
    (r'\bCONSEJO\b', "Consejo"),
    (r'\bCOMISI[OÓ]N\b', "Comisión"),
]


@dataclass
class ResultadoClasificacion:
    """
    Resultado de la clasificación del documento.
    
    Atributos:
    ==========
    - tipo_titular: "empresa" o "persona"
    - nombre_titular: Nombre identificado del titular
    - nombre_representante: Nombre del representante (o None)
    - confianza: "alta", "media", o "baja"
    - razon: Explicación de por qué se clasificó así
    - patrones_encontrados: Lista de patrones que se detectaron
    - metodo: "llm", "regex", o "hibrido"
    """
    tipo_titular: str
    nombre_titular: Optional[str]
    nombre_representante: Optional[str]
    confianza: str
    razon: str
    patrones_encontrados: List[str]
    metodo: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            "tipo_titular": self.tipo_titular,
            "nombre_titular": self.nombre_titular,
            "nombre_representante": self.nombre_representante,
            "confianza": self.confianza,
            "razon": self.razon,
            "patrones_encontrados": self.patrones_encontrados,
            "metodo": self.metodo
        }


# =============================================================================
# PROMPT DE CLASIFICACIÓN (LIGERO)
# =============================================================================

SYSTEM_PROMPT_CLASIFICACION = """Eres un clasificador de documentos notariales mexicanos.

Tu ÚNICA tarea es identificar 3 cosas:
1. Si el TITULAR (quien vende/transmite) es EMPRESA/INSTITUCIÓN o PERSONA FÍSICA
2. El nombre exacto del TITULAR
3. El nombre del REPRESENTANTE (si existe)

REGLAS IMPORTANTES:
- "empresa" incluye: sociedades (S.A., S.A. de C.V., S. de R.L.), instituciones gubernamentales 
  (Instituto, Secretaría, Gobierno), organismos públicos (INFONAVIT, FOVISSSTE, INSS), 
  fideicomisos, fondos, asociaciones civiles (A.C.)
- "persona" es SOLO para personas físicas que actúan por sí mismas
- El REPRESENTANTE siempre es una PERSONA FÍSICA que firma en nombre del titular
- Una institución NUNCA puede ser representante

Responde SOLO con JSON, sin explicaciones adicionales."""


def _build_prompt_clasificacion(texto_documento: str) -> str:
    """
    Construye el prompt para clasificación.
    
    Args:
        texto_documento: Primeros ~3000 caracteres del documento
        
    Returns:
        Prompt formateado para enviar a DeepSeek
    """
    
    return f"""Analiza este fragmento de documento notarial:

<documento>
{texto_documento}
</documento>

Identifica y responde con este JSON exacto:

```json
{{
  "tipo_titular": "empresa o persona",
  "nombre_titular": "nombre completo del titular (empresa/institución o persona)",
  "nombre_representante": "nombre de quien firma por el titular, o null si no hay",
  "razon": "explica brevemente por qué clasificaste así"
}}
```

EJEMPLOS DE RESPUESTA:

Si dice "comparece JUAN PÉREZ LÓPEZ por su propio derecho":
```json
{{
  "tipo_titular": "persona",
  "nombre_titular": "Juan Pérez López",
  "nombre_representante": null,
  "razon": "Es una persona física actuando por sí misma"
}}
```

Si dice "comparece ERNESTO PADILLA en representación del INSTITUTO NACIONAL DEL SUELO":
```json
{{
  "tipo_titular": "empresa",
  "nombre_titular": "Instituto Nacional del Suelo Sustentable",
  "nombre_representante": "Ernesto Padilla",
  "razon": "INSS es una institución gubernamental, Ernesto es su representante"
}}
```

Si dice "INMOBILIARIA ABC S.A. DE C.V. representada por MARÍA GARCÍA":
```json
{{
  "tipo_titular": "empresa",
  "nombre_titular": "Inmobiliaria ABC S.A. de C.V.",
  "nombre_representante": "María García",
  "razon": "Es una sociedad mercantil (S.A. de C.V.)"
}}
```

Ahora analiza el documento y responde SOLO con el JSON:"""


# =============================================================================
# FUNCIONES DE DETECCIÓN POR REGEX (VALIDACIÓN)
# =============================================================================

def detectar_tipo_por_nombre(nombre: str) -> Tuple[str, List[str]]:
    """
    Detecta si un nombre corresponde a empresa/institución o persona física.
    
    Esta función usa PATRONES REGEX para validar/corregir la clasificación
    del LLM. Es la "segunda opinión" que asegura consistencia.
    
    Args:
        nombre: Nombre a analizar
        
    Returns:
        Tupla de (tipo_detectado, patrones_encontrados)
        - tipo_detectado: "empresa", "persona", o "ambiguo"
        - patrones_encontrados: Lista de patrones que coincidieron
        
    Ejemplo:
        >>> detectar_tipo_por_nombre("Instituto Nacional del Suelo Sustentable")
        ('empresa', ['Instituto'])
        
        >>> detectar_tipo_por_nombre("Juan Pérez López")
        ('persona', [])
    """
    
    if not nombre:
        return "ambiguo", ["Nombre vacío"]
    
    nombre_upper = nombre.upper()
    patrones_encontrados = []
    
    # Buscar patrones de empresa/institución
    for patron, descripcion in PATRONES_EMPRESA:
        if re.search(patron, nombre_upper, re.IGNORECASE):
            patrones_encontrados.append(descripcion)
    
    # Determinar tipo basado en patrones encontrados
    if patrones_encontrados:
        return "empresa", patrones_encontrados
    
    # Si no hay patrones de empresa, verificar si parece nombre de persona
    # Un nombre de persona típicamente tiene 2-4 palabras sin patrones especiales
    palabras = nombre.split()
    if 2 <= len(palabras) <= 5:
        # Verificar que no tenga palabras "raras" para un nombre de persona
        palabras_no_persona = [
            "DESARROLLO", "INMOBILIARIA", "CONSTRUCTORA", "SERVICIOS",
            "COMERCIAL", "INDUSTRIAL", "NACIONAL", "ESTATAL", "FEDERAL",
            "INSTITUTO", "SECRETARIA", "GOBIERNO", "FIDEICOMISO"
        ]
        tiene_palabra_rara = any(
            palabra.upper() in palabras_no_persona 
            for palabra in palabras
        )
        if not tiene_palabra_rara:
            return "persona", []
    
    return "ambiguo", ["No se pudo determinar con certeza"]


def validar_representante_no_es_institucion(nombre_representante: str) -> Tuple[bool, str]:
    """
    Valida que el representante sea una persona física, no una institución.
    
    REGLA: El representante siempre es quien FIRMA, una persona física.
    Una institución NO puede ser representante.
    
    Args:
        nombre_representante: Nombre del supuesto representante
        
    Returns:
        Tupla de (es_valido, mensaje_error)
        
    Ejemplo:
        >>> validar_representante_no_es_institucion("Juan Pérez")
        (True, "")
        
        >>> validar_representante_no_es_institucion("Instituto Nacional...")
        (False, "El representante parece ser una institución")
    """
    
    if not nombre_representante:
        return True, ""
    
    tipo, patrones = detectar_tipo_por_nombre(nombre_representante)
    
    if tipo == "empresa":
        return False, f"El representante '{nombre_representante}' parece ser una institución ({', '.join(patrones)}), no una persona física"
    
    return True, ""


# =============================================================================
# FUNCIÓN PRINCIPAL DE CLASIFICACIÓN
# =============================================================================

def clasificar_documento(
    texto_documento: str,
    ollama_service=None
) -> ResultadoClasificacion:
    """
    FUNCIÓN PRINCIPAL - Clasifica el documento en FASE 1.
    
    Esta función:
    1. Envía el documento a DeepSeek para clasificación inicial
    2. Valida la respuesta con patrones regex
    3. Corrige si hay inconsistencias
    4. Devuelve clasificación confirmada
    
    Args:
        texto_documento: Texto completo del documento (se truncará)
        ollama_service: Servicio de Ollama (opcional, si no se pasa se obtiene)
        
    Returns:
        ResultadoClasificacion con toda la información
        
    Ejemplo:
        >>> resultado = clasificar_documento(texto)
        >>> print(resultado.tipo_titular)
        'empresa'
        >>> print(resultado.nombre_titular)
        'Instituto Nacional del Suelo Sustentable'
    """
    
    # Truncar texto a los primeros 3000 caracteres
    # (la información del titular usualmente está al inicio)
    texto_truncado = texto_documento[:3000]
    
    print("\n🔍 FASE 1: Clasificando documento...")
    
    # =========================================================================
    # PASO 1: Detección previa por REGEX
    # =========================================================================
    # Antes de llamar al LLM, hacemos una detección rápida por patrones
    # Esto nos ayuda a validar después
    
    tipo_regex, patrones_regex = _detectar_tipo_en_texto(texto_truncado)
    print(f"   📋 Detección regex previa: {tipo_regex}")
    if patrones_regex:
        print(f"      Patrones encontrados: {', '.join(patrones_regex[:3])}")
    
    # =========================================================================
    # PASO 2: Clasificación con LLM
    # =========================================================================
    
    clasificacion_llm = None
    
    if ollama_service is not None:
        try:
            prompt = _build_prompt_clasificacion(texto_truncado)
            
            # Llamada ligera a DeepSeek (max 500 tokens, determinístico)
            response = ollama_service.generate(
                prompt=prompt,
                system=SYSTEM_PROMPT_CLASIFICACION,
                temperature=0.0,  # Determinístico
                max_tokens=500    # Respuesta corta
            )
            
            response_text = response.get('response', '')
            clasificacion_llm = _parsear_respuesta_clasificacion(response_text)
            
            if clasificacion_llm:
                print(f"   🤖 Clasificación LLM: {clasificacion_llm.get('tipo_titular')}")
                print(f"      Titular: {clasificacion_llm.get('nombre_titular', 'N/A')[:50]}...")
                
        except Exception as e:
            print(f"   ⚠️ Error en clasificación LLM: {e}")
            clasificacion_llm = None
    
    # =========================================================================
    # PASO 3: Validar y combinar resultados
    # =========================================================================
    
    return _combinar_clasificaciones(
        clasificacion_llm=clasificacion_llm,
        tipo_regex=tipo_regex,
        patrones_regex=patrones_regex,
        texto_documento=texto_truncado
    )


def _detectar_tipo_en_texto(texto: str) -> Tuple[str, List[str]]:
    """
    Detecta patrones de empresa/institución en el texto completo.
    
    Busca patrones en TODO el texto, no solo en un nombre específico.
    """
    
    texto_upper = texto.upper()
    patrones_encontrados = []
    
    for patron, descripcion in PATRONES_EMPRESA:
        if re.search(patron, texto_upper, re.IGNORECASE):
            if descripcion not in patrones_encontrados:
                patrones_encontrados.append(descripcion)
    
    if patrones_encontrados:
        return "empresa", patrones_encontrados
    
    return "persona", []


def _parsear_respuesta_clasificacion(response_text: str) -> Optional[Dict[str, Any]]:
    """
    Parsea la respuesta JSON del LLM.
    
    Args:
        response_text: Texto de respuesta de DeepSeek
        
    Returns:
        Dict con la clasificación o None si no se pudo parsear
    """
    
    try:
        # Buscar JSON en la respuesta
        # Puede estar en bloque ```json ``` o directo
        
        # Primero intentar con bloque de código
        json_match = re.search(r'```(?:json)?\s*(\{[^`]+\})\s*```', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        
        # Si no, buscar JSON directo
        json_match = re.search(r'\{[^{}]*"tipo_titular"[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        
        # Intentar parsear todo como JSON
        return json.loads(response_text.strip())
        
    except (json.JSONDecodeError, AttributeError):
        return None


def _combinar_clasificaciones(
    clasificacion_llm: Optional[Dict[str, Any]],
    tipo_regex: str,
    patrones_regex: List[str],
    texto_documento: str
) -> ResultadoClasificacion:
    """
    Combina la clasificación del LLM con la validación por regex.
    
    LÓGICA:
    - Si LLM y regex coinciden → Alta confianza
    - Si LLM dice "persona" pero regex detecta patrones de empresa → Corregir a empresa
    - Si LLM no responde → Usar regex
    """
    
    # Caso 1: No tenemos respuesta del LLM
    if clasificacion_llm is None:
        print("   ⚠️ Sin respuesta LLM, usando solo regex")
        return ResultadoClasificacion(
            tipo_titular=tipo_regex,
            nombre_titular=None,
            nombre_representante=None,
            confianza="baja",
            razon="Clasificación solo por patrones regex (LLM no disponible)",
            patrones_encontrados=patrones_regex,
            metodo="regex"
        )
    
    tipo_llm = clasificacion_llm.get('tipo_titular', '').lower()
    nombre_titular_llm = clasificacion_llm.get('nombre_titular')
    nombre_rep_llm = clasificacion_llm.get('nombre_representante')
    razon_llm = clasificacion_llm.get('razon', '')
    
    # Caso 2: LLM y regex coinciden
    if tipo_llm == tipo_regex:
        print(f"   ✅ LLM y regex coinciden: {tipo_llm}")
        return ResultadoClasificacion(
            tipo_titular=tipo_llm,
            nombre_titular=nombre_titular_llm,
            nombre_representante=nombre_rep_llm,
            confianza="alta",
            razon=razon_llm,
            patrones_encontrados=patrones_regex,
            metodo="hibrido"
        )
    
    # Caso 3: LLM dice "persona" pero regex detecta empresa
    if tipo_llm == "persona" and tipo_regex == "empresa":
        print(f"   ⚠️ CORRECCIÓN: LLM dijo 'persona' pero regex detectó empresa")
        print(f"      Patrones encontrados: {', '.join(patrones_regex[:3])}")
        
        # Verificar si el nombre del titular tiene patrones de empresa
        if nombre_titular_llm:
            tipo_nombre, patrones_nombre = detectar_tipo_por_nombre(nombre_titular_llm)
            if tipo_nombre == "empresa":
                # El nombre del titular SÍ es empresa, el LLM se equivocó en el tipo
                return ResultadoClasificacion(
                    tipo_titular="empresa",
                    nombre_titular=nombre_titular_llm,
                    nombre_representante=nombre_rep_llm,
                    confianza="media",
                    razon=f"Corregido: El titular '{nombre_titular_llm[:30]}...' es empresa ({', '.join(patrones_nombre)})",
                    patrones_encontrados=patrones_regex,
                    metodo="hibrido_corregido"
                )
        
        # El LLM puso los nombres al revés (titular↔representante)
        # Verificar si el "representante" es realmente la empresa
        if nombre_rep_llm:
            tipo_rep, patrones_rep = detectar_tipo_por_nombre(nombre_rep_llm)
            if tipo_rep == "empresa":
                print(f"   🔄 Intercambiando: El representante era en realidad el titular")
                return ResultadoClasificacion(
                    tipo_titular="empresa",
                    nombre_titular=nombre_rep_llm,  # El "representante" es el titular real
                    nombre_representante=nombre_titular_llm,  # El "titular" es el representante real
                    confianza="media",
                    razon=f"Corregido e intercambiado: '{nombre_rep_llm[:30]}...' es el titular (empresa), '{nombre_titular_llm[:30]}...' es el representante",
                    patrones_encontrados=patrones_rep,
                    metodo="hibrido_corregido"
                )
        
        # Usar tipo regex pero mantener nombres del LLM
        return ResultadoClasificacion(
            tipo_titular="empresa",
            nombre_titular=nombre_titular_llm,
            nombre_representante=nombre_rep_llm,
            confianza="media",
            razon=f"Corregido por regex: Se detectaron patrones de empresa ({', '.join(patrones_regex[:2])})",
            patrones_encontrados=patrones_regex,
            metodo="hibrido_corregido"
        )
    
    # Caso 4: LLM dice "empresa" pero regex dice "persona"
    # Confiar más en LLM en este caso (puede haber empresa sin patrones obvios)
    if tipo_llm == "empresa" and tipo_regex == "persona":
        print(f"   📝 LLM dice empresa, regex no detectó patrones")
        return ResultadoClasificacion(
            tipo_titular="empresa",
            nombre_titular=nombre_titular_llm,
            nombre_representante=nombre_rep_llm,
            confianza="media",
            razon=razon_llm,
            patrones_encontrados=[],
            metodo="llm"
        )
    
    # Caso default
    return ResultadoClasificacion(
        tipo_titular=tipo_llm or tipo_regex,
        nombre_titular=nombre_titular_llm,
        nombre_representante=nombre_rep_llm,
        confianza="baja",
        razon="Clasificación con baja confianza",
        patrones_encontrados=patrones_regex,
        metodo="hibrido"
    )


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DEL CLASIFICADOR DE DOCUMENTOS")
    print("=" * 60)
    
    # Prueba 1: Detección por nombre
    print("\n📋 Prueba 1: Detección de tipo por nombre")
    print("-" * 40)
    
    nombres_prueba = [
        "Instituto Nacional del Suelo Sustentable",
        "Juan Pérez López",
        "Inmobiliaria del Norte S.A. de C.V.",
        "María García Hernández",
        "INFONAVIT",
        "Fideicomiso de Vivienda",
        "Secretaría de Desarrollo Agrario",
        "Ernesto Padilla Aceves",
        "Desarrollos Turísticos del Pacífico",
        "Ana López",
    ]
    
    for nombre in nombres_prueba:
        tipo, patrones = detectar_tipo_por_nombre(nombre)
        patrones_str = f" ({', '.join(patrones)})" if patrones else ""
        print(f"   {nombre[:40]:40} → {tipo}{patrones_str}")
    
    # Prueba 2: Validación de representante
    print("\n📋 Prueba 2: Validación de representante")
    print("-" * 40)
    
    representantes_prueba = [
        "Juan Pérez López",
        "Instituto Nacional del Suelo Sustentable",
        "María García",
        "INFONAVIT",
    ]
    
    for rep in representantes_prueba:
        es_valido, error = validar_representante_no_es_institucion(rep)
        status = "✅" if es_valido else "❌"
        print(f"   {status} {rep[:40]:40} → {'Válido' if es_valido else error[:30]}")
    
    # Prueba 3: Detección en texto
    print("\n📋 Prueba 3: Detección en texto completo")
    print("-" * 40)
    
    texto_prueba = """
    ESCRITURA NÚMERO 2397
    Comparece el señor ERNESTO PADILLA ACEVES en su carácter de 
    REPRESENTANTE REGIONAL del INSTITUTO NACIONAL DEL SUELO SUSTENTABLE (INSS),
    organismo público descentralizado...
    """
    
    tipo, patrones = _detectar_tipo_en_texto(texto_prueba)
    print(f"   Tipo detectado: {tipo}")
    print(f"   Patrones: {', '.join(patrones)}")
    
    print("\n" + "=" * 60)
    print("✅ PRUEBAS COMPLETADAS")
    print("=" * 60)
