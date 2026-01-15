"""
models/secciones.py - Modelos para secciones del documento (Plan D)

PROPÓSITO:
==========
Las escrituras públicas tienen una estructura típica que podemos aprovechar
para mejorar la extracción. Este módulo define las secciones y qué campos
esperamos encontrar en cada una.

SECCIONES TÍPICAS:
==================
1. ENCABEZADO: Número de escritura, notaría, notario, fecha, lugar
2. COMPARECIENTES: Quiénes participan (vendedor/comprador, representantes)
3. ANTECEDENTES: Historia del inmueble, escrituras anteriores
4. CLÁUSULAS: Términos de la operación (precio, condiciones)
5. CERTIFICACIONES: Firmas, sellos, fe del notario

ESTRATEGIA:
===========
- Si se detectan secciones → extraer de cada una por separado
- Si NO se detectan → usar texto completo (como funciona actualmente)

USO CON PLAN E:
===============
El Plan E usa las secciones para enviar solo el texto relevante
a cada prompt específico, mejorando precisión y reduciendo tokens.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from dataclasses import dataclass


# =============================================================================
# CONFIGURACIÓN DE SECCIONES
# =============================================================================

# Qué campos esperamos extraer de cada sección
CAMPOS_POR_SECCION: Dict[str, List[str]] = {
    "encabezado": [
        "numero_escritura",
        "numero_notaria",
        "nombre_notario",
        "fecha_documento",
        "municipio",
        "estado"
    ],
    "comparecientes": [
        "tipo_titular",
        "titulares",
        "adquirientes",
    ],
    "clausulas": [
        "monto_operacion",
        "tipo_moneda",
        "valor_catastral"
    ],
    "antecedentes": [
        "datos_inmueble",
        "escritura_antecedente"
    ],
    "certificaciones": []  # Normalmente no extraemos datos de aquí
}

# Patrones (anclas) que indican el inicio de cada sección
ANCLAS_SECCIONES: Dict[str, List[str]] = {
    "encabezado": [
        r"ESCRITURA\s+(?:P[UÚ]BLICA\s+)?N[UÚ]MERO",
        r"^En\s+(?:la\s+)?(?:ciudad|municipio)\s+de",
    ],
    "comparecientes": [
        r"COMPARECE[N]?",
        r"INTERVIENEN",
        r"ANTE\s+M[IÍ]\s+COMPARECE",
        r"COMO\s+(?:PARTE\s+)?(?:VENDEDOR|ENAJENANTE)",
        r"(?:PRIMERO|PRIMERA)[\.\-\:]?\s*[\-\.]?\s*Como",
    ],
    "antecedentes": [
        r"ANTECEDENTES?\s*(?:DE\s+(?:LA\s+)?PROPIEDAD)?",
        r"ANTECEDENTES?\s+REGISTRALES?",
        r"ANTECEDENTES?\s+DEL\s+INMUEBLE",
    ],
    "clausulas": [
        r"CL[AÁ]USULAS?",
        r"(?:PRIMERA|SEGUNDA|TERCERA)[\.\-\:]\s*[\-\.]",
        r"PRECIO[\.\-\:]",
        r"OBJETO\s+DEL\s+CONTRATO",
    ],
    "certificaciones": [
        r"CERTIFICACIONES?",
        r"DOY\s+FE",
        r"ANTE\s+M[IÍ]\s+(?:Y\s+)?PASO",
        r"LEA\s+QUE\s+FUE",
    ]
}

# ⭐ NUEVO: Mapeo de campo a sección para Plan E
SECCION_POR_CAMPO: Dict[str, str] = {
    "numero_escritura": "encabezado",
    "numero_notaria": "encabezado",
    "nombre_notario": "encabezado",
    "fecha_documento": "encabezado",
    "municipio": "encabezado",
    "estado": "encabezado",
    "tipo_titular": "comparecientes",
    "titulares": "comparecientes",
    "adquirientes": "comparecientes",
    "monto_operacion": "clausulas",
    "tipo_moneda": "clausulas",
    "valor_catastral": "clausulas",
}


# =============================================================================
# MODELOS
# =============================================================================

@dataclass
class Seccion:
    """
    Representa una sección individual del documento.
    
    Attributes:
        nombre: Identificador de la sección (encabezado, comparecientes, etc.)
        texto: Contenido de texto de la sección
        inicio: Posición de inicio en el texto completo
        fin: Posición de fin en el texto completo
        confianza: Qué tan seguro está de que detectó bien la sección (0.0 a 1.0)
    """
    nombre: str
    texto: str
    inicio: int
    fin: int
    confianza: float = 1.0


class SeccionesDocumento(BaseModel):
    """
    Contenedor de todas las secciones detectadas en un documento.
    
    Si una sección no se detecta, su valor será None.
    El campo usar_fallback indica si debemos usar texto_completo
    en lugar de las secciones individuales.
    """
    
    # Secciones individuales (pueden ser None si no se detectaron)
    encabezado: Optional[Dict[str, Any]] = None
    comparecientes: Optional[Dict[str, Any]] = None
    antecedentes: Optional[Dict[str, Any]] = None
    clausulas: Optional[Dict[str, Any]] = None
    certificaciones: Optional[Dict[str, Any]] = None
    
    # Texto completo (siempre disponible como fallback)
    texto_completo: str = ""
    
    # Lista de nombres de secciones que se detectaron
    secciones_detectadas: List[str] = Field(default_factory=list)
    
    # Si es True, usar texto_completo en lugar de secciones
    usar_fallback: bool = False
    
    # Confianza general de la segmentación
    confianza_segmentacion: float = 0.0
    
    class Config:
        arbitrary_types_allowed = True
    
    def obtener_texto_para_campo(self, campo: str) -> str:
        """
        Obtiene el texto más relevante para extraer un campo específico.
        
        Si la segmentación funcionó, devuelve la sección correspondiente.
        Si no, devuelve el texto completo.
        
        Args:
            campo: Nombre del campo a extraer
            
        Returns:
            Texto donde buscar el campo
            
        Ejemplo:
            >>> texto = secciones.obtener_texto_para_campo("nombre_notario")
            # Devuelve la sección "encabezado" si existe, o texto completo
        """
        if self.usar_fallback:
            return self.texto_completo
        
        # Buscar en qué sección está el campo
        seccion_nombre = SECCION_POR_CAMPO.get(campo)
        
        if seccion_nombre:
            seccion = getattr(self, seccion_nombre, None)
            if seccion and isinstance(seccion, dict):
                texto_seccion = seccion.get("texto", "")
                if texto_seccion and len(texto_seccion) > 100:
                    return texto_seccion
        
        # Fallback al texto completo
        return self.texto_completo
    
    def obtener_seccion(self, nombre: str) -> Optional[str]:
        """
        Obtiene el texto de una sección específica.
        
        Args:
            nombre: Nombre de la sección
            
        Returns:
            Texto de la sección o None
        """
        seccion = getattr(self, nombre, None)
        if seccion and isinstance(seccion, dict):
            return seccion.get("texto")
        return None
    
    def obtener_texto_para_plan_e(self, campo: str) -> str:
        """
        ⭐ NUEVO: Obtiene el texto óptimo para usar con Plan E.
        
        Prioridad:
        1. Sección específica del campo
        2. Primeros/últimos N caracteres según el tipo de campo
        3. Texto completo truncado
        
        Args:
            campo: Nombre del campo a extraer
            
        Returns:
            Texto optimizado para el prompt del Plan E
        """
        # Intentar usar sección
        if not self.usar_fallback:
            seccion_nombre = SECCION_POR_CAMPO.get(campo)
            if seccion_nombre:
                texto_seccion = self.obtener_seccion(seccion_nombre)
                if texto_seccion and len(texto_seccion) > 200:
                    return texto_seccion[:4000]  # Máximo 4000 chars
        
        # Fallback inteligente según el campo
        texto = self.texto_completo
        
        if campo in ["numero_escritura", "numero_notaria", "nombre_notario", "fecha_documento"]:
            # Estos campos suelen estar al inicio
            return texto[:3500]
        
        elif campo in ["monto_operacion", "tipo_moneda", "valor_catastral"]:
            # Estos campos suelen estar en medio-final
            mitad = len(texto) // 2
            return texto[max(0, mitad-2000):min(len(texto), mitad+2000)]
        
        # Por defecto, primeros 4000 caracteres
        return texto[:4000]