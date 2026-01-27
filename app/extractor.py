"""
app/extractor.py - Extractor con Sistema Plan Z (ABDF + E)

ARQUITECTURA PLAN Z:
====================

┌─────────────────────────────────────────────────────────────────────────────┐
│                           PLAN Z - FLUJO COMPLETO                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐      ┌──────────────┐      ┌─────────────────────┐           │
│  │   PDF    │ ───> │  Azure OCR   │ ───> │   Texto limpio      │           │
│  └──────────┘      └──────────────┘      └──────────┬──────────┘           │
│                                                     │                       │
│                                                     ▼                       │
│                                          ┌──────────────────────┐           │
│                                          │  FASE 1: CLASIFICAR  │           │
│                                          │  (Prompt ligero)     │           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                                     ▼                       │
│                                          ┌──────────────────────┐           │
│                                          │  Plan D: SEGMENTAR   │           │
│                                          │  Dividir en secciones│           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                                     ▼                       │
│                                          ┌──────────────────────┐           │
│                                          │  Plan A: REGEX       │           │
│                                          │  Extracción directa  │           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                                     ▼                       │
│                                          ┌──────────────────────┐           │
│                                          │  FASE 2: LLM GENERAL │           │
│                                          │  Extracción completa │           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                                     ▼                       │
│                                          ┌──────────────────────┐           │
│                                          │  Plan B: VALIDACIÓN  │           │
│                                          │  Cruzar con texto    │           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                          ┌──────────┴───────────┐           │
│                                          │ ¿Campos BAJA conf.?  │           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                          ┌──────────┴───────────┐           │
│                                          ▼                      ▼           │
│                                   ┌─────────────┐        ┌─────────────┐    │
│                                   │ NO: Seguir  │        │ SÍ: Plan E  │    │
│                                   └──────┬──────┘        │ Extracción  │    │
│                                          │               │ individual  │    │
│                                          │               └──────┬──────┘    │
│                                          │                      │           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                                     ▼                       │
│                                          ┌──────────────────────┐           │
│                                          │  Plan F: CONSOLIDAR  │           │
│                                          │  Evaluar calidad     │           │
│                                          └──────────┬───────────┘           │
│                                                     │                       │
│                                                     ▼                       │
│                                              RESULTADO FINAL                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

COMPONENTES DEL PLAN Z:
=======================
- Plan A: Extracción por regex (determinística, alta confianza)
- Plan B: Validación cruzada (detectar alucinaciones del LLM)
- Plan D: Segmentación del documento (optimizar prompts)
- Plan E: Extracción individual (recuperar campos fallidos)
- Plan F: Sistema de confianza (evaluar calidad, marcar revisión)
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field
from pydantic import ValidationError
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# SERVICIOS
# =============================================================================
from services.ollama_service import OllamaService, OllamaConfig, get_ollama_service
from services.azure_ocr_service import AzureOCRService, AzureConfig, get_ocr_service

# =============================================================================
# UTILIDADES EXISTENTES
# =============================================================================
from utils.text_processing import (
    process_deepseek_response,
    clean_ocr_text,
    format_for_prompt,
    extraer_datos_con_regex,
    merge_extractions,
)
from utils.prompt_builder import (
    build_extraction_prompt,
    build_validation_prompt,
    estimate_tokens,
    limpiar_json_extra,
)

# =============================================================================
# MODELOS EXISTENTES
# =============================================================================
from models.escritura import (
    EscrituraPublica,
    EscrituraPublicaFlexible,
    validar_json_flexible,
    generar_feedback_error,
    analizar_json_parcial,
)

# =============================================================================
# ⭐ NUEVOS IMPORTS PARA PLAN Z (ABDF + E)
# =============================================================================
from extraction.segmentador import segmentar_documento
from extraction.validador_cruzado import ValidadorCruzado
from extraction.plan_e_extractor import PlanEExtractor, ResultadoPlanE
from extraction.sistema_confianza import SistemaConfianza

from models.confianza import (
    ResultadoConfianza,
    evaluar_calidad_extraccion,
    NivelResultado,
    NivelConfianza,
    identificar_campos_para_plan_e,
)
from models.secciones import SeccionesDocumento

from utils.text_processing import (
    extraer_todos_regex,
    extraer_estado_civil,
    extraer_representante_adquiriente,
    extraer_numero_instrumento_poder,
    extraer_fecha_poder,
)
from utils.gemini_prompts import (
    build_gemini_prompt_critico,
    build_gemini_prompt_expandido,
    build_gemini_prompt_completo,
    parse_gemini_response,
)


# =============================================================================
# CONFIGURACIÓN GEMINI FALLBACK (Fase 2)
# =============================================================================
GEMINI_FALLBACK_ENABLED = os.getenv("GEMINI_FALLBACK_ENABLED", "false").lower() == "true"


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

@dataclass
class ExtractionConfig:
    """
    Configuración del extractor.
    
    Atributos:
    ==========
    - max_retries: Número máximo de reintentos si falla validación
    - temperature: Temperatura del LLM (0.0 = determinístico)
    - max_tokens: Máximo de tokens en la respuesta
    - max_context_tokens: Máximo de tokens del documento a enviar
    - include_examples: Si incluir ejemplos en el prompt
    - save_thinking: Si guardar el bloque <think> de DeepSeek
    - use_classification: Si usar la Fase 1 de clasificación (RECOMENDADO)
    - use_plan_e: Si usar Plan E para campos problemáticos (RECOMENDADO)
    """
    
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("TEMPERATURE", "0.0"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS", "4096"))
    )
    max_context_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
    )
    include_examples: bool = True
    save_thinking: bool = True
    use_classification: bool = True   # Habilitar sistema híbrido
    use_plan_e: bool = True           # ⭐ NUEVO: Habilitar Plan E


@dataclass
class ExtractionResult:
    """
    Resultado de la extracción.
    
    Atributos principales:
    ======================
    - success: Si la extracción fue exitosa (al menos parcialmente)
    - validacion_estricta: Si pasó validación con todos los campos
    - data: Datos extraídos (diccionario)
    - campos_encontrados: Número de campos extraídos
    - campos_no_encontrados: Lista de campos faltantes
    
    Atributos de clasificación:
    ===========================
    - clasificacion: Resultado de la Fase 1
    - tipo_detectado: "empresa" o "persona"
    - metodo_clasificacion: Cómo se determinó el tipo
    
    ⭐ NUEVOS Atributos del Plan Z:
    ===============================
    - confianza: Nivel de confianza por campo
    - origen: Origen de cada dato (regex, llm, plan_e)
    - requiere_revision: Campos que necesitan revisión humana
    - calidad_general: Porcentaje de calidad de la extracción
    - plan_e_activado: Si se usó Plan E
    - campos_mejorados_plan_e: Campos que mejoró Plan E
    - secciones_detectadas: Secciones del documento identificadas
    
    Atributos de debug:
    ===================
    - thinking: Contenido del bloque <think> de DeepSeek
    - raw_json: JSON crudo antes de validación
    - intentos_realizados: Número de intentos de extracción
    """
    
    success: bool = False
    validacion_estricta: bool = False
    data: Optional[Dict[str, Any]] = None
    reporte: Optional[Dict[str, Any]] = None
    raw_json: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: float = 0.0
    thinking: Optional[str] = None
    ocr_metadata: Dict[str, Any] = field(default_factory=dict)
    model_used: str = ""
    intentos_realizados: int = 0
    retries_used: int = 0  # Alias para compatibilidad
    campos_encontrados: int = 0
    campos_no_encontrados: List[str] = field(default_factory=list)
    
    # Campos para sistema híbrido (existentes)
    clasificacion: Optional[Dict[str, Any]] = None
    tipo_detectado: str = ""
    metodo_clasificacion: str = ""
    
    # ⭐ NUEVOS campos para Plan Z (ABDF + E)
    confianza: Dict[str, str] = field(default_factory=dict)
    origen: Dict[str, str] = field(default_factory=dict)
    requiere_revision: List[str] = field(default_factory=list)
    calidad_general: float = 0.0
    detalles_fallo: Optional[Dict[str, Any]] = None
    
    # Info del Plan E
    plan_e_activado: bool = False
    campos_mejorados_plan_e: List[str] = field(default_factory=list)
    
    # Info de segmentación (Plan D)
    secciones_detectadas: List[str] = field(default_factory=list)


# =============================================================================
# EXTRACTOR PRINCIPAL
# =============================================================================

class EscrituraExtractor:
    """
    Extractor de escrituras públicas con Sistema Plan Z.
    
    FLUJO PLAN Z:
    =============
    1. OCR del PDF (Azure Document Intelligence)
    2. Limpieza del texto
    3. FASE 1: Clasificación (determinar tipo de titular)
    4. Plan D: Segmentación del documento
    5. Plan A: Extracción por regex
    6. FASE 2: Extracción con LLM general
    7. Plan B: Validación cruzada
    8. Plan E: Extracción individual (si hay campos problemáticos)
    9. Plan F: Consolidación y evaluación de calidad
    
    Ejemplo de uso:
    ===============
    >>> extractor = EscrituraExtractor()
    >>> result = extractor.extract("escritura.pdf")
    >>> if result.success:
    ...     print(result.data)
    ...     print(f"Calidad: {result.calidad_general}%")
    ...     print(f"Confianza: {result.confianza}")
    """
    
    def __init__(
        self,
        config: Optional[ExtractionConfig] = None,
        ollama_config: Optional[OllamaConfig] = None,
        azure_config: Optional[AzureConfig] = None
    ):
        """
        Inicializa el extractor.
        
        Args:
            config: Configuración de extracción
            ollama_config: Configuración de Ollama (opcional)
            azure_config: Configuración de Azure OCR (opcional)
        """
        self.config = config or ExtractionConfig()
        self.ollama_service = get_ollama_service(ollama_config)
        self.ocr_service = get_ocr_service(azure_config)

        # FIX: Comentado temporalmente por encoding issues en Windows
        # print(f"🔧 Extractor inicializado (Sistema Plan Z)")
        # print(f"   - Modelo: {self.ollama_service.config.model}")
        # print(f"   - Clasificación previa: {'✅' if self.config.use_classification else '❌'}")
        # print(f"   - Plan E (recuperación): {'✅' if self.config.use_plan_e else '❌'}")
        # print(f"   - Max reintentos: {self.config.max_retries}")
        # print(f"   - Temperature: {self.config.temperature}")
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extrae información de una escritura pública usando Plan Z.
        
        Este es el método principal que orquesta todo el flujo.
        
        Args:
            pdf_path: Ruta al archivo PDF
            
        Returns:
            ExtractionResult con los datos extraídos y metadatos
        """
        
        start_time = time.time()
        result = ExtractionResult(success=False)
        
        try:
            # =================================================================
            # PASO 1: OCR
            # =================================================================
            print(f"\n{'='*60}")
            print(f"📄 PROCESANDO: {Path(pdf_path).name}")
            print(f"{'='*60}")
            
            print(f"\n📝 Paso 1: Extrayendo texto con OCR...")
            ocr_text, ocr_meta = self._step_ocr(pdf_path)
            result.ocr_metadata = ocr_meta
            print(f"   ✅ OCR completado: {ocr_meta.get('pages', '?')} páginas, {len(ocr_text)} caracteres")
            
            # =================================================================
            # PASO 2: Limpiar texto
            # =================================================================
            print(f"\n🧹 Paso 2: Limpiando texto...")
            clean_text = clean_ocr_text(ocr_text)
            formatted_text = format_for_prompt(clean_text, self.config.max_context_tokens)
            print(f"   ✅ Texto limpiado: {len(clean_text)} caracteres")
            print(f"   ✅ Tokens estimados: ~{estimate_tokens(formatted_text)}")
            
            # =================================================================
            # PASO 3: Extracción con LLM (clasificación individual por entidad)
            # =================================================================
            print(f"\n🤖 Paso 3: Extrayendo datos con LLM...")
            
            json_data, intentos, validacion_estricta, thinking = self._fase2_extraer(
                document_text=formatted_text
            )
            
            result.intentos_realizados = intentos
            result.retries_used = intentos
            result.raw_json = json_data
            result.thinking = thinking
            result.model_used = self.ollama_service.config.model

            # =================================================================
            # PASO 4.5: APLICAR CLASIFICACIÓN FALLBACK
            # =================================================================
            if json_data:
                print(f"\n🔍 Paso 4.5: Aplicando clasificación fallback...")
                json_data = self._aplicar_clasificacion_fallback(json_data)

            # =================================================================
            # PASO 5: SEGMENTACIÓN DEL DOCUMENTO (Plan D)
            # =================================================================
            print(f"\n📄 Paso 5: Segmentación del documento (Plan D)...")
            
            secciones = segmentar_documento(ocr_text)
            
            if secciones.usar_fallback:
                print(f"   ⚠️ No se detectaron secciones claras, usando texto completo")
            else:
                print(f"   ✅ Secciones detectadas: {secciones.secciones_detectadas}")
                result.secciones_detectadas = secciones.secciones_detectadas
            
            # =================================================================
            # PASO 6: EXTRACCIÓN REGEX EXPANDIDA (Plan A)
            # =================================================================
            print(f"\n🔍 Paso 6: Extracción por Regex (Plan A)...")
            datos_regex = extraer_todos_regex(ocr_text)
            
            # Mostrar qué encontró regex
            campos_regex_encontrados = 0
            for campo, valor in datos_regex.items():
                if valor is not None and valor != [] and valor != "":
                    campos_regex_encontrados += 1
                    if isinstance(valor, list):
                        print(f"   ✅ {campo}: {len(valor)} encontrados")
                    else:
                        valor_str = str(valor)[:50]
                        print(f"   ✅ {campo}: {valor_str}")
            
            print(f"   📊 Total campos por regex: {campos_regex_encontrados}")

            # =================================================================
            # PASO 6.5: EXTRACCIÓN CONTEXTUAL (campos que necesitan contexto)
            # =================================================================
            print(f"\n📍 Paso 6.5: Extracción contextual con regex...")

            if datos_regex and json_data:
                # Extraer estado_civil para cada adquiriente
                for adq in json_data.get("adquirientes", []):
                    nombre = adq.get("nombre")
                    if nombre and not adq.get("estado_civil"):
                        estado = extraer_estado_civil(ocr_text, nombre)
                        if estado:
                            adq["estado_civil"] = estado.upper()
                            datos_regex[f"adquiriente_{nombre}_estado_civil"] = estado.upper()
                            print(f"   ✅ Estado civil de '{nombre[:30]}...': {estado.upper()}")

                # Extraer representante para cada adquiriente
                for adq in json_data.get("adquirientes", []):
                    nombre = adq.get("nombre")
                    if nombre and not adq.get("representante"):
                        rep_data = extraer_representante_adquiriente(ocr_text, nombre)
                        if rep_data:
                            adq["representante"] = rep_data
                            print(f"   ✅ Representante de '{nombre[:30]}...': {rep_data['nombre'][:30]}...")

                # Asignar datos del poder al titular con representante
                numero_inst = datos_regex.get("numero_instrumento_poder")
                fecha_poder_val = datos_regex.get("fecha_poder")

                if numero_inst or fecha_poder_val:
                    for titular in json_data.get("titulares", []):
                        rep = titular.get("representante")
                        if rep and isinstance(rep, dict):
                            if numero_inst and not rep.get("escritura"):
                                rep["escritura"] = numero_inst
                                print(f"   ✅ Número de instrumento: {numero_inst}")
                            if fecha_poder_val and not rep.get("fecha_poder"):
                                rep["fecha_poder"] = fecha_poder_val
                                print(f"   ✅ Fecha de poder: {fecha_poder_val}")

            # =================================================================
            # PASO 6.6: EXTRACCIÓN GEMINI (Campos expandidos <90%)
            # =================================================================
            print(f"\n🔮 Paso 6.6: Extracción Gemini (expandido: titular/adquiriente/municipio/monto)...")

            # Extraer campos expandidos con Gemini v2 (titular/adquiriente + municipio + monto + poder)
            gemini_data = self._extraer_con_gemini(ocr_text, nivel="expandido")

            # Mergear Gemini con DeepSeek (prioridad Gemini para titular/adquiriente)
            if gemini_data and json_data:
                json_data = self._merge_deepseek_gemini(json_data, gemini_data)
            elif gemini_data and not json_data:
                # Si DeepSeek falló completamente, usar Gemini como base
                print(f"   ⚠️ DeepSeek falló, usando Gemini como fuente principal")
                json_data = {
                    "titulares": [gemini_data.get("titular")] if gemini_data.get("titular") else [],
                    "adquirientes": [gemini_data.get("adquiriente")] if gemini_data.get("adquiriente") else [],
                    # Agregar campos de DeepSeek/REGEX que puedan existir
                    "numero_escritura": datos_regex.get("numero_escritura"),
                    "fecha_documento": datos_regex.get("fecha_documento"),
                    "numero_notaria": datos_regex.get("numero_notaria"),
                    "nombre_notario": datos_regex.get("nombre_notario"),
                    "municipio": gemini_data.get("municipio") or datos_regex.get("municipio"),
                    "monto_operacion": gemini_data.get("monto_operacion") or datos_regex.get("monto_operacion"),
                }

            # =================================================================
            # PASO 7: VALIDACIÓN CRUZADA (Plan B)
            # =================================================================
            print(f"\n✓ Paso 7: Validación Cruzada (Plan B)...")
            
            validador = ValidadorCruzado(ocr_text)
            validaciones = {}
            
            if json_data:
                validaciones = validador.validar_todos(json_data)
                
                # Mostrar correcciones
                correcciones = 0
                for nombre, resultado_val in validaciones.items():
                    if resultado_val.fue_corregido:
                        correcciones += 1
                        print(f"   ⚠️ {nombre}: CORREGIDO '{resultado_val.valor_original}' → '{resultado_val.valor_validado}'")
                    elif not resultado_val.encontrado_en_texto and resultado_val.valor_original:
                        print(f"   ❓ {nombre}: No validado en texto (valor: {resultado_val.valor_original})")
                
                if correcciones > 0:
                    print(f"   📊 Total correcciones: {correcciones}")
                else:
                    print(f"   ✅ No se requirieron correcciones")
            
            # =================================================================
            # PASO 8: CONSOLIDACIÓN INICIAL PARA DETECTAR CAMPOS DUDOSOS
            # =================================================================
            print(f"\n📊 Paso 8: Análisis de confianza inicial...")
            
            sistema = SistemaConfianza()
            sistema.agregar_regex(datos_regex)
            
            if json_data:
                sistema.agregar_llm(json_data)
            
            sistema.aplicar_validacion(validaciones)
            
            # Obtener campos con confianza BAJA para Plan E
            confianza_actual = sistema.obtener_confianza()
            campos_dudosos = identificar_campos_para_plan_e(
                datos_regex=datos_regex,
                datos_llm=json_data or {},
                confianza=confianza_actual
            )
            
            # Mostrar análisis inicial
            confianza_alta = sum(1 for c in confianza_actual.values() if c == NivelConfianza.ALTA)
            confianza_baja = sum(1 for c in confianza_actual.values() if c == NivelConfianza.BAJA)
            print(f"   ✅ Campos con confianza ALTA: {confianza_alta}")
            print(f"   ❌ Campos con confianza BAJA: {confianza_baja}")
            
            if campos_dudosos:
                print(f"   🎯 Candidatos para Plan E: {campos_dudosos}")
            
            # =================================================================
            # PASO 9: PLAN E - EXTRACCIÓN INDIVIDUAL (si hay campos dudosos)
            # =================================================================
            resultados_plan_e = {}
            
            if campos_dudosos and self.config.use_plan_e:
                print(f"\n🎯 Paso 9: Plan E - Extracción Individual...")
                print(f"   📋 Campos a procesar: {campos_dudosos}")
                
                plan_e = PlanEExtractor(self.ollama_service)
                resultados_plan_e = plan_e.ejecutar(
                    campos_dudosos=campos_dudosos,
                    texto_documento=ocr_text,
                    secciones=secciones
                )
                
                # Mostrar resultados de Plan E
                for campo, resultado_e in resultados_plan_e.items():
                    if resultado_e.exito:
                        print(f"   ✅ {campo}: {resultado_e.valor} (Plan E, {resultado_e.tiempo_segundos:.1f}s)")
                    else:
                        error_msg = resultado_e.error or "No mejorado"
                        print(f"   ❌ {campo}: {error_msg}")
                
                # Agregar resultados de Plan E al sistema
                sistema.agregar_plan_e(resultados_plan_e)
                
                result.plan_e_activado = True
                result.campos_mejorados_plan_e = [
                    c for c, r in resultados_plan_e.items() if r.exito
                ]
            elif campos_dudosos and not self.config.use_plan_e:
                print(f"\n⚠️ Paso 9: Plan E deshabilitado (hay {len(campos_dudosos)} campos dudosos)")
            else:
                print(f"\n✅ Paso 9: Plan E no requerido (todos los campos OK)")
            
            # =================================================================
            # PASO 10: CONSOLIDACIÓN FINAL Y EVALUACIÓN (Plan F)
            # =================================================================
            print(f"\n📊 Paso 10: Consolidación Final (Plan F)...")
            
            resultado_confianza = sistema.consolidar()

            # =================================================================
            # PASO 11: GEMINI FALLBACK GLOBAL (recuperar campos MEDIA/BAJA confianza)
            # =================================================================
            campos_recuperados_gemini = []
            if GEMINI_FALLBACK_ENABLED and resultado_confianza.success:
                print(f"\n🤖 Paso 11: Gemini Fallback Global...")

                # Detectar campos con MEDIA o BAJA confianza
                campos_media_baja = [
                    campo for campo, nivel in resultado_confianza.confianza.items()
                    if nivel in ["media", "baja"]
                ]

                if campos_media_baja:
                    print(f"   Campos con MEDIA/BAJA confianza: {campos_media_baja}")

                    try:
                        from services.gemini_service import get_gemini_fallback_service

                        gemini = get_gemini_fallback_service()

                        # Llamar Gemini con todos los campos de una vez
                        campos_recuperados = gemini.recuperar_campos_faltantes(
                            texto_ocr=ocr_text,
                            campos_baja_confianza=campos_media_baja,
                            datos_actuales=resultado_confianza.datos
                        )

                        # Actualizar resultado con campos recuperados
                        if campos_recuperados:
                            for campo, valor in campos_recuperados.items():
                                resultado_confianza.datos[campo] = valor
                                resultado_confianza.confianza[campo] = "media"  # Gemini = confianza MEDIA
                                resultado_confianza.origen[campo] = "gemini_fallback"
                                campos_recuperados_gemini.append(campo)
                                print(f"   ✅ Gemini recuperó '{campo}': {str(valor)[:50]}...")

                            # Remover de requiere_revision si fue recuperado
                            resultado_confianza.requiere_revision = [
                                c for c in resultado_confianza.requiere_revision
                                if c not in campos_recuperados
                            ]

                            print(f"   📊 Total campos recuperados: {len(campos_recuperados)}")

                            # Recalcular calidad general
                            campos_totales = 8
                            campos_encontrados = sum(
                                1 for campo in ["numero_escritura", "numero_notaria", "nombre_notario",
                                               "fecha_documento", "monto_operacion", "titulares",
                                               "adquirientes", "municipio"]
                                if resultado_confianza.datos.get(campo) not in [None, "", [], "no encontrado"]
                            )
                            calidad_anterior = resultado_confianza.calidad_general
                            resultado_confianza.calidad_general = (campos_encontrados / campos_totales) * 100
                            resultado_confianza.campos_encontrados = campos_encontrados

                            print(f"   📊 Mejora de calidad: {calidad_anterior:.1f}% → {resultado_confianza.calidad_general:.1f}%")
                        else:
                            print(f"   ⚠️ Gemini no pudo recuperar ningún campo")

                        # Campos que Gemini no pudo recuperar
                        campos_no_recuperados = set(campos_media_baja) - set(campos_recuperados.keys())
                        if campos_no_recuperados:
                            print(f"   ❌ Campos que requieren revisión manual: {list(campos_no_recuperados)}")

                            # Marcar con nota especial
                            for campo in campos_no_recuperados:
                                resultado_confianza.origen[campo] = "requiere_revision_manual"

                    except Exception as e:
                        print(f"   ⚠️ Error en Gemini Fallback: {e}")
                        # No fallar el flujo completo, solo registrar error
                else:
                    print(f"   ✅ No hay campos con MEDIA/BAJA confianza, Gemini no necesario")

            # =================================================================
            # PASO 12: CONSTRUIR RESPUESTA FINAL
            # =================================================================
            if not resultado_confianza.success:
                # FALLO: No se pudieron extraer suficientes datos
                result.success = False
                result.error = resultado_confianza.error
                result.data = None
                result.detalles_fallo = resultado_confianza.detalles_fallo
                result.calidad_general = resultado_confianza.calidad_general
                result.campos_encontrados = resultado_confianza.campos_encontrados
                result.campos_no_encontrados = resultado_confianza.campos_faltantes
                
                print(f"\n❌ {resultado_confianza.error}")
                if resultado_confianza.detalles_fallo:
                    detalles = resultado_confianza.detalles_fallo
                    print(f"   Nivel: {detalles.get('nivel', 'N/A')}")
                    print(f"   Campos críticos: {detalles.get('campos_criticos', 0)}/4")
                    if detalles.get('posibles_causas'):
                        print(f"   Posibles causas:")
                        for causa in detalles['posibles_causas'][:2]:
                            print(f"      - {causa}")
            else:
                # ÉXITO (completo o parcial)
                result.success = True

                # Limpiar campos internos que NO deben aparecer en raíz del JSON final
                datos_limpios = dict(resultado_confianza.datos) if resultado_confianza.datos else {}
                campos_internos = ['numero_instrumento_poder', 'fecha_poder']
                for campo in campos_internos:
                    if campo in datos_limpios:
                        del datos_limpios[campo]

                result.data = datos_limpios
                result.confianza = resultado_confianza.confianza
                result.origen = resultado_confianza.origen
                result.requiere_revision = resultado_confianza.requiere_revision
                result.calidad_general = resultado_confianza.calidad_general
                result.campos_encontrados = resultado_confianza.campos_encontrados
                result.campos_no_encontrados = resultado_confianza.campos_faltantes

                # Determinar si pasó validación estricta (8 campos encontrados)
                result.validacion_estricta = resultado_confianza.campos_encontrados >= 8
                
                # Mostrar resumen
                if resultado_confianza.advertencia:
                    print(f"\n⚠️ {resultado_confianza.advertencia}")
                else:
                    print(f"\n✅ Extracción exitosa")
                
                print(f"   📊 Calidad: {resultado_confianza.calidad_general}%")
                print(f"   📊 Campos encontrados: {resultado_confianza.campos_encontrados}/8")
                
                # Mostrar confianza por campo
                confianza_alta = sum(1 for c in resultado_confianza.confianza.values() if c == "alta")
                confianza_media = sum(1 for c in resultado_confianza.confianza.values() if c == "media")
                confianza_baja = sum(1 for c in resultado_confianza.confianza.values() if c == "baja")
                
                print(f"   ✅ Alta confianza: {confianza_alta}")
                print(f"   ⚠️ Media confianza: {confianza_media}")
                print(f"   ❌ Baja confianza: {confianza_baja}")
                
                if resultado_confianza.plan_e_activado:
                    print(f"   🎯 Plan E mejoró: {resultado_confianza.campos_mejorados_plan_e}")
                
                if resultado_confianza.requiere_revision:
                    print(f"   🔍 Requieren revisión: {', '.join(resultado_confianza.requiere_revision)}")
        
        except FileNotFoundError as e:
            result.error = f"Archivo no encontrado: {e}"
            print(f"\n❌ Error: {result.error}")
        except Exception as e:
            result.error = f"Error inesperado: {e}"
            print(f"\n❌ Error: {result.error}")
            import traceback
            traceback.print_exc()
        
        result.processing_time = time.time() - start_time
        self._log_resultado_final(result)
        
        return result
    
    def _step_ocr(self, pdf_path: str) -> Tuple[str, dict]:
        """
        Paso 1: OCR del PDF usando Azure Document Intelligence.
        
        Args:
            pdf_path: Ruta al archivo PDF
            
        Returns:
            Tupla de (texto_extraido, metadata)
        """
        return self.ocr_service.extract_text(pdf_path)
    
    def _fase2_extraer(
        self,
        document_text: str
    ) -> Tuple[Optional[Dict], int, bool, Optional[str]]:
        """
        FASE 2: Extracción con prompt genérico y sistema de retry.

        Esta función:
        1. Construye el prompt genérico
        2. Envía a DeepSeek para extracción
        3. Valida la respuesta
        4. Si falla, reintenta con feedback

        Args:
            document_text: Texto del documento (ya formateado)

        Returns:
            Tupla de (json_data, intentos_usados, paso_validacion_estricta, thinking)
        """
        
        last_error = None
        last_json = None
        json_data = None
        all_thinking = []
        
        for attempt in range(self.config.max_retries):
            print(f"\n   🔄 Intento {attempt + 1}/{self.config.max_retries}")
            
            try:
                # Construir prompt
                if attempt == 0:
                    # Primer intento: prompt genérico
                    system_prompt, user_prompt = build_extraction_prompt(
                        document_text=document_text,
                        include_examples=self.config.include_examples
                    )
                    print(f"      📝 Prompt genérico (clasificación individual por titular/adquiriente)")
                else:
                    # Retry: prompt de corrección
                    system_prompt, user_prompt = build_validation_prompt(
                        json_anterior=last_json,
                        error_validacion=str(last_error),
                        document_text=document_text[:2000]  # Truncar para retry
                    )
                    print(f"      📝 Prompt de corrección con feedback")
                
                # Llamar a DeepSeek
                response = self.ollama_service.generate(
                    prompt=user_prompt,
                    system=system_prompt,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens
                )
                
                elapsed = response.get('elapsed_time_seconds', 0)
                print(f"      ⏱️ Tiempo de inferencia: {elapsed:.2f}s")
                
                # Procesar respuesta
                response_text = response.get('response', '')
                processed = process_deepseek_response(response_text)
                
                # Guardar thinking si existe
                if processed.get('thinking'):
                    all_thinking.append(processed['thinking'])
                
                json_data = processed.get('json_data')
                
                # 🔍 DEBUG LOG 1: Valor después de process_deepseek_response
                import json as json_module
                print(f"\n      📋 DEBUG - json_data ANTES de limpiar:")
                if json_data:
                    try:
                        debug_str = json_module.dumps(json_data, indent=2, ensure_ascii=False)
                        print(f"         {debug_str[:2000]}{'...' if len(debug_str) > 2000 else ''}")
                    except:
                        print(f"         {str(json_data)[:2000]}")
                else:
                    print(f"         None")
                
                if not json_data:
                    print(f"      ⚠️ No se extrajo JSON de la respuesta")
                    last_error = "No se pudo parsear JSON de la respuesta"
                    continue
                
                # ============================================================
                # LIMPIEZA DE CAMPOS EXTRA (CRÍTICO)
                # ============================================================
                print(f"      🧹 Limpiando campos extra del JSON...")
                json_data = limpiar_json_extra(json_data)
                
                # 🔍 DEBUG LOG 2: Valor después de limpiar_json_extra
                print(f"\n      📋 DEBUG - json_data DESPUÉS de limpiar:")
                try:
                    debug_str = json_module.dumps(json_data, indent=2, ensure_ascii=False)
                    print(f"         {debug_str[:2000]}{'...' if len(debug_str) > 2000 else ''}")
                except:
                    print(f"         {str(json_data)[:2000]}")
                
                # Guardar para siguiente intento
                last_json = json_data

                # Intentar validación estricta
                try:
                    EscrituraPublica.model_validate(json_data)
                    print(f"      ✅ Validación estricta EXITOSA")
                    
                    # Unir todos los bloques de thinking
                    thinking_final = "\n---\n".join(all_thinking) if all_thinking else None
                    
                    return json_data, attempt + 1, True, thinking_final
                    
                except ValidationError as e:
                    last_error = str(e)
                    print(f"      ⚠️ Validación estricta falló")
                    
                    # 🔍 DEBUG LOG 3: Error de validación estricta completo
                    print(f"\n      ❌ DEBUG - Error de validación estricta:")
                    print(f"         {e}")
                    
                    # Mostrar análisis del JSON
                    analisis = analizar_json_parcial(json_data)
                    print(f"      📊 Porcentaje completo: {analisis['porcentaje']}%")
                    if analisis.get('campos_faltantes'):
                        print(f"      ❌ Faltan: {', '.join(analisis['campos_faltantes'][:3])}")
                    if analisis.get('problemas_detectados'):
                        for problema in analisis['problemas_detectados'][:2]:
                            print(f"      ⚠️ {problema}")
                    
            except Exception as e:
                last_error = str(e)
                print(f"      ❌ Error: {e}")
        
        # Después de todos los intentos
        print(f"\n   ⚠️ Usando validación flexible después de {self.config.max_retries} intentos")

        thinking_final = "\n---\n".join(all_thinking) if all_thinking else None
        return json_data, self.config.max_retries, False, thinking_final

    def _separar_representantes_concatenados(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST-PROCESSING para separar entidades concatenadas (titulares, adquirientes, representantes).

        Gemini a veces ignora las instrucciones y devuelve nombres concatenados:

        CASO 1 - Titulares/Adquirientes concatenados:
        {
          "titular": {
            "nombre": "NORMA CELIS y GABRIEL VIZCARRA",  ← 2 personas en 1
            "tipo": "persona"
          }
        }
        → Se convierte en array de 2 titulares separados

        CASO 2 - Representantes concatenados:
        {
          "representante": {
            "nombre": "ROSA GUZMAN Y MARGARITA FLORES",
            "en_calidad": "apoderadas legales"
          }
        }
        → Se convierte en array de 2 representantes separados
        """
        import re
        import copy

        def procesar_entidad(entidad: Dict[str, Any], tipo_entidad: str = "titular") -> list:
            """
            Procesa titular o adquiriente para separar nombres concatenados.

            SOLO separa titulares/adquirientes concatenados en el nombre principal.
            NO modifica representantes (ya vienen correctamente de Gemini).

            Retorna:
            - Lista de entidades si detecta concatenación en nombre principal
            - Lista de 1 elemento si no hay concatenación
            """
            if not entidad:
                return [entidad]

            # Detectar concatenación en el NOMBRE PRINCIPAL (titular/adquiriente)
            nombre_principal = entidad.get("nombre", "")
            if re.search(r'\s+[Yy]\s+', nombre_principal):
                # Hay concatenación de titulares/adquirientes
                nombres = re.split(r'\s+[Yy]\s+', nombre_principal)
                nombres = [n.strip() for n in nombres if n.strip()]

                # Crear entidades separadas con DEEP COPY para evitar compartir referencias
                entidades_separadas = []
                for nombre_individual in nombres:
                    entidad_copia = copy.deepcopy(entidad)  # DEEP COPY para objetos anidados
                    entidad_copia["nombre"] = nombre_individual
                    entidades_separadas.append(entidad_copia)

                print(f"   🔧 Separados {len(nombres)} {tipo_entidad}s concatenados")
                return entidades_separadas

            # Sin concatenación, retornar como lista de 1 elemento
            return [entidad]

        # Procesar titular (puede retornar múltiples titulares concatenados)
        if "titular" in json_data and json_data["titular"]:
            if isinstance(json_data["titular"], dict):
                entidades = procesar_entidad(json_data["titular"], "titular")
                if len(entidades) == 1:
                    # Un solo titular - mantener formato singular
                    json_data["titular"] = entidades[0]
                else:
                    # Múltiples titulares - convertir a formato plural
                    json_data["titulares"] = entidades
                    del json_data["titular"]
            else:
                print(f"   ⚠️ POST-PROCESSING: 'titular' no es un diccionario, ignorando: {type(json_data['titular'])}")

        # Procesar adquiriente (puede retornar múltiples adquirientes concatenados)
        if "adquiriente" in json_data and json_data["adquiriente"]:
            if isinstance(json_data["adquiriente"], dict):
                entidades = procesar_entidad(json_data["adquiriente"], "adquiriente")
                if len(entidades) == 1:
                    # Un solo adquiriente - mantener formato singular
                    json_data["adquiriente"] = entidades[0]
                else:
                    # Múltiples adquirientes - convertir a formato plural
                    json_data["adquirientes"] = entidades
                    del json_data["adquiriente"]
            else:
                print(f"   ⚠️ POST-PROCESSING: 'adquiriente' no es un diccionario, ignorando: {type(json_data['adquiriente'])}")

        return json_data

    def _extraer_con_gemini(
        self,
        ocr_text: str,
        nivel: str = "critico"
    ) -> Dict[str, Any]:
        """
        Extrae campos usando Gemini según el nivel de cobertura.

        ARQUITECTURA MODULAR:
        ====================
        Esta función permite escalar gradualmente la extracción con Gemini.

        Niveles disponibles:
        - "critico": Solo titular/adquiriente (VERSIÓN 1 - ACTUAL)
        - "expandido": + municipio, monto, poder (VERSIÓN 2 - FUTURA)
        - "completo": Todos los campos <90% (VERSIÓN 3 - FUTURA)

        Args:
            ocr_text: Texto OCR del documento
            nivel: "critico" | "expandido" | "completo"

        Returns:
            Dict con campos extraídos por Gemini

        Ejemplo de retorno (nivel="critico"):
            {
                "titular": {
                    "nombre": "INSTITUTO NACIONAL...",
                    "tipo": "empresa",
                    "representante": {
                        "nombre": "ERNESTO PADILLA ACEVES",
                        "en_calidad": "Representante Regional"
                    }
                },
                "adquiriente": {
                    "nombre": "ANGELBERTA PÉREZ SOTO",
                    "tipo": "persona",
                    "representante": null
                }
            }
        """

        # Seleccionar prompt según nivel
        if nivel == "critico":
            prompt = build_gemini_prompt_critico(ocr_text)
        elif nivel == "expandido":
            prompt = build_gemini_prompt_expandido(ocr_text)
        else:  # completo
            prompt = build_gemini_prompt_completo(ocr_text)

        try:
            # Importar servicio Gemini (lazy import)
            from services.gemini_service import get_gemini_fallback_service

            gemini_service = get_gemini_fallback_service()

            print(f"\n🔮 Extrayendo campos con Gemini (nivel: {nivel})...")

            # Generar contenido con Gemini
            response = gemini_service.generate_content(prompt)

            if not response:
                print(f"   ⚠️ Gemini no devolvió respuesta")
                return {}

            # Parsear respuesta JSON
            json_data = parse_gemini_response(response)

            # POST-PROCESSING: Separar representantes concatenados
            if json_data:
                json_data = self._separar_representantes_concatenados(json_data)

            if json_data:
                # Mostrar resumen de lo extraído
                if "titular" in json_data and json_data["titular"]:
                    titular_nombre = json_data["titular"].get("nombre", "N/A")
                    print(f"   ✅ Titular (vendedor): {titular_nombre[:50]}...")

                if "adquiriente" in json_data and json_data["adquiriente"]:
                    adq_nombre = json_data["adquiriente"].get("nombre", "N/A")
                    print(f"   ✅ Adquiriente (comprador): {adq_nombre[:50]}...")

                if nivel in ["expandido", "completo"]:
                    if "municipio" in json_data:
                        print(f"   ✅ Municipio: {json_data.get('municipio', 'N/A')}")
                    if "monto_operacion" in json_data:
                        print(f"   ✅ Monto: {json_data.get('monto_operacion', 'N/A')}")

                return json_data
            else:
                print(f"   ⚠️ No se pudo parsear respuesta de Gemini")
                return {}

        except Exception as e:
            print(f"   ❌ Error en Gemini ({nivel}): {e}")
            import traceback
            traceback.print_exc()
            return {}

    def _merge_deepseek_gemini(
        self,
        deepseek_data: Dict[str, Any],
        gemini_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Combina datos de DeepSeek y Gemini con prioridades inteligentes.

        ESTRATEGIA DE MERGE:
        ===================
        1. DeepSeek: Campos estructurados fáciles (>90% precisión)
           - numero_escritura
           - fecha_documento
           - numero_notaria
           - nombre_notario
           - tipo_titular

        2. Gemini: Campos contextuales críticos (<90% precisión)
           - titular.nombre ← PRIORIDAD GEMINI
           - titular.tipo ← PRIORIDAD GEMINI
           - titular.representante ← PRIORIDAD GEMINI
           - adquiriente.nombre ← PRIORIDAD GEMINI
           - adquiriente.tipo ← PRIORIDAD GEMINI
           - adquiriente.representante ← PRIORIDAD GEMINI

        3. REGEX: Campos numéricos (fallback)
           - municipio
           - monto_operacion

        Args:
            deepseek_data: Datos de DeepSeek
            gemini_data: Datos de Gemini

        Returns:
            Dict fusionado con las mejores fuentes
        """

        # Copiar todos los datos de DeepSeek como base
        resultado = dict(deepseek_data) if deepseek_data else {}

        if not gemini_data:
            print("   ⚠️ No hay datos de Gemini para mergear")
            return resultado

        print("\n🔀 Mergeando DeepSeek + Gemini...")

        # ====================================================================
        # MERGE DE TITULAR (prioridad Gemini para nombre/tipo/representante)
        # ====================================================================

        # Gemini puede retornar "titular" (singular) o "titulares" (plural)
        gemini_titulares_list = []
        if "titulares" in gemini_data and gemini_data["titulares"]:
            # Caso 1: Gemini detectó múltiples titulares concatenados (ya separados)
            raw_list = gemini_data["titulares"]
            # VALIDACIÓN: Filtrar solo elementos que sean diccionarios (ignorar strings u otros tipos)
            if isinstance(raw_list, list):
                gemini_titulares_list = [t for t in raw_list if isinstance(t, dict)]
                if len(gemini_titulares_list) != len(raw_list):
                    print(f"   ⚠️ Gemini retornó {len(raw_list)} elementos, pero solo {len(gemini_titulares_list)} son diccionarios válidos")
                else:
                    print(f"   🔧 Gemini retornó {len(gemini_titulares_list)} titulares separados")
            else:
                print(f"   ⚠️ Gemini retornó 'titulares' pero no es una lista: {type(raw_list)}")
        elif "titular" in gemini_data and gemini_data["titular"]:
            # Caso 2: Gemini retornó un solo titular
            if isinstance(gemini_data["titular"], dict):
                gemini_titulares_list = [gemini_data["titular"]]
            else:
                print(f"   ⚠️ Gemini retornó 'titular' pero no es un diccionario: {type(gemini_data['titular'])}")

        if gemini_titulares_list:
            # Si DeepSeek tiene titulares, reemplazarlos con los de Gemini
            if "titulares" in resultado and resultado["titulares"]:
                # Reemplazar completamente los titulares de DeepSeek con los de Gemini
                for i, gemini_titular in enumerate(gemini_titulares_list):
                    if i < len(resultado["titulares"]):
                        deepseek_titular = resultado["titulares"][i]
                    else:
                        # Gemini encontró más titulares que DeepSeek
                        deepseek_titular = {
                            "nombre": "",
                            "tipo": "persona",
                            "actua_por": "derecho propio",
                            "representante": None
                        }
                        resultado["titulares"].append(deepseek_titular)

                    # PRIORIDAD GEMINI: nombre
                    if gemini_titular.get("nombre"):
                        deepseek_titular["nombre"] = gemini_titular["nombre"]
                        print(f"   ✅ Titular[{i}].nombre ← Gemini")

                    # PRIORIDAD GEMINI: tipo
                    if gemini_titular.get("tipo"):
                        deepseek_titular["tipo"] = gemini_titular["tipo"]
                        print(f"   ✅ Titular[{i}].tipo ← Gemini ({gemini_titular['tipo']})")

                    # PRIORIDAD GEMINI: representante (singular)
                    if "representante" in gemini_titular:
                        rep = gemini_titular["representante"]
                        deepseek_titular["representante"] = rep
                        if rep:
                            deepseek_titular["actua_por"] = "representación"
                            rep_nombre = rep.get("nombre", "N/A") if isinstance(rep, dict) else "N/A"
                            print(f"   ✅ Titular[{i}].representante ← Gemini ({rep_nombre[:30]}...)")
                        else:
                            deepseek_titular["actua_por"] = "derecho propio"
                            print(f"   ✅ Titular[{i}].representante ← Gemini (null)")

            else:
                # DeepSeek no tiene titulares, crear desde Gemini
                resultado["titulares"] = []
                for gemini_titular in gemini_titulares_list:
                    resultado["titulares"].append({
                        "nombre": gemini_titular.get("nombre"),
                        "tipo": gemini_titular.get("tipo"),
                        "actua_por": "representación" if gemini_titular.get("representante") else "derecho propio",
                        "representante": gemini_titular.get("representante")
                    })
                print(f"   ✅ {len(gemini_titulares_list)} Titular(es) completo(s) ← Gemini (DeepSeek no lo tenía)")

        # ====================================================================
        # MERGE DE ADQUIRIENTE (prioridad Gemini para nombre/tipo/representante)
        # ====================================================================

        # Gemini puede retornar "adquiriente" (singular) o "adquirientes" (plural)
        gemini_adquirientes_list = []
        if "adquirientes" in gemini_data and gemini_data["adquirientes"]:
            # Caso 1: Gemini detectó múltiples adquirientes concatenados (ya separados)
            raw_list = gemini_data["adquirientes"]
            # VALIDACIÓN: Filtrar solo elementos que sean diccionarios (ignorar strings u otros tipos)
            if isinstance(raw_list, list):
                gemini_adquirientes_list = [a for a in raw_list if isinstance(a, dict)]
                if len(gemini_adquirientes_list) != len(raw_list):
                    print(f"   ⚠️ Gemini retornó {len(raw_list)} elementos, pero solo {len(gemini_adquirientes_list)} son diccionarios válidos")
                else:
                    print(f"   🔧 Gemini retornó {len(gemini_adquirientes_list)} adquirientes separados")
            else:
                print(f"   ⚠️ Gemini retornó 'adquirientes' pero no es una lista: {type(raw_list)}")
        elif "adquiriente" in gemini_data and gemini_data["adquiriente"]:
            # Caso 2: Gemini retornó un solo adquiriente
            if isinstance(gemini_data["adquiriente"], dict):
                gemini_adquirientes_list = [gemini_data["adquiriente"]]
            else:
                print(f"   ⚠️ Gemini retornó 'adquiriente' pero no es un diccionario: {type(gemini_data['adquiriente'])}")

        if gemini_adquirientes_list:
            # Si DeepSeek tiene adquirientes, reemplazarlos con los de Gemini
            if "adquirientes" in resultado and resultado["adquirientes"]:
                # Reemplazar completamente los adquirientes de DeepSeek con los de Gemini
                for i, gemini_adq in enumerate(gemini_adquirientes_list):
                    if i < len(resultado["adquirientes"]):
                        deepseek_adq = resultado["adquirientes"][i]
                    else:
                        # Gemini encontró más adquirientes que DeepSeek
                        deepseek_adq = {
                            "nombre": "",
                            "tipo": "persona",
                            "actua_por": "derecho propio",
                            "estado_civil": None,
                            "representante": None
                        }
                        resultado["adquirientes"].append(deepseek_adq)

                    # PRIORIDAD GEMINI: nombre
                    if gemini_adq.get("nombre"):
                        deepseek_adq["nombre"] = gemini_adq["nombre"]
                        print(f"   ✅ Adquiriente[{i}].nombre ← Gemini")

                    # PRIORIDAD GEMINI: tipo
                    if gemini_adq.get("tipo"):
                        deepseek_adq["tipo"] = gemini_adq["tipo"]
                        print(f"   ✅ Adquiriente[{i}].tipo ← Gemini ({gemini_adq['tipo']})")

                    # PRIORIDAD GEMINI: representante (singular)
                    if "representante" in gemini_adq:
                        rep = gemini_adq["representante"]
                        deepseek_adq["representante"] = rep
                        if rep:
                            deepseek_adq["actua_por"] = "representación"
                            rep_nombre = rep.get("nombre", "N/A") if isinstance(rep, dict) else "N/A"
                            print(f"   ✅ Adquiriente[{i}].representante ← Gemini ({rep_nombre[:30]}...)")
                        else:
                            deepseek_adq["actua_por"] = "derecho propio"
                            print(f"   ✅ Adquiriente[{i}].representante ← Gemini (null)")

                    # Gemini también puede traer estado_civil
                    if gemini_adq.get("estado_civil"):
                        deepseek_adq["estado_civil"] = gemini_adq["estado_civil"]
                        print(f"   ✅ Adquiriente[{i}].estado_civil ← Gemini")

                    # Gemini también puede traer tipo_sociedad
                    if gemini_adq.get("tipo_sociedad"):
                        deepseek_adq["tipo_sociedad"] = gemini_adq["tipo_sociedad"]
                        print(f"   ✅ Adquiriente[{i}].tipo_sociedad ← Gemini")

                    # Gemini también puede traer edad
                    if gemini_adq.get("edad"):
                        deepseek_adq["edad"] = gemini_adq["edad"]
                        print(f"   ✅ Adquiriente[{i}].edad ← Gemini")

                    # Gemini también puede traer rfc
                    if gemini_adq.get("rfc"):
                        deepseek_adq["rfc"] = gemini_adq["rfc"]
                        print(f"   ✅ Adquiriente[{i}].rfc ← Gemini")

                    # Gemini también puede traer curp
                    if gemini_adq.get("curp"):
                        deepseek_adq["curp"] = gemini_adq["curp"]
                        print(f"   ✅ Adquiriente[{i}].curp ← Gemini")

            else:
                # DeepSeek no tiene adquirientes, crear desde Gemini
                resultado["adquirientes"] = []
                for gemini_adq in gemini_adquirientes_list:
                    resultado["adquirientes"].append({
                        "nombre": gemini_adq.get("nombre"),
                        "tipo": gemini_adq.get("tipo"),
                        "actua_por": "representación" if gemini_adq.get("representante") else "derecho propio",
                        "estado_civil": gemini_adq.get("estado_civil"),
                        "representante": gemini_adq.get("representante"),
                        "rfc": gemini_adq.get("rfc", False),
                        "curp": gemini_adq.get("curp", False),
                        "tipo_sociedad": gemini_adq.get("tipo_sociedad"),
                        "edad": gemini_adq.get("edad"),
                    })
                print(f"   ✅ {len(gemini_adquirientes_list)} Adquiriente(s) completo(s) ← Gemini (DeepSeek no lo tenía)")

        # ====================================================================
        # MERGE DE CAMPOS NUMÉRICOS (si Gemini nivel expandido/completo)
        # ====================================================================

        if "municipio" in gemini_data and gemini_data["municipio"]:
            resultado["municipio"] = gemini_data["municipio"]
            print(f"   ✅ Municipio ← Gemini")

        if "monto_operacion" in gemini_data and gemini_data["monto_operacion"]:
            resultado["monto_operacion"] = gemini_data["monto_operacion"]
            print(f"   ✅ Monto ← Gemini")

        # ====================================================================
        # MERGE DE DATOS DEL PODER (escritura/fecha_poder) en representantes
        # ====================================================================

        # Mergear datos del poder en titular
        if "titular" in gemini_data and gemini_data["titular"]:
            gemini_rep = gemini_data["titular"].get("representante")
            if gemini_rep and isinstance(gemini_rep, dict):
                # Buscar titular en resultado
                if "titulares" in resultado and resultado["titulares"]:
                    for titular in resultado["titulares"]:
                        rep = titular.get("representante")
                        if rep and isinstance(rep, dict):
                            # Mergear escritura
                            if gemini_rep.get("escritura") and not rep.get("escritura"):
                                rep["escritura"] = gemini_rep["escritura"]
                                print(f"   ✅ Titular.representante.escritura ← Gemini ({gemini_rep['escritura']})")

                            # Mergear fecha_poder
                            if gemini_rep.get("fecha_poder") and not rep.get("fecha_poder"):
                                rep["fecha_poder"] = gemini_rep["fecha_poder"]
                                print(f"   ✅ Titular.representante.fecha_poder ← Gemini ({gemini_rep['fecha_poder']})")

        # Mergear datos del poder en adquiriente
        if "adquiriente" in gemini_data and gemini_data["adquiriente"]:
            gemini_rep = gemini_data["adquiriente"].get("representante")
            if gemini_rep and isinstance(gemini_rep, dict):
                # Buscar adquiriente en resultado
                if "adquirientes" in resultado and resultado["adquirientes"]:
                    for adq in resultado["adquirientes"]:
                        rep = adq.get("representante")
                        if rep and isinstance(rep, dict):
                            # Mergear escritura
                            if gemini_rep.get("escritura") and not rep.get("escritura"):
                                rep["escritura"] = gemini_rep["escritura"]
                                print(f"   ✅ Adquiriente.representante.escritura ← Gemini ({gemini_rep['escritura']})")

                            # Mergear fecha_poder
                            if gemini_rep.get("fecha_poder") and not rep.get("fecha_poder"):
                                rep["fecha_poder"] = gemini_rep["fecha_poder"]
                                print(f"   ✅ Adquiriente.representante.fecha_poder ← Gemini ({gemini_rep['fecha_poder']})")

        return resultado

    def _aplicar_clasificacion_fallback(self, json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aplica clasificación fallback por regex cuando el campo 'tipo' es None.

        Esta función detecta si un titular/adquiriente es empresa o persona
        usando patrones regex cuando el LLM no asignó el tipo.

        Args:
            json_data: JSON extraído con datos de titulares/adquirientes

        Returns:
            JSON con tipos asignados donde faltaban
        """
        import re

        # Patrones de empresa (movidos de clasificador.py)
        PATRONES_EMPRESA = [
            r'\bS\.?A\.?(\s+DE\s+C\.?V\.?)?',
            r'\bS\.?R\.?L\.?(\s+DE\s+C\.?V\.?)?',
            r'\bS\.?C\.?(\s+DE\s+C\.?V\.?)?',
            r'\bCÍA\.?',
            r'\bCOMPAÑÍA',
            r'\bCORPORACIÓN',
            r'\bGRUPO\s+',
            r'\bASSOCIATES?\b',
            # Instituciones gubernamentales y organismos
            r'\bINFONAVIT\b',
            r'\bFOVISSSTE\b',
            r'\bIMSS\b',
            r'\bISST[EE]\b',
            r'\bCFE\b',
            r'\bPEMEX\b',
            r'\bBANOBRAS\b',
            r'\bFONHAPO\b',
            r'\bINSUS\b',
            r'\bINVIEND\b',
            r'\bCONAVI\b',
            r'\bFONADIN\b',
            r'\bSEDATU\b',
            r'\bSEDESO[L]\?\b',
            r'\bINSTITUTO\s+(?:FEDERAL|ESTATAL|NACIONAL)',
            r'\bORGANISMO\s+',
        ]

        def detectar_tipo_por_nombre(nombre: str) -> str:
            """Detecta si nombre es empresa o persona por regex."""
            if not nombre:
                return "persona"
            nombre_upper = nombre.upper()
            for patron in PATRONES_EMPRESA:
                if re.search(patron, nombre_upper, re.IGNORECASE):
                    return "empresa"
            return "persona"

        # Procesar titulares
        titulares = json_data.get('titulares', [])
        for i, titular in enumerate(titulares):
            if not isinstance(titular, dict):
                continue

            if titular.get('tipo') is None:
                nombre = titular.get('nombre', '')
                tipo_detectado = detectar_tipo_por_nombre(nombre)

                if tipo_detectado in ['empresa', 'persona']:
                    titular['tipo'] = tipo_detectado
                    print(f"\n   🔧 FALLBACK: Titular {i+1} clasificado como '{tipo_detectado}'")
                    print(f"      Razón: '{nombre[:40]}...' (patrón de nombre)")

        # Procesar adquirientes
        adquirientes = json_data.get('adquirientes', [])
        for i, adquiriente in enumerate(adquirientes):
            if not isinstance(adquiriente, dict):
                continue

            if adquiriente.get('tipo') is None:
                nombre = adquiriente.get('nombre', '')
                tipo_detectado = detectar_tipo_por_nombre(nombre)

                if tipo_detectado in ['empresa', 'persona']:
                    adquiriente['tipo'] = tipo_detectado
                    print(f"\n   🔧 FALLBACK: Adquiriente {i+1} clasificado como '{tipo_detectado}'")
                    print(f"      Razón: '{nombre[:40]}...' (patrón de nombre)")

        return json_data
    
    def _log_resultado_final(self, result: ExtractionResult):
        """
        Imprime el resumen final de la extracción.
        """
        print(f"\n{'='*60}")
        print(f"📊 RESULTADO FINAL - PLAN Z")
        print(f"{'='*60}")
        
        if result.success:
            if result.validacion_estricta:
                print(f"✅ EXTRACCIÓN EXITOSA (validación estricta)")
            else:
                print(f"⚠️ EXTRACCIÓN PARCIAL (validación flexible)")
            
            print(f"   Calidad: {result.calidad_general}%")
            print(f"   Campos encontrados: {result.campos_encontrados}/8")
            
            if result.campos_no_encontrados:
                print(f"   Campos faltantes: {', '.join(result.campos_no_encontrados)}")
            
            if result.plan_e_activado:
                print(f"\n🎯 Plan E:")
                print(f"   Activado: Sí")
                print(f"   Campos mejorados: {result.campos_mejorados_plan_e}")
            
            if result.requiere_revision:
                print(f"\n🔍 Campos que requieren revisión:")
                for campo in result.requiere_revision:
                    print(f"   - {campo}")
        else:
            print(f"❌ EXTRACCIÓN FALLIDA")
            print(f"   Error: {result.error}")
            if result.detalles_fallo:
                print(f"   Nivel: {result.detalles_fallo.get('nivel', 'N/A')}")
        
        if result.tipo_detectado:
            print(f"\n📋 Clasificación:")
            print(f"   Tipo: {result.tipo_detectado}")
            print(f"   Método: {result.metodo_clasificacion}")
        
        if result.secciones_detectadas:
            print(f"\n📄 Secciones detectadas: {result.secciones_detectadas}")
        
        print(f"\n⏱️ Tiempo total: {result.processing_time:.2f}s")
        print(f"🔄 Intentos LLM: {result.intentos_realizados}")
        print(f"🤖 Modelo: {result.model_used}")
        print(f"{'='*60}\n")
    
    def health_check(self) -> Dict[str, bool]:
        """
        Verifica el estado de los servicios.
        
        Returns:
            Dict con el estado de cada servicio
        """
        return {
            'ollama': self.ollama_service.health_check(),
            'azure_ocr': self.ocr_service is not None
        }


# =============================================================================
# FUNCIÓN DE CONVENIENCIA
# =============================================================================

def extract_escritura(pdf_path: str, **kwargs) -> ExtractionResult:
    """
    Función de conveniencia para extraer una escritura.
    
    Crea un extractor temporal y procesa el documento.
    
    Args:
        pdf_path: Ruta al archivo PDF
        **kwargs: Argumentos para ExtractionConfig
        
    Returns:
        ExtractionResult con los datos extraídos
        
    Ejemplo:
        >>> result = extract_escritura("documento.pdf")
        >>> if result.success:
        ...     print(result.data)
        ...     print(f"Calidad: {result.calidad_general}%")
        ...     print(f"Confianza: {result.confianza}")
    """
    config = ExtractionConfig(**kwargs)
    extractor = EscrituraExtractor(config=config)
    return extractor.extract(pdf_path)


# =============================================================================
# CÓDIGO DE PRUEBA
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("EXTRACTOR DE ESCRITURAS PÚBLICAS")
    print("Sistema Plan Z (ABDF + E)")
    print("=" * 60)
    
    # Crear extractor
    extractor = EscrituraExtractor()
    
    # Verificar servicios
    print("\n🔍 Verificando servicios...")
    health = extractor.health_check()
    
    for service, status in health.items():
        emoji = "✅" if status else "❌"
        print(f"   {emoji} {service}")
    
    print("\n📝 Uso:")
    print("   result = extractor.extract('documento.pdf')")
    print("   ")
    print("   if result.success:")
    print("       print(result.data)")
    print("       print(f'Calidad: {result.calidad_general}%')")
    print("       print(f'Confianza: {result.confianza}')")
    print("       print(f'Plan E activado: {result.plan_e_activado}')")
    print("       if result.requiere_revision:")
    print("           print(f'Revisar: {result.requiere_revision}')")
