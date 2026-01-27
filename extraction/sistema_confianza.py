"""
extraction/sistema_confianza.py - Sistema de confianza (Plan F)

PROPÓSITO:
==========
Consolida todos los resultados de extracción (regex + LLM + Plan E + validación)
y genera el resultado final con niveles de confianza.

RESPONSABILIDADES:
==================
1. Combinar datos de regex, LLM y Plan E (regex tiene prioridad)
2. Aplicar resultados de validación cruzada
3. Determinar confianza final de cada campo
4. Evaluar calidad general de la extracción
5. Marcar campos que requieren revisión humana
6. Generar respuesta con formato de campos separados
"""

from typing import Dict, Any, List, Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.confianza import (
    NivelConfianza,
    OrigenDato,
    ResultadoConfianza,
    EvaluacionCalidad,
    CAMPOS_CRITICOS,
    CAMPOS_TOTALES,
    VALORES_INVALIDOS,
    evaluar_calidad_extraccion,
    campo_tiene_valor,
)
from extraction.validador_cruzado import ResultadoValidacion
from extraction.plan_e_extractor import ResultadoPlanE


# Campos críticos que SIEMPRE deben revisarse si tienen baja confianza
CAMPOS_REQUIEREN_REVISION_SI_BAJA = [
    "numero_escritura",
    "numero_notaria",
    "nombre_notario",
    "monto_operacion",
]


class SistemaConfianza:
    """
    Consolida resultados y gestiona niveles de confianza.
    
    Uso:
        sistema = SistemaConfianza()
        
        # Agregar resultados de diferentes fuentes
        sistema.agregar_regex(datos_regex)
        sistema.agregar_llm(datos_llm)
        sistema.agregar_plan_e(resultados_plan_e)  # ⭐ NUEVO
        sistema.aplicar_validacion(resultados_validacion)
        
        # Obtener resultado final
        resultado = sistema.consolidar()
        
        if resultado.success:
            print(resultado.datos)
            print(resultado.confianza)
        else:
            print(resultado.error)
    """
    
    def __init__(self):
        # Almacenamiento interno
        self._datos: Dict[str, Any] = {}
        self._confianza: Dict[str, NivelConfianza] = {}
        self._origen: Dict[str, OrigenDato] = {}
        self._validaciones: Dict[str, ResultadoValidacion] = {}
        
        # Listas anidadas (titulares, adquirientes)
        self._listas: Dict[str, List] = {}
        
        # ⭐ NUEVO: Tracking de Plan E
        self._campos_plan_e: List[str] = []
    
    def agregar_regex(self, datos_regex: Dict[str, Any]):
        """
        Agrega resultados de la extracción por regex.
        
        Los datos de regex tienen PRIORIDAD MÁXIMA porque
        son determinísticos y más confiables para campos estructurados.
        
        Args:
            datos_regex: Diccionario con datos extraídos por regex
        """
        for nombre, valor in datos_regex.items():
            # Solo agregar si tiene valor válido
            if valor not in VALORES_INVALIDOS:
                self._datos[nombre] = valor
                self._confianza[nombre] = NivelConfianza.ALTA
                self._origen[nombre] = OrigenDato.REGEX
    
    def agregar_llm(self, datos_llm: Dict[str, Any]):
        """
        Agrega resultados de la extracción por LLM.
        
        Solo agrega campos que NO fueron ya extraídos por regex.
        La confianza inicial es MEDIA (pendiente validación).
        
        Args:
            datos_llm: Diccionario con datos extraídos por LLM
        """
        for nombre, valor in datos_llm.items():
            # Si regex ya lo extrajo con alta confianza, no sobrescribir
            if nombre in self._datos and self._confianza.get(nombre) == NivelConfianza.ALTA:
                continue
            
            # Manejar listas (titulares, adquirientes)
            if isinstance(valor, list):
                self._listas[nombre] = valor
                # Las listas tienen confianza MEDIA por defecto
                if valor:  # Si no está vacía
                    self._confianza[nombre] = NivelConfianza.MEDIA
                    self._origen[nombre] = OrigenDato.LLM_NO_VALIDADO
                continue
            
            # Manejar dicts anidados
            if isinstance(valor, dict):
                self._datos[nombre] = valor
                self._confianza[nombre] = NivelConfianza.MEDIA
                self._origen[nombre] = OrigenDato.LLM_NO_VALIDADO
                continue
            
            # Solo agregar si tiene valor válido
            if valor not in VALORES_INVALIDOS:
                self._datos[nombre] = valor
                self._confianza[nombre] = NivelConfianza.MEDIA
                self._origen[nombre] = OrigenDato.LLM_NO_VALIDADO
    
    def agregar_plan_e(self, resultados_plan_e: Dict[str, ResultadoPlanE]):
        """
        ⭐ NUEVO: Agrega resultados del Plan E.
        
        Plan E tiene prioridad sobre LLM (pero no sobre regex).
        Solo se agregan valores que fueron validados en el texto.
        
        Args:
            resultados_plan_e: Resultados del extractor Plan E
        """
        for campo, resultado in resultados_plan_e.items():
            # Solo usar si fue exitoso Y validado
            if resultado.exito and resultado.validado_en_texto:
                # Solo sobrescribir si el campo no viene de regex
                if self._origen.get(campo) != OrigenDato.REGEX:
                    self._datos[campo] = resultado.valor
                    self._confianza[campo] = NivelConfianza.ALTA
                    self._origen[campo] = OrigenDato.PLAN_E
                    self._campos_plan_e.append(campo)
    
    def aplicar_validacion(self, validaciones: Dict[str, ResultadoValidacion]):
        """
        Aplica los resultados de la validación cruzada.
        
        Actualiza los niveles de confianza y corrige valores si es necesario.
        
        Args:
            validaciones: Resultados del validador cruzado
        """
        self._validaciones = validaciones
        
        for nombre, resultado in validaciones.items():
            if nombre not in self._datos:
                continue
            
            # Si ya viene de regex o Plan E, no modificar
            if self._origen.get(nombre) in [OrigenDato.REGEX, OrigenDato.PLAN_E]:
                continue
            
            # Si fue corregido, actualizar valor y marcar como CORREGIDO
            if resultado.fue_corregido:
                self._datos[nombre] = resultado.valor_validado
                self._confianza[nombre] = resultado.confianza
                self._origen[nombre] = OrigenDato.CORREGIDO
            
            # Si fue validado en texto, subir confianza
            elif resultado.encontrado_en_texto:
                self._confianza[nombre] = NivelConfianza.ALTA
                if self._origen[nombre] == OrigenDato.LLM_NO_VALIDADO:
                    self._origen[nombre] = OrigenDato.LLM_VALIDADO
            
            # Si no fue validado y viene del LLM, puede ser alucinación
            elif self._origen.get(nombre) in [OrigenDato.LLM_NO_VALIDADO, OrigenDato.LLM_VALIDADO]:
                # Bajar confianza solo si actualmente es MEDIA
                if self._confianza.get(nombre) == NivelConfianza.MEDIA:
                    self._confianza[nombre] = NivelConfianza.BAJA
    
    def obtener_confianza(self) -> Dict[str, NivelConfianza]:
        """
        Obtiene el diccionario de confianza actual.
        
        Returns:
            Dict[campo, NivelConfianza]
        """
        return dict(self._confianza)
    
    def consolidar(self) -> ResultadoConfianza:
        """
        Genera el resultado final consolidado.
        
        Returns:
            ResultadoConfianza con todos los datos y metadatos
        """
        # Construir diccionario de datos final
        datos_finales = dict(self._datos)
        
        # Agregar listas
        for nombre, lista in self._listas.items():
            datos_finales[nombre] = lista
        
        # Convertir confianza a strings
        confianza_str = {k: v.value for k, v in self._confianza.items()}
        origen_str = {k: v.value for k, v in self._origen.items()}
        
        # Determinar campos que requieren revisión
        requiere_revision = []
        for campo in CAMPOS_REQUIEREN_REVISION_SI_BAJA:
            if self._confianza.get(campo) == NivelConfianza.BAJA:
                requiere_revision.append(campo)
        
        # Limitar a máximo 3 campos para revisión (para no abrumar)
        requiere_revision = requiere_revision[:3]
        
        # Evaluar calidad general
        evaluacion = evaluar_calidad_extraccion(datos_finales)
        
        # Si la evaluación dice que falló, retornar error
        if not evaluacion.success:
            return ResultadoConfianza(
                success=False,
                error=evaluacion.mensaje,
                error_code=evaluacion.error_code,
                datos={},  # No devolver datos basura
                confianza={},
                origen={},
                requiere_revision=[],
                calidad_general=evaluacion.calidad_porcentaje,
                campos_encontrados=evaluacion.campos_encontrados,
                campos_faltantes=evaluacion.campos_faltantes,
                plan_e_activado=len(self._campos_plan_e) > 0,
                campos_mejorados_plan_e=self._campos_plan_e,
                detalles_fallo={
                    "nivel": evaluacion.nivel.value,
                    "campos_criticos": evaluacion.campos_criticos_encontrados,
                    "posibles_causas": evaluacion.posibles_causas,
                    "sugerencias": evaluacion.sugerencias
                }
            )
        
        # Construir resultado exitoso
        resultado = ResultadoConfianza(
            success=True,
            datos=datos_finales,
            confianza=confianza_str,
            origen=origen_str,
            requiere_revision=requiere_revision,
            calidad_general=evaluacion.calidad_porcentaje,
            campos_encontrados=evaluacion.campos_encontrados,
            campos_faltantes=evaluacion.campos_faltantes,
            plan_e_activado=len(self._campos_plan_e) > 0,
            campos_mejorados_plan_e=self._campos_plan_e
        )
        
        # Si es extracción parcial, agregar advertencia
        if evaluacion.nivel.value == "parcial":
            resultado.advertencia = evaluacion.mensaje
        
        return resultado
    
    def generar_reporte(self) -> str:
        """
        Genera un reporte legible del estado de confianza.
        
        Útil para debugging y logs.
        """
        lineas = []
        lineas.append("=" * 60)
        lineas.append("REPORTE DE CONFIANZA")
        lineas.append("=" * 60)
        
        # Agrupar por nivel de confianza
        por_nivel = {
            NivelConfianza.ALTA: [],
            NivelConfianza.MEDIA: [],
            NivelConfianza.BAJA: [],
            NivelConfianza.NO_ENCONTRADO: []
        }
        
        for nombre in list(self._datos.keys()) + list(self._listas.keys()):
            confianza = self._confianza.get(nombre, NivelConfianza.NO_ENCONTRADO)
            valor = self._datos.get(nombre) or self._listas.get(nombre)
            por_nivel[confianza].append((nombre, valor))
        
        # Mostrar por nivel
        emojis = {
            NivelConfianza.ALTA: "✅",
            NivelConfianza.MEDIA: "⚠️",
            NivelConfianza.BAJA: "❌",
            NivelConfianza.NO_ENCONTRADO: "❓"
        }
        
        for nivel, campos in por_nivel.items():
            if campos:
                emoji = emojis.get(nivel, "•")
                lineas.append(f"\n{emoji} {nivel.value.upper()}:")
                for nombre, valor in campos:
                    origen = self._origen.get(nombre, OrigenDato.NO_EXTRAIDO)
                    valor_str = str(valor)[:50] + "..." if len(str(valor)) > 50 else str(valor)
                    lineas.append(f"   - {nombre}: {valor_str} ({origen.value})")
        
        # ⭐ NUEVO: Info de Plan E
        if self._campos_plan_e:
            lineas.append(f"\n🎯 CAMPOS MEJORADOS POR PLAN E:")
            for campo in self._campos_plan_e:
                lineas.append(f"   - {campo}")
        
        # Estadísticas
        resultado = self.consolidar()
        lineas.append(f"\n{'=' * 60}")
        lineas.append("📊 ESTADÍSTICAS:")
        lineas.append(f"   Campos encontrados: {resultado.campos_encontrados}/8")
        lineas.append(f"   Calidad general: {resultado.calidad_general}%")
        lineas.append(f"   Plan E activado: {'Sí' if resultado.plan_e_activado else 'No'}")
        
        if resultado.requiere_revision:
            lineas.append(f"\n⚠️ CAMPOS QUE REQUIEREN REVISIÓN:")
            for campo in resultado.requiere_revision:
                lineas.append(f"   - {campo}")
        
        lineas.append("=" * 60)
        
        return "\n".join(lineas)


# =============================================================================
# FUNCIÓN DE CONVENIENCIA
# =============================================================================

def consolidar_extraccion(
    datos_regex: Dict[str, Any],
    datos_llm: Dict[str, Any],
    validaciones: Dict[str, ResultadoValidacion],
    resultados_plan_e: Optional[Dict[str, ResultadoPlanE]] = None,
    texto_original: str = ""
) -> ResultadoConfianza:
    """
    Función de conveniencia para consolidar una extracción completa.
    
    Args:
        datos_regex: Datos extraídos por regex
        datos_llm: Datos extraídos por LLM
        validaciones: Resultados de validación cruzada
        resultados_plan_e: Resultados de Plan E (opcional)
        texto_original: Texto original (opcional, para logs)
        
    Returns:
        ResultadoConfianza con el resultado final
    """
    sistema = SistemaConfianza()
    sistema.agregar_regex(datos_regex)
    sistema.agregar_llm(datos_llm)
    
    if resultados_plan_e:
        sistema.agregar_plan_e(resultados_plan_e)
    
    sistema.aplicar_validacion(validaciones)
    
    return sistema.consolidar()