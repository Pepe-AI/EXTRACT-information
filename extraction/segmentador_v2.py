"""
extraction/segmentador_v2.py - Segmentador Mejorado con Mapeo de Secciones

MEJORAS vs segmentador.py:
===========================
✅ Usa el mapeo de campos → secciones de la tabla oficial
✅ Detecta secciones con patrones más robustos
✅ Retorna secciones con su contenido exacto
✅ Permite extracción dirigida (solo campos de la sección correcta)

OBSOLETO:
=========
- extraction/segmentador.py (mantener como respaldo pero ya no usar)
- models/secciones.py (reemplazado por models/seccion_mapping.py)

VENTAJAS:
=========
1. Mayor precisión: busca campos solo en secciones correctas
2. Menor ambigüedad: número_escritura del documento vs del poder
3. Validación: rechaza campos extraídos de secciones incorrectas
4. Eficiencia: envía menos tokens al LLM (solo texto relevante)
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Importar el nuevo mapeo de secciones
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.seccion_mapping import (
    SeccionDocumento,
    PATRONES_TITULOS_SECCION,
    CAMPOS_POR_SECCION,
    ConfiguracionSeccion,
)


@dataclass
class SeccionExtraida:
    """Representa una sección extraída del documento."""
    tipo: SeccionDocumento
    inicio: int
    fin: int
    contenido: str
    confianza: float  # 0.0 a 1.0


@dataclass
class ResultadoSegmentacion:
    """Resultado de la segmentación del documento."""
    secciones: Dict[SeccionDocumento, SeccionExtraida]
    texto_completo: str
    usar_fallback: bool  # True si no se pudo segmentar bien
    confianza_general: float


class SegmentadorV2:
    """
    Segmentador mejorado con mapeo oficial de campos → secciones.

    Uso:
        segmentador = SegmentadorV2()
        resultado = segmentador.segmentar(texto_documento)

        # Obtener sección específica
        if SeccionDocumento.GENERALES in resultado.secciones:
            seccion_generales = resultado.secciones[SeccionDocumento.GENERALES]
            print(seccion_generales.contenido)
    """

    def __init__(self, min_confianza: float = 0.5):
        """
        Args:
            min_confianza: Confianza mínima (0.0-1.0) para usar segmentación
        """
        self.min_confianza = min_confianza

        # Compilar patrones una sola vez para eficiencia
        self.patrones_compilados: Dict[SeccionDocumento, List[re.Pattern]] = {}
        for seccion, patrones in PATRONES_TITULOS_SECCION.items():
            self.patrones_compilados[seccion] = [
                re.compile(patron, re.IGNORECASE | re.MULTILINE)
                for patron in patrones
            ]

    def segmentar(self, texto: str) -> ResultadoSegmentacion:
        """
        Segmenta el documento en secciones identificables.

        Args:
            texto: Texto completo del documento limpio de OCR

        Returns:
            ResultadoSegmentacion con secciones o fallback
        """

        # Documento muy corto: usar fallback
        if len(texto) < 2000:
            return ResultadoSegmentacion(
                secciones={},
                texto_completo=texto,
                usar_fallback=True,
                confianza_general=0.0
            )

        # Detectar posiciones de inicio de cada sección
        posiciones = self._detectar_posiciones_secciones(texto)

        # Si no detectamos suficientes secciones (< 3), usar fallback
        if len(posiciones) < 3:
            return ResultadoSegmentacion(
                secciones={},
                texto_completo=texto,
                usar_fallback=True,
                confianza_general=len(posiciones) * 0.2  # 0.2 por cada sección detectada
            )

        # Extraer contenido de cada sección
        secciones_extraidas = self._extraer_contenido_secciones(texto, posiciones)

        # Calcular confianza general
        if secciones_extraidas:
            confianza_general = sum(s.confianza for s in secciones_extraidas.values()) / len(secciones_extraidas)
        else:
            confianza_general = 0.0

        # Decidir si usar segmentación o fallback
        usar_fallback = confianza_general < self.min_confianza

        return ResultadoSegmentacion(
            secciones=secciones_extraidas,
            texto_completo=texto,
            usar_fallback=usar_fallback,
            confianza_general=confianza_general
        )

    def _detectar_posiciones_secciones(self, texto: str) -> Dict[SeccionDocumento, int]:
        """
        Detecta la posición de inicio de cada sección en el texto.

        Returns:
            Dict[SeccionDocumento, int]: Posición de inicio de cada sección
        """
        posiciones: Dict[SeccionDocumento, int] = {}

        for seccion, patrones in self.patrones_compilados.items():
            # Buscar primera coincidencia de cualquier patrón
            mejor_pos = -1

            for patron in patrones:
                match = patron.search(texto)
                if match:
                    pos = match.start()
                    if mejor_pos == -1 or pos < mejor_pos:
                        mejor_pos = pos

            if mejor_pos != -1:
                posiciones[seccion] = mejor_pos

        return posiciones

    def _extraer_contenido_secciones(
        self,
        texto: str,
        posiciones: Dict[SeccionDocumento, int]
    ) -> Dict[SeccionDocumento, SeccionExtraida]:
        """
        Extrae el contenido de cada sección usando las posiciones detectadas.

        Returns:
            Dict[SeccionDocumento, SeccionExtraida]: Secciones con contenido
        """
        secciones: Dict[SeccionDocumento, SeccionExtraida] = {}

        # Ordenar secciones por posición
        secciones_ordenadas = sorted(posiciones.items(), key=lambda x: x[1])

        for i, (seccion_tipo, pos_inicio) in enumerate(secciones_ordenadas):
            # Determinar fin de la sección
            if i < len(secciones_ordenadas) - 1:
                # Fin = inicio de la siguiente sección
                pos_fin = secciones_ordenadas[i + 1][1]
            else:
                # Última sección: hasta el final del documento
                pos_fin = len(texto)

            # Extraer contenido
            contenido = texto[pos_inicio:pos_fin].strip()

            # Calcular confianza basada en longitud
            confianza = self._calcular_confianza_seccion(seccion_tipo, contenido)

            # Aplicar límite de caracteres si es necesario
            limite = ConfiguracionSeccion.LIMITES_CARACTERES.get(seccion_tipo, len(contenido))
            if len(contenido) > limite:
                # Truncar pero intentar no cortar a mitad de palabra
                contenido_truncado = contenido[:limite]
                ultimo_espacio = contenido_truncado.rfind(' ')
                if ultimo_espacio > limite * 0.8:  # Si el último espacio está cerca del límite
                    contenido = contenido_truncado[:ultimo_espacio]
                else:
                    contenido = contenido_truncado

            secciones[seccion_tipo] = SeccionExtraida(
                tipo=seccion_tipo,
                inicio=pos_inicio,
                fin=pos_fin,
                contenido=contenido,
                confianza=confianza
            )

        return secciones

    def _calcular_confianza_seccion(self, seccion: SeccionDocumento, contenido: str) -> float:
        """
        Calcula confianza de extracción de una sección basada en su longitud.

        Returns:
            float: Confianza entre 0.0 y 1.0
        """
        longitud = len(contenido)

        # Límites esperados por tipo de sección
        limites_esperados = {
            SeccionDocumento.INTRODUCCION: (500, 3000),
            SeccionDocumento.CLAUSULA_PRIMERA: (1000, 8000),
            SeccionDocumento.CLAUSULA_SEGUNDA: (800, 5000),
            SeccionDocumento.PERSONALIDAD: (300, 3000),
            SeccionDocumento.GENERALES: (2000, 12000),
        }

        min_esperado, max_esperado = limites_esperados.get(seccion, (100, 10000))

        if longitud < min_esperado * 0.5:
            # Muy corta: baja confianza
            return 0.3
        elif longitud < min_esperado:
            # Un poco corta: confianza media
            return 0.6
        elif longitud <= max_esperado:
            # Longitud apropiada: alta confianza
            return 0.9
        else:
            # Muy larga: confianza media-alta (puede ser normal)
            return 0.7


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

def obtener_seccion_para_campo(
    resultado: ResultadoSegmentacion,
    campo: str
) -> Optional[str]:
    """
    Obtiene el texto de la sección donde debe buscarse un campo.

    Args:
        resultado: Resultado de segmentación
        campo: Nombre del campo a buscar

    Returns:
        Texto de la sección o texto completo si no se segmentó
    """
    from models.seccion_mapping import SECCION_POR_CAMPO

    # Si no se pudo segmentar, retornar texto completo
    if resultado.usar_fallback:
        return resultado.texto_completo

    # Obtener sección del campo
    try:
        seccion = SECCION_POR_CAMPO[campo]
    except KeyError:
        # Campo no mapeado, usar texto completo
        return resultado.texto_completo

    # Retornar contenido de la sección
    if seccion in resultado.secciones:
        return resultado.secciones[seccion].contenido
    else:
        # Sección no detectada, usar texto completo
        return resultado.texto_completo


__all__ = [
    "SegmentadorV2",
    "ResultadoSegmentacion",
    "SeccionExtraida",
    "obtener_seccion_para_campo",
]
