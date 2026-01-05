"""
utils/text_processing.py - Utilidades para procesamiento de texto OCR

MEJORAS PARA REDUCIR VARIABILIDAD:
===================================
1. Limpieza más agresiva del ruido OCR
2. NUEVO: Extracción por regex de datos críticos (número de escritura, montos)
3. NUEVO: Normalización de formatos de fecha

¿Por qué extracción por regex?
==============================
Los datos numéricos como "ESCRITURA NÚMERO 18,226" son fáciles de extraer
con expresiones regulares. Si el LLM falla en extraerlos, usamos regex
como fallback. Esto GARANTIZA que campos críticos siempre se extraigan.
"""

import re
import json
from typing import Optional, Dict, Any, Tuple, List
from collections import Counter


# =============================================================================
# PATRONES DE RUIDO OCR (MEJORADO)
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
# EXTRACCIÓN POR REGEX (NUEVO - CRÍTICO PARA CONSISTENCIA)
# =============================================================================

class RegexExtractor:
    """
    NUEVA CLASE - Extrae datos críticos usando expresiones regulares.
    
    ¿Por qué esto es importante?
    ============================
    El LLM a veces falla en extraer datos numéricos simples como el
    número de escritura. Con regex, podemos GARANTIZAR que estos
    datos se extraigan correctamente.
    
    Este extractor actúa como:
    1. Validador: Verifica si el LLM extrajo correctamente
    2. Fallback: Si el LLM falló, proporciona el valor correcto
    """
    
    @staticmethod
    def extraer_numero_escritura(texto: str) -> Optional[int]:
        """
        Extrae el número de escritura del documento.
        
        PATRONES QUE BUSCA:
        ===================
        - "ESCRITURA NÚMERO 18,226" → 18226
        - "ESCRITURA PÚBLICA NÚMERO DIECIOCHO MIL DOSCIENTOS VEINTISEIS"
        - "Escritura número 18226"
        - "ESCRITURA No. 18,226"
        
        Returns:
            int: Número de escritura, o None si no se encuentra
        """
        # Patrón 1: Número con formato (comas, puntos)
        # Busca: ESCRITURA [PÚBLICA] [NÚMERO/No./NUM] seguido de número
        patrones_numero = [
            r'ESCRITURA\s+(?:P[UÚ]BLICA\s+)?(?:N[UÚ]MERO|No\.?|NUM\.?)\s*[:\s]*(\d{1,3}(?:[,.\s]\d{3})*)',
            r'ESCRITURA\s+(\d{1,3}(?:[,.\s]\d{3})*)',
            r'N[UÚ]MERO\s+DE\s+ESCRITURA[:\s]*(\d{1,3}(?:[,.\s]\d{3})*)',
        ]
        
        for patron in patrones_numero:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                # Limpiar el número (quitar comas, puntos, espacios)
                numero_str = re.sub(r'[,.\s]', '', match.group(1))
                try:
                    return int(numero_str)
                except ValueError:
                    continue
        
        # Patrón 2: Número en palabras (más complejo)
        # Ejemplo: "DIECIOCHO MIL DOSCIENTOS VEINTISEIS"
        numero_palabras = RegexExtractor._extraer_numero_en_palabras(texto)
        if numero_palabras:
            return numero_palabras
        
        return None
    
    @staticmethod
    def _extraer_numero_en_palabras(texto: str) -> Optional[int]:
        """
        Convierte números escritos en palabras a dígitos.
        
        Ejemplo: "DIECIOCHO MIL DOSCIENTOS VEINTISEIS" → 18226
        
        NOTA: Esta es una implementación simplificada para números comunes.
        """
        # Diccionario de conversión
        palabras_a_numeros = {
            'cero': 0, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
            'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
            'diez': 10, 'once': 11, 'doce': 12, 'trece': 13, 'catorce': 14,
            'quince': 15, 'dieciseis': 16, 'diecisiete': 17, 'dieciocho': 18,
            'diecinueve': 19, 'veinte': 20, 'veintiuno': 21, 'veintidos': 22,
            'veintitres': 23, 'veinticuatro': 24, 'veinticinco': 25,
            'veintiseis': 26, 'veintisiete': 27, 'veintiocho': 28,
            'veintinueve': 29, 'treinta': 30, 'cuarenta': 40, 'cincuenta': 50,
            'sesenta': 60, 'setenta': 70, 'ochenta': 80, 'noventa': 90,
            'cien': 100, 'ciento': 100, 'doscientos': 200, 'trescientos': 300,
            'cuatrocientos': 400, 'quinientos': 500, 'seiscientos': 600,
            'setecientos': 700, 'ochocientos': 800, 'novecientos': 900,
            'mil': 1000
        }
        
        # Buscar patrón después de "ESCRITURA NÚMERO"
        match = re.search(
            r'ESCRITURA\s+(?:P[UÚ]BLICA\s+)?N[UÚ]MERO\s+([A-ZÁÉÍÓÚ\s]+?)(?:\.|,|TOMO|LIBRO|FOLIO)',
            texto,
            re.IGNORECASE
        )
        
        if not match:
            return None
        
        palabras_numero = match.group(1).lower().strip()
        palabras = palabras_numero.replace(' y ', ' ').split()
        
        try:
            resultado = 0
            actual = 0
            
            for palabra in palabras:
                palabra = palabra.strip()
                if palabra in palabras_a_numeros:
                    valor = palabras_a_numeros[palabra]
                    if valor == 1000:
                        actual = (actual if actual else 1) * 1000
                        resultado += actual
                        actual = 0
                    elif valor >= 100:
                        actual += valor
                    else:
                        actual += valor
            
            resultado += actual
            return resultado if resultado > 0 else None
            
        except Exception:
            return None
    
    @staticmethod
    def extraer_monto_operacion(texto: str) -> Optional[str]:
        """
        Extrae el monto de la operación.
        
        PATRONES QUE BUSCA:
        ===================
        - "$600,000.00"
        - "SEISCIENTOS MIL PESOS"
        - "$1,500,000.00 MXN"
        
        Returns:
            str: Monto formateado, o None si no se encuentra
        """
        # Patrón para montos en formato numérico
        patrones_monto = [
            # $600,000.00 (SEISCIENTOS MIL PESOS)
            r'\$\s*(\d{1,3}(?:[,]\d{3})*(?:\.\d{2})?)',
            # precio de: $600,000
            r'precio\s+(?:de\s+)?(?:esta\s+operaci[oó]n\s+)?(?:fue\s+)?(?:la\s+cantidad\s+de\s+)?\$?\s*(\d{1,3}(?:[,]\d{3})*(?:\.\d{2})?)',
            # monto de la operación: $600,000
            r'monto\s+(?:de\s+)?(?:la\s+)?operaci[oó]n[:\s]+\$?\s*(\d{1,3}(?:[,]\d{3})*(?:\.\d{2})?)',
        ]
        
        for patron in patrones_monto:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                monto = match.group(1)
                # Asegurar formato con $
                if not monto.startswith('$'):
                    monto = f"${monto}"
                return monto
        
        return None
    
    @staticmethod
    def extraer_fecha_documento(texto: str) -> Optional[str]:
        """
        Extrae la fecha del documento.
        
        PATRONES QUE BUSCA:
        ===================
        - "A los (22) veintidós días del mes de marzo del año 2024"
        - "11 de abril de 2024"
        - "22/03/2024"
        
        Returns:
            str: Fecha en formato legible, o None si no se encuentra
        """
        # Patrón para fecha en formato legal notarial
        patron_legal = r'(?:A\s+los\s+)?(?:\(\d+\)\s+)?(\w+)\s+d[ií]as?\s+del\s+mes\s+de\s+(\w+)\s+del\s+a[ñn]o\s+(\d{4})'
        match = re.search(patron_legal, texto, re.IGNORECASE)
        if match:
            dia = match.group(1)
            mes = match.group(2)
            año = match.group(3)
            return f"{dia} de {mes} de {año}"
        
        # Patrón para fecha simple
        patron_simple = r'(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(\d{4})'
        match = re.search(patron_simple, texto, re.IGNORECASE)
        if match:
            return f"{match.group(1)} de {match.group(2)} de {match.group(3)}"
        
        return None
    
    @staticmethod
    def extraer_nombre_notario(texto: str) -> Optional[str]:
        """
        Extrae el nombre del notario.
        
        PATRONES QUE BUSCA:
        ===================
        - "GUILLERMO LOZA RAMÍREZ, Notario titular"
        - "Licenciado Juan Pérez, Notario Público"
        - "ante mí, [Lic.] NOMBRE APELLIDO, Notario"
        
        Returns:
            str: Nombre del notario, o None si no se encuentra
        """
        patrones = [
            # "ante mí, [Lic./Licenciado] NOMBRE, Notario"
            r'ante\s+m[ií],?\s+(?:Lic(?:enciado)?\.?\s+)?([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ\s]+?),?\s+Notario',
            # "NOMBRE APELLIDO, Notario titular/público"
            r'([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+?),?\s+Notario\s+(?:titular|p[uú]blico)',
            # En el encabezado: "MD. Guillermo Loza Ramírez"
            r'(?:MD|Lic|Dr)\.?\s+([A-ZÁÉÍÓÚÑ][a-záéíóúñA-ZÁÉÍÓÚÑ\s]+?)(?:\n|Notario|NOTARIO)',
        ]
        
        for patron in patrones:
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                nombre = match.group(1).strip()
                # Limpiar y normalizar
                nombre = re.sub(r'\s+', ' ', nombre)
                return nombre
        
        return None
    
    @staticmethod
    def detectar_tipo_titular(texto: str) -> str:
        """
        Detecta si el titular/vendedor es empresa o persona física.
        
        INDICADORES DE EMPRESA:
        =======================
        - "S.A.", "S.A. de C.V.", "S. de R.L."
        - "SOCIEDAD ANÓNIMA", "SOCIEDAD MERCANTIL"
        - "CAPITAL VARIABLE"
        
        Returns:
            str: "empresa" o "persona"
        """
        texto_upper = texto.upper()
        
        indicadores_empresa = [
            'S.A.',
            'S.A. DE C.V.',
            'S. DE R.L.',
            'SOCIEDAD ANÓNIMA',
            'SOCIEDAD ANONIMA',
            'SOCIEDAD MERCANTIL',
            'CAPITAL VARIABLE',
            'PERSONA MORAL',
        ]
        
        for indicador in indicadores_empresa:
            if indicador in texto_upper:
                return "empresa"
        
        return "persona"
    
    @staticmethod
    def extraer_rfc(texto: str, nombre: str = None) -> Optional[str]:
        """
        Extrae RFC del texto.
        
        Formato RFC México:
        - Personas físicas: 4 letras + 6 dígitos + 3 caracteres (13 total)
        - Personas morales: 3 letras + 6 dígitos + 3 caracteres (12 total)
        
        Returns:
            str: RFC encontrado, o None
        """
        # Patrón RFC
        patron_rfc = r'\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b'
        
        matches = re.findall(patron_rfc, texto.upper())
        
        if matches:
            # Si se proporcionó nombre, intentar encontrar el RFC asociado
            if nombre:
                nombre_upper = nombre.upper()
                # Buscar RFC cerca del nombre
                for match in matches:
                    # Verificar si las primeras letras coinciden con el nombre
                    iniciales = match[:4] if len(match) == 13 else match[:3]
                    if any(inicial in nombre_upper for inicial in [iniciales[:2], iniciales]):
                        return match
            
            return matches[0]  # Devolver el primero encontrado
        
        return None


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
    
    El JSON puede venir en:
    1. Bloques ```json ... ```
    2. Bloques ``` ... ```
    3. JSON directo
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
        re.compile(r'\{[\s\S]*\}'),
        re.compile(r'\[[\s\S]*\]')
    ]
    
    for pattern in json_patterns:
        matches = pattern.findall(clean_text)
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
    
    Combina extracción de <think> y JSON.
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
# FUNCIÓN PRINCIPAL DE EXTRACCIÓN HÍBRIDA (NUEVO)
# =============================================================================

def extraer_datos_con_regex(texto: str) -> Dict[str, Any]:
    """
    NUEVA FUNCIÓN - Extrae datos usando regex como fallback/validación.
    
    Esta función se usa para:
    1. Validar lo que extrajo el LLM
    2. Proporcionar valores correctos si el LLM falló
    
    Returns:
        Dict con los datos extraídos por regex
    """
    extractor = RegexExtractor()
    
    return {
        'numero_escritura': extractor.extraer_numero_escritura(texto),
        'monto_operacion': extractor.extraer_monto_operacion(texto),
        'fecha_documento': extractor.extraer_fecha_documento(texto),
        'notario': extractor.extraer_nombre_notario(texto),
        'tipo_titular': extractor.detectar_tipo_titular(texto),
    }


def merge_extractions(llm_data: Dict, regex_data: Dict) -> Dict[str, Any]:
    """
    NUEVA FUNCIÓN - Combina extracción del LLM con regex.
    
    Prioriza los datos del LLM, pero usa regex como fallback
    para campos críticos que el LLM pudo haber fallado.
    
    Args:
        llm_data: Datos extraídos por el LLM
        regex_data: Datos extraídos por regex
        
    Returns:
        Dict combinado con los mejores valores
    """
    if not llm_data:
        llm_data = {}
    
    merged = llm_data.copy()
    
    # Campos críticos donde regex tiene prioridad si LLM falló
    campos_criticos = ['numero_escritura', 'monto_operacion', 'tipo_titular']
    
    for campo in campos_criticos:
        valor_llm = llm_data.get(campo)
        valor_regex = regex_data.get(campo)
        
        # Si LLM no tiene el valor o tiene un valor inválido, usar regex
        if valor_regex is not None:
            if valor_llm is None:
                merged[campo] = valor_regex
                print(f"   📝 {campo}: Usando valor de regex ({valor_regex})")
            elif campo == 'numero_escritura' and isinstance(valor_llm, str):
                # Si numero_escritura es string (error), usar regex
                merged[campo] = valor_regex
                print(f"   📝 {campo}: Corregido por regex ({valor_regex})")
    
    return merged


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DE EXTRACCIÓN POR REGEX")
    print("=" * 60)
    
    texto_prueba = """
    ESCRITURA NÚMERO DIECIOCHO MIL DOSCIENTOS VEINTISEIS.
    TOMO CENTÉSIMO PRIMERO. - LIBRO TERCERO.
    
    GUILLERMO LOZA RAMÍREZ, Notario titular de la Notaría Número 10 Diez
    
    A los (22) veintidós días del mes de marzo del año 2024 dos mil veinticuatro.
    
    COMO (PARTE) VENDEDORA o ENAJENANTE: La sociedad mercantil denominada
    "DESARROLLO TURISTICO LOS COCOS", SOCIEDAD ANÓNIMA DE CAPITAL VARIABLE
    
    El precio de esta operación fue la cantidad de: $600,000.00 (SEISCIENTOS MIL PESOS)
    
    RFC: DTC9012191U5
    """
    
    datos = extraer_datos_con_regex(texto_prueba)
    
    print("\n📊 Datos extraídos por REGEX:")
    for campo, valor in datos.items():
        print(f"   {campo}: {valor}")
