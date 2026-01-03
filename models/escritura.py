"""
models/escritura.py - Modelos Pydantic con validación flexible

ENFOQUE FLEXIBLE:
=================
- Modelo ESTRICTO: Para intentar primero (campos obligatorios)
- Modelo FLEXIBLE: Si falla el estricto, acepta lo que hay
- Reporte: Muestra qué campos se encontraron y cuáles no

VALOR POR DEFECTO PARA CAMPOS NO ENCONTRADOS:
============================================
Cuando un campo no se encuentra, se usa: "NO SE ENCONTRÓ DATO"
Para números: None
Para booleanos: False
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
    """Representante con todos los campos opcionales."""
    
    nombre: Optional[str] = Field(default=NO_ENCONTRADO)
    en_calidad: Optional[str] = Field(default=NO_ENCONTRADO)
    escritura: Optional[str] = Field(default=NO_ENCONTRADO)
    bis: Optional[bool] = Field(default=False)
    fecha_poder: Optional[str] = Field(default=NO_ENCONTRADO)
    
    model_config = {"extra": "allow"}  # Permite campos adicionales


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
    
    model_config = {"extra": "allow"}  # Permite campos adicionales de DeepSeek
    
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
        
        total_campos = 8  # Campos principales
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
    """Representante con campos obligatorios."""
    
    nombre: str = Field(..., description="Nombre del representante")
    en_calidad: str = Field(..., description="En qué calidad actúa")
    escritura: str = Field(..., description="Número de escritura del poder")
    bis: bool = Field(default=False, description="Si tiene bis")
    fecha_poder: str = Field(..., description="Fecha del poder")


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
    
    Se usa para el primer intento de validación.
    Si falla, se usa EscrituraPublicaFlexible.
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
        """Si es empresa, todos los titulares deben tener representante."""
        if self.tipo_titular.lower() == "empresa":
            for i, titular in enumerate(self.titulares):
                if titular.representante is None:
                    raise ValueError(f"Titular #{i+1} es empresa y debe tener representante")
        return self


# =============================================================================
# MODELO DE RESPUESTA
# =============================================================================

class ExtractionResponse(BaseModel):
    """Respuesta de la API de extracción."""
    
    success: bool = Field(..., description="Si la extracción fue exitosa")
    validacion_estricta: bool = Field(default=False, description="Si pasó validación estricta")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Datos extraídos")
    campos_encontrados: int = Field(default=0)
    campos_no_encontrados: List[str] = Field(default_factory=list)
    porcentaje_exito: float = Field(default=0.0)
    error: Optional[str] = Field(default=None)
    processing_time: Optional[float] = Field(default=None)
    model_used: Optional[str] = Field(default=None)
    intentos_realizados: int = Field(default=0)


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
    # Normalizar nombres de campos comunes
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
        
        # Normalizar titulares
        if key_norm == "titulares" and isinstance(value, list):
            value = [_normalizar_titular(t) for t in value if isinstance(t, dict)]
        
        # Normalizar adquirientes
        if key_norm == "adquirientes" and isinstance(value, list):
            value = [_normalizar_adquiriente(a) for a in value if isinstance(a, dict)]
        
        resultado[key_norm] = value
    
    # Extraer tipo_titular si está dentro de titulares
    if "tipo_titular" not in resultado and "titulares" in resultado:
        for t in resultado.get("titulares", []):
            if "tipo_titular" in t:
                resultado["tipo_titular"] = t.pop("tipo_titular")
                break
    
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
        
        # Saltar tipo_titular (va en raíz)
        if key_lower == "tipo_titular":
            continue
            
        key_norm = mapeo.get(key_lower, key_lower)
        
        # Normalizar representante si es string
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


def generar_feedback_error(error_validacion: str, json_anterior: dict = None) -> str:
    """
    Genera un mensaje de feedback INTELIGENTE para DeepSeek.
    
    MEJORA: Incluye el JSON del intento anterior para que DeepSeek
    CORRIJA en lugar de empezar desde cero.
    
    Args:
        error_validacion: Error de Pydantic
        json_anterior: JSON del intento anterior (para corregir)
        
    Returns:
        Mensaje de feedback contextual
    """
    import json
    
    # Analizar qué campos están bien y cuáles faltan
    campos_encontrados = []
    campos_faltantes = []
    
    campos_requeridos = [
        "notario", "numero_escritura", "fecha_documento", 
        "tipo_titular", "titulares", "adquirientes",
        "monto_operacion", "tipo_moneda"
    ]
    
    if json_anterior:
        for campo in campos_requeridos:
            if campo in json_anterior and json_anterior[campo]:
                # Verificar que no sea valor vacío
                valor = json_anterior[campo]
                if isinstance(valor, list) and len(valor) > 0:
                    campos_encontrados.append(campo)
                elif isinstance(valor, str) and valor.strip():
                    campos_encontrados.append(campo)
                elif isinstance(valor, (int, float)) and valor is not None:
                    campos_encontrados.append(campo)
                else:
                    campos_faltantes.append(campo)
            else:
                campos_faltantes.append(campo)
    
    # Construir feedback contextual
    feedback_parts = []
    
    feedback_parts.append("=" * 50)
    feedback_parts.append("CORRECCIÓN REQUERIDA")
    feedback_parts.append("=" * 50)
    
    # Mostrar JSON anterior si existe
    if json_anterior:
        feedback_parts.append("\n📋 TU RESPUESTA ANTERIOR:")
        feedback_parts.append("-" * 30)
        try:
            json_str = json.dumps(json_anterior, indent=2, ensure_ascii=False)
            # Limitar tamaño para no exceder contexto
            if len(json_str) > 2000:
                json_str = json_str[:2000] + "\n... (truncado)"
            feedback_parts.append(json_str)
        except:
            feedback_parts.append(str(json_anterior)[:2000])
    
    # Mostrar análisis de campos
    if campos_encontrados:
        feedback_parts.append(f"\n✅ CAMPOS QUE YA TIENES BIEN ({len(campos_encontrados)}):")
        feedback_parts.append(f"   {', '.join(campos_encontrados)}")
        feedback_parts.append("   → MANTÉN estos valores, no los cambies")
    
    if campos_faltantes:
        feedback_parts.append(f"\n❌ CAMPOS QUE FALTAN O ESTÁN MAL ({len(campos_faltantes)}):")
        feedback_parts.append(f"   {', '.join(campos_faltantes)}")
        feedback_parts.append("   → BUSCA estos datos en el documento y agrégalos")
    
    # Mostrar error específico
    feedback_parts.append("\n🔍 ERROR DE VALIDACIÓN:")
    feedback_parts.append("-" * 30)
    # Simplificar el error para que sea más legible
    error_simplificado = _simplificar_error_pydantic(error_validacion)
    feedback_parts.append(error_simplificado)
    
    # Instrucciones de corrección
    feedback_parts.append("\n📝 INSTRUCCIONES DE CORRECCIÓN:")
    feedback_parts.append("-" * 30)
    feedback_parts.append("1. MANTÉN los campos que ya están bien")
    feedback_parts.append("2. AGREGA los campos faltantes buscándolos en el documento")
    feedback_parts.append("3. CORRIGE los nombres de campos:")
    feedback_parts.append('   - Usa "nombre" (no "nombre_titular")')
    feedback_parts.append('   - Usa "actua_por" (no "actua")')
    feedback_parts.append('   - "tipo_titular" va en la RAÍZ, no dentro de titulares')
    feedback_parts.append("4. Si no encuentras un dato, usa:")
    feedback_parts.append('   - "NO SE ENCONTRÓ DATO" para textos')
    feedback_parts.append('   - null para números')
    feedback_parts.append('   - false para RFC/CURP no encontrados')
    
    feedback_parts.append("\n" + "=" * 50)
    feedback_parts.append("Responde SOLO con el JSON corregido y completo.")
    feedback_parts.append("=" * 50)
    
    return "\n".join(feedback_parts)


def _simplificar_error_pydantic(error: str) -> str:
    """
    Simplifica el error de Pydantic para que sea más legible.
    
    Transforma:
        "notario Field required [type=missing, input_value=..."
    En:
        "- notario: Campo requerido (falta en el JSON)"
    """
    import re
    
    lineas_simplificadas = []
    
    # Buscar patrones de error comunes
    # Patrón: "campo Field required"
    matches_required = re.findall(r'(\w+)\s+Field required', error)
    for campo in matches_required:
        lineas_simplificadas.append(f"- {campo}: Campo REQUERIDO (falta en el JSON)")
    
    # Patrón: "campo.0.subcampo Field required" (campos anidados)
    matches_nested = re.findall(r'(\w+)\.(\d+)\.(\w+)\s+Field required', error)
    for lista, indice, campo in matches_nested:
        lineas_simplificadas.append(f"- {lista}[{indice}].{campo}: Campo REQUERIDO en {lista}")
    
    # Patrón: "Input should be a valid dictionary"
    if "Input should be a valid dictionary" in error:
        lineas_simplificadas.append("- representante: Debe ser un OBJETO {}, no un string")
    
    # Si no encontramos patrones conocidos, mostrar error resumido
    if not lineas_simplificadas:
        # Tomar solo las primeras líneas del error
        lineas = error.split('\n')[:5]
        lineas_simplificadas = [f"  {l.strip()}" for l in lineas if l.strip()]
    
    return "\n".join(lineas_simplificadas)


def analizar_json_parcial(json_data: dict) -> dict:
    """
    Analiza un JSON parcial y devuelve información sobre qué tiene y qué falta.
    
    Útil para el feedback de retry.
    
    Returns:
        {
            "campos_encontrados": ["notario", "titulares"],
            "campos_faltantes": ["numero_escritura", ...],
            "porcentaje": 25.0,
            "problemas_detectados": ["tipo_titular dentro de titular", ...]
        }
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
            # Verificar que no sea vacío
            if isinstance(valor, list) and len(valor) > 0:
                encontrados.append(campo)
            elif isinstance(valor, str) and valor.strip() and valor != "NO SE ENCONTRÓ DATO":
                encontrados.append(campo)
            elif isinstance(valor, (int, float)):
                encontrados.append(campo)
            else:
                faltantes.append(campo)
        else:
            faltantes.append(campo)
    
    # Detectar problemas comunes
    if "titulares" in json_data:
        for i, titular in enumerate(json_data.get("titulares", [])):
            if isinstance(titular, dict):
                if "tipo_titular" in titular:
                    problemas.append(f"tipo_titular está dentro de titulares[{i}], debe ir en la raíz")
                if "nombre_titular" in titular:
                    problemas.append(f'titulares[{i}] usa "nombre_titular", debe ser "nombre"')
                if "nombre_completo" in titular:
                    problemas.append(f'titulares[{i}] usa "nombre_completo", debe ser "nombre"')
                if isinstance(titular.get("representante"), str):
                    problemas.append(f"titulares[{i}].representante es string, debe ser objeto")
    
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
    print("PRUEBA DE MODELO FLEXIBLE")
    print("=" * 60)
    
    # JSON incompleto de DeepSeek
    json_incompleto = {
        "titulares": [
            {
                "tipo_titular": "empresa",
                "nombre_titular": "DESARROLLOS S.A. DE C.V.",
                "representante": "Juan Pérez"
            }
        ]
    }
    
    print("\n📋 JSON de entrada (incompleto):")
    print(json.dumps(json_incompleto, indent=2, ensure_ascii=False))
    
    # Validar con modelo flexible
    escritura = validar_json_flexible(json_incompleto)
    
    # Generar reporte
    reporte = escritura.generar_reporte()
    
    print("\n📊 REPORTE DE EXTRACCIÓN:")
    print("-" * 40)
    print(f"✅ Campos encontrados: {reporte['resumen']['campos_encontrados']}/{reporte['resumen']['total_campos']}")
    print(f"❌ Campos no encontrados: {reporte['resumen']['campos_no_encontrados']}")
    print(f"📈 Porcentaje de éxito: {reporte['resumen']['porcentaje_exito']}%")
    
    print("\n📋 Campos faltantes:")
    for campo in reporte['campos_faltantes']:
        print(f"   - {campo}")
    
    print("\n✅ Datos encontrados:")
    print(json.dumps(reporte['datos_encontrados'], indent=2, ensure_ascii=False))
