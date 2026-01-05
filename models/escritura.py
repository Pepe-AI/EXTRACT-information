"""
models/escritura.py - Modelos Pydantic para escrituras públicas

DOS MODOS DE VALIDACIÓN:
========================
1. ESTRICTO (EscrituraPublica): Todos los campos obligatorios
2. FLEXIBLE (EscrituraPublicaFlexible): Acepta datos parciales

¿Por qué dos modos?
===================
- Intentamos primero validación ESTRICTA (ideal)
- Si falla, usamos FLEXIBLE para no perder los datos extraídos
- La validación flexible reporta qué campos se encontraron y cuáles no
"""

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Dict, Any, Union
from enum import Enum


# =============================================================================
# CONSTANTES
# =============================================================================

NO_ENCONTRADO = "NO SE ENCONTRÓ DATO"


# =============================================================================
# ENUMS
# =============================================================================

class TipoTitular(str, Enum):
    PERSONA = "persona"
    EMPRESA = "empresa"


# =============================================================================
# MODELOS FLEXIBLES (Todo opcional)
# =============================================================================

class RepresentanteFlexible(BaseModel):
    """
    Representante con todos los campos opcionales.
    
    NOTA: El campo 'escritura' acepta tanto str como int porque
    DeepSeek a veces devuelve el número como entero.
    Se convierte automáticamente a string.
    """
    
    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    en_calidad: Optional[str] = Field(default=NO_ENCONTRADO)
    escritura: Optional[Union[str, int]] = Field(default=NO_ENCONTRADO)
    bis: Optional[bool] = Field(default=False)
    fecha_poder: Optional[str] = Field(default=NO_ENCONTRADO)
    
    model_config = {"extra": "allow"}
    
    @field_validator('escritura', mode='before')
    @classmethod
    def convertir_escritura_a_string(cls, v):
        """
        Convierte el número de escritura a string si viene como int.
        
        ¿Por qué es necesario?
        ======================
        DeepSeek a veces devuelve:
            "escritura": 13425      ← int (causa error sin este validador)
        En lugar de:
            "escritura": "13425"    ← str (correcto)
        
        Este validador acepta ambos y los normaliza a string.
        """
        if v is None:
            return NO_ENCONTRADO
        if isinstance(v, int):
            return str(v)  # Convertir 13425 → "13425"
        return v


class TitularFlexible(BaseModel):
    """Titular con todos los campos opcionales."""
    
    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    actua_por: Optional[str] = Field(default=NO_ENCONTRADO)
    representante: Optional[RepresentanteFlexible] = Field(default=None)
    
    model_config = {"extra": "allow"}


class AdquirienteFlexible(BaseModel):
    """Adquiriente con todos los campos opcionales."""
    
    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    estado_civil: Optional[str] = Field(default=NO_ENCONTRADO)
    tipo_sociedad: Optional[str] = Field(default=None)
    edad: Optional[int] = Field(default=None)
    rfc: Optional[Union[str, bool]] = Field(default=False)
    curp: Optional[Union[str, bool]] = Field(default=False)
    
    model_config = {"extra": "allow"}


class EscrituraPublicaFlexible(BaseModel):
    """
    Modelo FLEXIBLE - Acepta cualquier dato que venga.
    
    Todos los campos son opcionales.
    Si no se encuentra un campo, usa valor por defecto.
    """
    
    notario: Optional[str] = Field(default=NO_ENCONTRADO)
    numero_escritura: Optional[int] = Field(default=None)
    fecha_documento: Optional[str] = Field(default=NO_ENCONTRADO)
    tipo_titular: Optional[str] = Field(default=NO_ENCONTRADO)
    titulares: Optional[List[TitularFlexible]] = Field(default_factory=list)
    adquirientes: Optional[List[AdquirienteFlexible]] = Field(default_factory=list)
    monto_operacion: Optional[str] = Field(default=NO_ENCONTRADO)
    tipo_moneda: Optional[str] = Field(default=NO_ENCONTRADO)
    valor_catastral: Optional[str] = Field(default=None)
    
    model_config = {"extra": "allow"}
    
    def get_campos_encontrados(self) -> Dict[str, Any]:
        """Devuelve solo los campos que SÍ se encontraron."""
        encontrados = {}
        
        if self.notario and self.notario != NO_ENCONTRADO:
            encontrados["notario"] = self.notario
        if self.numero_escritura is not None:
            encontrados["numero_escritura"] = self.numero_escritura
        if self.fecha_documento and self.fecha_documento != NO_ENCONTRADO:
            encontrados["fecha_documento"] = self.fecha_documento
        if self.tipo_titular and self.tipo_titular != NO_ENCONTRADO:
            encontrados["tipo_titular"] = self.tipo_titular
        if self.titulares:
            encontrados["titulares"] = [t.model_dump() for t in self.titulares]
        if self.adquirientes:
            encontrados["adquirientes"] = [a.model_dump() for a in self.adquirientes]
        if self.monto_operacion and self.monto_operacion != NO_ENCONTRADO:
            encontrados["monto_operacion"] = self.monto_operacion
        if self.tipo_moneda and self.tipo_moneda != NO_ENCONTRADO:
            encontrados["tipo_moneda"] = self.tipo_moneda
        if self.valor_catastral:
            encontrados["valor_catastral"] = self.valor_catastral
            
        return encontrados
    
    def get_campos_no_encontrados(self) -> List[str]:
        """Devuelve lista de campos que NO se encontraron."""
        no_encontrados = []
        
        if not self.notario or self.notario == NO_ENCONTRADO:
            no_encontrados.append("notario")
        if self.numero_escritura is None:
            no_encontrados.append("numero_escritura")
        if not self.fecha_documento or self.fecha_documento == NO_ENCONTRADO:
            no_encontrados.append("fecha_documento")
        if not self.tipo_titular or self.tipo_titular == NO_ENCONTRADO:
            no_encontrados.append("tipo_titular")
        if not self.titulares:
            no_encontrados.append("titulares")
        if not self.adquirientes:
            no_encontrados.append("adquirientes")
        if not self.monto_operacion or self.monto_operacion == NO_ENCONTRADO:
            no_encontrados.append("monto_operacion")
        if not self.tipo_moneda or self.tipo_moneda == NO_ENCONTRADO:
            no_encontrados.append("tipo_moneda")
            
        return no_encontrados
    
    def generar_reporte(self) -> Dict[str, Any]:
        """Genera un reporte completo de la extracción."""
        encontrados = self.get_campos_encontrados()
        no_encontrados = self.get_campos_no_encontrados()
        
        total_campos = 8
        campos_encontrados = total_campos - len(no_encontrados)
        porcentaje = (campos_encontrados / total_campos) * 100
        
        return {
            "resumen": {
                "campos_encontrados": campos_encontrados,
                "campos_no_encontrados": len(no_encontrados),
                "total_campos": total_campos,
                "porcentaje_exito": round(porcentaje, 1)
            },
            "datos_encontrados": encontrados,
            "campos_faltantes": no_encontrados,
            "datos_completos": self.model_dump()
        }


# =============================================================================
# MODELOS ESTRICTOS (Para validación inicial)
# =============================================================================

class Representante(BaseModel):
    """
    Representante con campos obligatorios.
    
    NOTA: El campo 'escritura' acepta tanto str como int porque
    DeepSeek a veces devuelve el número como entero.
    """
    
    nombre: str = Field(..., description="Nombre del representante")
    en_calidad: str = Field(..., description="En qué calidad actúa")
    escritura: Union[str, int] = Field(..., description="Número de escritura del poder")
    bis: bool = Field(default=False, description="Si tiene bis")
    fecha_poder: str = Field(..., description="Fecha del poder")
    
    @field_validator('escritura', mode='before')
    @classmethod
    def convertir_escritura_a_string(cls, v):
        """Convierte int a string si es necesario."""
        if isinstance(v, int):
            return str(v)
        return v


class Titular(BaseModel):
    """Titular con campos obligatorios."""
    
    nombre: str = Field(..., description="Nombre del titular")
    actua_por: str = Field(..., description="En qué calidad actúa")
    representante: Optional[Representante] = Field(default=None)


class Adquiriente(BaseModel):
    """Adquiriente con campos obligatorios."""
    
    nombre: str = Field(..., description="Nombre del adquiriente")
    estado_civil: str = Field(..., description="Estado civil")
    tipo_sociedad: Optional[str] = Field(default=None)
    edad: Optional[int] = Field(default=None)
    rfc: Union[str, bool] = Field(default=False)
    curp: Union[str, bool] = Field(default=False)


class EscrituraPublica(BaseModel):
    """
    Modelo ESTRICTO - Valida que los campos obligatorios estén presentes.
    """
    
    notario: str = Field(..., description="Nombre del notario")
    numero_escritura: int = Field(..., description="Número de escritura")
    fecha_documento: str = Field(..., description="Fecha del documento")
    tipo_titular: str = Field(..., description="empresa o persona")
    titulares: List[Titular] = Field(..., min_length=1)
    adquirientes: List[Adquiriente] = Field(..., min_length=1)
    monto_operacion: str = Field(..., description="Monto de la operación")
    tipo_moneda: str = Field(..., description="Tipo de moneda")
    valor_catastral: Optional[str] = Field(default=None)
    
    @field_validator('numero_escritura')
    @classmethod
    def validar_numero(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Número de escritura debe ser mayor a 0")
        return v
    
    @model_validator(mode='after')
    def validar_representantes(self):
        """
        Valida la presencia de representante según el tipo de titular.
        
        REGLA DE NEGOCIO:
        =================
        - EMPRESA: Representante es OBLIGATORIO
          (las sociedades siempre actúan a través de un apoderado)
        
        - PERSONA FÍSICA: Representante es OPCIONAL
          (puede actuar por derecho propio o mediante apoderado)
        """
        if self.tipo_titular.lower() == "empresa":
            for i, titular in enumerate(self.titulares):
                if titular.representante is None:
                    raise ValueError(f"Titular #{i+1} es empresa y debe tener representante")
        # Para persona física, no se valida (representante es opcional)
        return self


# =============================================================================
# MODELO DE RESPUESTA DE EXTRACCIÓN
# =============================================================================

class ExtractionResponse(BaseModel):
    """
    Respuesta estándar de la API de extracción.
    
    Este modelo encapsula el resultado completo de una extracción,
    incluyendo datos, metadatos y estadísticas.
    
    Atributos:
    ==========
    - success: Si la extracción fue exitosa (al menos parcialmente)
    - validacion_estricta: Si pasó validación con todos los campos
    - data: Los datos extraídos (dict)
    - campos_encontrados: Número de campos que se extrajeron
    - campos_no_encontrados: Lista de nombres de campos faltantes
    - porcentaje_exito: Porcentaje de campos encontrados
    - error: Mensaje de error si falló
    - processing_time: Tiempo de procesamiento en segundos
    - model_used: Nombre del modelo LLM usado
    - intentos_realizados: Número de intentos de extracción
    """
    
    success: bool = Field(..., description="Si la extracción fue exitosa")
    validacion_estricta: bool = Field(default=False, description="Si pasó validación estricta")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Datos extraídos")
    campos_encontrados: int = Field(default=0, description="Número de campos encontrados")
    campos_no_encontrados: List[str] = Field(default_factory=list, description="Campos no encontrados")
    porcentaje_exito: float = Field(default=0.0, description="Porcentaje de éxito")
    error: Optional[str] = Field(default=None, description="Mensaje de error")
    processing_time: Optional[float] = Field(default=None, description="Tiempo de procesamiento")
    model_used: Optional[str] = Field(default=None, description="Modelo usado")
    intentos_realizados: int = Field(default=0, description="Intentos realizados")


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def get_campos_obligatorios() -> List[str]:
    """Lista de campos obligatorios."""
    return [
        "notario", "numero_escritura", "fecha_documento",
        "tipo_titular", "titulares", "adquirientes",
        "monto_operacion", "tipo_moneda"
    ]


def get_campos_no_obligatorios() -> List[str]:
    """Lista de campos no obligatorios."""
    return ["valor_catastral"]


def validar_json_flexible(json_data: Dict[str, Any]) -> EscrituraPublicaFlexible:
    """
    Valida JSON con modelo flexible.
    
    Nunca falla - acepta lo que venga y llena el resto con defaults.
    """
    json_normalizado = _normalizar_campos(json_data)
    return EscrituraPublicaFlexible.model_validate(json_normalizado)


def _normalizar_campos(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza nombres de campos incorrectos."""
    
    mapeo = {
        "nombre_titular": "nombre",
        "nombre_completo": "nombre",
        "razon_social": "nombre",
        "num_escritura": "numero_escritura",
        "fecha": "fecha_documento",
        "fecha_escritura": "fecha_documento",
        "monto": "monto_operacion",
        "precio": "monto_operacion",
        "moneda": "tipo_moneda",
    }
    
    resultado = {}
    
    for key, value in data.items():
        key_lower = key.lower().strip()
        key_norm = mapeo.get(key_lower, key_lower)
        
        if key_norm == "titulares" and isinstance(value, list):
            value = [_normalizar_titular(t) for t in value if isinstance(t, dict)]
        
        if key_norm == "adquirientes" and isinstance(value, list):
            value = [_normalizar_adquiriente(a) for a in value if isinstance(a, dict)]
        
        resultado[key_norm] = value
    
    return resultado


def _normalizar_titular(titular: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza un titular."""
    mapeo = {
        "nombre_titular": "nombre",
        "nombre_completo": "nombre",
        "razon_social": "nombre",
        "actua": "actua_por",
    }
    
    resultado = {}
    for key, value in titular.items():
        key_lower = key.lower().strip()
        if key_lower == "tipo_titular":
            continue
        key_norm = mapeo.get(key_lower, key_lower)
        
        if key_norm == "representante" and isinstance(value, str):
            value = {"nombre": value} if value.strip() else None
        
        resultado[key_norm] = value
    
    return resultado


def _normalizar_adquiriente(adq: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza un adquiriente."""
    mapeo = {
        "nombre_completo": "nombre",
        "nombre_adquiriente": "nombre",
        "edo_civil": "estado_civil",
    }
    
    resultado = {}
    for key, value in adq.items():
        key_lower = key.lower().strip()
        key_norm = mapeo.get(key_lower, key_lower)
        resultado[key_norm] = value
    
    return resultado


def generar_feedback_error(
    error_validacion: str, 
    json_anterior: dict = None,
    tipo_titular: str = None
) -> dict:
    """
    Genera un análisis detallado del error para el retry.
    
    MEJORA: Ahora devuelve un diccionario con información estructurada
    que puede ser usada por build_validation_prompt.
    
    Args:
        error_validacion: Error de Pydantic o mensaje de error
        json_anterior: JSON del intento anterior
        tipo_titular: Tipo ya clasificado ("empresa" o "persona")
    
    Returns:
        dict con:
        - campos_ok: Lista de campos que están correctos
        - campos_faltantes: Lista de campos que faltan
        - campos_incorrectos: Lista de campos con formato incorrecto
        - problemas: Lista de problemas específicos detectados
        - sugerencias: Lista de sugerencias de corrección
        - json_anterior: El JSON anterior (para referencia)
    """
    import re
    
    resultado = {
        "campos_ok": [],
        "campos_faltantes": [],
        "campos_incorrectos": [],
        "problemas": [],
        "sugerencias": [],
        "json_anterior": json_anterior,
        "tipo_titular": tipo_titular
    }
    
    campos_requeridos = [
        "notario", "numero_escritura", "fecha_documento", 
        "tipo_titular", "titulares", "adquirientes",
        "monto_operacion", "tipo_moneda"
    ]
    
    if json_anterior:
        # Analizar qué campos están bien
        for campo in campos_requeridos:
            if campo in json_anterior:
                valor = json_anterior[campo]
                # Verificar si el valor es válido
                if valor is None:
                    resultado["campos_faltantes"].append(campo)
                elif isinstance(valor, list):
                    if len(valor) > 0:
                        resultado["campos_ok"].append(campo)
                    else:
                        resultado["campos_faltantes"].append(campo)
                elif isinstance(valor, str):
                    if valor.strip() and valor != NO_ENCONTRADO:
                        resultado["campos_ok"].append(campo)
                    else:
                        resultado["campos_faltantes"].append(campo)
                elif isinstance(valor, (int, float)):
                    resultado["campos_ok"].append(campo)
                else:
                    resultado["campos_ok"].append(campo)
            else:
                resultado["campos_faltantes"].append(campo)
        
        # Detectar problemas específicos
        
        # Problema 1: tipo_titular en lugar incorrecto
        if "titulares" in json_anterior and isinstance(json_anterior["titulares"], list):
            for i, titular in enumerate(json_anterior["titulares"]):
                if isinstance(titular, dict) and "tipo_titular" in titular:
                    resultado["problemas"].append(
                        f"tipo_titular está DENTRO de titulares[{i}], debe ir en la RAÍZ del JSON"
                    )
                    resultado["sugerencias"].append(
                        "Mueve 'tipo_titular' fuera de titulares, al nivel principal del JSON"
                    )
        
        # Problema 2: nombres de campos incorrectos
        nombres_incorrectos = {
            "nombre_titular": "nombre",
            "nombre_completo": "nombre",
            "razon_social": "nombre",
            "actua": "actua_por",
            "num_escritura": "numero_escritura",
            "fecha": "fecha_documento",
            "fecha_escritura": "fecha_documento",
            "monto": "monto_operacion",
            "precio": "monto_operacion",
            "moneda": "tipo_moneda",
        }
        
        def buscar_nombres_incorrectos(obj, path=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if key in nombres_incorrectos:
                        resultado["problemas"].append(
                            f"Campo incorrecto: '{key}' → debe ser '{nombres_incorrectos[key]}'"
                        )
                        resultado["campos_incorrectos"].append(key)
                    buscar_nombres_incorrectos(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    buscar_nombres_incorrectos(item, f"{path}[{i}]")
        
        buscar_nombres_incorrectos(json_anterior)
        
        # Problema 3: representante como string (debe ser objeto o null)
        if "titulares" in json_anterior:
            for i, titular in enumerate(json_anterior.get("titulares", [])):
                if isinstance(titular, dict):
                    rep = titular.get("representante")
                    if isinstance(rep, str):
                        resultado["problemas"].append(
                            f"titulares[{i}].representante es STRING, debe ser OBJETO o null"
                        )
                        resultado["sugerencias"].append(
                            "Cambia representante a un objeto con: nombre, en_calidad, escritura, bis, fecha_poder"
                        )
        
        # Problema 4: numero_escritura como string
        if "numero_escritura" in json_anterior:
            num = json_anterior["numero_escritura"]
            if isinstance(num, str):
                resultado["problemas"].append(
                    f"numero_escritura es STRING ('{num}'), debe ser INTEGER"
                )
                resultado["sugerencias"].append(
                    "Quita las comillas de numero_escritura, debe ser un número sin comillas"
                )
        
        # Problema 5: Empresa sin representante
        if tipo_titular == "empresa" and "titulares" in json_anterior:
            for i, titular in enumerate(json_anterior.get("titulares", [])):
                if isinstance(titular, dict):
                    rep = titular.get("representante")
                    if rep is None:
                        resultado["problemas"].append(
                            f"titulares[{i}] es EMPRESA pero no tiene representante (es OBLIGATORIO)"
                        )
                        resultado["sugerencias"].append(
                            "Las empresas SIEMPRE deben tener representante. Busca quién representa a la empresa."
                        )
    
    # Parsear errores de Pydantic
    if error_validacion:
        # Buscar campos requeridos faltantes
        matches = re.findall(r'(\w+)\s+Field required', error_validacion)
        for campo in matches:
            if campo not in resultado["campos_faltantes"]:
                resultado["campos_faltantes"].append(campo)
        
        # Buscar errores de tipo
        if "Input should be a valid integer" in error_validacion:
            resultado["sugerencias"].append(
                "Hay campos que deberían ser números pero son texto. Revisa numero_escritura y edad."
            )
    
    return resultado


def formatear_feedback_para_prompt(analisis: dict) -> str:
    """
    Convierte el análisis de feedback en texto para el prompt.
    
    Args:
        analisis: Diccionario generado por generar_feedback_error
    
    Returns:
        String formateado para incluir en el prompt
    """
    import json
    
    lines = []
    lines.append("=" * 50)
    lines.append("🔄 CORRECCIÓN REQUERIDA")
    lines.append("=" * 50)
    
    # Tipo titular (mantener consistencia con clasificación)
    if analisis.get("tipo_titular"):
        lines.append(f"\n⚠️ IMPORTANTE: El tipo de titular es {analisis['tipo_titular'].upper()}")
        lines.append(f"   NO cambies esto, ya fue clasificado correctamente.")
    
    # Campos OK
    if analisis["campos_ok"]:
        lines.append(f"\n✅ CAMPOS CORRECTOS (no los cambies):")
        lines.append(f"   {', '.join(analisis['campos_ok'])}")
    
    # Campos faltantes
    if analisis["campos_faltantes"]:
        lines.append(f"\n❌ CAMPOS FALTANTES (agrégalos):")
        for campo in analisis["campos_faltantes"]:
            lines.append(f"   - {campo}")
    
    # Campos con nombre incorrecto
    if analisis["campos_incorrectos"]:
        lines.append(f"\n⚠️ CAMPOS CON NOMBRE INCORRECTO:")
        for campo in analisis["campos_incorrectos"]:
            lines.append(f"   - {campo}")
    
    # Problemas detectados
    if analisis["problemas"]:
        lines.append(f"\n🔍 PROBLEMAS DETECTADOS:")
        for i, problema in enumerate(analisis["problemas"], 1):
            lines.append(f"   {i}. {problema}")
    
    # Sugerencias
    if analisis["sugerencias"]:
        lines.append(f"\n💡 SUGERENCIAS DE CORRECCIÓN:")
        for i, sugerencia in enumerate(analisis["sugerencias"], 1):
            lines.append(f"   {i}. {sugerencia}")
    
    # JSON anterior (truncado)
    if analisis.get("json_anterior"):
        lines.append(f"\n📋 TU JSON ANTERIOR:")
        lines.append("-" * 30)
        try:
            json_str = json.dumps(analisis["json_anterior"], indent=2, ensure_ascii=False)
            if len(json_str) > 1500:
                json_str = json_str[:1500] + "\n... (truncado)"
            lines.append(json_str)
        except:
            lines.append(str(analisis["json_anterior"])[:1500])
    
    lines.append("\n" + "=" * 50)
    lines.append("Corrige los problemas y devuelve el JSON completo.")
    lines.append("=" * 50)
    
    return "\n".join(lines)


def analizar_json_parcial(json_data: dict, tipo_titular: str = None) -> dict:
    """
    Analiza un JSON parcial y devuelve información detallada.
    
    MEJORA: Ahora también detecta problemas específicos en la estructura.
    
    Args:
        json_data: JSON a analizar
        tipo_titular: Tipo clasificado ("empresa" o "persona") para reglas específicas
    
    Returns:
        dict con campos_encontrados, campos_faltantes, porcentaje, problemas_detectados
    """
    campos_requeridos = [
        "notario", "numero_escritura", "fecha_documento", 
        "tipo_titular", "titulares", "adquirientes",
        "monto_operacion", "tipo_moneda"
    ]
    
    encontrados = []
    faltantes = []
    problemas = []
    
    for campo in campos_requeridos:
        if campo in json_data and json_data[campo]:
            valor = json_data[campo]
            if isinstance(valor, list) and len(valor) > 0:
                encontrados.append(campo)
            elif isinstance(valor, str) and valor.strip() and valor != NO_ENCONTRADO:
                encontrados.append(campo)
            elif isinstance(valor, (int, float)):
                encontrados.append(campo)
            else:
                faltantes.append(campo)
        else:
            faltantes.append(campo)
    
    # Detectar problemas específicos
    
    # Problema 1: tipo_titular en lugar incorrecto
    if "titulares" in json_data and isinstance(json_data["titulares"], list):
        for i, titular in enumerate(json_data["titulares"]):
            if isinstance(titular, dict):
                if "tipo_titular" in titular:
                    problemas.append(
                        f"tipo_titular dentro de titulares[{i}], debe ir en raíz"
                    )
    
    # Problema 2: nombres de campos incorrectos
    nombres_incorrectos = ["nombre_titular", "nombre_completo", "razon_social"]
    if "titulares" in json_data:
        for i, titular in enumerate(json_data.get("titulares", [])):
            if isinstance(titular, dict):
                for nombre_inc in nombres_incorrectos:
                    if nombre_inc in titular:
                        problemas.append(
                            f"titulares[{i}] usa '{nombre_inc}', debe ser 'nombre'"
                        )
    
    # Problema 3: representante como string
    if "titulares" in json_data:
        for i, titular in enumerate(json_data.get("titulares", [])):
            if isinstance(titular, dict):
                rep = titular.get("representante")
                if isinstance(rep, str):
                    problemas.append(
                        f"titulares[{i}].representante es string, debe ser objeto"
                    )
    
    # Problema 4: numero_escritura como string
    if "numero_escritura" in json_data:
        num = json_data["numero_escritura"]
        if isinstance(num, str):
            problemas.append(
                f"numero_escritura es string, debe ser integer"
            )
    
    # Problema 5: Empresa sin representante (solo si sabemos el tipo)
    tipo = tipo_titular or json_data.get("tipo_titular", "")
    if tipo == "empresa" and "titulares" in json_data:
        for i, titular in enumerate(json_data.get("titulares", [])):
            if isinstance(titular, dict):
                rep = titular.get("representante")
                if rep is None:
                    problemas.append(
                        f"titulares[{i}] es empresa pero no tiene representante"
                    )
    
    porcentaje = (len(encontrados) / len(campos_requeridos)) * 100
    
    return {
        "campos_encontrados": encontrados,
        "campos_faltantes": faltantes,
        "porcentaje": round(porcentaje, 1),
        "problemas_detectados": problemas
    }


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    import json
    
    print("=" * 60)
    print("PRUEBA DE MODELOS PYDANTIC")
    print("=" * 60)
    
    # JSON de prueba (incompleto)
    json_prueba = {
        "notario": "GUILLERMO LOZA RAMÍREZ",
        "numero_escritura": 18226,
        "tipo_titular": "empresa",
        "titulares": [
            {"nombre": "DESARROLLO TURISTICO LOS COCOS S.A. de C.V."}
        ]
    }
    
    escritura = validar_json_flexible(json_prueba)
    reporte = escritura.generar_reporte()
    
    print(f"\n📊 Campos encontrados: {reporte['resumen']['campos_encontrados']}/8")
    print(f"📊 Porcentaje: {reporte['resumen']['porcentaje_exito']}%")
