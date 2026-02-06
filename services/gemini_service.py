"""
services/gemini_service.py - Servicio Gemini para Fallback Global

ESTRATEGIA:
===========
- Se activa DESPUÉS del Plan F (consolidación final)
- Recibe lista de campos con confianza MEDIA o BAJA
- Hace UNA llamada con prompt estructurado para TODOS los campos
- Retorna JSON con campos recuperados

COSTO ESTIMADO:
===============
- Gemini 2.0 Flash: $0.075 / 1M tokens entrada
- Prompt típico: ~2000 tokens (texto OCR + estructura JSON)
- 300 docs/día × 0.6 (tasa confianza MEDIA/BAJA) = 180 llamadas/día
- 180 × 2000 tokens × 30 días = 10.8M tokens/mes
- Costo mensual: ~$0.81 USD/mes

OPTIMIZACIONES:
===============
- Solo se activa si hay campos con MEDIA o BAJA confianza
- Prompt único (no múltiples llamadas)
- Timeout de 15 segundos
- Cache de respuestas (futuro)
"""

import os
import json
import re
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GeminiFallbackService:
    """Servicio de fallback global para campos con baja confianza."""

    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-genai no instalado. "
                "Ejecuta: pip install google-genai"
            )

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no configurada en .env")

        # Inicializar cliente con nueva API
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = 'gemini-3-flash-preview'  # ← Cambiar aquí para otro modelo

    def recuperar_campos_faltantes(
        self,
        texto_ocr: str,
        campos_baja_confianza: List[str],
        datos_actuales: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recupera campos con media o baja confianza usando Gemini.

        Args:
            texto_ocr: Texto completo del OCR
            campos_baja_confianza: Lista de nombres de campos con MEDIA o BAJA confianza
            datos_actuales: Datos ya extraídos (para contexto)

        Returns:
            Dict con campos recuperados:
            {
                "numero_escritura": 2307,
                "nombre_notario": "RIGOBERTO OCHOA TORRES",
                ...
            }
        """
        if not campos_baja_confianza:
            return {}

        # Construir prompt estructurado
        prompt = self._construir_prompt(
            texto_ocr,
            campos_baja_confianza,
            datos_actuales
        )

        try:
            # Llamar a Gemini con nueva API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "temperature": 0.1,  # Baja temperatura = más determinístico
                    "max_output_tokens": 8000,  # Incrementado para JSON complejos
                }
            )

            # Parsear respuesta JSON
            json_str = response.text.strip()

            # Limpiar markdown si existe (tanto al inicio como al final)
            if '```' in json_str:
                # Remover bloques markdown completos
                json_str = re.sub(r'```(?:json)?\s*', '', json_str)
                json_str = json_str.strip()

            # Si el JSON está incompleto, intentar repararlo
            if not json_str.endswith('}') and not json_str.endswith(']'):
                print(f"⚠️ JSON parece incompleto, intentando reparar...")
                # Agregar cierre de objetos/arrays faltantes
                open_braces = json_str.count('{') - json_str.count('}')
                open_brackets = json_str.count('[') - json_str.count(']')

                for _ in range(open_brackets):
                    json_str += ']'
                for _ in range(open_braces):
                    json_str += '}'

            # Parsear JSON
            campos_recuperados = json.loads(json_str)

            # Validar estructura
            if not isinstance(campos_recuperados, dict):
                print(f"⚠️ Gemini devolvió formato inválido: {type(campos_recuperados)}")
                return {}

            # Filtrar solo campos solicitados
            resultado = {}
            for campo in campos_baja_confianza:
                if campo in campos_recuperados:
                    valor = campos_recuperados[campo]
                    # Validar que no sea null o vacío
                    if valor is not None and valor != "" and valor != []:
                        resultado[campo] = valor

            return resultado

        except json.JSONDecodeError as e:
            print(f"⚠️ Error parseando JSON de Gemini: {e}")

            # Intentar extraer al menos lo que se pueda del JSON parcial
            # Buscar el último objeto/campo válido antes del error
            try:
                # Truncar en el punto del error y cerrar el JSON
                error_pos = e.pos if hasattr(e, 'pos') else len(json_str)
                json_parcial = json_str[:error_pos]

                # Encontrar el último objeto completo
                ultimo_cierre = max(
                    json_parcial.rfind('}'),
                    json_parcial.rfind(']'),
                    0
                )

                if ultimo_cierre > 0:
                    json_truncado = json_parcial[:ultimo_cierre + 1]
                    # Cerrar estructuras abiertas
                    open_braces = json_truncado.count('{') - json_truncado.count('}')
                    open_brackets = json_truncado.count('[') - json_truncado.count(']')

                    for _ in range(open_brackets):
                        json_truncado += ']'
                    for _ in range(open_braces):
                        json_truncado += '}'

                    print(f"   🔧 Intentando parsear JSON parcial...")
                    campos_recuperados = json.loads(json_truncado)

                    # Filtrar campos válidos
                    resultado = {}
                    for campo in campos_baja_confianza:
                        if campo in campos_recuperados and campos_recuperados[campo]:
                            resultado[campo] = campos_recuperados[campo]

                    if resultado:
                        print(f"   ✅ Recuperados {len(resultado)} campos del JSON parcial")
                        return resultado
            except:
                pass

            print(f"   Respuesta: {response.text[:200]}...")
            return {}
        except Exception as e:
            print(f"⚠️ Error en Gemini Fallback: {e}")
            return {}

    def _construir_prompt(
        self,
        texto_ocr: str,
        campos_baja_confianza: List[str],
        datos_actuales: Dict[str, Any]
    ) -> str:
        """Construye prompt estructurado para Gemini con búsqueda dirigida por sección."""

        # Mapeo MEJORADO de campos a descripciones con ubicación de sección
        DESCRIPCIONES_CAMPOS = {
            "numero_escritura": "Número de la escritura pública (4-7 dígitos) - SECCIÓN: Introducción/Encabezado",
            "numero_notaria": "Número de la notaría (1-3 dígitos) - SECCIÓN: Introducción",
            "nombre_notario": "Nombre completo del notario público - SECCIÓN: Introducción",
            "fecha_documento": "Fecha del documento - SECCIÓN: Introducción",
            "monto_operacion": "Monto de la operación ($X,XXX.XX) - SECCIÓN: Cláusula Segunda",
            "municipio": "Municipio donde se encuentra la notaría - SECCIÓN: Introducción",
            "titulares": "Lista de titulares/vendedores - SECCIÓN: Cláusula Primera (Comparecencia)",
            "adquirientes": "Lista de adquirientes/compradores con RFC/CURP/edad - SECCIONES: Cláusula Primera (nombres) + Generales/FE NOTARIAL (RFC/CURP/edad AL FINAL)",
        }

        # Construir lista de campos solicitados
        lista_campos = "\n".join([
            f"- {campo}: {DESCRIPCIONES_CAMPOS.get(campo, 'Extraer del documento')}"
            for campo in campos_baja_confianza
        ])

        # Construir estructura JSON esperada
        estructura_json = {}
        for campo in campos_baja_confianza:
            if campo == "titulares":
                estructura_json[campo] = [
                    {
                        "nombre": "...",
                        "tipo": "empresa o persona",
                        "actua_por": "...",
                        "representante": {
                            "nombre": "...",
                            "en_calidad": "...",
                            "escritura": "...",
                            "fecha_poder": "..."
                        }
                    }
                ]
            elif campo == "adquirientes":
                estructura_json[campo] = [
                    {
                        "nombre": "...",
                        "tipo": "empresa o persona",
                        "actua_por": "...",
                        "estado_civil": "... o false",
                        "rfc": "... o false",
                        "curp": "... o false",
                        "edad": "X o false",
                        "tipo_sociedad": "... o false",
                        "representante": {
                            "nombre": "...",
                            "en_calidad": "...",
                            "escritura": "...",
                            "fecha_poder": "..."
                        }
                    }
                ]
            else:
                estructura_json[campo] = "..."

        prompt = f"""Eres un experto en extracción de datos de escrituras públicas notariales mexicanas.

TAREA:
======
Del siguiente texto OCR de una escritura pública, extrae ÚNICAMENTE los siguientes campos que fallaron en la extracción automática:

{lista_campos}

CONTEXTO (datos ya extraídos):
==============================
{json.dumps(datos_actuales, indent=2, ensure_ascii=False)[:500]}...

═══════════════════════════════════════════════════════════════
⚠️ UBICACIÓN DE CAMPOS POR SECCIÓN (CRÍTICO)
═══════════════════════════════════════════════════════════════

ESTRUCTURA DEL DOCUMENTO:
1. INTRODUCCIÓN/ENCABEZADO (primeras páginas)
   → numero_escritura, fecha_documento, numero_notaria, municipio, nombre_notario

2. CLÁUSULA PRIMERA (Comparecencia)
   → titulares.nombre, adquirientes.nombre, representantes

3. CLÁUSULA SEGUNDA (Operación)
   → monto_operacion, valor_catastral

4. PERSONALIDAD (Poderes notariales)
   → representante.escritura, representante.fecha_poder

5. GENERALES / FE NOTARIAL (AL FINAL del documento)
   → RFC, CURP, edad, estado_civil, tipo_sociedad

⚠️ IMPORTANTE:
- Los RFC, CURP y edad están SOLO en la sección FINAL (FE NOTARIAL, COMPARECIENTES, DOY FE)
- NO están al inicio del documento
- El numero_escritura del DOCUMENTO está en Introducción
- El numero_escritura del PODER está en Personalidad (son diferentes)

TEXTO DEL DOCUMENTO:
====================
{texto_ocr}

INSTRUCCIONES:
==============
1. Busca CUIDADOSAMENTE cada campo en el texto original
2. Si encuentras el campo, extráelo con PRECISIÓN
3. Si NO encuentras el campo, deja el valor como null o false (según corresponda)
4. NO inventes datos que no estén en el texto
5. Para RFC/CURP/edad: busca en la sección FE NOTARIAL al FINAL del documento
5. Respeta los formatos especificados

RESPONDE SOLO CON JSON EN ESTE FORMATO:
========================================
{json.dumps(estructura_json, indent=2, ensure_ascii=False)}

JSON:"""

        return prompt

    def generate_content(self, prompt: str) -> str:
        """
        Método genérico para llamar a Gemini (usado por extracción híbrida).

        Args:
            prompt: Texto del prompt a enviar

        Returns:
            str: Respuesta de Gemini en texto plano
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "temperature": 0.1,
                    "max_output_tokens": 2000,
                }
            )
            return response.text.strip()
        except Exception as e:
            print(f"⚠️ Error llamando a Gemini: {e}")
            return ""


# Singleton para reutilizar conexión
_gemini_service = None

def get_gemini_fallback_service() -> GeminiFallbackService:
    """Obtiene instancia singleton de GeminiFallbackService."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiFallbackService()
    return _gemini_service
