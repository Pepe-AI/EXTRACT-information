"""
services/gemini_service.py - Servicio Gemini para Fallback Global

ESTRATEGIA:
===========
- Se activa DESPUÉS del Plan F (consolidación final)
- Recibe lista de campos con confianza BAJA
- Hace UNA llamada con prompt estructurado para TODOS los campos
- Retorna JSON con campos recuperados

COSTO ESTIMADO:
===============
- Gemini 2.0 Flash: $0.075 / 1M tokens entrada
- Prompt típico: ~2000 tokens (texto OCR + estructura JSON)
- 300 docs/día × 0.4 (tasa confianza BAJA) = 120 llamadas/día
- 120 × 2000 tokens × 30 días = 7.2M tokens/mes
- Costo mensual: ~$0.54 USD/mes

OPTIMIZACIONES:
===============
- Solo se activa si hay campos con BAJA confianza
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
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class GeminiFallbackService:
    """Servicio de fallback global para campos con baja confianza."""

    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai no instalado. "
                "Ejecuta: pip install google-generativeai"
            )

        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY no configurada en .env")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

    def recuperar_campos_faltantes(
        self,
        texto_ocr: str,
        campos_baja_confianza: List[str],
        datos_actuales: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recupera campos con baja confianza usando Gemini.

        Args:
            texto_ocr: Texto completo del OCR
            campos_baja_confianza: Lista de nombres de campos con BAJA confianza
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
            # Llamar a Gemini con timeout
            response = self.model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.1,  # Baja temperatura = más determinístico
                    "max_output_tokens": 2000,
                }
            )

            # Parsear respuesta JSON
            json_str = response.text.strip()

            # Limpiar markdown si existe
            if json_str.startswith('```'):
                json_str = re.sub(r'```(?:json)?\n?', '', json_str).strip()

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
        """Construye prompt estructurado para Gemini."""

        # Mapeo de campos a descripciones
        DESCRIPCIONES_CAMPOS = {
            "numero_escritura": "Número de la escritura pública (4-7 dígitos)",
            "numero_notaria": "Número de la notaría (1-3 dígitos)",
            "nombre_notario": "Nombre completo del notario público",
            "fecha_documento": "Fecha del documento en formato legible",
            "monto_operacion": "Monto de la operación en formato $X,XXX.XX",
            "municipio": "Municipio donde se encuentra la notaría",
            "titulares": "Lista de titulares/vendedores con nombre, tipo, actua_por, representante",
            "adquirientes": "Lista de adquirientes/compradores con nombre, tipo, actua_por, estado_civil, representante",
        }

        # Construir lista de campos solicitados
        lista_campos = "\n".join([
            f"- {campo}: {DESCRIPCIONES_CAMPOS.get(campo, 'Extraer del documento')}"
            for campo in campos_baja_confianza
        ])

        # Construir estructura JSON esperada
        estructura_json = {}
        for campo in campos_baja_confianza:
            if campo in ["titulares", "adquirientes"]:
                estructura_json[campo] = [
                    {
                        "nombre": "...",
                        "tipo": "empresa o persona",
                        "actua_por": "...",
                        "representante": {
                            "nombre": "...",
                            "en_calidad": "...",
                            "escritura": "...",
                            "bis": False,
                            "fecha_poder": "..."
                        } if campo == "adquirientes" else None
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

TEXTO DEL DOCUMENTO:
====================
{texto_ocr[:3000]}

INSTRUCCIONES:
==============
1. Busca CUIDADOSAMENTE cada campo en el texto original
2. Si encuentras el campo, extráelo con PRECISIÓN
3. Si NO encuentras el campo, deja el valor como null
4. NO inventes datos que no estén en el texto
5. Respeta los formatos especificados

RESPONDE SOLO CON JSON EN ESTE FORMATO:
========================================
{json.dumps(estructura_json, indent=2, ensure_ascii=False)}

JSON:"""

        return prompt


# Singleton para reutilizar conexión
_gemini_service = None

def get_gemini_fallback_service() -> GeminiFallbackService:
    """Obtiene instancia singleton de GeminiFallbackService."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiFallbackService()
    return _gemini_service
