"""
extraction/segmentador.py - Segmentador de documentos (Plan D)

PROPÓSITO:
==========
Divide el documento en secciones para procesamiento más preciso.
Si no puede segmentar, usa el texto completo como fallback.

ESTRATEGIA:
===========
1. Buscar "anclas" (palabras clave que indican inicio de sección)
2. Si encuentra suficientes anclas → segmentar
3. Si no encuentra → usar texto completo

IMPORTANTE:
===========
La segmentación es OPCIONAL. Si falla, el sistema sigue funcionando
igual que antes usando el texto completo.

USO CON PLAN E:
===============
El Plan E usa las secciones para enviar prompts más cortos y precisos.
"""

import re
from typing import Optional, List, Tuple, Dict, Any

# Importar configuración de secciones
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.secciones import (
    Seccion,
    SeccionesDocumento,
    ANCLAS_SECCIONES,
    CAMPOS_POR_SECCION,
)


class Segmentador:
    """
    Divide el documento en secciones lógicas.
    
    Uso:
        segmentador = Segmentador()
        secciones = segmentador.segmentar(texto_documento)
        
        if secciones.usar_fallback:
            # No se pudo segmentar, usar texto completo
            texto = secciones.texto_completo
        else:
            # Usar secciones individuales
            texto_encabezado = secciones.obtener_seccion("encabezado")
    """
    
    def __init__(self, min_secciones: int = 2, min_chars_seccion: int = 100):
        """
        Args:
            min_secciones: Mínimo de secciones a detectar para no usar fallback
            min_chars_seccion: Mínimo de caracteres para considerar una sección válida
        """
        self.min_secciones = min_secciones
        self.min_chars_seccion = min_chars_seccion
        
        # Compilar patrones para eficiencia (se hace una sola vez)
        self.patrones_compilados: Dict[str, List[re.Pattern]] = {}
        for seccion, anclas in ANCLAS_SECCIONES.items():
            self.patrones_compilados[seccion] = [
                re.compile(ancla, re.IGNORECASE | re.MULTILINE)
                for ancla in anclas
            ]
    
    def segmentar(self, texto: str) -> SeccionesDocumento:
        """
        Segmenta el documento en secciones.
        
        Args:
            texto: Texto completo del documento (ya limpio de OCR)
            
        Returns:
            SeccionesDocumento con las secciones detectadas o fallback
        """
        
        # Documento muy corto: no segmentar
        if len(texto) < 3000:
            return SeccionesDocumento(
                texto_completo=texto,
                usar_fallback=True,
                confianza_segmentacion=0.0,
                secciones_detectadas=[]
            )
        
        # Encontrar posiciones de cada sección
        posiciones = self._encontrar_posiciones(texto)
        
        # Si no encontramos suficientes secciones, usar fallback
        if len(posiciones) < self.min_secciones:
            return SeccionesDocumento(
                texto_completo=texto,
                usar_fallback=True,
                confianza_segmentacion=0.0,
                secciones_detectadas=[]
            )
        
        # Ordenar por posición
        posiciones_ordenadas = sorted(posiciones, key=lambda x: x[1])
        
        # Crear el resultado
        resultado = SeccionesDocumento(
            texto_completo=texto,
            usar_fallback=False,
            secciones_detectadas=[]
        )
        
        # Construir cada sección
        confianzas = []
        for i, (nombre_seccion, pos_inicio, confianza) in enumerate(posiciones_ordenadas):
            # El fin es el inicio de la siguiente sección o el fin del documento
            if i + 1 < len(posiciones_ordenadas):
                pos_fin = posiciones_ordenadas[i + 1][1]
            else:
                pos_fin = len(texto)
            
            texto_seccion = texto[pos_inicio:pos_fin].strip()
            
            # Solo guardar si tiene suficiente contenido
            if len(texto_seccion) >= self.min_chars_seccion:
                seccion_dict = {
                    "texto": texto_seccion,
                    "inicio": pos_inicio,
                    "fin": pos_fin,
                    "confianza": confianza
                }
                setattr(resultado, nombre_seccion, seccion_dict)
                resultado.secciones_detectadas.append(nombre_seccion)
                confianzas.append(confianza)
        
        # Si después de filtrar no hay suficientes secciones, usar fallback
        if len(resultado.secciones_detectadas) < self.min_secciones:
            resultado.usar_fallback = True
            resultado.confianza_segmentacion = 0.0
        else:
            resultado.confianza_segmentacion = sum(confianzas) / len(confianzas) if confianzas else 0.0
        
        # Asegurar que siempre hay encabezado (los primeros N caracteres)
        if "encabezado" not in resultado.secciones_detectadas and not resultado.usar_fallback:
            primer_inicio = posiciones_ordenadas[0][1] if posiciones_ordenadas else len(texto)
            if primer_inicio > 200:  # Si hay texto antes de la primera sección
                resultado.encabezado = {
                    "texto": texto[:primer_inicio].strip(),
                    "inicio": 0,
                    "fin": primer_inicio,
                    "confianza": 0.5  # Confianza baja porque es inferido
                }
                resultado.secciones_detectadas.insert(0, "encabezado")
        
        return resultado
    
    def _encontrar_posiciones(self, texto: str) -> List[Tuple[str, int, float]]:
        """
        Encuentra las posiciones donde inicia cada sección.
        
        Returns:
            Lista de (nombre_seccion, posicion_inicio, confianza)
        """
        posiciones = []
        
        for nombre_seccion, patrones in self.patrones_compilados.items():
            mejor_match = None
            mejor_confianza = 0.0
            
            for i, patron in enumerate(patrones):
                match = patron.search(texto)
                if match:
                    # El primer patrón de la lista tiene más confianza
                    confianza = 1.0 - (i * 0.15)  # 1.0, 0.85, 0.70, ...
                    confianza = max(confianza, 0.5)  # Mínimo 0.5
                    
                    if confianza > mejor_confianza:
                        mejor_match = match
                        mejor_confianza = confianza
            
            if mejor_match:
                posiciones.append((nombre_seccion, mejor_match.start(), mejor_confianza))
        
        return posiciones


# =============================================================================
# FUNCIÓN DE CONVENIENCIA
# =============================================================================

def segmentar_documento(texto: str) -> SeccionesDocumento:
    """
    Función de conveniencia para segmentar un documento.
    
    Args:
        texto: Texto del documento
        
    Returns:
        SeccionesDocumento con secciones o fallback a texto completo
    """
    segmentador = Segmentador()
    return segmentador.segmentar(texto)