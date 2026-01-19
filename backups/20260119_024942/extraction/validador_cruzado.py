"""
extraction/validador_cruzado.py - Validación cruzada (Plan B)

PROPÓSITO:
==========
Verifica que los datos extraídos por el LLM realmente existen
en el texto original del documento. Detecta "alucinaciones".

ESTRATEGIA:
===========
1. Para cada campo extraído por LLM, buscar si existe en el texto
2. Si existe → confianza ALTA
3. Si no existe → intentar corregir con regex, si no → confianza BAJA

EJEMPLO:
========
    LLM dice: "numero_notaria": 45
    Texto dice: "Notaría Pública número 10"
    Validación: 45 NO está en el texto
    Acción: Buscar con regex → encuentra 10
    Resultado: numero_notaria = 10 (CORREGIDO)
"""

import re
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.confianza import NivelConfianza, OrigenDato, VALORES_INVALIDOS
from utils.text_processing import (
    extraer_numero_escritura,
    extraer_numero_notaria,
    extraer_nombre_notario,
    extraer_monto_operacion,
    extraer_fecha_documento,
    validar_dato_en_texto,
)


@dataclass
class ResultadoValidacion:
    """
    Resultado de validar un campo contra el texto original.
    
    Attributes:
        campo: Nombre del campo validado
        valor_original: Lo que dijo el LLM
        valor_validado: El valor final (puede ser corregido)
        encontrado_en_texto: Si el valor está en el texto
        fue_corregido: Si se tuvo que corregir
        confianza: Nivel de confianza resultante
        origen: Cómo se obtuvo el valor final
    """
    campo: str
    valor_original: Any          # Lo que dijo el LLM
    valor_validado: Any          # El valor final (puede ser corregido)
    encontrado_en_texto: bool    # Si el valor está en el texto
    fue_corregido: bool          # Si se tuvo que corregir
    confianza: NivelConfianza
    origen: OrigenDato


class ValidadorCruzado:
    """
    Valida los datos extraídos contra el texto original.
    
    Uso:
        validador = ValidadorCruzado(texto_original)
        
        # Validar un campo
        resultado = validador.validar_campo("numero_notaria", 45)
        if resultado.fue_corregido:
            print(f"Corregido: {resultado.valor_original} -> {resultado.valor_validado}")
        
        # Validar todos los campos
        resultados = validador.validar_todos(datos_llm)
    """
    
    def __init__(self, texto_original: str):
        """
        Args:
            texto_original: El texto del documento (usado para validación)
        """
        self.texto = texto_original
        self.texto_upper = texto_original.upper()
    
    def validar_campo(self, nombre_campo: str, valor_llm: Any) -> ResultadoValidacion:
        """
        Valida un campo individual extraído por el LLM.
        
        Args:
            nombre_campo: Nombre del campo
            valor_llm: Valor que extrajo el LLM
            
        Returns:
            ResultadoValidacion con el análisis
        """
        
        # Si el valor es inválido, no hay nada que validar
        if valor_llm in VALORES_INVALIDOS:
            return ResultadoValidacion(
                campo=nombre_campo,
                valor_original=valor_llm,
                valor_validado=None,
                encontrado_en_texto=False,
                fue_corregido=False,
                confianza=NivelConfianza.NO_ENCONTRADO,
                origen=OrigenDato.NO_EXTRAIDO
            )
        
        # Seleccionar método de validación según el tipo de campo
        if nombre_campo == "numero_escritura":
            return self._validar_numero_escritura(valor_llm)
        elif nombre_campo == "numero_notaria":
            return self._validar_numero_notaria(valor_llm)
        elif nombre_campo == "nombre_notario":
            return self._validar_nombre_notario(valor_llm)
        elif nombre_campo == "monto_operacion":
            return self._validar_monto(valor_llm)
        elif nombre_campo in ["rfc", "curp"]:
            return self._validar_identificador(nombre_campo, valor_llm)
        else:
            return self._validar_texto_generico(nombre_campo, valor_llm)
    
    def _validar_numero_escritura(self, valor_llm: Any) -> ResultadoValidacion:
        """Valida el número de escritura."""
        nombre = "numero_escritura"
        
        # Verificar si está en el texto
        if validar_dato_en_texto(valor_llm, self.texto):
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_llm,
                encontrado_en_texto=True,
                fue_corregido=False,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.LLM_VALIDADO
            )
        
        # No está en el texto, intentar extraer con regex
        valor_regex = extraer_numero_escritura(self.texto)
        if valor_regex is not None:
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_regex,
                encontrado_en_texto=True,
                fue_corregido=True,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.CORREGIDO
            )
        
        # No se encontró en texto ni con regex
        return ResultadoValidacion(
            campo=nombre,
            valor_original=valor_llm,
            valor_validado=valor_llm,
            encontrado_en_texto=False,
            fue_corregido=False,
            confianza=NivelConfianza.BAJA,
            origen=OrigenDato.LLM_NO_VALIDADO
        )
    
    def _validar_numero_notaria(self, valor_llm: Any) -> ResultadoValidacion:
        """Valida el número de notaría."""
        nombre = "numero_notaria"
        
        if validar_dato_en_texto(valor_llm, self.texto):
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_llm,
                encontrado_en_texto=True,
                fue_corregido=False,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.LLM_VALIDADO
            )
        
        valor_regex = extraer_numero_notaria(self.texto)
        if valor_regex is not None:
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_regex,
                encontrado_en_texto=True,
                fue_corregido=True,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.CORREGIDO
            )
        
        return ResultadoValidacion(
            campo=nombre,
            valor_original=valor_llm,
            valor_validado=valor_llm,
            encontrado_en_texto=False,
            fue_corregido=False,
            confianza=NivelConfianza.BAJA,
            origen=OrigenDato.LLM_NO_VALIDADO
        )
    
    def _validar_nombre_notario(self, valor_llm: str) -> ResultadoValidacion:
        """
        Valida el nombre del notario.
        
        Para nombres, usamos validación parcial: verificamos que
        las palabras principales del nombre estén en el texto.
        """
        nombre = "nombre_notario"
        
        if not valor_llm or not isinstance(valor_llm, str):
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=None,
                encontrado_en_texto=False,
                fue_corregido=False,
                confianza=NivelConfianza.NO_ENCONTRADO,
                origen=OrigenDato.NO_EXTRAIDO
            )
        
        # Validación parcial: contar cuántas palabras del nombre están en el texto
        palabras = [p for p in valor_llm.upper().split() if len(p) > 2]
        if not palabras:
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_llm,
                encontrado_en_texto=False,
                fue_corregido=False,
                confianza=NivelConfianza.BAJA,
                origen=OrigenDato.LLM_NO_VALIDADO
            )
        
        palabras_encontradas = sum(1 for p in palabras if p in self.texto_upper)
        porcentaje = palabras_encontradas / len(palabras)
        
        # Si más del 60% de las palabras están en el texto, es válido
        if porcentaje >= 0.6:
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_llm,
                encontrado_en_texto=True,
                fue_corregido=False,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.LLM_VALIDADO
            )
        
        # Intentar extraer con regex
        valor_regex = extraer_nombre_notario(self.texto)
        if valor_regex:
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_regex,
                encontrado_en_texto=True,
                fue_corregido=True,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.CORREGIDO
            )
        
        # No se pudo validar
        return ResultadoValidacion(
            campo=nombre,
            valor_original=valor_llm,
            valor_validado=valor_llm,
            encontrado_en_texto=False,
            fue_corregido=False,
            confianza=NivelConfianza.MEDIA,  # Media porque es nombre
            origen=OrigenDato.LLM_NO_VALIDADO
        )
    
    def _validar_monto(self, valor_llm: Any) -> ResultadoValidacion:
        """Valida el monto de la operación."""
        nombre = "monto_operacion"
        
        # Extraer número del monto
        if isinstance(valor_llm, str):
            numero_str = re.sub(r'[^\d.]', '', valor_llm)
            try:
                numero = float(numero_str) if numero_str else 0
            except ValueError:
                numero = 0
        elif isinstance(valor_llm, (int, float)):
            numero = float(valor_llm)
        else:
            numero = 0
        
        # Buscar el número en el texto
        if numero > 0:
            numero_int = int(numero)
            # Buscar con diferentes formatos
            formatos = [
                str(numero_int),
                f"{numero_int:,}",
                f"{numero_int:,.2f}",
            ]
            for fmt in formatos:
                if fmt in self.texto or fmt.replace(",", "") in self.texto:
                    return ResultadoValidacion(
                        campo=nombre,
                        valor_original=valor_llm,
                        valor_validado=valor_llm,
                        encontrado_en_texto=True,
                        fue_corregido=False,
                        confianza=NivelConfianza.ALTA,
                        origen=OrigenDato.LLM_VALIDADO
                    )
        
        # Intentar con regex
        valor_regex = extraer_monto_operacion(self.texto)
        if valor_regex:
            return ResultadoValidacion(
                campo=nombre,
                valor_original=valor_llm,
                valor_validado=valor_regex,
                encontrado_en_texto=True,
                fue_corregido=True,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.CORREGIDO
            )
        
        return ResultadoValidacion(
            campo=nombre,
            valor_original=valor_llm,
            valor_validado=valor_llm,
            encontrado_en_texto=False,
            fue_corregido=False,
            confianza=NivelConfianza.BAJA,
            origen=OrigenDato.LLM_NO_VALIDADO
        )
    
    def _validar_identificador(self, nombre_campo: str, valor_llm: str) -> ResultadoValidacion:
        """Valida RFC o CURP."""
        
        if not valor_llm or not isinstance(valor_llm, str):
            return ResultadoValidacion(
                campo=nombre_campo,
                valor_original=valor_llm,
                valor_validado=None,
                encontrado_en_texto=False,
                fue_corregido=False,
                confianza=NivelConfianza.NO_ENCONTRADO,
                origen=OrigenDato.NO_EXTRAIDO
            )
        
        valor_upper = valor_llm.upper().strip()
        
        if valor_upper in self.texto_upper:
            return ResultadoValidacion(
                campo=nombre_campo,
                valor_original=valor_llm,
                valor_validado=valor_upper,
                encontrado_en_texto=True,
                fue_corregido=False,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.LLM_VALIDADO
            )
        
        return ResultadoValidacion(
            campo=nombre_campo,
            valor_original=valor_llm,
            valor_validado=valor_llm,
            encontrado_en_texto=False,
            fue_corregido=False,
            confianza=NivelConfianza.BAJA,
            origen=OrigenDato.LLM_NO_VALIDADO
        )
    
    def _validar_texto_generico(self, nombre_campo: str, valor_llm: Any) -> ResultadoValidacion:
        """Validación genérica para campos de texto."""
        
        if not valor_llm:
            return ResultadoValidacion(
                campo=nombre_campo,
                valor_original=valor_llm,
                valor_validado=None,
                encontrado_en_texto=False,
                fue_corregido=False,
                confianza=NivelConfianza.NO_ENCONTRADO,
                origen=OrigenDato.NO_EXTRAIDO
            )
        
        valor_str = str(valor_llm)
        if valor_str.upper() in self.texto_upper:
            return ResultadoValidacion(
                campo=nombre_campo,
                valor_original=valor_llm,
                valor_validado=valor_llm,
                encontrado_en_texto=True,
                fue_corregido=False,
                confianza=NivelConfianza.ALTA,
                origen=OrigenDato.LLM_VALIDADO
            )
        
        return ResultadoValidacion(
            campo=nombre_campo,
            valor_original=valor_llm,
            valor_validado=valor_llm,
            encontrado_en_texto=False,
            fue_corregido=False,
            confianza=NivelConfianza.MEDIA,
            origen=OrigenDato.LLM_NO_VALIDADO
        )
    
    def validar_todos(self, datos_llm: Dict[str, Any]) -> Dict[str, ResultadoValidacion]:
        """
        Valida todos los campos de un diccionario.
        
        Args:
            datos_llm: Diccionario con los datos extraídos por LLM
            
        Returns:
            Diccionario {nombre_campo: ResultadoValidacion}
        """
        resultados = {}
        
        for campo, valor in datos_llm.items():
            # Saltar listas y dicts anidados (se validan diferente)
            if isinstance(valor, (list, dict)):
                continue
            
            resultados[campo] = self.validar_campo(campo, valor)
        
        return resultados


# =============================================================================
# FUNCIONES DE CONVENIENCIA
# =============================================================================

def validar_campo(texto: str, nombre_campo: str, valor: Any) -> ResultadoValidacion:
    """Función de conveniencia para validar un solo campo."""
    validador = ValidadorCruzado(texto)
    return validador.validar_campo(nombre_campo, valor)


def validar_todos_campos(texto: str, datos: Dict[str, Any]) -> Dict[str, ResultadoValidacion]:
    """Función de conveniencia para validar todos los campos."""
    validador = ValidadorCruzado(texto)
    return validador.validar_todos(datos)