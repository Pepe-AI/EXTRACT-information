"""
utils/text_processing.py - Utilidades para procesamiento de texto OCR

Funciones principales:
- clean_ocr_text(): Limpia texto extraído por OCR
- truncate_text(): Trunca texto largo para el contexto del LLM
- format_for_prompt(): Prepara texto para el prompt
- extract_think_block(): Extrae bloque <think> de DeepSeek R1
- extract_json_from_response(): Extrae JSON de la respuesta del LLM
- process_deepseek_response(): Procesa respuesta completa de DeepSeek
"""

import re
import json
from typing import Optional, Dict, Any, Tuple
from collections import Counter


# =============================================================================
# PATRONES DE RUIDO OCR
# =============================================================================

NOISE_PATTERNS = [
    # Artefactos de interfaz web
    r"IMPRIMIRSALIR",
    r"AGREGAR OTRO INSTRUMENTO",
    r"Fecha de impresi[oó]n",
    r"https?://\S+",
    
    # Fechas y horas sueltas
    r"^\d{1,2}/\d{1,2}/\d{2,4}$",
    r"^\d{1,2}:\d{2}$",
    
    # Números de página
    r"^Page \d+ of \d+$",
    r"^\d+/\d+$",
    r"^P[aá]gina \d+$",
    r"^\d+$",
    
    # Watermarks y sellos de notarías mexicanas
    r"ESTADOS\s*UNIDOS\s*MEX",
    r"MEXICANOS?",
    r"NOTARI[AO]\s*\d*",
    r"NOTARI[AO]\s*P[UÚ]BLICA",
    r"COTEJADO",
    r"Day F4CA",
    
    # Líneas muy cortas en mayúsculas (probable ruido)
    r"^[A-Z\s\.,]{2,15}$",
]

# Patrones de encabezados (solo eliminar si están repetidos)
HEADER_PATTERNS = [
    r"Cotejado",
    r"Notario P[uú]blico",
    r"ESCRITURA P[UÚ]BLICA",
    r"LIBRO",
    r"TOMO",
    r"FOLIO",
]


# =============================================================================
# LIMPIEZA DE TEXTO OCR
# =============================================================================

def clean_ocr_text(text: str) -> str:
    """
    Limpia texto extraído por OCR de documentos notariales.
    
    PROCESO:
    ========
    1. Normalizar saltos de línea
    2. Eliminar ruido (watermarks, sellos)
    3. Eliminar encabezados repetidos
    4. Unir palabras cortadas
    5. Normalizar espacios
    
    Args:
        text: Texto crudo del OCR
        
    Returns:
        Texto limpio y normalizado
    """
    if not text:
        return ""
    
    # Normalizar saltos de línea
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    lines = text.splitlines()
    cleaned_lines = []
    
    # Contar ocurrencias para detectar encabezados repetidos
    line_counts = Counter(line.strip() for line in lines if line.strip())
    seen_headers = set()
    
    for line in lines:
        stripped_line = line.strip()
        
        if not stripped_line:
            continue
        
        # Ignorar líneas muy cortas (ruido)
        if len(stripped_line) < 5:
            continue
        
        # Verificar si es ruido
        is_noise = False
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, stripped_line, re.IGNORECASE):
                is_noise = True
                break
        
        if is_noise:
            continue
        
        # Verificar si es encabezado repetido
        is_header = False
        for pattern in HEADER_PATTERNS:
            if re.search(pattern, stripped_line, re.IGNORECASE):
                is_header = True
                break
        
        if is_header:
            if line_counts[stripped_line] > 1:
                if stripped_line in seen_headers:
                    continue
                else:
                    seen_headers.add(stripped_line)
        
        cleaned_lines.append(stripped_line)
    
    # Unir palabras cortadas
    processed_text = ""
    for line in cleaned_lines:
        if line.endswith("-"):
            processed_text += line[:-1]
        else:
            processed_text += line + " "
    
    # Normalizar espacios
    processed_text = re.sub(r'\s+', ' ', processed_text).strip()
    
    return processed_text


def truncate_text(text: str, max_tokens: int = 8000, chars_per_token: float = 4.0) -> str:
    """
    Trunca el texto para que quepa en el contexto del modelo.
    
    Preserva inicio y final del documento (donde suele estar
    la información más importante).
    
    Args:
        text: Texto a truncar
        max_tokens: Número máximo de tokens
        chars_per_token: Caracteres por token (estimación)
        
    Returns:
        Texto truncado o el original si no excede el límite
    """
    max_chars = int(max_tokens * chars_per_token)
    
    if len(text) <= max_chars:
        return text
    
    half = max_chars // 2
    
    truncated = (
        text[:half] +
        "\n\n[... CONTENIDO TRUNCADO POR LONGITUD ...]\n\n" +
        text[-half:]
    )
    
    print(f"⚠️  Texto truncado de {len(text)} a {len(truncated)} caracteres")
    
    return truncated


def format_for_prompt(text: str, max_tokens: int = 8000) -> str:
    """
    Prepara el texto OCR para el prompt.
    
    Aplica limpieza, truncado y envoltura en delimitadores.
    
    Args:
        text: Texto crudo del OCR
        max_tokens: Máximo de tokens permitidos
        
    Returns:
        Texto formateado listo para el prompt
    """
    clean = clean_ocr_text(text)
    truncated = truncate_text(clean, max_tokens)
    
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
    
    DeepSeek R1 "piensa en voz alta" en bloques <think>...</think>
    antes de dar su respuesta final.
    
    Args:
        text: Texto completo de la respuesta
        
    Returns:
        Tupla de (contenido_think, texto_sin_think)
        - contenido_think: El contenido dentro de <think>, o None
        - texto_sin_think: El texto con los tags <think> removidos
    """
    if not text:
        return None, ""
    
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
    
    El JSON puede venir en:
    1. Bloques ```json ... ```
    2. Bloques ``` ... ```
    3. JSON directo en el texto
    
    Args:
        text: Texto que contiene JSON
        
    Returns:
        Dict con el JSON parseado, o None si no se encontró
    """
    if not text:
        return None
    
    # Eliminar bloque <think>
    _, clean_text = extract_think_block(text)
    
    # Buscar JSON en bloque de código markdown
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
    
    # Buscar JSON directo (objeto o array)
    json_patterns = [
        re.compile(r'\{[\s\S]*\}'),  # Objeto
        re.compile(r'\[[\s\S]*\]')   # Array
    ]
    
    for pattern in json_patterns:
        matches = pattern.findall(clean_text)
        # Ordenar por longitud (el más largo suele ser el JSON completo)
        matches.sort(key=len, reverse=True)
        
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
    
    Combina:
    - Extracción del bloque <think>
    - Extracción del JSON
    
    Args:
        response_text: Respuesta completa del modelo
        
    Returns:
        Dict con:
        - thinking: Contenido del bloque <think> o None
        - json_data: JSON extraído o None
        - raw_response: Respuesta sin el bloque <think>
        - success: True si se extrajo JSON válido
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
    print("PRUEBA DE PROCESAMIENTO DE TEXTO")
    print("=" * 60)
    
    # Prueba de limpieza
    texto_sucio = """
COTEJADO
ESTADOS UNIDOS MEXICANOS
NOTARIA 45
1/5

ESCRITURA PÚBLICA NÚMERO 3125

En la Ciudad de México, ante mí, Licenciado Roberto Martínez,
comparecen como VENDEDOR: Juan Pérez López.

COTEJADO
2/5
"""
    
    print("\n📄 Texto original:")
    print(texto_sucio[:200] + "...")
    
    texto_limpio = clean_ocr_text(texto_sucio)
    print("\n🧹 Texto limpio:")
    print(texto_limpio)
    
    # Prueba de extracción de JSON
    print("\n" + "=" * 60)
    respuesta_con_think = """
<think>
Analizando el documento...
El número de escritura es 3125.
</think>

```json
{"numero_escritura": 3125, "notario": "Roberto Martínez"}
```
"""
    
    resultado = process_deepseek_response(respuesta_con_think)
    print(f"\n✅ JSON extraído: {resultado['json_data']}")
    print(f"💭 Tiene thinking: {resultado['thinking'] is not None}")


# =============================================================================
# EXTRACCIÓN DE DATOS POR REGEX (RESPALDO/FALLBACK)
# =============================================================================

def extraer_monto_operacion(texto: str) -> Optional[str]:
    """
    Extrae el monto de la operación del documento usando expresiones regulares.
    
    PATRONES QUE BUSCA (en orden de prioridad):
    ============================================
    1. "precio de... $X,XXX.XX" o "precio... $X,XXX.XX"
    2. "cantidad de $X,XXX.XX"
    3. "suma de $X,XXX.XX"
    4. "monto de $X,XXX.XX" o "monto total $X,XXX.XX"
    5. "valor de $X,XXX.XX"
    6. "$X,XXX.XX (CANTIDAD EN PALABRAS PESOS)"
    7. "M.N. $X,XXX.XX" o "$X,XXX.XX M.N."
    8. Cualquier monto con formato $X,XXX.XX cerca de palabras clave
    
    FORMATO DE MONTOS MEXICANOS:
    ============================
    - $1,500,000.00 (con comas para miles)
    - $1500000.00 (sin comas)
    - $1,500,000 (sin centavos)
    - 1,500,000.00 (sin símbolo $)
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        str: Monto formateado como "$X,XXX.XX" o None si no se encuentra
    """
    
    # Patrón base para montos: captura números con formato mexicano
    # Soporta: $1,500,000.00 | $1500000.00 | $1,500,000 | 1,500,000.00
    # IMPORTANTE: El orden importa - primero probar números largos sin comas
    PATRON_MONTO = r'\$?\s*(\d{4,}(?:\.\d{2})?|\d{1,3}(?:[,]\d{3})+(?:\.\d{2})?|\d{1,3}(?:\.\d{2})?)'
    
    # Lista de patrones ordenados por especificidad (más específico primero)
    patrones = [
        # 1. Precio de esta operación/venta
        (r'precio\s+(?:de\s+)?(?:esta\s+)?(?:operaci[oó]n|venta|compraventa|enajenaci[oó]n)[\s:]+(?:es\s+)?(?:la\s+cantidad\s+de\s+)?' + PATRON_MONTO, 1),
        
        # 2. "la cantidad de $X,XXX.XX"
        (r'(?:la\s+)?cantidad\s+de\s+' + PATRON_MONTO, 1),
        
        # 3. "por la suma de $X,XXX.XX"
        (r'(?:por\s+)?(?:la\s+)?suma\s+de\s+' + PATRON_MONTO, 1),
        
        # 4. "monto de/total/es $X,XXX.XX" - MEJORADO
        (r'monto\s+(?:de\s+)?(?:la\s+)?(?:operaci[oó]n\s+)?(?:es\s+)?(?:de\s+)?' + PATRON_MONTO, 1),
        
        # 5. "valor de $X,XXX.XX"
        (r'valor\s+(?:de\s+|total\s+)?' + PATRON_MONTO, 1),
        
        # 6. "$X,XXX.XX (CANTIDAD EN PALABRAS PESOS)"
        (PATRON_MONTO + r'\s*\([A-ZÁÉÍÓÚÑ\s]+(?:PESOS?|MIL|MILL[OÓ]N)\)', 0),
        
        # 7. Formato "M.N." (Moneda Nacional)
        (r'M\.?\s*N\.?\s*:?\s*' + PATRON_MONTO, 1),
        (PATRON_MONTO + r'\s*M\.?\s*N\.?', 0),
        
        # 8. "precio: $X,XXX.XX" o "precio $X,XXX.XX" (formato simple) - MEJORADO
        (r'precio\s*:?\s*' + PATRON_MONTO, 1),
        
        # 9. "importe de $X,XXX.XX"
        (r'importe\s+(?:de\s+|total\s+)?' + PATRON_MONTO, 1),
        
        # 10. "precio acordado/pactado"
        (r'precio\s+(?:acordado|pactado|convenido)\s+(?:fue\s+)?(?:de\s+)?' + PATRON_MONTO, 1),
        
        # 11. "precio fue de"
        (r'precio\s+(?:fue|es|será)\s+(?:de\s+)?(?:la\s+cantidad\s+de\s+)?' + PATRON_MONTO, 1),
        
        # 12. Cerca de palabras clave de compraventa
        (r'(?:compraventa|enajena|vende|transmite)[\s\S]{0,100}' + PATRON_MONTO, 1),
    ]
    
    mejores_montos = []
    
    for patron, grupo_idx in patrones:
        matches = re.finditer(patron, texto, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            try:
                # Obtener el grupo del monto
                grupos = match.groups()
                if grupos:
                    monto_str = grupos[0] if grupo_idx == 1 else grupos[-1]
                else:
                    continue
                
                if monto_str:
                    # Limpiar y normalizar el monto
                    monto_limpio = monto_str.replace(',', '').replace(' ', '')
                    
                    try:
                        monto_num = float(monto_limpio)
                        
                        # Filtrar montos muy pequeños (probablemente no son el precio)
                        # y muy grandes (probablemente errores de OCR)
                        if 1000 <= monto_num <= 500000000:  # Entre $1,000 y $500M
                            mejores_montos.append((monto_num, monto_str, match.start()))
                    except ValueError:
                        continue
            except (IndexError, AttributeError):
                continue
    
    if mejores_montos:
        # Ordenar por:
        # 1. Montos más "redondos" (típicos de precios) primero
        # 2. Posición en el documento (primeros párrafos suelen tener el precio)
        def score_monto(item):
            monto, _, pos = item
            # Penalizar posiciones muy tardías en el documento
            pos_score = pos / 1000
            # Bonificar montos redondos (múltiplos de 1000)
            redondez = 0 if monto % 1000 == 0 else (0.5 if monto % 100 == 0 else 1)
            return redondez + pos_score * 0.1
        
        mejores_montos.sort(key=score_monto)
        mejor_monto = mejores_montos[0][0]
        
        # Formatear el monto como moneda mexicana
        return f"${mejor_monto:,.2f}"
    
    return None


def extraer_numero_escritura(texto: str) -> Optional[int]:
    """
    Extrae el número de escritura del documento.
    
    PATRONES QUE BUSCA:
    ===================
    - "ESCRITURA NÚMERO 18,226"
    - "ESCRITURA PÚBLICA NÚMERO 3125"
    - "Escritura número 18226"
    - "ESCRITURA No. 18,226"
    - Números en palabras: "DIECIOCHO MIL DOSCIENTOS VEINTISEIS"
    
    Returns:
        int: Número de escritura, o None si no se encuentra
    """
    
    patrones = [
        # Patrón 1: ESCRITURA [PÚBLICA] [NÚMERO/No./NUM] seguido de número
        r'ESCRITURA\s+(?:P[UÚ]BLICA\s+)?(?:N[UÚ]MERO|No\.?|NUM\.?|#)\s*[:\s]*(\d{1,3}(?:[,.\s]\d{3})*)',
        
        # Patrón 2: ESCRITURA seguida directamente de número
        r'ESCRITURA\s+(\d{1,3}(?:[,.\s]\d{3})*)',
        
        # Patrón 3: N[UÚ]MERO DE ESCRITURA
        r'N[UÚ]MERO\s+DE\s+ESCRITURA[:\s]*(\d{1,3}(?:[,.\s]\d{3})*)',
        
        # Patrón 4: INSTRUMENTO NÚMERO (algunos documentos usan esto)
        r'INSTRUMENTO\s+(?:N[UÚ]MERO|No\.?)\s*[:\s]*(\d{1,3}(?:[,.\s]\d{3})*)',
    ]
    
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            numero_str = re.sub(r'[,.\s]', '', match.group(1))
            try:
                numero = int(numero_str)
                if 1 <= numero <= 999999:  # Rango válido
                    return numero
            except ValueError:
                continue
    
    return None


def extraer_fecha_documento(texto: str) -> Optional[str]:
    """
    Extrae la fecha del documento.
    
    PATRONES QUE BUSCA:
    ===================
    - "A los (22) veintidós días del mes de marzo del año 2024"
    - "A los veintidós días del mes de marzo del año dos mil veinticuatro"
    - "11 de abril de 2024"
    - "En la ciudad de... a 15 de mayo de 2024"
    
    Returns:
        str: Fecha en formato legible
    """
    
    MESES = r'(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)'
    
    # Patrones para años en palabras
    ANIO_PALABRAS = r'(?:dos\s+mil\s+(?:veinti(?:uno|dos|tres|cuatro|cinco|seis)|dieci(?:siete|ocho|nueve)|veinte)|\d{4})'
    
    patrones = [
        # Patrón legal notarial con año en números: "A los (22) veintidós días del mes de marzo del año 2024"
        rf'(?:A\s+los\s+)?(?:\(\d+\)\s+)?(\w+)\s+d[ií]as?\s+del\s+mes\s+de\s+({MESES})\s+(?:del\s+)?a[ñn]o\s+(\d{{4}})',
        
        # Patrón legal notarial con año en palabras: "del año dos mil veinticuatro"
        rf'(?:A\s+los\s+)?(?:\(\d+\)\s+)?(\w+)\s+d[ií]as?\s+del\s+mes\s+de\s+({MESES})\s+(?:del\s+)?a[ñn]o\s+({ANIO_PALABRAS})',
        
        # Patrón simple: "15 de mayo de 2024"
        rf'(\d{{1,2}})\s+de\s+({MESES})\s+(?:de\s+|del\s+)?(\d{{4}})',
        
        # Patrón con "a": "a 15 de mayo de 2024"
        rf'[aA]\s+(\d{{1,2}})\s+de\s+({MESES})\s+(?:de\s+|del\s+)?(\d{{4}})',
        
        # Patrón con año en palabras: "15 de mayo de dos mil veinticuatro"
        rf'(\d{{1,2}})\s+de\s+({MESES})\s+(?:de\s+|del\s+)?({ANIO_PALABRAS})',
    ]
    
    # Diccionario para convertir años en palabras a números
    ANIOS_PALABRAS = {
        'dos mil veintiuno': '2021',
        'dos mil veintidos': '2022',
        'dos mil veintitres': '2023',
        'dos mil veinticuatro': '2024',
        'dos mil veinticinco': '2025',
        'dos mil veintiseis': '2026',
        'dos mil diecisiete': '2017',
        'dos mil dieciocho': '2018',
        'dos mil diecinueve': '2019',
        'dos mil veinte': '2020',
    }
    
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            grupos = match.groups()
            if len(grupos) == 3:
                dia, mes, año = grupos
                
                # Convertir año en palabras a número si es necesario
                año_lower = año.lower().strip()
                if año_lower in ANIOS_PALABRAS:
                    año = ANIOS_PALABRAS[año_lower]
                
                # Si el día es en palabras, mantenerlo
                if not dia.isdigit():
                    dia = dia.capitalize()
                
                return f"{dia} de {mes.lower()} de {año}"
    
    return None


def extraer_datos_con_regex(texto: str) -> Dict[str, Any]:
    """
    Extrae datos críticos del documento usando expresiones regulares.
    
    Esta función sirve como RESPALDO cuando el LLM falla en extraer
    datos específicos. Es especialmente útil para campos numéricos
    como monto_operacion y numero_escritura.
    
    Args:
        texto: Texto completo del documento OCR
        
    Returns:
        Dict con los datos extraídos:
        - monto_operacion: str o None
        - numero_escritura: int o None
        - fecha_documento: str o None
    """
    
    return {
        'monto_operacion': extraer_monto_operacion(texto),
        'numero_escritura': extraer_numero_escritura(texto),
        'fecha_documento': extraer_fecha_documento(texto),
    }


def merge_extractions(llm_data: Dict, regex_data: Dict) -> Dict[str, Any]:
    """
    Combina los datos extraídos por el LLM con los datos de regex.
    
    ESTRATEGIA:
    ===========
    - Priorizar datos del LLM (más contexto)
    - Usar regex como FALLBACK para campos faltantes
    - Para monto_operacion: si LLM devuelve "...", usar regex
    
    Args:
        llm_data: Datos extraídos por DeepSeek
        regex_data: Datos extraídos por regex
        
    Returns:
        Dict combinado con los mejores valores
    """
    
    if not llm_data:
        llm_data = {}
    
    merged = llm_data.copy()
    
    # Campos donde regex puede servir de fallback
    campos_fallback = ['monto_operacion', 'numero_escritura', 'fecha_documento']
    
    NO_VALIDOS = [None, '', '...', 'NO SE ENCONTRÓ DATO', '$X,XXX.XX', '$...']
    
    for campo in campos_fallback:
        valor_llm = llm_data.get(campo)
        valor_regex = regex_data.get(campo)
        
        # Si el valor del LLM no es válido, usar regex
        if valor_llm in NO_VALIDOS or (isinstance(valor_llm, str) and valor_llm.startswith('$X')):
            if valor_regex is not None:
                merged[campo] = valor_regex
                print(f"   📝 {campo}: Usando valor de regex ({valor_regex})")
    
    return merged
