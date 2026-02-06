"""
models/seccion_mapping.py - Mapa de campos a secciones del documento

Este módulo define qué campos se extraen de qué secciones del documento.
Basado en la estructura estándar de escrituras públicas mexicanas.

SECCIONES DEL DOCUMENTO:
========================
1. Introducción (Encabezado)
2. Cláusula Primera (Comparecencia)
3. Cláusula Segunda (Operación)
4. Personalidad (Poderes)
5. Generales (Identificación)

VENTAJAS DE ESTE ENFOQUE:
=========================
- Mayor precisión al buscar en secciones específicas
- Menor ambigüedad (número de escritura del PODER vs del DOCUMENTO)
- Validación: rechazar campos extraídos de secciones incorrectas
- Reducción de tokens enviados a LLMs (solo texto relevante)
"""

from typing import Dict, List, Set
from enum import Enum


class SeccionDocumento(str, Enum):
    """Secciones estándar de una escritura pública."""
    INTRODUCCION = "introduccion"
    CLAUSULA_PRIMERA = "clausula_primera"
    CLAUSULA_SEGUNDA = "clausula_segunda"
    PERSONALIDAD = "personalidad"
    GENERALES = "generales"


# =============================================================================
# MAPA DE CAMPOS → SECCIONES
# =============================================================================

CAMPOS_POR_SECCION: Dict[SeccionDocumento, List[str]] = {
    # INTRODUCCIÓN: Datos del encabezado
    SeccionDocumento.INTRODUCCION: [
        "numero_escritura",
        "fecha_documento",
        "numero_notaria",
        "municipio",
        "nombre_notario",
    ],

    # CLÁUSULA PRIMERA: Comparecencia (quién vende, quién compra)
    SeccionDocumento.CLAUSULA_PRIMERA: [
        "titulares",              # Vendedores
        "adquirientes",           # Compradores
        "titular.nombre",
        "titular.actua_por",
        "titular.representante.nombre",
        "titular.representante.en_calidad",
        "adquiriente.nombre",
        "adquiriente.actua_por",
        "adquiriente.representante.nombre",
        "adquiriente.representante.en_calidad",
    ],

    # CLÁUSULA SEGUNDA: Datos de la operación
    SeccionDocumento.CLAUSULA_SEGUNDA: [
        "monto_operacion",
        "valor_catastral",
    ],

    # PERSONALIDAD: Datos de poderes notariales
    SeccionDocumento.PERSONALIDAD: [
        "representante.escritura",      # Número de escritura del PODER
        "representante.fecha_poder",    # Fecha del poder
    ],

    # GENERALES: Identificación de las personas (al final del documento)
    SeccionDocumento.GENERALES: [
        "estado_civil",
        "tipo_sociedad",
        "edad",
        "rfc",
        "curp",
    ],
}


# =============================================================================
# MAPA INVERSO: CAMPO → SECCIÓN
# =============================================================================

SECCION_POR_CAMPO: Dict[str, SeccionDocumento] = {}
for seccion, campos in CAMPOS_POR_SECCION.items():
    for campo in campos:
        SECCION_POR_CAMPO[campo] = seccion


# =============================================================================
# PATRONES DE TÍTULOS DE SECCIÓN
# =============================================================================

PATRONES_TITULOS_SECCION: Dict[SeccionDocumento, List[str]] = {
    SeccionDocumento.INTRODUCCION: [
        r"ESCRITURA\s+NÚMERO",
        r"ESCRITURA\s+PÚBLICA\s+NÚMERO",
        r"INSTRUMENTO\s+NÚMERO",
        r"^NÚMERO\s+\d+",
        # No tiene título explícito, es el inicio del documento
    ],

    SeccionDocumento.CLAUSULA_PRIMERA: [
        r"CLÁUSULA\s+PRIMERA",
        r"CLAUSULA\s+PRIMERA",
        r"PRIMERA\.",
        r"I\.",
        r"COMPARECENCIA",
        r"ANTECEDENTES",
    ],

    SeccionDocumento.CLAUSULA_SEGUNDA: [
        r"CLÁUSULA\s+SEGUNDA",
        r"CLAUSULA\s+SEGUNDA",
        r"SEGUNDA\.",
        r"II\.",
        r"DECLARACIONES",
    ],

    SeccionDocumento.PERSONALIDAD: [
        r"PERSONALIDAD",
        r"ACREDITACIÓN\s+DE\s+PERSONALIDAD",
        r"REPRESENTACIÓN",
        r"PODERES",
    ],

    SeccionDocumento.GENERALES: [
        r"GENERALES",
        r"IDENTIFICACIÓN",
        r"DOY\s+FE",
        r"FE\s+NOTARIAL",
        r"COMPARECIENTES",
        r"CERTIFICACIONES",
    ],
}


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def obtener_seccion_de_campo(campo: str) -> SeccionDocumento:
    """
    Obtiene la sección donde debe buscarse un campo.

    Args:
        campo: Nombre del campo (ej: "rfc", "numero_escritura")

    Returns:
        SeccionDocumento donde se encuentra el campo

    Raises:
        KeyError: Si el campo no está mapeado
    """
    return SECCION_POR_CAMPO[campo]


def obtener_campos_de_seccion(seccion: SeccionDocumento) -> List[str]:
    """
    Obtiene todos los campos que se extraen de una sección.

    Args:
        seccion: Sección del documento

    Returns:
        Lista de nombres de campos
    """
    return CAMPOS_POR_SECCION[seccion]


def validar_campo_en_seccion(campo: str, seccion: SeccionDocumento) -> bool:
    """
    Valida si un campo debe extraerse de una sección específica.

    Args:
        campo: Nombre del campo
        seccion: Sección del documento

    Returns:
        True si el campo pertenece a esa sección, False en caso contrario
    """
    try:
        seccion_esperada = obtener_seccion_de_campo(campo)
        return seccion_esperada == seccion
    except KeyError:
        # Campo no mapeado, aceptar por defecto
        return True


# =============================================================================
# CONFIGURACIÓN DE EXTRACCIÓN POR SECCIÓN
# =============================================================================

class ConfiguracionSeccion:
    """Configuración de cómo extraer datos de cada sección."""

    # Secciones que se envían completas al LLM (son cortas)
    SECCIONES_COMPLETAS: Set[SeccionDocumento] = {
        SeccionDocumento.INTRODUCCION,
        SeccionDocumento.PERSONALIDAD,
    }

    # Secciones que se truncan (son muy largas)
    SECCIONES_TRUNCADAS: Set[SeccionDocumento] = {
        SeccionDocumento.CLAUSULA_PRIMERA,
        SeccionDocumento.CLAUSULA_SEGUNDA,
    }

    # Límites de caracteres por sección
    LIMITES_CARACTERES: Dict[SeccionDocumento, int] = {
        SeccionDocumento.INTRODUCCION: 2000,
        SeccionDocumento.CLAUSULA_PRIMERA: 5000,
        SeccionDocumento.CLAUSULA_SEGUNDA: 3000,
        SeccionDocumento.PERSONALIDAD: 2000,
        SeccionDocumento.GENERALES: 8000,  # La más larga, contiene todas las identificaciones
    }


# =============================================================================
# EXPORTAR TODO
# =============================================================================

__all__ = [
    "SeccionDocumento",
    "CAMPOS_POR_SECCION",
    "SECCION_POR_CAMPO",
    "PATRONES_TITULOS_SECCION",
    "obtener_seccion_de_campo",
    "obtener_campos_de_seccion",
    "validar_campo_en_seccion",
    "ConfiguracionSeccion",
]
