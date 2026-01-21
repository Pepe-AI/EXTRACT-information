"""
models/confianza.py - Modelos para el sistema de confianza (Plan F)

VERSIÓN: 2.0 - Con FIX #3 para activación de Plan E

FIX #3 APLICADO:
================
La función identificar_campos_para_plan_e() ahora:
1. Activa Plan E para confianza BAJA o MEDIA (no solo BAJA)
2. Activa Plan E si el campo NO fue extraído o fue CORREGIDO
3. Maneja correctamente tipos string y enum
4. Considera campos que fallaron validación cruzada (Plan B)

PROPÓSITO:
==========
Define las estructuras de datos para manejar niveles de confianza
y evaluar la calidad de la extracción.

NIVELES DE CONFIANZA:
=====================
- ALTA: Dato extraído por regex O validado contra texto original
- MEDIA: Dato extraído por LLM pero no validado completamente
- BAJA: Dato dudoso, posible alucinación, requiere revisión
- NO_ENCONTRADO: No se pudo extraer el dato

ORIGEN DEL DATO:
================
- REGEX: Extraído directamente por expresión regular
- LLM_VALIDADO: Extraído por LLM y confirmado en texto
- LLM_NO_VALIDADO: Extraído por LLM sin confirmación
- PLAN_E: Extraído por el Plan E (extracción individual)
- CORREGIDO: Se detectó error y se corrigió automáticamente
"""

from enum import Enum
from typing import Optional, List, Dict, Any, Set
from pydantic import BaseModel, Field


# =============================================================================
# ENUMERACIONES
# =============================================================================

class NivelConfianza(str, Enum):
    """
    Niveles de confianza para campos extraídos.
    
    Uso:
        confianza = NivelConfianza.ALTA
        if confianza == NivelConfianza.BAJA:
            print("Revisar este campo")
    
    NOTA: Hereda de str para permitir comparación directa con strings.
    Esto significa que NivelConfianza.BAJA == "baja" es True.
    """
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    NO_ENCONTRADO = "no_encontrado"


class OrigenDato(str, Enum):
    """
    Indica cómo se obtuvo cada dato.
    
    Esto permite saber si un dato vino de regex (más confiable)
    o del LLM (puede tener errores).
    """
    REGEX = "regex"
    LLM_VALIDADO = "llm_validado"
    LLM_NO_VALIDADO = "llm_no_validado"
    PLAN_E = "plan_e"
    CORREGIDO = "corregido"
    NO_EXTRAIDO = "no_extraido"


class NivelResultado(str, Enum):
    """
    Nivel de éxito de la extracción completa.
    """
    CRITICO = "critico"           # 0-1 campos: Fallo total
    INSUFICIENTE = "insuficiente" # 2-3 campos: Fallo parcial
    PARCIAL = "parcial"           # 4-5 campos: Éxito con advertencia
    COMPLETO = "completo"         # 6-8 campos: Éxito total


# =============================================================================
# CONSTANTES PARA EVALUACIÓN
# =============================================================================

# Campos críticos: debe encontrar al menos 2 de 4
CAMPOS_CRITICOS = [
    "numero_escritura",
    "numero_notaria",
    "nombre_notario",
    "monto_operacion"
]

# Campos totales: debe encontrar al menos 4 de 8
CAMPOS_TOTALES = [
    "numero_escritura",
    "numero_notaria",
    "nombre_notario",
    "fecha_documento",
    "titulares",
    "adquirientes",
    "monto_operacion"
]

# Campos que pueden usar Plan E (solo campos simples)
CAMPOS_PLAN_E_PERMITIDOS = [
    "numero_escritura",
    "numero_notaria",
    "nombre_notario",
    "monto_operacion",
    "fecha_documento",
]

# Valores que se consideran "no encontrado"
VALORES_INVALIDOS = [
    None,
    "",
    "NO SE ENCONTRÓ DATO",
    "...",
    "N/A",
    "null",
    "$X,XXX.XX",
    "$...",
    0,
    0.0,
    "0",
    "0.0",
    False
]


# =============================================================================
# MODELOS PYDANTIC
# =============================================================================

class CampoConfianza(BaseModel):
    """
    Información de confianza para un campo individual.
    """
    nombre: str
    valor: Any = None
    confianza: NivelConfianza = NivelConfianza.NO_ENCONTRADO
    origen: OrigenDato = OrigenDato.NO_EXTRAIDO
    valor_original_llm: Optional[Any] = None
    requiere_revision: bool = False
    intentos_plan_e: int = 0
    fue_corregido: bool = False  # ⭐ NUEVO: Si fue corregido por validación


class EvaluacionCalidad(BaseModel):
    """
    Resultado de evaluar la calidad de una extracción.
    """
    nivel: NivelResultado
    success: bool
    mensaje: str
    error_code: Optional[str] = None
    
    campos_encontrados: int = 0
    campos_totales: int = 8
    campos_criticos_encontrados: int = 0
    campos_criticos_requeridos: int = 2
    
    campos_faltantes: List[str] = Field(default_factory=list)
    posibles_causas: List[str] = Field(default_factory=list)
    sugerencias: List[str] = Field(default_factory=list)
    
    calidad_porcentaje: float = 0.0
    campos_mejorados_plan_e: List[str] = Field(default_factory=list)


class ResultadoConfianza(BaseModel):
    """
    Resultado final con datos y metadatos de confianza.
    """
    # Estado general
    success: bool = False
    error: Optional[str] = None
    error_code: Optional[str] = None
    advertencia: Optional[str] = None
    
    # Datos extraídos
    datos: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata de confianza
    confianza: Dict[str, str] = Field(default_factory=dict)
    origen: Dict[str, str] = Field(default_factory=dict)
    
    # Campos que requieren revisión humana
    requiere_revision: List[str] = Field(default_factory=list)
    
    # Estadísticas
    calidad_general: float = 0.0
    campos_encontrados: int = 0
    campos_totales: int = 8
    campos_faltantes: List[str] = Field(default_factory=list)
    
    # Info del Plan E
    plan_e_activado: bool = False
    campos_mejorados_plan_e: List[str] = Field(default_factory=list)
    
    # Metadata del proceso
    tiempo_procesamiento: float = 0.0
    metodo_clasificacion: Optional[str] = None
    tipo_detectado: Optional[str] = None
    secciones_detectadas: List[str] = Field(default_factory=list)
    
    # Para casos de fallo
    detalles_fallo: Optional[Dict[str, Any]] = None


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def campo_tiene_valor(datos: Dict[str, Any], campo: str) -> bool:
    """
    Verifica si un campo tiene un valor válido (no vacío/nulo).
    
    Args:
        datos: Diccionario con los datos extraídos
        campo: Nombre del campo a verificar
        
    Returns:
        True si el campo tiene un valor válido
    """
    valor = datos.get(campo)
    
    if valor in VALORES_INVALIDOS:
        return False
    
    if isinstance(valor, list):
        return len(valor) > 0
    
    if isinstance(valor, str):
        valor_limpio = valor.strip()
        if not valor_limpio or valor_limpio in VALORES_INVALIDOS:
            return False
    
    return True


def evaluar_calidad_extraccion(datos: Dict[str, Any]) -> EvaluacionCalidad:
    """
    Evalúa si la extracción fue exitosa o debe marcarse como fallo.
    
    REGLAS:
    - CRÍTICO: ≤1 campo total → "No se pudo detectar datos"
    - INSUFICIENTE: 2-3 campos O <2 críticos → "Datos insuficientes"
    - PARCIAL: 4-5 campos, ≥2 críticos → Éxito con advertencia
    - COMPLETO: 6-8 campos → Éxito total
    """
    
    criticos_encontrados = sum(
        1 for campo in CAMPOS_CRITICOS
        if campo_tiene_valor(datos, campo)
    )
    
    totales_encontrados = sum(
        1 for campo in CAMPOS_TOTALES
        if campo_tiene_valor(datos, campo)
    )
    
    campos_faltantes = [
        campo for campo in CAMPOS_TOTALES
        if not campo_tiene_valor(datos, campo)
    ]
    
    calidad = round((totales_encontrados / 8) * 100, 1)
    
    if totales_encontrados <= 1:
        return EvaluacionCalidad(
            nivel=NivelResultado.CRITICO,
            success=False,
            mensaje="No se pudo detectar datos en el archivo",
            error_code="EXTRACTION_FAILED",
            campos_encontrados=totales_encontrados,
            campos_criticos_encontrados=criticos_encontrados,
            campos_faltantes=campos_faltantes,
            calidad_porcentaje=calidad,
            posibles_causas=[
                "El documento no es una escritura pública",
                "El documento está muy dañado o ilegible",
                "El OCR no pudo procesar correctamente el archivo",
                "El formato del documento no es reconocido"
            ],
            sugerencias=[
                "Verifique que el archivo sea una escritura pública notarial",
                "Asegúrese de que el PDF sea legible y no esté protegido",
                "Intente con un escaneo de mejor calidad"
            ]
        )
    
    elif totales_encontrados <= 3 or criticos_encontrados < 2:
        return EvaluacionCalidad(
            nivel=NivelResultado.INSUFICIENTE,
            success=False,
            mensaje="Datos insuficientes. Verifique que sea una escritura pública",
            error_code="INSUFFICIENT_DATA",
            campos_encontrados=totales_encontrados,
            campos_criticos_encontrados=criticos_encontrados,
            campos_faltantes=campos_faltantes,
            calidad_porcentaje=calidad,
            posibles_causas=[
                "El documento puede no ser una escritura pública completa",
                "Algunas páginas pueden estar faltando o dañadas",
                "El formato del documento es inusual"
            ],
            sugerencias=[
                "Verifique que el documento esté completo",
                "Revise que todas las páginas sean legibles"
            ]
        )
    
    elif totales_encontrados <= 5:
        return EvaluacionCalidad(
            nivel=NivelResultado.PARCIAL,
            success=True,
            mensaje="Extracción parcial. Algunos campos no fueron detectados",
            campos_encontrados=totales_encontrados,
            campos_criticos_encontrados=criticos_encontrados,
            campos_faltantes=campos_faltantes,
            calidad_porcentaje=calidad
        )
    
    else:
        return EvaluacionCalidad(
            nivel=NivelResultado.COMPLETO,
            success=True,
            mensaje="Extracción exitosa",
            campos_encontrados=totales_encontrados,
            campos_criticos_encontrados=criticos_encontrados,
            campos_faltantes=campos_faltantes,
            calidad_porcentaje=calidad
        )


def determinar_confianza_campo(
    valor_regex: Any,
    valor_llm: Any,
    valor_plan_e: Any,
    validado_en_texto: bool
) -> tuple[Any, NivelConfianza, OrigenDato]:
    """
    Determina el valor final, confianza y origen para un campo.
    
    PRIORIDAD:
    1. Si regex encontró valor → usar regex (ALTA, REGEX)
    2. Si Plan E encontró valor validado → usar Plan E (ALTA, PLAN_E)
    3. Si LLM encontró y está validado → usar LLM (ALTA, LLM_VALIDADO)
    4. Si LLM encontró sin validar → usar LLM (MEDIA, LLM_NO_VALIDADO)
    5. Si nada encontró → (None, NO_ENCONTRADO, NO_EXTRAIDO)
    """
    
    regex_valido = valor_regex not in VALORES_INVALIDOS
    llm_valido = valor_llm not in VALORES_INVALIDOS
    plan_e_valido = valor_plan_e not in VALORES_INVALIDOS
    
    if regex_valido:
        return (valor_regex, NivelConfianza.ALTA, OrigenDato.REGEX)
    
    if plan_e_valido:
        return (valor_plan_e, NivelConfianza.ALTA, OrigenDato.PLAN_E)
    
    if llm_valido and validado_en_texto:
        return (valor_llm, NivelConfianza.ALTA, OrigenDato.LLM_VALIDADO)
    
    if llm_valido:
        return (valor_llm, NivelConfianza.MEDIA, OrigenDato.LLM_NO_VALIDADO)
    
    return (None, NivelConfianza.NO_ENCONTRADO, OrigenDato.NO_EXTRAIDO)


# =============================================================================
# FIX #3: identificar_campos_para_plan_e CORREGIDO
# =============================================================================

def _normalizar_nivel_confianza(valor: Any) -> str:
    """
    Normaliza un nivel de confianza a string para comparación segura.
    
    FIX #3: Esta función resuelve el problema de incompatibilidad de tipos
    entre NivelConfianza (enum) y strings.
    
    Args:
        valor: Puede ser NivelConfianza, string, o None
        
    Returns:
        String normalizado: "alta", "media", "baja", o "no_encontrado"
        
    Ejemplo:
        >>> _normalizar_nivel_confianza(NivelConfianza.BAJA)
        "baja"
        >>> _normalizar_nivel_confianza("BAJA")
        "baja"
        >>> _normalizar_nivel_confianza("baja")
        "baja"
    """
    if valor is None:
        return "no_encontrado"
    
    # Si es un enum, obtener su valor
    if isinstance(valor, NivelConfianza):
        return valor.value
    
    # Si es string, normalizar a minúsculas
    if isinstance(valor, str):
        return valor.lower().strip()
    
    return "no_encontrado"


def identificar_campos_para_plan_e(
    datos_regex: Dict[str, Any],
    datos_llm: Dict[str, Any],
    confianza: Dict[str, Any],  # Puede ser Dict[str, NivelConfianza] o Dict[str, str]
    campos_corregidos: Set[str] = None,  # ⭐ NUEVO: Campos corregidos por Plan B
    campos_no_validados: Set[str] = None  # ⭐ NUEVO: Campos no validados en texto
) -> List[str]:
    """
    Identifica qué campos deben procesarse con Plan E.
    
    FIX #3 APLICADO:
    ================
    Esta función fue corregida para:
    1. Activar Plan E para confianza BAJA O MEDIA (no solo BAJA)
    2. Activar Plan E si el campo fue CORREGIDO por validación cruzada
    3. Activar Plan E si el campo NO fue validado en el texto
    4. Manejar correctamente tipos string y enum (NivelConfianza)
    5. NO descartar campos solo porque regex extrajo algo
    
    PROBLEMA ORIGINAL:
    ==================
    La función original tenía esta lógica:
    
    ```python
    if confianza.get(campo) != NivelConfianza.BAJA:
        continue  # Solo considera BAJA
    
    if valor_regex not in VALORES_INVALIDOS:
        continue  # Si regex tiene algo, lo descarta
    ```
    
    Esto causaba que:
    - Campos con confianza MEDIA nunca iban a Plan E
    - Campos con valores INCORRECTOS de regex nunca iban a Plan E
    - La comparación enum vs string fallaba silenciosamente
    
    NUEVA LÓGICA:
    =============
    Un campo va a Plan E si cumple CUALQUIERA de estas condiciones:
    1. Confianza es BAJA
    2. Confianza es MEDIA y NO hay valor de regex
    3. El campo fue CORREGIDO por validación cruzada (Plan B)
    4. El campo NO fue validado en el texto original
    5. El campo es NO_ENCONTRADO
    
    Args:
        datos_regex: Datos extraídos por regex
        datos_llm: Datos extraídos por LLM
        confianza: Niveles de confianza por campo (puede ser enum o string)
        campos_corregidos: Set de campos que fueron corregidos por Plan B
        campos_no_validados: Set de campos que no se validaron en el texto
        
    Returns:
        Lista de nombres de campos para Plan E (máximo 3)
        
    Ejemplo:
        >>> confianza = {"numero_escritura": "alta", "fecha_documento": "baja"}
        >>> campos_corregidos = {"fecha_documento"}
        >>> identificar_campos_para_plan_e(
        ...     datos_regex={}, 
        ...     datos_llm={},
        ...     confianza=confianza,
        ...     campos_corregidos=campos_corregidos
        ... )
        ["fecha_documento"]
    """
    
    # Inicializar sets vacíos si no se proporcionaron
    if campos_corregidos is None:
        campos_corregidos = set()
    if campos_no_validados is None:
        campos_no_validados = set()
    
    campos_plan_e = []
    
    print(f"\n   🔍 Evaluando campos para Plan E...")
    
    for campo in CAMPOS_PLAN_E_PERMITIDOS:
        # =====================================================================
        # PASO 1: Obtener nivel de confianza normalizado
        # =====================================================================
        nivel_raw = confianza.get(campo)
        nivel = _normalizar_nivel_confianza(nivel_raw)
        
        # =====================================================================
        # PASO 2: Obtener valores de regex y LLM
        # =====================================================================
        valor_regex = datos_regex.get(campo)
        valor_llm = datos_llm.get(campo)
        
        tiene_regex = valor_regex not in VALORES_INVALIDOS
        tiene_llm = valor_llm not in VALORES_INVALIDOS
        
        # =====================================================================
        # PASO 3: Evaluar si necesita Plan E
        # =====================================================================
        necesita_plan_e = False
        razon = ""
        
        # Criterio 1: Confianza BAJA → SIEMPRE va a Plan E
        if nivel == "baja":
            necesita_plan_e = True
            razon = "confianza BAJA"
        
        # Criterio 2: Confianza NO_ENCONTRADO → SIEMPRE va a Plan E
        elif nivel == "no_encontrado":
            necesita_plan_e = True
            razon = "no encontrado"
        
        # Criterio 3: Fue CORREGIDO por validación → va a Plan E
        elif campo in campos_corregidos:
            necesita_plan_e = True
            razon = "corregido por validación"
        
        # Criterio 4: NO fue validado en texto → va a Plan E
        elif campo in campos_no_validados:
            necesita_plan_e = True
            razon = "no validado en texto"
        
        # Criterio 5: Confianza MEDIA y NO tiene regex → va a Plan E
        elif nivel == "media" and not tiene_regex:
            necesita_plan_e = True
            razon = "confianza MEDIA sin respaldo regex"
        
        # =====================================================================
        # PASO 4: Agregar a la lista si necesita Plan E
        # =====================================================================
        if necesita_plan_e:
            campos_plan_e.append(campo)
            print(f"      ✓ {campo}: Necesita Plan E ({razon})")
        else:
            # Debug: mostrar por qué NO necesita Plan E
            if nivel == "alta":
                print(f"      ○ {campo}: OK (confianza ALTA)")
            elif nivel == "media" and tiene_regex:
                print(f"      ○ {campo}: OK (confianza MEDIA con respaldo regex)")
    
    # =========================================================================
    # PASO 5: Priorizar campos críticos si hay más de 3
    # =========================================================================
    if len(campos_plan_e) > 3:
        print(f"      ⚠️ Priorizando campos críticos ({len(campos_plan_e)} candidatos, máximo 3)")
        
        # Ordenar: primero los campos críticos, luego el resto
        def prioridad_campo(campo):
            if campo in CAMPOS_CRITICOS:
                return 0  # Mayor prioridad
            return 1  # Menor prioridad
        
        campos_plan_e.sort(key=prioridad_campo)
        campos_plan_e = campos_plan_e[:3]
        print(f"      📋 Seleccionados: {campos_plan_e}")
    
    return campos_plan_e


# =============================================================================
# FUNCIÓN AUXILIAR PARA EXTRAER CAMPOS CORREGIDOS
# =============================================================================

def extraer_campos_corregidos(validaciones: Dict[str, Any]) -> Set[str]:
    """
    Extrae los nombres de campos que fueron corregidos por validación cruzada.
    
    Esta función procesa el resultado del ValidadorCruzado (Plan B)
    para identificar campos que tuvieron errores y fueron corregidos.
    
    Args:
        validaciones: Diccionario de resultados de validación
                      {campo: ResultadoValidacion}
        
    Returns:
        Set de nombres de campos corregidos
        
    Ejemplo:
        >>> validaciones = {
        ...     "fecha_documento": ResultadoValidacion(fue_corregido=True, ...),
        ...     "numero_escritura": ResultadoValidacion(fue_corregido=False, ...)
        ... }
        >>> extraer_campos_corregidos(validaciones)
        {"fecha_documento"}
    """
    if not validaciones:
        return set()
    
    corregidos = set()
    
    for campo, resultado in validaciones.items():
        # El resultado puede ser un objeto o un dict
        if hasattr(resultado, 'fue_corregido'):
            if resultado.fue_corregido:
                corregidos.add(campo)
        elif isinstance(resultado, dict):
            if resultado.get('fue_corregido', False):
                corregidos.add(campo)
    
    return corregidos


def extraer_campos_no_validados(validaciones: Dict[str, Any]) -> Set[str]:
    """
    Extrae los nombres de campos que NO fueron encontrados en el texto.
    
    Args:
        validaciones: Diccionario de resultados de validación
        
    Returns:
        Set de nombres de campos no validados
    """
    if not validaciones:
        return set()
    
    no_validados = set()
    
    for campo, resultado in validaciones.items():
        if hasattr(resultado, 'encontrado_en_texto'):
            if not resultado.encontrado_en_texto and hasattr(resultado, 'valor_original') and resultado.valor_original:
                no_validados.add(campo)
        elif isinstance(resultado, dict):
            if not resultado.get('encontrado_en_texto', True) and resultado.get('valor_original'):
                no_validados.add(campo)
    
    return no_validados


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PRUEBA DE FIX #3: identificar_campos_para_plan_e")
    print("=" * 70)
    
    # Caso de prueba 1: Confianza como strings
    print("\n📄 CASO 1: Confianza como strings (el bug original)")
    print("-" * 70)
    
    confianza_str = {
        "numero_escritura": "alta",
        "fecha_documento": "baja",
        "numero_notaria": "media",
        "monto_operacion": "no_encontrado",
        "nombre_notario": "alta"
    }
    
    datos_regex = {
        "numero_escritura": 2397,  # Tiene valor pero incorrecto
        "fecha_documento": None,
        "numero_notaria": None,
        "monto_operacion": None,
        "nombre_notario": "RIGOBERTO OCHOA TORRES"
    }
    
    datos_llm = {
        "fecha_documento": "ocho de noviembre de mil novecientos setenta y cuatro"
    }
    
    campos_corregidos = {"fecha_documento"}  # Plan B detectó error
    
    resultado = identificar_campos_para_plan_e(
        datos_regex=datos_regex,
        datos_llm=datos_llm,
        confianza=confianza_str,
        campos_corregidos=campos_corregidos
    )
    
    print(f"\n   Resultado: {resultado}")
    print(f"   Esperado: ['fecha_documento', 'numero_notaria', 'monto_operacion']")
    esperado = {'fecha_documento', 'numero_notaria', 'monto_operacion'}
    obtenido = set(resultado)
    print(f"   {'✅ CORRECTO' if obtenido == esperado else '❌ INCORRECTO'}")
    
    # Caso de prueba 2: Confianza como enums
    print("\n📄 CASO 2: Confianza como enums (compatibilidad)")
    print("-" * 70)
    
    confianza_enum = {
        "numero_escritura": NivelConfianza.ALTA,
        "fecha_documento": NivelConfianza.BAJA,
        "numero_notaria": NivelConfianza.MEDIA,
    }
    
    resultado2 = identificar_campos_para_plan_e(
        datos_regex={},
        datos_llm={},
        confianza=confianza_enum
    )
    
    print(f"\n   Resultado: {resultado2}")
    # fecha_documento (BAJA) y numero_notaria (MEDIA sin regex) deben estar
    # Pero numero_notaria es crítico, así que tiene prioridad
    print(f"   Esperado: contiene 'numero_notaria' (crítico con confianza MEDIA)")
    tiene_notaria = 'numero_notaria' in resultado2
    print(f"   {'✅ CORRECTO' if tiene_notaria else '❌ INCORRECTO'}")
    
    # Caso de prueba 3: Todo OK (no debe activar Plan E)
    print("\n📄 CASO 3: Todos los campos OK (Plan E no debe activarse)")
    print("-" * 70)
    
    confianza_ok = {
        "numero_escritura": "alta",
        "fecha_documento": "alta",
        "numero_notaria": "alta",
        "monto_operacion": "alta",
        "nombre_notario": "alta"
    }
    
    resultado3 = identificar_campos_para_plan_e(
        datos_regex=datos_regex,
        datos_llm={},
        confianza=confianza_ok
    )
    
    print(f"\n   Resultado: {resultado3}")
    print(f"   Esperado: [] (lista vacía)")
    print(f"   {'✅ CORRECTO' if resultado3 == [] else '❌ INCORRECTO'}")
    
    print("\n" + "=" * 70)
    print("FIN DE PRUEBAS")
    print("=" * 70)
