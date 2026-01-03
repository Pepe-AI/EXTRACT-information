"""
utils/text_processing.py - Utilidades para procesamiento de texto OCR

EXPLICACIÓN:
============
Este módulo contiene funciones para:

1. LIMPIAR TEXTO OCR:
   - Eliminar ruido de escaneo (watermarks, sellos, encabezados repetidos)
   - Normalizar espacios y caracteres especiales
   - Unir palabras cortadas por guiones

2. PROCESAR RESPUESTAS DE DEEPSEEK R1:
   - Extraer bloques <think> (razonamiento del modelo)
   - Extraer y parsear JSON de la respuesta

CONTEXTO:
=========
El OCR de documentos notariales mexicanos genera mucho ruido:
- Sellos de "COTEJADO"
- Watermarks de la notaría
- Encabezados/pies de página repetidos
- Números de página
- Artefactos de escaneo

Este módulo limpia ese ruido para que el LLM pueda extraer
la información relevante de forma más precisa.
"""

import re
import json
from typing import Optional, Dict, Any, Tuple, List
from collections import Counter


# =============================================================================
# LIMPIEZA DE TEXTO OCR
# =============================================================================

# Patrones de RUIDO que SIEMPRE se eliminan
# (watermarks, sellos, artefactos de interfaz web, etc.)
NOISE_PATTERNS = [
    # === Artefactos de interfaz web ===
    r"IMPRIMIRSALIR",
    r"AGREGAR OTRO INSTRUMENTO",
    r"Fecha de impresi[oó]n",
    r"https?://\S+",                    # URLs
    
    # === Fechas y horas sueltas ===
    r"^\d{1,2}/\d{1,2}/\d{2,4}$",       # 6/10/23
    r"^\d{1,2}:\d{2}$",                 # 10:56
    
    # === Números de página ===
    r"^Page \d+ of \d+$",
    r"^\d+/\d+$",                       # 1/1
    r"^P[aá]gina \d+$",
    r"^\d+$",                           # Solo números
    
    # === Watermarks y sellos de notarías mexicanas ===
    r"ESTADOS\s*UNIDOS\s*MEX",
    r"MEXICANOS?",
    r"NOTARI[AO]\s*\d*",
    r"NOTARI[AO]\s*P[UÚ]BLICA",
    r"TECUALA",
    r"NAYARIT",
    r"AGUAYO",
    r"CANALES",
    r"GLADI",
    r"HUDIT",
    r"NOSSO?S?A?",
    r"PARIA",
    r"GUAYO",
    r"NIDOS",
    r"MEXI?C?",
    r"ARIT",
    r"ANOSS",
    r"ESTADI?O?S?",
    r"UNIDOS",
    r"CUALA",
    r"CANAL",
    r"Day F4CA",
    r"TITULAR",
    r"NOTA \d+",
    r"COTEJADO",
    
    # === Líneas muy cortas en mayúsculas (probable ruido) ===
    r"^[A-Z\s\.,]{2,20}$",
    
    # === Fragmentos de sellos ===
    r"^LAR$",
    r"^NOFARIA$",
]

# Patrones de ENCABEZADOS que solo se eliminan si están REPETIDOS
HEADER_PATTERNS = [
    r"Cotejado",
    r"Notario P[uú]blico",
    r"Lic\.",
    r"ESCRITURA P[UÚ]BLICA",
    r"LIBRO",
    r"TOMO",
    r"FOLIO",
    r"VOLUMEN",
]


def clean_ocr_text(text: str) -> str:
    """
    Limpia texto extraído por OCR de documentos notariales.
    
    PROCESO DE LIMPIEZA:
    ====================
    1. Normalizar saltos de línea
    2. Contar líneas repetidas (para detectar encabezados)
    3. Eliminar ruido (watermarks, sellos, artefactos)
    4. Eliminar encabezados repetidos
    5. Unir palabras cortadas por guiones
    6. Normalizar espacios
    7. Eliminar fragmentos aislados
    
    ¿Por qué este proceso?
    ======================
    Los documentos notariales escaneados tienen mucho ruido visual:
    - Sellos de "COTEJADO" en cada página
    - Watermarks de la notaría
    - Encabezados repetidos (nombre del notario, número de escritura)
    - Números de página
    
    Este ruido confunde al LLM y reduce la calidad de extracción.
    
    Args:
        text: Texto crudo del OCR
        
    Returns:
        Texto limpio y normalizado
        
    Ejemplo:
        >>> dirty = "COTEJADO\\nESCRITURA 3125\\n1/5\\nJuan Pérez vende..."
        >>> clean = clean_ocr_text(dirty)
        >>> print(clean)  # "ESCRITURA 3125 Juan Pérez vende..."
    """
    
    # Paso 1: Normalizar saltos de línea (Windows → Unix)
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    lines = text.splitlines()
    cleaned_lines = []
    
    # Paso 2: Contar ocurrencias de cada línea para detectar encabezados repetidos
    # Counter es un dict especializado que cuenta elementos
    line_counts = Counter(line.strip() for line in lines if line.strip())
    
    # Set para rastrear encabezados ya vistos
    seen_headers = set()
    
    # Paso 3: Procesar cada línea
    for line in lines:
        stripped_line = line.strip()
        
        # Ignorar líneas vacías
        if not stripped_line:
            continue
        
        # Ignorar líneas muy cortas (probable ruido de OCR)
        if len(stripped_line) < 5:
            continue
        
        # Verificar si es ruido (siempre eliminar)
        is_noise = False
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, stripped_line, re.IGNORECASE):
                is_noise = True
                break
        
        if is_noise:
            continue
        
        # Verificar si es encabezado (eliminar solo si está repetido)
        is_header = False
        for pattern in HEADER_PATTERNS:
            if re.search(pattern, stripped_line, re.IGNORECASE):
                is_header = True
                break
        
        if is_header:
            # Si aparece más de una vez, es encabezado repetido
            if line_counts[stripped_line] > 1:
                # Solo mantener la primera aparición
                if stripped_line in seen_headers:
                    continue
                else:
                    seen_headers.add(stripped_line)
        
        cleaned_lines.append(stripped_line)
    
    # Paso 4: Unir palabras cortadas por guiones al final de línea
    # Ejemplo: "compra-" + "venta" → "compraventa"
    processed_text = ""
    for i, line in enumerate(cleaned_lines):
        if line.endswith("-"):
            # Quitar guión y NO agregar espacio
            processed_text += line[:-1]
        else:
            processed_text += line + " "
    
    # Paso 5: Normalizar espacios múltiples
    processed_text = re.sub(r'\s+', ' ', processed_text).strip()
    
    # Paso 6: Eliminar fragmentos aislados
    # Letras sueltas en mayúsculas (1-3 caracteres)
    processed_text = re.sub(r'\s[A-Z]{1,3}\s', ' ', processed_text)
    
    # Signos de puntuación aislados
    processed_text = re.sub(r'\s[¡!¿?]+\s', ' ', processed_text)
    
    # Normalizar espacios de nuevo
    processed_text = re.sub(r'\s+', ' ', processed_text).strip()
    
    return processed_text


def truncate_text(
    text: str,
    max_tokens: int = 8000,
    chars_per_token: float = 4.0
) -> str:
    """
    Trunca el texto para que quepa en el contexto del modelo.
    
    ¿Por qué truncar?
    =================
    Los modelos LLM tienen un límite de tokens que pueden procesar.
    Para documentos muy largos, es mejor truncar inteligentemente
    que dejar que el modelo falle o ignore contenido.
    
    ESTRATEGIA:
    ===========
    Si el texto excede el límite, preservamos:
    - El inicio (datos generales de la escritura)
    - El final (firmas, valores, datos importantes)
    
    Esto funciona bien para escrituras porque la información
    clave suele estar al inicio y al final.
    
    Args:
        text: Texto a truncar
        max_tokens: Máximo de tokens permitidos
        chars_per_token: Estimación de caracteres por token
                        (4 es buena aproximación para español)
        
    Returns:
        Texto truncado si excede el límite
    """
    
    max_chars = int(max_tokens * chars_per_token)
    
    if len(text) <= max_chars:
        return text
    
    # Dividir espacio entre inicio y fin
    half = max_chars // 2
    
    # Truncar preservando inicio y fin
    truncated = (
        text[:half] +
        "\n\n[... CONTENIDO TRUNCADO POR LONGITUD ...]\n\n" +
        text[-half:]
    )
    
    print(f"⚠️  Texto truncado de {len(text)} a {len(truncated)} caracteres")
    
    return truncated


def format_for_prompt(text: str, max_tokens: int = 8000) -> str:
    """
    Prepara el texto OCR para incluirlo en el prompt de DeepSeek.
    
    Aplica:
    1. Limpieza de ruido OCR
    2. Truncado si es necesario
    3. Envoltura en delimitadores claros
    
    Los delimitadores <documento>...</documento> ayudan al modelo
    a identificar claramente dónde está el contenido a procesar.
    
    Args:
        text: Texto crudo del OCR
        max_tokens: Límite de tokens
        
    Returns:
        Texto listo para incluir en el prompt
    """
    
    # Limpiar
    clean = clean_ocr_text(text)
    
    # Truncar si es necesario
    truncated = truncate_text(clean, max_tokens)
    
    # Envolver en delimitadores
    formatted = f"""<documento>
{truncated}
</documento>"""
    
    return formatted


# =============================================================================
# PROCESAMIENTO DE RESPUESTAS DE DEEPSEEK R1
# =============================================================================

def extract_think_block(text: str) -> Tuple[Optional[str], str]:
    """
    Extrae el bloque <think> de una respuesta de DeepSeek R1.
    
    ¿Qué es el bloque <think>?
    ==========================
    DeepSeek R1 usa "Chain-of-Thought" (CoT): antes de responder,
    "piensa en voz alta" dentro de bloques <think>...</think>.
    
    Ejemplo:
        <think>
        El documento menciona a Juan Pérez como vendedor.
        El precio es $500,000 MXN.
        Debo estructurar esto en JSON.
        </think>
        
        {"vendedor": "Juan Pérez", "precio": 500000}
    
    Este razonamiento es útil para:
    - Debug: entender por qué el modelo llegó a cierta conclusión
    - Mejora: ver qué información usa o ignora
    
    REGEX EXPLICADO:
    ================
    r'<think>(.*?)</think>'
    
    - <think>   → Texto literal "<think>"
    - (.*?)     → Captura cualquier carácter, no-codicioso
                  (captura lo mínimo necesario)
    - </think>  → Texto literal "</think>"
    - re.DOTALL → El punto (.) también coincide con saltos de línea
    
    Args:
        text: Respuesta de DeepSeek R1
        
    Returns:
        Tupla (contenido_think, texto_sin_think)
    """
    
    think_pattern = re.compile(
        r'<think>(.*?)</think>',
        re.DOTALL | re.IGNORECASE
    )
    
    match = think_pattern.search(text)
    
    if match:
        think_content = match.group(1).strip()
        clean_text = think_pattern.sub('', text).strip()
        return think_content, clean_text
    
    return None, text.strip()


def extract_json_from_response(text: str) -> Optional[Dict[str, Any]]:
    """
    Extrae y parsea JSON de una respuesta de texto.
    
    El JSON puede venir en varios formatos:
    1. Envuelto en ```json ... ```
    2. Envuelto en ``` ... ```
    3. JSON directo sin envolver
    4. Mezclado con texto antes/después
    
    ESTRATEGIA:
    ===========
    1. Eliminar bloque <think>
    2. Buscar JSON en bloques de código (```)
    3. Si no hay, buscar JSON directo con regex
    4. Parsear y devolver
    
    Args:
        text: Texto que contiene JSON
        
    Returns:
        Dict parseado, o None si no se encontró
        
    Ejemplo:
        >>> text = '<think>...</think>```json{"ok": true}```'
        >>> result = extract_json_from_response(text)
        >>> print(result)  # {'ok': True}
    """
    
    # Eliminar bloque <think>
    _, clean_text = extract_think_block(text)
    
    # Buscar JSON en bloque de código
    code_block_pattern = re.compile(
        r'```(?:json)?\s*([\s\S]*?)```',
        re.IGNORECASE
    )
    
    code_match = code_block_pattern.search(clean_text)
    
    if code_match:
        json_str = code_match.group(1).strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"⚠️  Error parseando JSON del bloque de código: {e}")
    
    # Buscar JSON directo
    json_patterns = [
        re.compile(r'\{[\s\S]*\}'),  # Objeto: { ... }
        re.compile(r'\[[\s\S]*\]')   # Array: [ ... ]
    ]
    
    for pattern in json_patterns:
        matches = pattern.findall(clean_text)
        matches.sort(key=len, reverse=True)  # Intentar el más largo primero
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
    
    print("⚠️  No se encontró JSON válido en la respuesta")
    return None


def process_deepseek_response(response_text: str) -> Dict[str, Any]:
    """
    Procesa una respuesta completa de DeepSeek R1.
    
    Función de conveniencia que combina:
    1. Extracción del bloque <think>
    2. Extracción del JSON
    3. Metadatos del procesamiento
    
    Args:
        response_text: Respuesta cruda de DeepSeek
        
    Returns:
        Dict con:
        - 'thinking': Contenido del <think> (o None)
        - 'json_data': JSON parseado (o None)
        - 'raw_response': Respuesta sin <think>
        - 'success': Si se extrajo JSON exitosamente
    """
    
    thinking, clean_response = extract_think_block(response_text)
    json_data = extract_json_from_response(clean_response)
    
    return {
        'thinking': thinking,
        'json_data': json_data,
        'raw_response': clean_response,
        'success': json_data is not None
    }


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DE LIMPIEZA DE TEXTO OCR")
    print("=" * 60)
    
    # Simular texto OCR con ruido
    dirty_text = """
COTEJADO
ESTADOS UNIDOS MEXICANOS
NOTARIA 45
1/5

ESCRITURA PÚBLICA NÚMERO 3125

En la Ciudad de México, siendo las diez horas del día quince de mayo
del año dos mil veinticuatro, ante mí, Licenciado Roberto Martínez
González, Notario Público número cuarenta y cinco, comparecen:

COTEJADO

Como VENDEDOR: JUAN CARLOS PÉREZ LÓPEZ, mexicano, mayor de edad,
con domicilio en Avenida Reforma número 123.

COTEJADO

Como COMPRADOR: MARÍA GARCÍA HERNÁNDEZ, mexicana, casada, con
RFC: GAHM900515XYZ.

2/5
NOTARIA 45
Day F4CA
"""
    
    print("\n📝 Texto sucio (OCR):")
    print("-" * 40)
    print(dirty_text)
    
    print("\n🧹 Texto limpio:")
    print("-" * 40)
    clean = clean_ocr_text(dirty_text)
    print(clean)
    
    print("\n" + "=" * 60)
    print("PRUEBA DE EXTRACCIÓN DE JSON")
    print("=" * 60)
    
    test_response = """
<think>
El documento es una escritura de compraventa.
El vendedor es Juan Carlos Pérez López.
El comprador es María García Hernández.
</think>

```json
{
    "numero_escritura": 3125,
    "tipo_operacion": "Compraventa",
    "vendedores": [{"nombre_completo": "Juan Carlos Pérez López"}],
    "compradores": [{"nombre_completo": "María García Hernández", "rfc": "GAHM900515XYZ"}]
}
```
"""
    
    result = process_deepseek_response(test_response)
    
    print("\n💭 Pensamiento extraído:")
    print(result['thinking'][:100] + "..." if result['thinking'] else "No encontrado")
    
    print("\n📊 JSON extraído:")
    print(json.dumps(result['json_data'], indent=2, ensure_ascii=False))
    
    print(f"\n✅ Extracción exitosa: {result['success']}")
