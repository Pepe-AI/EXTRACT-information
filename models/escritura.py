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

NO_ENCONTRADO = None  # Valor por defecto cuando no se encuentra un dato


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
    tipo: Optional[str] = Field(default=None, description="Tipo: 'empresa' o 'persona'")
    actua_por: Optional[str] = Field(default=NO_ENCONTRADO)
    representante: Optional[RepresentanteFlexible] = Field(default=None)

    model_config = {"extra": "allow"}


class AdquirienteFlexible(BaseModel):
    """Adquiriente con todos los campos opcionales."""

    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    tipo: Optional[str] = Field(default=None, description="Tipo: 'empresa' o 'persona'")
    actua_por: Optional[str] = Field(default=NO_ENCONTRADO)
    estado_civil: Optional[Union[str, bool]] = Field(default=False, description="Estado civil o false si no existe")
    tipo_sociedad: Optional[Union[str, bool]] = Field(default=False, description="Tipo de sociedad conyugal o false si no existe")
    edad: Optional[Union[int, bool]] = Field(default=False, description="Edad o false si no existe")
    rfc: Optional[Union[str, bool]] = Field(default=False, description="RFC o false si no existe")
    curp: Optional[Union[str, bool]] = Field(default=False, description="CURP o false si no existe")
    representante: Optional[RepresentanteFlexible] = Field(default=None, description="Representante o null si no existe")

    model_config = {"extra": "allow"}


class EscrituraPublicaFlexible(BaseModel):
    """
    Modelo FLEXIBLE - Acepta cualquier dato que venga.
    """

    numero_escritura: Optional[int] = Field(default=None)
    fecha_documento: Optional[str] = Field(default=NO_ENCONTRADO)
    numero_notaria: Optional[Union[str, int]] = Field(default=NO_ENCONTRADO)
    municipio: Optional[str] = Field(default=NO_ENCONTRADO)
    nombre_notario: Optional[str] = Field(default=NO_ENCONTRADO)

    tipo_titular: Optional[str] = Field(
        default=NO_ENCONTRADO,
        description="DEPRECATED: Usar campo 'tipo' individual en cada titular/adquiriente"
    )
    titulares: Optional[List[TitularFlexible]] = Field(default_factory=list)
    adquirientes: Optional[List[AdquirienteFlexible]] = Field(default_factory=list)
    monto_operacion: Optional[str] = Field(default=NO_ENCONTRADO)
    valor_catastral: Optional[str] = Field(default=None)
    curps: Optional[List[str]] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @field_validator('numero_notaria', mode='before')
    @classmethod
    def convertir_numero_notaria_a_string(cls, v):
        """Convierte numero_notaria a string si viene como número."""
        if v is None:
            return NO_ENCONTRADO
        if isinstance(v, int):
            return str(v)
        return v
    
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
        """
        encontrados = {}

        if self.numero_escritura is not None:
            encontrados["numero_escritura"] = self.numero_escritura
        if self.fecha_documento and self.fecha_documento != NO_ENCONTRADO:
            encontrados["fecha_documento"] = self.fecha_documento
        if self.numero_notaria and self.numero_notaria != NO_ENCONTRADO:
            encontrados["numero_notaria"] = self.numero_notaria
        if self.municipio and self.municipio != NO_ENCONTRADO:
            encontrados["municipio"] = self.municipio
        if self.nombre_notario and self.nombre_notario != NO_ENCONTRADO:
            encontrados["nombre_notario"] = self.nombre_notario
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
        if self.curps:
            encontrados["curps"] = self.curps

        return encontrados
    
    def get_campos_no_encontrados(self) -> List[str]:
        """
        Devuelve lista de campos que NO se encontraron.
        """
        no_encontrados = []

        if self.numero_escritura is None:
            no_encontrados.append("numero_escritura")
        if not self.fecha_documento or self.fecha_documento == NO_ENCONTRADO:
            no_encontrados.append("fecha_documento")
        if not self.numero_notaria or self.numero_notaria == NO_ENCONTRADO:
            no_encontrados.append("numero_notaria")
        if not self.municipio or self.municipio == NO_ENCONTRADO:
            no_encontrados.append("municipio")
        if not self.nombre_notario or self.nombre_notario == NO_ENCONTRADO:
            no_encontrados.append("nombre_notario")
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

        total_campos = 9  # numero_escritura, fecha_documento, numero_notaria, municipio, nombre_notario, tipo_titular, titulares, adquirientes, monto_operacion
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
    tipo: Optional[str] = Field(default=None, description="Tipo: 'empresa' o 'persona'")
    actua_por: str = Field(..., description="En qué calidad actúa")
    representante: Optional[Representante] = Field(default=None)


class Adquiriente(BaseModel):
    """Adquiriente con campos obligatorios."""

    nombre: str = Field(..., description="Nombre del adquiriente")
    tipo: Optional[str] = Field(default=None, description="Tipo: 'empresa' o 'persona'")
    actua_por: str = Field(..., description="En qué calidad actúa")
    estado_civil: str = Field(..., description="Estado civil")
    tipo_sociedad: Optional[str] = Field(default=None)
    edad: Optional[int] = Field(default=None)
    rfc: Union[str, bool] = Field(default=False)
    curp: Union[str, bool] = Field(default=False)
    representante: Optional[Representante] = Field(default=None)


class EscrituraPublica(BaseModel):
    """
    Modelo ESTRICTO - Valida que los campos obligatorios estén presentes.
    """

    numero_escritura: int = Field(..., description="Número de escritura")
    fecha_documento: str = Field(..., description="Fecha del documento")
    numero_notaria: Union[str, int] = Field(..., description="Número de notaría")
    municipio: str = Field(..., description="Municipio de la notaría")
    nombre_notario: str = Field(..., description="Nombre del notario")

    tipo_titular: Optional[str] = Field(
        default=None,
        description="DEPRECATED: Usar campo 'tipo' individual en cada titular/adquiriente. Valores: 'empresa' o 'persona'"
    )
    titulares: List[Titular] = Field(..., min_length=1)
    adquirientes: List[Adquiriente] = Field(..., min_length=1)
    monto_operacion: str = Field(..., description="Monto de la operación")
    valor_catastral: Optional[str] = Field(default=None)
    curps: Optional[List[str]] = Field(default_factory=list)
    
    @field_validator('numero_escritura')
    @classmethod
    def validar_numero(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Número de escritura debe ser mayor a 0")
        return v
    
    @model_validator(mode='after')
    def validar_representantes(self):
        """
        Valida representantes según tipo individual de titular/adquiriente.

        REGLAS:
        - Si titular.tipo = "empresa" → DEBE tener representante (advertencia)
        - Si titular.tipo = "persona" → representante OPCIONAL
        - Si adquiriente.tipo = "empresa" → DEBE tener representante (advertencia)
        - Si adquiriente.tipo = "persona" → representante OPCIONAL
        - Si tipo = None → detectar por nombre con regex
        """
        import re

        # Patrones de empresa (movidos de clasificador.py)
        PATRONES_EMPRESA = [
            r'\bS\.?\s*A\.?\s*(?:DE\s*)?C\.?\s*V\.?\b',
            r'\bS\.?\s*DE\s*R\.?\s*L\.?\b',
            r'\bS\.?\s*A\.?\s*B\.?\b',
            r'\bS\.?\s*C\.?\b',
            r'\bA\.?\s*C\.?\b',
            r'\bI\.?\s*A\.?\s*P\.?\b',
            r'\bINSTITUTO\b',
            r'\bSECRETAR[IÍ]A\b',
            r'\bGOBIERNO\b',
            r'\bMUNICIPIO\b',
            r'\bAYUNTAMIENTO\b',
            r'\bFIDEICOMISO\b',
            r'\bINMOBILIARIA\b',
            r'\bCONSTRUCTORA\b',
            r'\bSOCIEDAD\b',
            r'\bFUNDACI[OÓ]N\b',
            r'\bASAMBLEA\b',
            r'\bASOCIACI[OÓ]N\b',
        ]

        def detectar_tipo_por_nombre(nombre: str) -> Optional[str]:
            """Detecta si nombre es empresa o persona por regex."""
            if not nombre:
                return None
            nombre_upper = nombre.upper()
            for patron in PATRONES_EMPRESA:
                if re.search(patron, nombre_upper, re.IGNORECASE):
                    return "empresa"
            return "persona"

        # Validar titulares
        for i, titular in enumerate(self.titulares):
            tipo = titular.tipo or detectar_tipo_por_nombre(titular.nombre)

            if tipo == "empresa" and titular.representante is None:
                # Solo advertencia, no error estricto
                print(f"⚠️ Advertencia: Titular #{i+1} '{titular.nombre}' "
                      f"parece empresa pero no tiene representante")

        # Validar adquirientes
        for i, adq in enumerate(self.adquirientes):
            tipo = adq.tipo or detectar_tipo_por_nombre(adq.nombre)

            if tipo == "empresa" and adq.representante is None:
                print(f"⚠️ Advertencia: Adquiriente #{i+1} '{adq.nombre}' "
                      f"parece empresa pero no tiene representante")

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
        "numero_escritura", "fecha_documento", "numero_notaria",
        "municipio", "nombre_notario", "tipo_titular",
        "titulares", "adquirientes", "monto_operacion"
    ]


def get_campos_no_obligatorios() -> List[str]:
    """Lista de campos no obligatorios."""
    return ["valor_catastral", "curps"]


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
        "tipo_titular": "tipo",  # Mapear tipo_titular a tipo individual
    }

    resultado = {}
    for key, value in titular.items():
        key_lower = key.lower().strip()
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
        "actua": "actua_por",
        "tipo_adquiriente": "tipo",  # Mapear tipo_adquiriente a tipo individual
    }

    resultado = {}
    for key, value in adq.items():
        key_lower = key.lower().strip()
        key_norm = mapeo.get(key_lower, key_lower)

        # Normalizar representante si viene como string
        if key_norm == "representante" and isinstance(value, str):
            value = {"nombre": value} if value.strip() else None

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
        "numero_escritura", "fecha_documento", "numero_notaria",
        "municipio", "nombre_notario", "tipo_titular",
        "titulares", "adquirientes", "monto_operacion"
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
        "numero_escritura": 123,
        "fecha_documento": "5 de mayo de 2023",
        "numero_notaria": "45",
        "municipio": "Tepic, Nayarit",
        "nombre_notario": "RIGOBERTO OCHOA TORRES",
        "tipo_titular": "empresa",
        "titulares": [
            {"nombre": "Empresa Test", "actua_por": "representación"}
        ]
    }

    escritura = validar_json_flexible(json_prueba)
    reporte = escritura.generar_reporte()

    print(f"\nCampos encontrados: {reporte['resumen']['campos_encontrados']}/9")
    print(f"Porcentaje: {reporte['resumen']['porcentaje_exito']}%")
