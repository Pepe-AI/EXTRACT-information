"""
utils/text_processing.py - Utilidades para procesamiento de texto OCR

VERSIÓN: 2.0 - Con correcciones Plan Z

FIXES APLICADOS:
================
- FIX #1: extraer_numero_escritura() - Busca primero en encabezado, excluye sellos de catastro
- FIX #2: extraer_estado() - Busca en contexto específico, no solo primera mención

Funciones principales:
- clean_ocr_text(): Limpia texto extraído por OCR
- truncate_text(): Trunca texto largo para el contexto del LLM
- format_for_prompt(): Prepara texto para el prompt
- extract_think_block(): Extrae bloque <think> de DeepSeek R1
- extract_json_from_response(): Extrae JSON de la respuesta del LLM
- process_deepseek_response(): Procesa respuesta completa de DeepSeek
- extraer_todos_regex(): Extrae todos los campos usando regex (Plan A)
"""

import re
import json
from typing import Optional, Dict, Any, Tuple, List
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


def estimate_tokens(text: str, chars_per_token: float = 4.0) -> int:
    """
    Estima el número de tokens en un texto.
    
    Args:
        text: Texto a estimar
        chars_per_token: Caracteres por token (default: 4.0)
        
    Returns:
        Número estimado de tokens
    """
    return int(len(text) / chars_per_token)


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
    PATRON_MONTO = r'\$?\s*(\d{4,}(?:\.\d{2})?|\d{1,3}(?:[,]\d{3})+(?:\.\d{2})?|\d{1,3}(?:\.\d{2})?)'
    
    # Lista de patrones ordenados por especificidad (más específico primero)
    patrones = [
        # 1. Precio de esta operación/venta
        (r'precio\s+(?:de\s+)?(?:esta\s+)?(?:operaci[oó]n|venta|compraventa|enajenaci[oó]n)[\s:]+(?:es\s+)?(?:la\s+cantidad\s+de\s+)?' + PATRON_MONTO, 1),
        
        # 2. "la cantidad de $X,XXX.XX"
        (r'(?:la\s+)?cantidad\s+de\s+' + PATRON_MONTO, 1),
        
        # 3. "por la suma de $X,XXX.XX"
        (r'(?:por\s+)?(?:la\s+)?suma\s+de\s+' + PATRON_MONTO, 1),
        
        # 4. "monto de/total/es $X,XXX.XX"
        (r'monto\s+(?:de\s+)?(?:la\s+)?(?:operaci[oó]n\s+)?(?:es\s+)?(?:de\s+)?' + PATRON_MONTO, 1),
        
        # 5. "valor de $X,XXX.XX"
        (r'valor\s+(?:de\s+|total\s+)?' + PATRON_MONTO, 1),
        
        # 6. "$X,XXX.XX (CANTIDAD EN PALABRAS PESOS)"
        (PATRON_MONTO + r'\s*\([A-ZÁÉÍÓÚÑ\s]+(?:PESOS?|MIL|MILL[OÓ]N)\)', 0),
        
        # 7. Formato "M.N." (Moneda Nacional)
        (r'M\.?\s*N\.?\s*:?\s*' + PATRON_MONTO, 1),
        (PATRON_MONTO + r'\s*M\.?\s*N\.?', 0),
        
        # 8. "precio: $X,XXX.XX" o "precio $X,XXX.XX" (formato simple)
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
                        
                        # Filtrar montos muy pequeños y muy grandes
                        if 1000 <= monto_num <= 500000000:
                            mejores_montos.append((monto_num, monto_str, match.start()))
                    except ValueError:
                        continue
            except (IndexError, AttributeError):
                continue
    
    if mejores_montos:
        # Ordenar por montos más "redondos" y posición en documento
        def score_monto(item):
            monto, _, pos = item
            pos_score = pos / 1000
            redondez = 0 if monto % 1000 == 0 else (0.5 if monto % 100 == 0 else 1)
            return redondez + pos_score * 0.1
        
        mejores_montos.sort(key=score_monto)
        mejor_monto = mejores_montos[0][0]
        
        return f"${mejor_monto:,.2f}"
    
    return None


# =============================================================================
# FIX #1: extraer_numero_escritura CORREGIDO
# =============================================================================

def extraer_numero_escritura(texto: str) -> Optional[int]:
    """
    Extrae el número de escritura del documento.
    
    FIX #1 APLICADO:
    ================
    - Busca PRIMERO en el encabezado (primeros 1000 chars)
    - Incluye patrón para "Instrumento Público Número"
    - Excluye sellos de catastro ("ESCRITURA NO X SE TRAMITÓ")
    
    PROBLEMA ORIGINAL:
    ==================
    El documento tenía:
      - INICIO: "Instrumento Público Número 2307" ← CORRECTO
      - FINAL:  "ESCRITURA NO 2,397" ← Sello de catastro (INCORRECTO)
    
    La función original encontraba 2397 porque no priorizaba el encabezado
    y no excluía contextos de sellos de catastro.
    
    PATRONES QUE BUSCA (en orden de prioridad):
    ===========================================
    1. "Instrumento Público Número 2307" ← MÁS CONFIABLE
    2. "ESCRITURA PÚBLICA NÚMERO 18,226"
    3. "ESCRITURA NÚMERO 3125"
    4. "NÚMERO DE ESCRITURA: 12345"
    5. "INSTRUMENTO NÚMERO 12345"
    
    PATRONES QUE EXCLUYE:
    =====================
    - "ESCRITURA NO 2,397 SE TRAMITÓ" (sello de catastro)
    - "PRESENTE ESCRITURA NO X CONFORME" (referencia)
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        int: Número de escritura, o None si no se encuentra
        
    Ejemplo:
        >>> texto = "Instrumento Público Número 2307 dos mil trescientos siete"
        >>> extraer_numero_escritura(texto)
        2307
    """
    
    # =========================================================================
    # Patrón base para números de escritura
    # =========================================================================
    # IMPORTANTE: El orden de las alternativas importa en regex.
    # Primero intentamos capturar números de 4-6 dígitos SIN separador,
    # luego números CON separadores de miles.
    # Si lo hacemos al revés, \d{1,3} capturaría solo los primeros 3 dígitos.
    
    PATRON_NUMERO = r'(\d{4,6}|\d{1,3}(?:[,]\d{3})+)'
    
    # =========================================================================
    # Patrones de búsqueda ordenados por especificidad
    # =========================================================================
    
    patrones = [
        # PATRÓN 1: "Instrumento Público Número X" (MÁS ESPECÍFICO)
        # Este formato aparece al inicio de escrituras notariales mexicanas.
        (
            "instrumento_publico",
            r'INSTRUMENTO\s+P[UÚ]BLICO\s+N[UÚ]MERO\s*' + PATRON_NUMERO,
            1  # Prioridad más alta
        ),
        
        # PATRÓN 2: "Escritura Pública Número X"
        (
            "escritura_publica_numero",
            r'ESCRITURA\s+P[UÚ]BLICA\s+(?:N[UÚ]MERO|No\.?|#)\s*[:\s]*' + PATRON_NUMERO,
            2
        ),
        
        # PATRÓN 3: "Escritura Número X" (sin "Pública")
        (
            "escritura_numero",
            r'ESCRITURA\s+(?:N[UÚ]MERO|No\.?|NUM\.?|#)\s*[:\s]*' + PATRON_NUMERO,
            3
        ),
        
        # PATRÓN 4: "Número de Escritura: X"
        (
            "numero_de_escritura",
            r'N[UÚ]MERO\s+DE\s+ESCRITURA[:\s]*' + PATRON_NUMERO,
            4
        ),
        
        # PATRÓN 5: "Instrumento Número X" (sin "Público")
        (
            "instrumento_numero",
            r'INSTRUMENTO\s+(?:N[UÚ]MERO|No\.?)\s*[:\s]*' + PATRON_NUMERO,
            5
        ),
    ]
    
    # =========================================================================
    # Patrones de EXCLUSIÓN (contextos a ignorar)
    # =========================================================================
    # Estos patrones identifican números que NO son el número de escritura,
    # como los sellos de catastro que aparecen al final del documento.
    
    patrones_exclusion = [
        r'ESCRITURA\s+NO\.?\s*[\d,.\s]+\s*SE\s+',       # "ESCRITURA NO 2,397 SE TRAMITÓ"
        r'ESCRITURA\s+NO\.?\s*[\d,.\s]+\s*CONFORME',    # "ESCRITURA NO 2,397 CONFORME"
        r'ESCRITURA\s+NO\.?\s*[\d,.\s]+\s*TRAMIT',      # "ESCRITURA NO 2,397 TRAMIT..."
        r'PRESENTE\s+ESCRITURA\s+NO\.?\s*[\d,.\s]+',    # "PRESENTE ESCRITURA NO 2,397"
    ]
    
    # =========================================================================
    # Funciones auxiliares
    # =========================================================================
    
    def limpiar_numero(numero_str: str) -> Optional[int]:
        """Convierte string de número a int, manejando formatos mexicanos."""
        limpio = re.sub(r'[,.\s]', '', numero_str)
        try:
            numero = int(limpio)
            if 1 <= numero <= 999999:  # Rango válido para escrituras
                return numero
            return None
        except ValueError:
            return None
    
    def esta_en_contexto_excluido(texto: str, posicion: int, ventana: int = 100) -> bool:
        """Verifica si el match está en un contexto de sello de catastro."""
        inicio = max(0, posicion - ventana)
        fin = min(len(texto), posicion + ventana)
        contexto = texto[inicio:fin].upper()
        
        for patron in patrones_exclusion:
            if re.search(patron, contexto, re.IGNORECASE):
                return True
        return False
    
    # =========================================================================
    # ESTRATEGIA PRINCIPAL: Buscar en ENCABEZADO primero
    # =========================================================================
    
    CHARS_ENCABEZADO = 1000
    texto_upper = texto.upper()
    encabezado = texto_upper[:CHARS_ENCABEZADO]
    
    matches_encontrados = []
    
    # Buscar en el encabezado con todos los patrones
    for nombre_patron, regex, prioridad in patrones:
        for match in re.finditer(regex, encabezado, re.IGNORECASE):
            posicion = match.start()
            
            # Verificar que no esté en contexto excluido
            if esta_en_contexto_excluido(texto_upper, posicion):
                continue
            
            numero = limpiar_numero(match.group(1))
            if numero:
                matches_encontrados.append((numero, prioridad, posicion, nombre_patron))
    
    # =========================================================================
    # FALLBACK: Si no encontró en encabezado, buscar en todo el documento
    # =========================================================================
    
    if not matches_encontrados:
        for nombre_patron, regex, prioridad in patrones:
            for match in re.finditer(regex, texto_upper, re.IGNORECASE):
                posicion = match.start()
                
                if esta_en_contexto_excluido(texto_upper, posicion):
                    continue
                
                numero = limpiar_numero(match.group(1))
                if numero:
                    # Penalizar posiciones tardías en búsqueda completa
                    prioridad_ajustada = prioridad + (posicion / 10000)
                    matches_encontrados.append((numero, prioridad_ajustada, posicion, nombre_patron))
    
    # =========================================================================
    # Seleccionar el mejor match
    # =========================================================================
    
    if matches_encontrados:
        # Ordenar por prioridad (menor = mejor), luego por posición
        matches_encontrados.sort(key=lambda x: (x[1], x[2]))
        return matches_encontrados[0][0]
    
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
    ANIO_PALABRAS = r'(?:dos\s+mil\s+(?:veinti(?:uno|dos|tres|cuatro|cinco|seis)|dieci(?:siete|ocho|nueve)|veinte)|\d{4})'
    
    patrones = [
        # Patrón legal notarial con año en números
        rf'(?:A\s+los\s+)?(?:\(\d+\)\s+)?(\w+)\s+d[ií]as?\s+del\s+mes\s+de\s+({MESES})\s+(?:del\s+)?a[ñn]o\s+(\d{{4}})',
        
        # Patrón legal notarial con año en palabras
        rf'(?:A\s+los\s+)?(?:\(\d+\)\s+)?(\w+)\s+d[ií]as?\s+del\s+mes\s+de\s+({MESES})\s+(?:del\s+)?a[ñn]o\s+({ANIO_PALABRAS})',
        
        # Patrón simple: "15 de mayo de 2024"
        rf'(\d{{1,2}})\s+de\s+({MESES})\s+(?:de\s+|del\s+)?(\d{{4}})',
        
        # Patrón con "a": "a 15 de mayo de 2024"
        rf'[aA]\s+(\d{{1,2}})\s+de\s+({MESES})\s+(?:de\s+|del\s+)?(\d{{4}})',
        
        # Patrón con año en palabras
        rf'(\d{{1,2}})\s+de\s+({MESES})\s+(?:de\s+|del\s+)?({ANIO_PALABRAS})',
    ]
    
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
    datos específicos.
    
    Args:
        texto: Texto completo del documento OCR
        
    Returns:
        Dict con los datos extraídos
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


# =============================================================================
# FUNCIONES DE EXTRACCIÓN REGEX EXPANDIDAS (Plan A - Plan Z)
# =============================================================================

def extraer_numero_notaria(texto: str) -> Optional[int]:
    """
    Extrae el número de notaría del documento.
    
    El número de notaría es un identificador de 1-3 dígitos que
    identifica a cada notaría en un estado.
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        int: Número de notaría o None
    """
    
    patrones = [
        r'[Nn]otar[ií]a\s+(?:P[uú]blica\s+)?(?:n[uú]mero|No\.?|#)\s*[:\s]*(\d+)',
        r'[Nn]otario\s+(?:P[uú]blico\s+)?(?:n[uú]mero|No\.?|#)\s*[:\s]*(\d+)',
        r'[Nn]otar[ií]a\s+(\d+)(?:\s|,|\.)',
        r'de\s+la\s+[Nn]otar[ií]a\s+(\d+)',
    ]
    
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            try:
                numero = int(match.group(1))
                if 1 <= numero <= 999:
                    return numero
            except (ValueError, IndexError):
                continue
    
    return None


def extraer_nombre_notario(texto: str) -> Optional[str]:
    """
    Extrae el nombre del notario del documento.
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        str: Nombre del notario o None
    """
    
    patrones = [
        # Patrón 1: "ante mí, Lic. NOMBRE, Notario"
        r'ante\s+m[ií],?\s+(?:(?:Lic(?:enciado)?|Dr\.?|Mtro\.?|C\.?)\s+)?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{5,50}?),?\s+[Nn]otario',

        # Patrón 2: "NOMBRE, Notario Público número"
        r'([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{5,50}?),?\s+[Nn]otario\s+[Pp][uú]blico\s+(?:n[uú]mero|No\.?)',

        # Patrón 3: "Notario: Lic. NOMBRE"
        r'[Nn]otario\s+(?:[Pp][uú]blico\s+)?[:\s]+(?:(?:Lic|Dr|Mtro)\.?\s+)?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]{5,50}?)(?:\n|,|;|Notaría)',

        # Patrón 4: "LIC. NOMBRE\nNOTARIO NUMERO" (multilinea)
        r'(?:Lic(?:enciado)?|Dr|Mtro)\.?\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,50}?)\s*\n\s*[Nn]otario\s+(?:[Nn][uú]mero|[Nn]o\.?)',

        # Patrón 5: "LICENCIADO NOMBRE, TITULAR DE LA NOTARÍA"
        r'(?:Lic(?:enciado)?|Dr|Mtro)\.?\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,50}?),?\s+[Tt]itular\s+de\s+la\s+[Nn]otar[ií]a',

        # Patrón 6: "Yo, LICENCIADO NOMBRE, TITULAR"
        r'[Yy]o,\s+(?:Lic(?:enciado)?|Dr|Mtro)\.?\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,50}?),?\s+[Tt]itular',
    ]
    
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
        if match:
            nombre = match.group(1).strip()
            nombre = re.sub(r'\s+', ' ', nombre)
            nombre = nombre.strip().rstrip(',.')
            
            palabras = nombre.split()
            if len(palabras) >= 2 and len(nombre) >= 10:
                return nombre
    
    return None


def extraer_estado_civil(texto: str, nombre_persona: str) -> Optional[str]:
    """
    Extrae estado civil de una persona en el documento.

    PATRONES QUE BUSCA:
    ===================
    1. "NOMBRE, mayor de edad, ESTADO_CIVIL"
       Ej: "ANGELBERTHA PÉREZ SOTO, mayor de edad, casada"

    2. "ESTADO_CIVIL, mayor de edad"
       Ej: "casada, empleada doméstica, originaria de..."

    3. Contexto cercano al nombre (±200 chars)

    Args:
        texto: Texto OCR completo
        nombre_persona: Nombre de la persona a buscar

    Returns:
        str: "casado"/"casada"/"soltero"/"soltera"/"divorciado"/etc o None

    Ejemplos:
        >>> texto = "MARIA LOPEZ, mayor de edad, casada, originaria de..."
        >>> extraer_estado_civil(texto, "MARIA LOPEZ")
        'casada'
    """
    if not nombre_persona or not texto:
        return None

    # Normalizar nombre para búsqueda flexible
    nombre_limpio = re.sub(r'[áéíóúÁÉÍÓÚ]', lambda m: {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U'
    }[m.group()], nombre_persona)

    # Patrón de estados civiles
    estados = r'(casad[oa]s?|solter[oa]s?|divorciad[oa]s?|viud[oa]s?)'

    # PATRÓN 1: "NOMBRE, mayor de edad, ESTADO_CIVIL"
    patron_1 = rf'{re.escape(nombre_limpio)}[^.]*?mayor\s+de\s+edad[,\s]+{estados}'
    match = re.search(patron_1, texto, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    # PATRÓN 2: Buscar en contexto cercano al nombre (±200 chars)
    pos_nombre = texto.upper().find(nombre_limpio.upper())
    if pos_nombre != -1:
        inicio = max(0, pos_nombre - 50)
        fin = min(len(texto), pos_nombre + 250)
        contexto = texto[inicio:fin]

        patron_2 = rf'{estados}[,\s]+.*?(?:mayor\s+de\s+edad|emplead[oa]|originari[oa])'
        match = re.search(patron_2, contexto, re.IGNORECASE)
        if match:
            return match.group(1).lower()

    # PATRÓN 3: "ser mexicano/a, mayor de edad, ESTADO"
    patron_3 = rf'ser\s+mexican[oa][,\s]+mayor\s+de\s+edad[,\s]+{estados}'
    match = re.search(patron_3, texto, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    return None


def extraer_representante_adquiriente(
    texto: str,
    nombre_adquiriente: str
) -> Optional[Dict[str, Any]]:
    """
    Extrae representante que actúa por el adquiriente.

    PATRONES QUE BUSCA:
    ===================
    1. "ADQUIRIENTE, representada por [NOMBRE], en calidad de [CARGO]"
    2. "representada por su [CARGO] [NOMBRE]"
    3. "gestor/a de negocios [NOMBRE]"
    4. "apoderado/a [NOMBRE]"

    Args:
        texto: Texto OCR completo
        nombre_adquiriente: Nombre del adquiriente

    Returns:
        Dict con estructura:
        {
            "nombre": "MARIA GUADALUPE HILDA BERNAL CHAVARIN",
            "en_calidad": "GESTOR",
            "escritura": None,
            "bis": False,
            "fecha_poder": None
        }

    Ejemplos:
        >>> texto = "ANGELBERTHA PEREZ SOTO, representada por su Gestora de Negocios la Licenciada MA. GUADALUPE HILDA BERNAL CHAVARIN"
        >>> extraer_representante_adquiriente(texto, "ANGELBERTHA PEREZ SOTO")
        {'nombre': 'MA. GUADALUPE HILDA BERNAL CHAVARIN', 'en_calidad': 'GESTOR', ...}
    """
    if not nombre_adquiriente or not texto:
        return None

    def limpiar_nombre_representante(nombre: str) -> str:
        """Limpia nombre de representante."""
        # Remover títulos profesionales
        nombre = re.sub(r'^(?:Lic(?:enciado)?|Dr|Mtro|C)\.?\s+', '', nombre, flags=re.IGNORECASE)
        # Remover "también conocida como..."
        nombre = re.sub(r'\s+tambien.*$', '', nombre, flags=re.IGNORECASE)
        nombre = re.sub(r'\s+conocid[oa].*$', '', nombre, flags=re.IGNORECASE)
        return nombre.strip().upper()

    # PATRÓN 1: "representad[oa] por [su] [CARGO] [la/el] [TÍTULO] [NOMBRE]"
    # Usar búsqueda más flexible sin restricción de caracteres acentuados
    patron_1 = rf'representad[oa]\s+(?:en\s+este\s+acto\s+)?por\s+su\s+([^,]+?)\s+(?:la|el)\s+(?:Lic(?:enciado|enciada)?|Dr|C)\.?\s+([A-Z][A-Z\s\.]+?)(?:\s+tambien|,)'

    match = re.search(patron_1, texto, re.IGNORECASE)
    if match:
        cargo = match.group(1).strip()
        nombre_rep = match.group(2).strip()

        # Normalizar cargo
        cargo_normalizado = cargo.upper()
        if 'GESTOR' in cargo_normalizado:
            en_calidad = 'GESTOR'
        elif 'APODERADO' in cargo_normalizado:
            en_calidad = 'APODERADO'
        elif 'REPRESENTANTE' in cargo_normalizado:
            en_calidad = 'REPRESENTANTE LEGAL'
        else:
            en_calidad = cargo.upper()

        return {
            "nombre": limpiar_nombre_representante(nombre_rep),
            "en_calidad": en_calidad,
            "escritura": None,
            "bis": False,
            "fecha_poder": None
        }

    # PATRÓN 2: "por [NOMBRE], en calidad/su calidad de [CARGO]"
    patron_2 = rf'por\s+(?:la|el)\s+(?:Lic|Dr|C)\.?\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s\.]{10,60}?),?\s+en\s+(?:su\s+)?calidad\s+de\s+([^,\.]+)'

    match = re.search(patron_2, texto, re.IGNORECASE)
    if match:
        nombre_rep = match.group(1).strip()
        cargo = match.group(2).strip()

        return {
            "nombre": limpiar_nombre_representante(nombre_rep),
            "en_calidad": cargo.upper(),
            "escritura": None,
            "bis": False,
            "fecha_poder": None
        }

    return None


def extraer_numero_instrumento_poder(texto: str) -> Optional[str]:
    """
    Extrae número de instrumento/escritura del poder.

    PATRONES QUE BUSCA:
    ===================
    1. "instrumento [NÚMERO] [texto_número]"
       Ej: "instrumento 63,550 sesenta y tres mil quinientos cincuenta"

    2. "escritura número [NÚMERO]"
       Ej: "escritura número 21,695 veintiún mil seiscientos noventa y cinco"

    3. Contexto: cerca de "poder", "representante", "apoderado"

    Args:
        texto: Texto OCR completo

    Returns:
        str: Número limpio sin comas (ej: "63550")

    Ejemplos:
        >>> texto = "exhibe instrumento 63,550 sesenta y tres mil quinientos cincuenta"
        >>> extraer_numero_instrumento_poder(texto)
        '63550'
    """
    if not texto:
        return None

    def limpiar_numero_instrumento(numero_str: str) -> Optional[int]:
        """Limpia y valida número de instrumento."""
        # Remover espacios, comas, puntos
        limpio = re.sub(r'[,.\s]', '', numero_str)
        try:
            numero = int(limpio)
            # Validar rango razonable
            if 100 <= numero <= 999999:
                return numero
        except ValueError:
            pass
        return None

    # PATRÓN 1: "instrumento [NÚMERO]" (más común en poderes)
    patron_1 = r'instrumento\s+(?:p[uú]blico\s+)?(?:n[uú]mero\s+)?([\d,.\s]+)'

    matches = re.finditer(patron_1, texto, re.IGNORECASE)
    for match in matches:
        numero_str = match.group(1)
        numero = limpiar_numero_instrumento(numero_str)
        if numero and 1000 <= numero <= 999999:  # Rango típico
            return str(numero)

    # PATRÓN 2: "escritura número [NÚMERO]" en contexto de poder
    patron_2 = r'(?:poder|representante|apoderado)[^.]{0,200}?escritura\s+(?:n[uú]mero|No\.?)\s*([\d,.\s]+)'

    match = re.search(patron_2, texto, re.IGNORECASE)
    if match:
        numero_str = match.group(1)
        numero = limpiar_numero_instrumento(numero_str)
        if numero and 1000 <= numero <= 999999:
            return str(numero)

    return None


def extraer_fecha_poder(texto: str) -> Optional[str]:
    """
    Extrae fecha del poder/instrumento.

    PATRONES QUE BUSCA:
    ===================
    1. "de fecha [DÍA] [día_texto] del mes de [MES] del año [AÑO]"
       Ej: "de fecha 15 quince del mes de abril del año 2020"

    2. "fecha [DÍA] de [MES] de [AÑO]"
       Ej: "fecha 14 de octubre de 2021"

    3. Contexto: cerca de "instrumento", "poder", "escritura"

    Args:
        texto: Texto OCR completo

    Returns:
        str: Fecha en formato "M/D/YYYY" (ej: "4/15/2020")

    Ejemplos:
        >>> texto = "de fecha 15 quince del mes de abril del año 2020"
        >>> extraer_fecha_poder(texto)
        '4/15/2020'
    """
    if not texto:
        return None

    # Mapeo de meses
    MESES = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }

    def validar_fecha(dia: int, mes: int, anio: int) -> bool:
        """Valida que la fecha sea válida."""
        if not (1 <= mes <= 12):
            return False
        if not (1 <= dia <= 31):
            return False
        if not (1990 <= anio <= 2030):  # Rango razonable
            return False

        # Validar días por mes
        dias_por_mes = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        return dia <= dias_por_mes[mes - 1]

    # PATRÓN 1: "de fecha [DÍA] ... del mes de [MES] ... del año [AÑO]"
    patron_1 = r'de\s+fecha\s+(\d{1,2})\s+[a-záéíóúñ]+\s+del\s+mes\s+de\s+([a-záéíóúñ]+)\s+del\s+a[ñn]o\s+(\d{4})'

    match = re.search(patron_1, texto, re.IGNORECASE)
    if match:
        dia = int(match.group(1))
        mes_nombre = match.group(2).lower()
        anio = int(match.group(3))

        mes = MESES.get(mes_nombre)
        if mes and validar_fecha(dia, mes, anio):
            return f"{mes}/{dia}/{anio}"

    # PATRÓN 2: "fecha [DÍA] de [MES] de [AÑO]"
    patron_2 = r'fecha\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de(?:l)?\s+(\d{4})'

    match = re.search(patron_2, texto, re.IGNORECASE)
    if match:
        dia = int(match.group(1))
        mes_nombre = match.group(2).lower()
        anio = int(match.group(3))

        mes = MESES.get(mes_nombre)
        if mes and validar_fecha(dia, mes, anio):
            return f"{mes}/{dia}/{anio}"

    # PATRÓN 3: Contexto "instrumento ... de fecha DD/MM/AAAA"
    patron_3 = r'instrumento[^.]{0,100}?de\s+fecha[^.]{0,50}?(\d{1,2})[/-](\d{1,2})[/-](\d{4})'

    match = re.search(patron_3, texto, re.IGNORECASE)
    if match:
        parte1 = int(match.group(1))
        parte2 = int(match.group(2))
        anio = int(match.group(3))

        # Detectar formato (DD/MM o MM/DD)
        if parte1 <= 12 and parte2 > 12:  # MM/DD/YYYY
            mes, dia = parte1, parte2
        elif parte2 <= 12 and parte1 > 12:  # DD/MM/YYYY
            dia, mes = parte1, parte2
        elif parte1 <= 12 and parte2 <= 12:  # Ambiguo, asumir MM/DD
            mes, dia = parte1, parte2
        else:
            return None

        if validar_fecha(dia, mes, anio):
            return f"{mes}/{dia}/{anio}"

    return None


def extraer_rfc_todos(texto: str) -> List[str]:
    """
    Extrae TODOS los RFC encontrados en el documento.
    
    FORMATO RFC MEXICANO:
    =====================
    - Persona física: 4 letras + 6 dígitos + 3 alfanuméricos (13 chars)
    - Persona moral: 3 letras + 6 dígitos + 3 alfanuméricos (12 chars)
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        List[str]: Lista de RFCs encontrados (sin duplicados)
    """
    
    patron = r'\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b'
    matches = re.findall(patron, texto.upper())
    rfcs_unicos = list(dict.fromkeys(matches))
    
    rfcs_validos = []
    for rfc in rfcs_unicos:
        if len(rfc) in [12, 13]:
            rfcs_validos.append(rfc)
    
    return rfcs_validos


def extraer_curp_todos(texto: str) -> List[str]:
    """
    Extrae TODOS los CURP encontrados en el documento.
    
    FORMATO CURP MEXICANO:
    ======================
    18 caracteres: 4 letras + 6 dígitos + 1 letra (sexo) + 2 letras (estado) 
                   + 3 consonantes + 1 dígito/letra + 1 dígito
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        List[str]: Lista de CURPs encontrados (sin duplicados)
    """
    
    patron = r'\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b'
    matches = re.findall(patron, texto.upper())
    
    return list(dict.fromkeys(matches))


def extraer_municipio(texto: str) -> Optional[str]:
    """
    Extrae el municipio/ciudad donde se firma el documento.
    
    PATRONES QUE BUSCA:
    ===================
    - "En la ciudad de Guadalajara, Jalisco"
    - "En el municipio de Zapopan"
    - "ciudad de México, Ciudad de México"
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        str: Nombre del municipio o None
    """
    
    patrones = [
        r'[Ee]n\s+(?:la\s+)?ciudad\s+de\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:,|\s+[A-Z])',
        r'[Ee]n\s+(?:el\s+)?municipio\s+de\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:,|\s+[A-Z])',
        r'ciudad\s+de\s+([A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?)(?:,|\.|\s+[Ee]stado)',
    ]
    
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            municipio = match.group(1).strip()
            municipio = re.sub(r'\s+', ' ', municipio)
            municipio = municipio.strip().rstrip(',.')
            
            if 3 <= len(municipio) <= 50:
                return municipio
    
    return None


# =============================================================================
# FIX #2: extraer_estado CORREGIDO
# =============================================================================

def extraer_estado(texto: str) -> Optional[str]:
    """
    Extrae el estado donde se firma el documento.
    
    FIX #2 APLICADO:
    ================
    - Busca en contexto específico ("ciudad de X, ESTADO" o "En X, ESTADO")
    - No retorna el primer estado que encuentre de la lista
    - Prioriza estados que aparecen junto al municipio
    
    PROBLEMA ORIGINAL:
    ==================
    El documento tenía:
      - "Representante Regional de Jalisco, Michoacán, Nayarit y Colima"
      - "En la Ciudad de Tepic, Nayarit"
    
    La función original iteraba la lista de estados alfabéticamente y
    retornaba "Colima" porque aparece antes que "Nayarit" en la lista.
    
    SOLUCIÓN:
    =========
    1. Buscar primero en patrones específicos de ubicación
    2. "ciudad de X, ESTADO" tiene prioridad sobre menciones sueltas
    3. Solo usar búsqueda en lista completa como fallback
    
    Args:
        texto: Texto del documento OCR
        
    Returns:
        str: Nombre del estado o None
    """
    
    # Lista de estados mexicanos para validación
    ESTADOS_MEXICO = [
        "Aguascalientes", "Baja California", "Baja California Sur", "Campeche",
        "Chiapas", "Chihuahua", "Ciudad de México", "CDMX", "Coahuila", "Colima",
        "Durango", "Estado de México", "Guanajuato", "Guerrero", "Hidalgo",
        "Jalisco", "México", "Michoacán", "Morelos", "Nayarit", "Nuevo León",
        "Oaxaca", "Puebla", "Querétaro", "Quintana Roo", "San Luis Potosí",
        "Sinaloa", "Sonora", "Tabasco", "Tamaulipas", "Tlaxcala", "Veracruz",
        "Yucatán", "Zacatecas"
    ]
    
    # =========================================================================
    # ESTRATEGIA 1: Buscar en contextos ESPECÍFICOS de ubicación
    # =========================================================================
    # Estos patrones buscan el estado en contextos donde es MÁS PROBABLE
    # que sea la ubicación real del documento (no una referencia).
    
    # Crear patrón para cualquier estado (para usar en los regex)
    estados_patron = '|'.join(re.escape(e) for e in ESTADOS_MEXICO)
    
    patrones_contexto = [
        # PATRÓN 1: "En la ciudad de X, ESTADO" o "ciudad de X, ESTADO"
        # Ejemplo: "En la Ciudad de Tepic, Nayarit"
        # Este es el patrón MÁS CONFIABLE porque indica la ubicación del acto.
        rf'[Cc]iudad\s+de\s+[A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?,\s*({estados_patron})',
        
        # PATRÓN 2: "En X, ESTADO; a los" (formato de encabezado notarial)
        # Ejemplo: "En Tepic, Nayarit; a los cinco días..."
        rf'[Ee]n\s+[A-ZÁÉÍÓÚÑa-záéíóúñ]+,\s*({estados_patron})\s*[;,]?\s*a\s+los',
        
        # PATRÓN 3: "municipio de X, ESTADO"
        # Ejemplo: "municipio de Xalisco, Nayarit"
        rf'municipio\s+de\s+[A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?,\s*({estados_patron})',
        
        # PATRÓN 4: "vecina/vecino de X, ESTADO" (dato de compareciente)
        # Ejemplo: "vecina de Xalisco, Nayarit"
        rf'vecin[oa]\s+de\s+[A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?,\s*({estados_patron})',
        
        # PATRÓN 5: "Registro Público de la Propiedad de X, ESTADO"
        # Ejemplo: "Registro Público de la Propiedad de Tepic, Nayarit"
        rf'Registro\s+P[úu]blico\s+(?:de\s+la\s+Propiedad\s+)?de\s+[A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?,\s*({estados_patron})',
        
        # PATRÓN 6: "Estado de ESTADO" (mención explícita)
        # Ejemplo: "Estado de Nayarit"
        rf'[Ee]stado\s+de\s+({estados_patron})',
        
        # PATRÓN 7: "Capital del Estado de ESTADO"
        # Ejemplo: "Capital del Estado de Nayarit"
        rf'[Cc]apital\s+del\s+[Ee]stado\s+de\s+({estados_patron})',
    ]
    
    # Buscar en cada patrón de contexto
    for patron in patrones_contexto:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            estado_encontrado = match.group(1)
            
            # Normalizar el estado encontrado (buscar en lista oficial)
            for estado_oficial in ESTADOS_MEXICO:
                if estado_oficial.lower() == estado_encontrado.lower():
                    return estado_oficial
            
            # Si no está exactamente en la lista, retornar como está
            return estado_encontrado
    
    # =========================================================================
    # ESTRATEGIA 2 (FALLBACK): Buscar estado cerca del municipio extraído
    # =========================================================================
    # Si no encontramos en contextos específicos, intentamos encontrar
    # el estado que aparece junto al municipio.
    
    municipio = extraer_municipio(texto)
    if municipio:
        # Buscar patrón "MUNICIPIO, ESTADO"
        patron_municipio_estado = rf'{re.escape(municipio)}\s*,\s*({estados_patron})'
        match = re.search(patron_municipio_estado, texto, re.IGNORECASE)
        if match:
            estado_encontrado = match.group(1)
            for estado_oficial in ESTADOS_MEXICO:
                if estado_oficial.lower() == estado_encontrado.lower():
                    return estado_oficial
    
    # =========================================================================
    # ESTRATEGIA 3 (ÚLTIMO RECURSO): NO retornar el primer estado de la lista
    # =========================================================================
    # A diferencia de la versión original, NO iteramos la lista completa
    # buscando cualquier mención. Esto evita falsos positivos como "Colima"
    # cuando el documento menciona "Jalisco, Michoacán, Nayarit y Colima"
    # en una lista de jurisdicciones.
    #
    # Si llegamos aquí, es mejor retornar None que un estado incorrecto.
    
    return None


def extraer_todos_regex(texto: str) -> Dict[str, Any]:
    """
    Ejecuta TODAS las extracciones por regex disponibles.
    
    Esta función es el punto de entrada principal para la extracción
    por regex del Plan A.
    
    Args:
        texto: Texto completo del documento OCR
        
    Returns:
        Dict con todos los campos extraídos:
        {
            "numero_escritura": int | None,
            "numero_notaria": int | None,
            "nombre_notario": str | None,
            "fecha_documento": str | None,
            "monto_operacion": str | None,
            "municipio": str | None,
        }
    """

    return {
        # Campos principales
        "numero_escritura": extraer_numero_escritura(texto),
        "fecha_documento": extraer_fecha_documento(texto),
        "monto_operacion": extraer_monto_operacion(texto),

        # Campos de notaría
        "numero_notaria": extraer_numero_notaria(texto),
        "nombre_notario": extraer_nombre_notario(texto),

        # Campos de ubicación
        "municipio": extraer_municipio(texto),

        # Campos de poder/instrumento (FASE 1 - Nuevos campos críticos)
        "numero_instrumento_poder": extraer_numero_instrumento_poder(texto),
        "fecha_poder": extraer_fecha_poder(texto),

        # NOTA: estado_civil y representante_adquiriente requieren contexto
        # Se extraerán en post-procesamiento con datos de adquirientes
    }


def validar_dato_en_texto(dato: Any, texto: str) -> bool:
    """
    Verifica si un dato extraído existe literalmente en el texto original.
    
    Esta es la base de la validación cruzada (Plan B).
    
    Args:
        dato: El dato a buscar (puede ser str, int, etc.)
        texto: El texto original donde buscar
        
    Returns:
        True si el dato se encuentra en el texto
        
    Ejemplo:
        >>> validar_dato_en_texto(18226, "ESCRITURA NÚMERO 18,226")
        True
        >>> validar_dato_en_texto("Juan Pérez", "comparece JUAN PÉREZ GARCÍA")
        True
    """
    if dato is None:
        return False
    
    dato_str = str(dato)
    texto_upper = texto.upper()
    
    # Para números, buscar con diferentes formatos
    if isinstance(dato, (int, float)):
        # Buscar número exacto
        if re.search(rf'\b{dato_str}\b', texto):
            return True
        # Buscar con formato de miles (18,226)
        if isinstance(dato, int) and dato >= 1000:
            formato_miles = f"{dato:,}"
            if formato_miles in texto:
                return True
        return False
    
    # Para strings
    if isinstance(dato, str):
        # Búsqueda case-insensitive
        if dato.upper() in texto_upper:
            return True
        
        # Para montos, limpiar formato
        if dato.startswith("$"):
            numero = re.sub(r'[^\d.]', '', dato)
            if numero in texto:
                return True
        
        # Buscar palabras individuales (para nombres)
        palabras = dato.upper().split()
        if len(palabras) >= 2:
            encontradas = sum(1 for p in palabras if p in texto_upper)
            if encontradas >= len(palabras) * 0.6:  # 60% de palabras
                return True
        
        return False
    
    return False


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("PRUEBA DE text_processing.py CON FIXES #1 y #2")
    print("=" * 70)
    
    # Texto de prueba (simulando el documento problemático)
    texto_prueba = """
    MEDIA URRES . TITULAIRESN NS UNIDOS Y LIC. RIGOBERTO OCHOA TORRES 
    Instrumento Público Número 2307 dos mil trescientos siete. Tomo Tercero.
    En la Ciudad de Tepic, Nayarit; a los 05 cinco días del mes de Mayo del año 2023.
    
    El Arquitecto ERNESTO PADILLA ACEVES, en representación legal de la persona 
    moral oficial denominada INSTITUTO NACIONAL DEL SUELO SUSTENTABLE, como 
    Representante Regional de Jalisco, Michoacán, Nayarit y Colima.
    
    El precio de esta operación es por la cantidad de $8,654.00 
    (OCHO MIL SEISCIENTOS CINCUENTA Y CUATRO PESOS 00/100 MONEDA NACIONAL).
    
    vecina de Xalisco, Nayarit, con domicilio en calle Estaño número 49.
    
    LA PRESENTE ESCRITURA NO 2,397 SE TRAMITÓ CONFORME A LA LEY
    REALIZANDO LOS MOVIMIENTOS CATASTRALES CORRESPONDIENTES
    """
    
    print("\n📄 PRUEBA DE EXTRACCIÓN CON FIXES")
    print("-" * 70)
    
    # Probar Fix #1: numero_escritura
    print("\n🔧 FIX #1: extraer_numero_escritura")
    resultado = extraer_numero_escritura(texto_prueba)
    esperado = 2307
    print(f"   Esperado: {esperado}")
    print(f"   Obtenido: {resultado}")
    print(f"   {'✅ CORRECTO' if resultado == esperado else '❌ INCORRECTO'}")
    
    # Probar Fix #2: estado
    print("\n🔧 FIX #2: extraer_estado")
    resultado = extraer_estado(texto_prueba)
    esperado = "Nayarit"
    print(f"   Esperado: {esperado}")
    print(f"   Obtenido: {resultado}")
    print(f"   {'✅ CORRECTO' if resultado == esperado else '❌ INCORRECTO'}")
    
    # Probar extracción completa
    print("\n📊 EXTRACCIÓN COMPLETA (extraer_todos_regex)")
    print("-" * 70)
    resultados = extraer_todos_regex(texto_prueba)
    
    for campo, valor in resultados.items():
        if valor is not None and valor != []:
            print(f"   ✅ {campo}: {valor}")
        else:
            print(f"   ❌ {campo}: No encontrado")
    
    print("\n" + "=" * 70)
    print("FIN DE PRUEBAS")
    print("=" * 70)
