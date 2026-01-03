"""
utils/prompt_builder.py - Constructor de prompts para extracción de escrituras públicas

VERSIÓN ULTRA EXPLÍCITA:
========================
- Plantilla JSON exacta que DeepSeek DEBE copiar y llenar
- Lista de errores comunes con ejemplos de INCORRECTO vs CORRECTO
- Estructura más simple y directa
"""

import json
from typing import Tuple, List, Dict

from models.escritura import (
    get_campos_obligatorios,
    get_campos_no_obligatorios
)


# =============================================================================
# SYSTEM PROMPT - ULTRA EXPLÍCITO
# =============================================================================

SYSTEM_PROMPT_EXTRACCION = """Eres un extractor de datos de documentos legales mexicanos.

Tu tarea es extraer información de escrituras públicas y devolverla en formato JSON.

REGLA #1: Copia la PLANTILLA JSON que te doy y rellena los valores.
REGLA #2: Usa EXACTAMENTE los nombres de campos que te indico.
REGLA #3: Responde SOLO con el JSON, sin texto adicional.
"""


def build_extraction_prompt(
    document_content: str,
    include_examples: bool = True
) -> Tuple[str, str]:
    """
    Construye el prompt para extracción de datos.
    """
    
    system_prompt = SYSTEM_PROMPT_EXTRACCION
    user_parts = []
    
    # 1. Plantilla EXACTA a seguir
    user_parts.append(_build_plantilla_json())
    
    # 2. Errores comunes
    user_parts.append(_build_errores_comunes())
    
    # 3. Ejemplos completos
    if include_examples:
        user_parts.append(_get_examples())
    
    # 4. Documento
    user_parts.append(f"""
========================================
DOCUMENTO A ANALIZAR:
========================================

{document_content}

========================================
TU RESPUESTA:
========================================

Copia esta plantilla y rellena con los datos del documento:

""")
    
    # 5. Plantilla final para copiar
    user_parts.append(_get_plantilla_para_copiar())
    
    user_prompt = "\n".join(user_parts)
    
    return system_prompt, user_prompt


def _build_plantilla_json() -> str:
    """Plantilla EXACTA del JSON."""
    
    return """
========================================
PLANTILLA JSON QUE DEBES SEGUIR:
========================================

Tu respuesta debe ser EXACTAMENTE así (rellena los valores entre comillas):

```json
{
  "notario": "AQUÍ_VA_EL_NOMBRE_DEL_NOTARIO",
  "numero_escritura": AQUÍ_VA_EL_NÚMERO,
  "fecha_documento": "AQUÍ_VA_LA_FECHA",
  "tipo_titular": "empresa",
  "titulares": [
    {
      "nombre": "AQUÍ_VA_NOMBRE_DE_LA_EMPRESA",
      "actua_por": "derecho propio",
      "representante": {
        "nombre": "AQUÍ_VA_NOMBRE_DEL_REPRESENTANTE",
        "en_calidad": "apoderado legal",
        "escritura": "NÚMERO_DE_ESCRITURA_DEL_PODER",
        "bis": false,
        "fecha_poder": "FECHA_DEL_PODER"
      }
    }
  ],
  "adquirientes": [
    {
      "nombre": "AQUÍ_VA_NOMBRE_DEL_COMPRADOR",
      "estado_civil": "casado",
      "tipo_sociedad": "sociedad conyugal",
      "edad": 45,
      "rfc": "RFC_O_false_SI_NO_HAY",
      "curp": "CURP_O_false_SI_NO_HAY"
    }
  ],
  "monto_operacion": "$1,500,000.00",
  "tipo_moneda": "MXN",
  "valor_catastral": null
}
```

========================================
EXPLICACIÓN DE CADA CAMPO:
========================================

CAMPOS EN LA RAÍZ (obligatorios):
- "notario": Nombre del notario público
- "numero_escritura": Número de la escritura (SIN comillas, es número)
- "fecha_documento": Fecha del documento
- "tipo_titular": Usar "empresa" si hay S.A., S.A. de C.V., etc. Usar "persona" si son personas físicas
- "titulares": Lista de quienes venden/transmiten
- "adquirientes": Lista de quienes compran/adquieren
- "monto_operacion": Precio o valor de la operación
- "tipo_moneda": MXN, USD, etc.

CAMPOS EN LA RAÍZ (opcionales):
- "valor_catastral": Valor catastral (usar null si no aparece)

CAMPOS DE CADA TITULAR:
- "nombre": Nombre de la persona o razón social de la empresa
- "actua_por": Cómo actúa (ej: "derecho propio", "representación")
- "representante": Datos del representante O null si no tiene

CAMPOS DEL REPRESENTANTE:
- "nombre": Nombre del representante
- "en_calidad": Cargo (ej: "apoderado legal", "representante legal")
- "escritura": Número de escritura donde consta el poder
- "bis": true o false
- "fecha_poder": Fecha del poder

CAMPOS DE CADA ADQUIRIENTE:
- "nombre": Nombre completo
- "estado_civil": soltero, casado, divorciado, viudo
- "tipo_sociedad": Tipo de régimen matrimonial O null
- "edad": Edad en años O null
- "rfc": El RFC O false si no aparece
- "curp": El CURP O false si no aparece
"""


def _build_errores_comunes() -> str:
    """Lista de errores comunes con ejemplos."""
    
    return """
========================================
ERRORES QUE NO DEBES COMETER:
========================================

ERROR 1 - Poner tipo_titular dentro de cada titular:
❌ INCORRECTO:
{
  "titulares": [
    {
      "tipo_titular": "empresa",  <-- MAL! No va aquí
      "nombre": "..."
    }
  ]
}

✅ CORRECTO:
{
  "tipo_titular": "empresa",  <-- Va en la RAÍZ
  "titulares": [
    {
      "nombre": "..."
    }
  ]
}

----------------------------------------

ERROR 2 - Usar nombres de campos incorrectos:
❌ INCORRECTO: "nombre_completo", "nombre_titular", "razon_social"
✅ CORRECTO: "nombre"

❌ INCORRECTO: "sector", "clave", "codigo"
✅ CORRECTO: No existen estos campos, no los uses

----------------------------------------

ERROR 3 - Omitir campos obligatorios:
❌ INCORRECTO:
{
  "titulares": [...]
}

✅ CORRECTO:
{
  "notario": "...",
  "numero_escritura": 123,
  "fecha_documento": "...",
  "tipo_titular": "...",
  "titulares": [...],
  "adquirientes": [...],
  "monto_operacion": "...",
  "tipo_moneda": "..."
}

----------------------------------------

ERROR 4 - Mezclar empresas y personas:
❌ INCORRECTO:
{
  "titulares": [
    { "tipo_titular": "empresa", ... },
    { "tipo_titular": "persona", ... }
  ]
}

✅ CORRECTO: 
Si hay empresas, TODAS son empresas.
Si hay personas, TODAS son personas.
El tipo se define UNA SOLA VEZ en la raíz.
"""


def _get_examples() -> str:
    """Ejemplos completos."""
    
    ejemplo_empresa = {
        "notario": "Lic. Roberto García Mendoza",
        "numero_escritura": 3125,
        "fecha_documento": "15 de mayo de 2024",
        "tipo_titular": "empresa",
        "titulares": [
            {
                "nombre": "Inmobiliaria del Norte S.A. de C.V.",
                "actua_por": "derecho propio",
                "representante": {
                    "nombre": "Juan Carlos Pérez López",
                    "en_calidad": "apoderado legal",
                    "escritura": "1234",
                    "bis": False,
                    "fecha_poder": "10 de enero de 2020"
                }
            }
        ],
        "adquirientes": [
            {
                "nombre": "Carlos Rodríguez Martínez",
                "estado_civil": "casado",
                "tipo_sociedad": "sociedad conyugal",
                "edad": 45,
                "rfc": "ROMC790515ABC",
                "curp": "ROMC790515HDFRRL09"
            }
        ],
        "monto_operacion": "$1,500,000.00",
        "tipo_moneda": "MXN",
        "valor_catastral": None
    }
    
    ejemplo_persona = {
        "notario": "Lic. María López Hernández",
        "numero_escritura": 3126,
        "fecha_documento": "20 de mayo de 2024",
        "tipo_titular": "persona",
        "titulares": [
            {
                "nombre": "Ana García López",
                "actua_por": "derecho propio",
                "representante": None
            }
        ],
        "adquirientes": [
            {
                "nombre": "Pedro Sánchez Ruiz",
                "estado_civil": "soltero",
                "tipo_sociedad": None,
                "edad": 35,
                "rfc": False,
                "curp": False
            }
        ],
        "monto_operacion": "$500,000.00",
        "tipo_moneda": "MXN",
        "valor_catastral": "$300,000.00"
    }
    
    return f"""
========================================
EJEMPLO 1 - EMPRESA (S.A. de C.V.):
========================================

{json.dumps(ejemplo_empresa, indent=2, ensure_ascii=False)}

========================================
EJEMPLO 2 - PERSONA FÍSICA:
========================================

{json.dumps(ejemplo_persona, indent=2, ensure_ascii=False)}

OBSERVA:
- "tipo_titular" está en la RAÍZ, no dentro de titulares
- Los nombres de campos son exactos: "nombre", "actua_por", etc.
- RFC/CURP usan false cuando no se encuentran (no null, no omitir)
"""


def _get_plantilla_para_copiar() -> str:
    """Plantilla final para que DeepSeek copie."""
    
    return """{
  "notario": "",
  "numero_escritura": 0,
  "fecha_documento": "",
  "tipo_titular": "",
  "titulares": [
    {
      "nombre": "",
      "actua_por": "",
      "representante": null
    }
  ],
  "adquirientes": [
    {
      "nombre": "",
      "estado_civil": "",
      "tipo_sociedad": null,
      "edad": null,
      "rfc": false,
      "curp": false
    }
  ],
  "monto_operacion": "",
  "tipo_moneda": "",
  "valor_catastral": null
}

Rellena los campos con la información del documento.
Si hay representante, agrega el objeto con: nombre, en_calidad, escritura, bis, fecha_poder.
Responde SOLO con el JSON completo.
"""


def build_validation_prompt(extracted_json: dict, original_text: str) -> Tuple[str, str]:
    """Prompt para validar la extracción."""
    
    system = """Verifica que el JSON tenga todos los campos requeridos."""
    
    user = f"""
JSON extraído:
{json.dumps(extracted_json, indent=2, ensure_ascii=False)}

Documento original:
{original_text}

¿El JSON tiene todos los campos obligatorios?
"""
    
    return system, user


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """Estima tokens."""
    return int(len(text) / chars_per_token)


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PROMPT ULTRA EXPLÍCITO")
    print("=" * 60)
    
    sample_doc = "ESCRITURA 3125\nNotario: Lic. García\nFecha: 15/05/2024"
    
    system, user = build_extraction_prompt(sample_doc)
    
    print("\n📋 SYSTEM PROMPT:")
    print(system)
    
    print("\n📝 USER PROMPT (primeros 2000 chars):")
    print(user[:2000])
    
    print(f"\n📊 Tokens estimados: ~{estimate_tokens(system + user)}")
