"""
extraction/plan_e_extractor.py - Extractor de campos individuales (Plan E)

PROPÓSITO:
==========
Cuando el LLM general falla en extraer un campo crítico (confianza BAJA),
este módulo hace preguntas específicas para recuperar el dato.

CUÁNDO SE USA:
==============
1. Campo es CRÍTICO (numero_escritura, numero_notaria, etc.)
2. Confianza es BAJA
3. Regex no pudo extraerlo
4. LLM general extrajo algo pero no se validó en texto

LÍMITES:
========
- Máximo 3 campos por documento
- Timeout de 15 segundos por campo
- Timeout total de 45 segundos

FILOSOFÍA:
==========
El Plan E hace UNA pregunta simple y espera UNA respuesta simple.
No es un extractor completo, es un "segundo intento" para campos problemáticos.
"""

import re
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.confianza import NivelConfianza, OrigenDato, VALORES_INVALIDOS
from models.secciones import SeccionesDocumento
from utils.text_processing import validar_dato_en_texto


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

# Límites de tiempo (en segundos)
TIMEOUT_POR_CAMPO = 25      # Máximo 25 segundos por campo
TIMEOUT_TOTAL = 75          # Máximo 45 segundos para todo Plan E
MAX_CAMPOS = 3              # Máximo 3 campos con Plan E
MAX_TOKENS_RESPUESTA = 550  # Respuestas cortas


# =============================================================================
# PROMPTS ESPECÍFICOS POR CAMPO
# =============================================================================

PROMPTS_PLAN_E = {
    "numero_escritura": """
En México, las escrituras públicas tienen un NÚMERO DE ESCRITURA que las identifica.
Este número suele ser de 4 a 7 dígitos (ejemplos: 2307, 18226, 1234567).

Del siguiente texto de una escritura pública, extrae ÚNICAMENTE el número de escritura.

TEXTO:
{texto}

INSTRUCCIONES:
- Responde SOLO con el número (ejemplo: 18226)
- Si no lo encuentras, responde exactamente: NO ENCONTRADO
- NO agregues explicaciones ni texto adicional
""",

    "numero_notaria": """
En México, cada notario tiene una NOTARÍA con un número asignado.
El número de notaría suele ser de 1 a 3 dígitos (ejemplos: 5, 45, 123).
NO confundir con el número de escritura (que es más largo, 4-7 dígitos).

Del siguiente texto, extrae ÚNICAMENTE el número de la notaría.

TEXTO:
{texto}

INSTRUCCIONES:
- Responde SOLO con el número (ejemplo: 10)
- Busca frases como "Notaría número X", "Notaría Pública X", "Notaría X"
- Si no lo encuentras, responde exactamente: NO ENCONTRADO
- NO agregues explicaciones ni texto adicional
""",

    "nombre_notario": """
En una escritura pública mexicana, el NOTARIO es quien da fe del acto.
El nombre del notario suele aparecer junto a frases como "ante mí" o "Notario Público".

Del siguiente texto, extrae ÚNICAMENTE el nombre completo del notario.

TEXTO:
{texto}

INSTRUCCIONES:
- Responde SOLO con el nombre completo en MAYÚSCULAS (ejemplo: JUAN PÉREZ GARCÍA)
- NO incluyas títulos como "Lic.", "Licenciado", "Dr."
- Si no lo encuentras, responde exactamente: NO ENCONTRADO
- NO agregues explicaciones ni texto adicional
""",

    "monto_operacion": """
En una escritura de compraventa, el MONTO o PRECIO es la cantidad de dinero de la operación.
Suele aparecer en pesos mexicanos con formato $X,XXX.XX

Del siguiente texto, extrae ÚNICAMENTE el monto de la operación.

TEXTO:
{texto}

INSTRUCCIONES:
- Responde SOLO con el monto en formato $X,XXX.XX (ejemplo: $600,000.00)
- Busca frases como "precio de", "cantidad de", "por la suma de"
- Si hay varios montos, elige el que parece ser el precio principal
- Si no lo encuentras, responde exactamente: NO ENCONTRADO
- NO agregues explicaciones ni texto adicional
""",

    "fecha_documento": """
En una escritura pública, la FECHA DEL DOCUMENTO es cuando se firmó.
Suele estar al inicio del documento.

Del siguiente texto, extrae ÚNICAMENTE la fecha del documento.

TEXTO:
{texto}

INSTRUCCIONES:
- Responde SOLO con la fecha en formato "día de mes de año" (ejemplo: 22 de marzo de 2024)
- Si no lo encuentras, responde exactamente: NO ENCONTRADO
- NO agregues explicaciones ni texto adicional
""",
}


# =============================================================================
# MODELOS DE RESULTADO
# =============================================================================

@dataclass
class ResultadoPlanE:
    """
    Resultado de extraer un campo con Plan E.
    
    Attributes:
        campo: Nombre del campo extraído
        valor: Valor extraído (o None si falló)
        exito: Si la extracción fue exitosa
        validado_en_texto: Si el valor existe en el texto original
        tiempo_segundos: Cuánto tardó la extracción
        respuesta_cruda: Respuesta original del LLM
        error: Mensaje de error si falló
    """
    campo: str
    valor: Any = None
    exito: bool = False
    validado_en_texto: bool = False
    tiempo_segundos: float = 0.0
    respuesta_cruda: str = ""
    error: Optional[str] = None


# =============================================================================
# CLASE PRINCIPAL
# =============================================================================

class PlanEExtractor:
    """
    Extractor de campos individuales con prompts específicos.
    
    Uso:
        plan_e = PlanEExtractor(ollama_service)
        
        resultados = plan_e.ejecutar(
            campos_dudosos=["numero_notaria", "nombre_notario"],
            texto_documento=texto,
            secciones=secciones
        )
        
        for campo, resultado in resultados.items():
            if resultado.exito:
                print(f"{campo}: {resultado.valor}")
    """
    
    def __init__(self, ollama_service):
        """
        Args:
            ollama_service: Instancia de OllamaService para hacer llamadas al LLM
        """
        self.ollama = ollama_service
    
    def ejecutar(
        self,
        campos_dudosos: List[str],
        texto_documento: str,
        secciones: Optional[SeccionesDocumento] = None
    ) -> Dict[str, ResultadoPlanE]:
        """
        Ejecuta Plan E para los campos dudosos.
        
        Args:
            campos_dudosos: Lista de campos a procesar (máximo 3)
            texto_documento: Texto completo del documento
            secciones: Secciones del documento (opcional, para optimizar)
            
        Returns:
            Diccionario {campo: ResultadoPlanE}
        """
        resultados = {}
        inicio_total = time.time()
        
        # Limitar a máximo 3 campos
        campos = campos_dudosos[:MAX_CAMPOS]
        
        for campo in campos:
            # Verificar timeout total
            if time.time() - inicio_total > TIMEOUT_TOTAL:
                print(f"   ⚠️ Plan E timeout total alcanzado ({TIMEOUT_TOTAL}s)")
                # Marcar campos restantes como no procesados
                for campo_pendiente in campos[campos.index(campo):]:
                    resultados[campo_pendiente] = ResultadoPlanE(
                        campo=campo_pendiente,
                        error="Timeout total de Plan E alcanzado"
                    )
                break
            
            # Verificar que tenemos prompt para este campo
            if campo not in PROMPTS_PLAN_E:
                resultados[campo] = ResultadoPlanE(
                    campo=campo,
                    error=f"No hay prompt definido para el campo '{campo}'"
                )
                continue
            
            # Obtener el texto óptimo para este campo
            if secciones:
                texto_para_prompt = secciones.obtener_texto_para_plan_e(campo)
            else:
                texto_para_prompt = self._obtener_texto_relevante(campo, texto_documento)
            
            # Extraer el campo
            resultado = self._extraer_campo(campo, texto_para_prompt, texto_documento)
            resultados[campo] = resultado
        
        return resultados
    
    def _extraer_campo(
        self,
        campo: str,
        texto_para_prompt: str,
        texto_completo: str
    ) -> ResultadoPlanE:
        """
        Extrae un campo individual usando un prompt específico.
        
        Args:
            campo: Nombre del campo a extraer
            texto_para_prompt: Texto a incluir en el prompt
            texto_completo: Texto completo para validación
            
        Returns:
            ResultadoPlanE con el resultado
        """
        inicio = time.time()
        
        try:
            # Construir el prompt
            prompt = PROMPTS_PLAN_E[campo].format(texto=texto_para_prompt)
            
            # Llamar al LLM
            response = self.ollama.generate(
                prompt=prompt,
                system="Eres un extractor de datos preciso. Responde SOLO con el dato solicitado, sin explicaciones.",
                temperature=0.0,
                max_tokens=MAX_TOKENS_RESPUESTA
            )
            
            tiempo = time.time() - inicio
            respuesta_cruda = response.get('response', '')
            
            # Limpiar y procesar la respuesta
            valor = self._limpiar_respuesta(respuesta_cruda, campo)
            
            # Verificar si no encontró nada
            if valor is None or valor == "NO ENCONTRADO":
                return ResultadoPlanE(
                    campo=campo,
                    valor=None,
                    exito=False,
                    validado_en_texto=False,
                    tiempo_segundos=tiempo,
                    respuesta_cruda=respuesta_cruda,
                    error="No se encontró el dato"
                )
            
            # Validar que el valor existe en el texto original
            validado = validar_dato_en_texto(valor, texto_completo)
            
            return ResultadoPlanE(
                campo=campo,
                valor=valor,
                exito=validado,  # Solo es éxito si está validado
                validado_en_texto=validado,
                tiempo_segundos=tiempo,
                respuesta_cruda=respuesta_cruda
            )
            
        except Exception as e:
            return ResultadoPlanE(
                campo=campo,
                error=str(e),
                tiempo_segundos=time.time() - inicio
            )
    
    def _limpiar_respuesta(self, respuesta: str, campo: str) -> Any:
        """
        Limpia y normaliza la respuesta del LLM.
        
        El LLM puede responder con formato extra, explicaciones, etc.
        Esta función extrae solo el valor útil.
        
        Args:
            respuesta: Respuesta cruda del LLM
            campo: Tipo de campo (para aplicar limpieza específica)
            
        Returns:
            Valor limpio o None si no se pudo extraer
        """
        if not respuesta:
            return None
        
        # 1. Eliminar bloque <think> si existe (DeepSeek R1)
        respuesta = re.sub(r'<think>.*?</think>', '', respuesta, flags=re.DOTALL)
        
        # 2. Eliminar markdown
        respuesta = re.sub(r'```.*?```', '', respuesta, flags=re.DOTALL)
        respuesta = respuesta.strip('`')
        
        # 3. Eliminar explicaciones comunes
        respuesta = re.sub(r'^(El |La |Este |Esta |Es |El número es |El nombre es |El monto es )', '', respuesta, flags=re.IGNORECASE)
        
        # 4. Tomar solo la primera línea
        respuesta = respuesta.split('\n')[0].strip()
        
        # 5. Verificar si es "NO ENCONTRADO"
        if 'NO ENCONTRADO' in respuesta.upper() or 'NO SE ENCONTR' in respuesta.upper():
            return None
        
        # 6. Limpieza específica según el campo
        if campo in ["numero_escritura", "numero_notaria"]:
            # Extraer solo números
            numeros = re.findall(r'\d+', respuesta)
            if numeros:
                numero = int(numeros[0])
                # Validar rangos
                if campo == "numero_notaria" and 1 <= numero <= 999:
                    return numero
                elif campo == "numero_escritura" and 1 <= numero <= 9999999:
                    return numero
            return None
        
        elif campo == "monto_operacion":
            # Extraer monto con formato
            match = re.search(r'\$?[\d,]+(?:\.\d{2})?', respuesta)
            if match:
                monto = match.group(0)
                # Asegurar que tiene $
                if not monto.startswith('$'):
                    monto = '$' + monto
                return monto
            return None
        
        elif campo == "nombre_notario":
            # Limpiar nombre
            nombre = respuesta.strip()
            nombre = re.sub(r'^(Lic\.?|Licenciado|Dr\.?|Mtro\.?)\s+', '', nombre, flags=re.IGNORECASE)
            nombre = nombre.strip().upper()
            # Validar que parece un nombre (al menos 2 palabras)
            if len(nombre.split()) >= 2:
                return nombre
            return None
        
        elif campo == "fecha_documento":
            # Validar que parece una fecha
            if re.search(r'\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', respuesta, re.IGNORECASE):
                return respuesta.strip()
            # Intentar otros formatos
            if re.search(r'\d{1,2}/\d{1,2}/\d{4}', respuesta):
                return respuesta.strip()
            return None
        
        # Por defecto, devolver limpio
        return respuesta.strip() if respuesta.strip() else None
    
    def _obtener_texto_relevante(self, campo: str, texto_completo: str) -> str:
        """
        Obtiene la porción de texto más relevante para un campo.
        
        Cuando no hay secciones disponibles, esta función selecciona
        la parte del texto donde es más probable encontrar el campo.
        
        Args:
            campo: Nombre del campo
            texto_completo: Texto completo del documento
            
        Returns:
            Porción de texto optimizada para el prompt
        """
        # Campos que suelen estar al inicio
        if campo in ["numero_escritura", "numero_notaria", "nombre_notario", "fecha_documento"]:
            return texto_completo[:3500]
        
        # Campos que suelen estar en medio-final
        elif campo in ["monto_operacion", "valor_catastral"]:
            mitad = len(texto_completo) // 2
            return texto_completo[max(0, mitad-2000):min(len(texto_completo), mitad+2000)]
        
        # Por defecto, primeros 4000 caracteres
        return texto_completo[:4000]


# =============================================================================
# FUNCIONES DE CONVENIENCIA
# =============================================================================

def ejecutar_plan_e(
    ollama_service,
    campos_dudosos: List[str],
    texto_documento: str,
    secciones: Optional[SeccionesDocumento] = None
) -> Dict[str, ResultadoPlanE]:
    """
    Función de conveniencia para ejecutar Plan E.
    
    Args:
        ollama_service: Servicio de Ollama
        campos_dudosos: Campos a procesar
        texto_documento: Texto del documento
        secciones: Secciones del documento (opcional)
        
    Returns:
        Resultados de Plan E
    """
    extractor = PlanEExtractor(ollama_service)
    return extractor.ejecutar(campos_dudosos, texto_documento, secciones)