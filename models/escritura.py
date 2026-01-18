"""
models/escritura.py - Modelos Pydantic para escrituras públicas

DOS MODOS DE VALIDACIÓN:
========================
1. ESTRICTO (EscrituraPublica): Todos los campos obligatorios
2. FLEXIBLE (EscrituraPublicaFlexible): Acepta datos parciales
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

class NotarioFlexible(BaseModel):
    """
    Modelo FLEXIBLE para datos del notario.
    
    ESTRUCTURA:
    ===========
    - nombre: Nombre completo del notario
    - numero_notario: Número de notaría (2-3 dígitos, ej: "45", "123")
    - municipio: Municipio donde ejerce
    - escritura: Número de escritura (4-7 dígitos, ej: "2307", "1234567")
    - fecha_documento: Fecha del documento notarial
    
    NOTA: Este modelo se usa dentro de un array, pero solo puede
    existir UN notario por documento.
    """
    
    nombre: Optional[str] = Field(default=NO_ENCONTRADO, description="Nombre del notario")
    numero_notario: Optional[Union[str, int]] = Field(
        default=NO_ENCONTRADO, 
        description="Número de notaría (2-3 dígitos)"
    )
    municipio: Optional[str] = Field(default=NO_ENCONTRADO, description="Municipio de la notaría")
    escritura: Optional[Union[str, int]] = Field(
        default=NO_ENCONTRADO, 
        description="Número de escritura (4-7 dígitos)"
    )
    fecha_documento: Optional[str] = Field(default=NO_ENCONTRADO, description="Fecha del documento")
    
    model_config = {"extra": "allow"}
    
    @field_validator('numero_notario', 'escritura', mode='before')
    @classmethod
    def convertir_numero_a_string(cls, v):
        """
        Convierte números a string para consistencia.
        
        ¿Por qué?
        =========
        El LLM puede devolver estos campos como int o string.
        Los normalizamos siempre a string para evitar inconsistencias.
        
        Ejemplo:
            2307 → "2307"
            "45" → "45"
        """
        if v is None:
            return NO_ENCONTRADO
        if isinstance(v, int):
            return str(v)
        return v


class RepresentanteFlexible(BaseModel):
    """Representante con todos los campos opcionales."""
    
    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    en_calidad: Optional[str] = Field(default=NO_ENCONTRADO)
    escritura: Optional[Union[str, int]] = Field(default=NO_ENCONTRADO)
    bis: Optional[bool] = Field(default=False)
    fecha_poder: Optional[str] = Field(default=NO_ENCONTRADO)
    
    model_config = {"extra": "allow"}
    
    @field_validator('escritura', mode='before')
    @classmethod
    def convertir_escritura_a_string(cls, v):
        if v is None:
            return NO_ENCONTRADO
        if isinstance(v, int):
            return str(v)
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
    
    CAMBIO IMPORTANTE EN notario:
    =============================
    Antes: notario era un string simple
    Ahora: notario es un array con UN objeto que contiene:
        - nombre: Nombre del notario
        - numero_notario: Número de notaría (2-3 dígitos)
        - municipio: Municipio de la notaría
        - escritura: Número de escritura (4-7 dígitos)
        - fecha_documento: Fecha del documento
    
    NOTA: Aunque es array, solo puede existir UN notario.
    """
    
    # notario ahora es una LISTA con un solo elemento
    notario: Optional[List[NotarioFlexible]] = Field(default_factory=list)
    
    # Estos campos se mantienen para compatibilidad, pero los datos
    # principales ahora están en notario[0].escritura y notario[0].fecha_documento
    numero_escritura: Optional[int] = Field(default=None)
    fecha_documento: Optional[str] = Field(default=NO_ENCONTRADO)
    
    tipo_titular: Optional[str] = Field(default=NO_ENCONTRADO)
    titulares: Optional[List[TitularFlexible]] = Field(default_factory=list)
    adquirientes: Optional[List[AdquirienteFlexible]] = Field(default_factory=list)
    monto_operacion: Optional[str] = Field(default=NO_ENCONTRADO)
    valor_catastral: Optional[str] = Field(default=None)
    
    model_config = {"extra": "allow"}
    
    @field_validator('monto_operacion', mode='before')
    @classmethod
    def convertir_monto_a_string(cls, v):
        """
        Convierte monto_operacion a string si viene como número.
        
        ¿Por qué es necesario?
        ======================
        El LLM a veces devuelve:
            "monto_operacion": 0.0       ← float (causa error sin este validador)
            "monto_operacion": 1500000   ← int
        En lugar de:
            "monto_operacion": "$1,500,000.00"  ← str (correcto)
        
        Este validador acepta ambos y los normaliza a string.
        """
        if v is None:
            return NO_ENCONTRADO
        if isinstance(v, (int, float)):
            # Si es 0 o 0.0, probablemente no se encontró el dato
            if v == 0:
                return NO_ENCONTRADO
            # Formatear como moneda mexicana
            return f"${v:,.2f}"
        return v
    
    @field_validator('valor_catastral', mode='before')
    @classmethod
    def convertir_catastral_a_string(cls, v):
        """Convierte valor_catastral a string si viene como número."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            if v == 0:
                return None
            return f"${v:,.2f}"
        return v
    
    def get_campos_encontrados(self) -> Dict[str, Any]:
        """
        Devuelve solo los campos que SÍ se encontraron.
        
        NOTA: Para notario, verificamos si existe el array y tiene datos válidos.
        """
        encontrados = {}
        
        # Verificar notario (nueva estructura como array)
        if self.notario and len(self.notario) > 0:
            notario_obj = self.notario[0]
            # Verificar si tiene al menos el nombre
            if notario_obj.nombre and notario_obj.nombre != NO_ENCONTRADO:
                encontrados["notario"] = [n.model_dump() for n in self.notario]
        
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
        if self.valor_catastral:
            encontrados["valor_catastral"] = self.valor_catastral
            
        return encontrados
    
    def get_campos_no_encontrados(self) -> List[str]:
        """
        Devuelve lista de campos que NO se encontraron.
        
        NOTA: Para notario, verificamos si el array tiene datos válidos.
        """
        no_encontrados = []
        
        # Verificar notario (nueva estructura)
        notario_valido = False
        if self.notario and len(self.notario) > 0:
            notario_obj = self.notario[0]
            if notario_obj.nombre and notario_obj.nombre != NO_ENCONTRADO:
                notario_valido = True
        
        if not notario_valido:
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

        return no_encontrados
    
    def generar_reporte(self) -> Dict[str, Any]:
        """Genera un reporte completo de la extracción."""
        encontrados = self.get_campos_encontrados()
        no_encontrados = self.get_campos_no_encontrados()

        total_campos = 7
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
# MODELOS ESTRICTOS
# =============================================================================

class Notario(BaseModel):
    """
    Modelo ESTRICTO para datos del notario.
    
    ESTRUCTURA:
    ===========
    - nombre: Nombre completo del notario (OBLIGATORIO)
    - numero_notario: Número de notaría, 2-3 dígitos (OBLIGATORIO)
    - municipio: Municipio donde ejerce (OBLIGATORIO)
    - escritura: Número de escritura, 4-7 dígitos (OBLIGATORIO)
    - fecha_documento: Fecha del documento (OBLIGATORIO)
    
    VALIDACIONES:
    =============
    - numero_notario debe tener 2-3 dígitos (ej: "45", "123")
    - escritura debe tener 4-7 dígitos (ej: "2307", "1234567")
    
    ¿Por qué estas validaciones?
    ============================
    En México, los números de notaría típicamente van del 1 al 999,
    mientras que los números de escritura pueden ser mucho más altos
    dependiendo de la antigüedad y actividad de la notaría.
    """
    
    nombre: str = Field(..., description="Nombre del notario")
    numero_notario: Union[str, int] = Field(..., description="Número de notaría (2-3 dígitos)")
    municipio: str = Field(..., description="Municipio de la notaría")
    escritura: Union[str, int] = Field(..., description="Número de escritura (4-7 dígitos)")
    fecha_documento: str = Field(..., description="Fecha del documento")
    
    @field_validator('numero_notario', mode='before')
    @classmethod
    def validar_numero_notario(cls, v):
        """
        Valida y normaliza el número de notario.
        
        REGLAS:
        =======
        - Acepta int o string
        - Convierte a string
        - Debe tener 2-3 dígitos (10-999)
        
        Ejemplos válidos: 45, "45", 123, "123"
        Ejemplos inválidos: 1, "1", 1234, "1234"
        """
        if isinstance(v, int):
            v = str(v)
        
        # Limpiar espacios
        v = str(v).strip()
        
        # Validar longitud (2-3 dígitos)
        if len(v) < 2 or len(v) > 3:
            raise ValueError(
                f"numero_notario debe tener 2-3 dígitos, recibido: '{v}' ({len(v)} dígitos)"
            )
        
        return v
    
    @field_validator('escritura', mode='before')
    @classmethod
    def validar_escritura(cls, v):
        """
        Valida y normaliza el número de escritura.
        
        REGLAS:
        =======
        - Acepta int o string
        - Convierte a string
        - Debe tener 4-7 dígitos (1000-9999999)
        
        Ejemplos válidos: 2307, "2307", 1234567, "1234567"
        Ejemplos inválidos: 123, "123", 12345678, "12345678"
        """
        if isinstance(v, int):
            v = str(v)
        
        # Limpiar espacios
        v = str(v).strip()
        
        # Validar longitud (4-7 dígitos)
        if len(v) < 4 or len(v) > 7:
            raise ValueError(
                f"escritura debe tener 4-7 dígitos, recibido: '{v}' ({len(v)} dígitos)"
            )
        
        return v


class Representante(BaseModel):
    """Representante con campos obligatorios."""
    
    nombre: str = Field(..., description="Nombre del representante")
    en_calidad: str = Field(..., description="En qué calidad actúa")
    escritura: Union[str, int] = Field(..., description="Número de escritura del poder")
    bis: bool = Field(default=False, description="Si tiene bis")
    fecha_poder: str = Field(..., description="Fecha del poder")
    
    @field_validator('escritura', mode='before')
    @classmethod
    def convertir_escritura_a_string(cls, v):
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
    
    CAMBIO EN notario:
    ==================
    Antes: notario era un string simple
    Ahora: notario es un array con exactamente UN objeto Notario
    
    El objeto Notario contiene:
    - nombre: Nombre del notario
    - numero_notario: Número de notaría (2-3 dígitos)
    - municipio: Municipio de la notaría
    - escritura: Número de escritura (4-7 dígitos)
    - fecha_documento: Fecha del documento
    """
    
    # notario ahora es una LISTA con exactamente 1 elemento
    notario: List[Notario] = Field(
        ..., 
        min_length=1, 
        max_length=1,
        description="Array con un solo objeto Notario"
    )
    
    # Estos campos se mantienen para compatibilidad
    numero_escritura: int = Field(..., description="Número de escritura")
    fecha_documento: str = Field(..., description="Fecha del documento")
    
    tipo_titular: str = Field(..., description="empresa o persona")
    titulares: List[Titular] = Field(..., min_length=1)
    adquirientes: List[Adquiriente] = Field(..., min_length=1)
    monto_operacion: str = Field(..., description="Monto de la operación")
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
        Valida representante según tipo de titular.
        
        REGLA:
        - EMPRESA: Representante es OBLIGATORIO
        - PERSONA: Representante es OPCIONAL
        """
        if self.tipo_titular.lower() == "empresa":
            for i, titular in enumerate(self.titulares):
                if titular.representante is None:
                    raise ValueError(
                        f"Titular #{i+1} es EMPRESA y DEBE tener representante"
                    )
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
        "monto_operacion"
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
) -> str:
    """
    Genera feedback para retry basado en el error.
    """
    feedback = []
    feedback.append("=" * 50)
    feedback.append("🔄 CORRECCIÓN REQUERIDA")
    feedback.append("=" * 50)
    
    if tipo_titular:
        feedback.append(f"\n⚠️ TIPO TITULAR: {tipo_titular.upper()}")
    
    if error_validacion:
        feedback.append(f"\n❌ Error: {error_validacion[:300]}")
    
    if json_anterior:
        import json
        feedback.append("\n📋 JSON anterior:")
        feedback.append(json.dumps(json_anterior, indent=2, ensure_ascii=False)[:500])
    
    return "\n".join(feedback)


def analizar_json_parcial(json_data: dict, tipo_titular: str = None) -> dict:
    """
    Analiza un JSON parcial y devuelve información detallada.
    """
    campos_requeridos = [
        "notario", "numero_escritura", "fecha_documento",
        "tipo_titular", "titulares", "adquirientes",
        "monto_operacion"
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
    if "titulares" in json_data and isinstance(json_data["titulares"], list):
        for i, titular in enumerate(json_data["titulares"]):
            if isinstance(titular, dict):
                if "tipo_titular" in titular:
                    problemas.append(
                        f"tipo_titular dentro de titulares[{i}], debe ir en raíz"
                    )
                if "representante_legal" in titular:
                    problemas.append(
                        f"titulares[{i}] tiene representante_legal, debe ser representante objeto"
                    )
    
    if "documento" in json_data:
        problemas.append("Campo 'documento' no permitido en raíz")
    
    porcentaje = (len(encontrados) / len(campos_requeridos)) * 100
    
    return {
        "campos_encontrados": encontrados,
        "campos_faltantes": faltantes,
        "porcentaje": round(porcentaje, 1),
        "problemas_detectados": problemas
    }


if __name__ == "__main__":
    import json
    
    print("=" * 60)
    print("PRUEBA DE MODELOS PYDANTIC")
    print("=" * 60)
    
    json_prueba = {
        "notario": "TEST",
        "numero_escritura": 123,
        "tipo_titular": "empresa",
        "titulares": [
            {"nombre": "Empresa Test", "actua_por": "representación"}
        ]
    }
    
    escritura = validar_json_flexible(json_prueba)
    reporte = escritura.generar_reporte()
    
    print(f"\n📊 Campos encontrados: {reporte['resumen']['campos_encontrados']}/8")
    print(f"📊 Porcentaje: {reporte['resumen']['porcentaje_exito']}%")
