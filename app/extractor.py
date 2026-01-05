"""
app/extractor.py - Extractor con estrategia "Divide y Vencerás"

ARQUITECTURA:
=============

┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│    PDF      │ ──> │   Azure OCR      │ ──> │   Texto limpio      │
└─────────────┘     └──────────────────┘     └──────────┬──────────┘
                                                        │
                                                        ▼
                                            ┌──────────────────────┐
                                            │  FASE 1: Clasificar  │
                                            │  ¿Empresa o Persona? │
                                            └──────────┬───────────┘
                                                       │
                              ┌─────────────────────────┴─────────────────────────┐
                              │                                                   │
                              ▼                                                   ▼
                    ┌─────────────────┐                               ┌─────────────────┐
                    │ FASE 2: Prompt  │                               │ FASE 2: Prompt  │
                    │    EMPRESA      │                               │    PERSONA      │
                    └────────┬────────┘                               └────────┬────────┘
                             │                                                  │
                             └────────────────────┬─────────────────────────────┘
                                                  │
                                                  ▼
                                       ┌──────────────────────┐
                                       │  FASE 3: Validación  │
                                       │  + Corrección Regex  │
                                       └──────────────────────┘

MEJORAS PARA CONSISTENCIA:
===========================
1. Clasificación PRIMERO (reduce ambigüedad)
2. Prompts específicos por tipo (menos variación)
3. temperature=0.0 + seed fija (determinístico)
4. Extracción regex como fallback (garantía de campos críticos)
5. Merge inteligente de LLM + regex
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from pydantic import ValidationError
from dotenv import load_dotenv

load_dotenv()

# Servicios
from services.ollama_service import OllamaService, OllamaConfig, get_ollama_service
from services.azure_ocr_service import AzureOCRService, AzureConfig, get_ocr_service

# Utilidades
from utils.text_processing import (
    process_deepseek_response,
    clean_ocr_text,
    format_for_prompt,
    extraer_datos_con_regex,
    merge_extractions,
)
from utils.prompt_builder import (
    build_classification_prompt,
    build_extraction_prompt,
    build_validation_prompt,
)

# Modelos
from models.escritura import (
    EscrituraPublica,
    EscrituraPublicaFlexible,
    validar_json_flexible,
    generar_feedback_error,
    formatear_feedback_para_prompt,
    analizar_json_parcial,
)


@dataclass
class ExtractionConfig:
    """
    Configuración del extractor.
    
    NUEVOS PARÁMETROS:
    ==================
    - use_classification: Si usar clasificación previa (RECOMENDADO: True)
    - use_regex_fallback: Si usar regex como fallback (RECOMENDADO: True)
    - deterministic: Si usar configuración determinística (RECOMENDADO: True)
    """
    
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("TEMPERATURE", "0.0"))  # CAMBIADO: era 0.1
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS", "4096"))
    )
    max_context_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
    )
    include_examples: bool = True
    save_thinking: bool = True
    
    # NUEVOS parámetros para consistencia
    use_classification: bool = True      # NUEVO: Usar clasificación previa
    use_regex_fallback: bool = True      # NUEVO: Usar regex como fallback
    deterministic: bool = True           # NUEVO: Modo determinístico


@dataclass
class ExtractionResult:
    """
    Resultado de la extracción.
    
    NUEVOS CAMPOS:
    ==============
    - tipo_detectado: "empresa" o "persona" (resultado de clasificación)
    - metodo_clasificacion: Cómo se detectó el tipo
    - datos_regex: Datos extraídos por regex (para debug)
    - seed_used: Semilla usada (para reproducibilidad)
    """
    
    success: bool
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
    campos_encontrados: int = 0
    campos_no_encontrados: list = field(default_factory=list)
    
    # NUEVOS campos
    tipo_detectado: str = ""             # "empresa" o "persona"
    metodo_clasificacion: str = ""       # "llm", "regex", "fallback"
    datos_regex: Dict[str, Any] = field(default_factory=dict)
    seed_used: int = 42


class EscrituraExtractor:
    """
    Extractor de escrituras públicas con estrategia "Divide y Vencerás".
    
    FLUJO MEJORADO:
    ===============
    1. OCR del PDF
    2. Limpieza de texto
    3. FASE 1: Clasificar (empresa/persona)
    4. FASE 2: Extraer con prompt específico
    5. FASE 3: Validar + corregir con regex
    
    ¿Por qué este flujo es mejor?
    =============================
    - La clasificación reduce el espacio de búsqueda del LLM
    - Prompts específicos = menos ambigüedad = más consistencia
    - Regex garantiza campos críticos (número escritura, monto)
    - Merge inteligente combina lo mejor del LLM y regex
    """
    
    def __init__(
        self,
        config: Optional[ExtractionConfig] = None,
        ollama_config: Optional[OllamaConfig] = None,
        azure_config: Optional[AzureConfig] = None
    ):
        self.config = config or ExtractionConfig()
        
        # Configurar Ollama con modo determinístico
        if ollama_config is None:
            ollama_config = OllamaConfig()
        ollama_config.deterministic = self.config.deterministic
        
        self.ollama_service = get_ollama_service(ollama_config)
        self.ocr_service = get_ocr_service(azure_config)
        
        print(f"🔧 Extractor inicializado (Divide y Vencerás)")
        print(f"   - Modelo: {self.ollama_service.config.model}")
        print(f"   - Max reintentos: {self.config.max_retries}")
        print(f"   - Clasificación previa: {self.config.use_classification}")
        print(f"   - Fallback regex: {self.config.use_regex_fallback}")
        print(f"   - Modo determinístico: {self.config.deterministic}")
        print(f"   - Seed: {self.ollama_service.config.default_seed}")
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extrae información de una escritura pública.
        
        FLUJO COMPLETO:
        ===============
        1. OCR del PDF
        2. Limpieza de texto
        3. Extracción por regex (datos críticos)
        4. FASE 1: Clasificación (empresa/persona)
        5. FASE 2: Extracción con prompt específico
        6. FASE 3: Merge LLM + regex
        7. Validación
        """
        
        start_time = time.time()
        result = ExtractionResult(success=False)
        result.seed_used = self.ollama_service.config.default_seed
        
        try:
            # === PASO 1: OCR ===
            print(f"\n📄 Procesando: {pdf_path}")
            ocr_text, ocr_meta = self._step_ocr(pdf_path)
            result.ocr_metadata = ocr_meta
            print(f"   ✅ OCR completado: {ocr_meta.get('pages', '?')} páginas")
            
            # === PASO 2: Limpiar texto ===
            clean_text = clean_ocr_text(ocr_text)
            formatted_text = format_for_prompt(clean_text, self.config.max_context_tokens)
            print(f"   ✅ Texto limpiado: {len(clean_text)} caracteres")
            
            # === PASO 3: Extracción por regex (datos críticos) ===
            datos_regex = {}  # Inicializar siempre
            if self.config.use_regex_fallback:
                datos_regex = extraer_datos_con_regex(ocr_text)  # Usar texto original para regex
                result.datos_regex = datos_regex
                print(f"   ✅ Regex extrajo: {sum(1 for v in datos_regex.values() if v is not None)} campos")
                
                # Mostrar datos regex
                for campo, valor in datos_regex.items():
                    if valor is not None:
                        print(f"      - {campo}: {valor}")
            
            # === PASO 4: FASE 1 - Clasificación ===
            tipo_titular = self._fase1_clasificar(clean_text)
            result.tipo_detectado = tipo_titular
            print(f"   ✅ Clasificación: {tipo_titular.upper()}")
            
            # === PASO 5: FASE 2 - Extracción con prompt específico ===
            json_data, intentos, validacion_estricta = self._fase2_extraer(
                formatted_text, 
                tipo_titular,
                datos_regex=datos_regex  # Ya está inicializado (vacío si regex está deshabilitado)
            )
            
            result.intentos_realizados = intentos
            result.raw_json = json_data
            result.model_used = self.ollama_service.config.model
            
            # === PASO 6: Merge LLM + Regex ===
            if json_data and self.config.use_regex_fallback:
                print(f"\n🔀 Combinando LLM + Regex...")
                json_data = merge_extractions(json_data, datos_regex)
            
            # === PASO 7: Validación final ===
            if json_data:
                if validacion_estricta:
                    result.validacion_estricta = True
                    result.data = json_data
                    result.success = True
                    result.campos_encontrados = 8
                    result.campos_no_encontrados = []
                    print(f"\n✅ Validación ESTRICTA exitosa")
                else:
                    # Validación flexible
                    escritura_flexible = validar_json_flexible(json_data)
                    reporte = escritura_flexible.generar_reporte()
                    
                    result.validacion_estricta = False
                    result.data = reporte["datos_encontrados"]
                    result.reporte = reporte
                    result.success = True
                    result.campos_encontrados = reporte["resumen"]["campos_encontrados"]
                    result.campos_no_encontrados = reporte["campos_faltantes"]
                    
                    print(f"\n⚠️ Validación FLEXIBLE aplicada")
                    print(f"   📊 Campos encontrados: {result.campos_encontrados}/8")
            else:
                result.error = "No se pudo extraer JSON del documento"
        
        except FileNotFoundError as e:
            result.error = f"Archivo no encontrado: {e}"
        except Exception as e:
            result.error = f"Error: {e}"
            import traceback
            traceback.print_exc()
        
        result.processing_time = time.time() - start_time
        self._log_result(result)
        
        return result
    
    def _fase1_clasificar(self, document_text: str) -> str:
        """
        FASE 1: Clasificar documento como empresa o persona.
        
        ESTRATEGIA:
        ===========
        1. Primero intentar con regex (más rápido y confiable)
        2. Si regex no es concluyente, usar LLM
        
        Returns:
            "empresa" o "persona"
        """
        
        if not self.config.use_classification:
            # Si clasificación está deshabilitada, intentar detectar por regex
            datos = extraer_datos_con_regex(document_text)
            return datos.get('tipo_titular', 'empresa')
        
        print(f"\n🔍 FASE 1: Clasificando documento...")
        
        # Método 1: Detección por regex (más confiable)
        texto_upper = document_text.upper()
        indicadores_empresa = [
            'S.A. DE C.V.',
            'S.A.',
            'SOCIEDAD ANÓNIMA',
            'SOCIEDAD ANONIMA',
            'CAPITAL VARIABLE',
            'S. DE R.L.',
            'SOCIEDAD MERCANTIL',
        ]
        
        for indicador in indicadores_empresa:
            if indicador in texto_upper:
                print(f"   📝 Detectado por regex: EMPRESA (encontró '{indicador}')")
                return "empresa"
        
        # Método 2: Usar LLM para clasificación
        try:
            result = self.ollama_service.classify_document(document_text)
            tipo = result.get('tipo', 'persona')
            metodo = result.get('metodo', 'llm')
            print(f"   📝 Detectado por {metodo}: {tipo.upper()}")
            return tipo
        except Exception as e:
            print(f"   ⚠️ Error en clasificación LLM: {e}")
            return "persona"  # Default más seguro
    
    def _fase2_extraer(
        self, 
        document_text: str, 
        tipo_titular: str,
        datos_regex: Dict[str, Any] = None
    ) -> Tuple[Optional[Dict], int, bool]:
        """
        FASE 2: Extraer datos con prompt específico.
        
        Usa el prompt correspondiente al tipo detectado en FASE 1.
        Incluye sistema de retry con feedback inteligente.
        
        Args:
            document_text: Texto del documento (formateado)
            tipo_titular: "empresa" o "persona" (de FASE 1)
            datos_regex: Datos extraídos por regex (para pistas en retry)
        
        Returns:
            (json_data, intentos_usados, paso_validacion_estricta)
        """
        
        print(f"\n🤖 FASE 2: Extracción ({tipo_titular})...")
        
        last_error = None
        last_json = None
        json_data = None
        
        for attempt in range(self.config.max_retries):
            print(f"\n   Intento {attempt + 1}/{self.config.max_retries}")
            
            try:
                # Construir prompt según intento
                if attempt == 0:
                    # Primer intento: prompt específico para el tipo
                    system_prompt, user_prompt = build_extraction_prompt(
                        document_text,
                        tipo_titular=tipo_titular
                    )
                else:
                    # Retry: prompt de corrección con feedback inteligente
                    system_prompt, user_prompt = build_validation_prompt(
                        json_anterior=last_json,
                        error_validacion=str(last_error),
                        document_text=document_text,
                        tipo_titular=tipo_titular,  # CLAVE: mantener tipo
                        datos_regex=datos_regex     # CLAVE: dar pistas
                    )
                    
                    # Mostrar análisis del intento anterior
                    if last_json:
                        analisis = analizar_json_parcial(last_json)
                        print(f"   📊 Análisis anterior: {analisis['porcentaje']}% completo")
                        if analisis["campos_faltantes"]:
                            print(f"   ❌ Faltantes: {', '.join(analisis['campos_faltantes'][:3])}")
                    
                    print(f"   📝 Enviando feedback de corrección")
                
                # Llamar a DeepSeek (determinístico)
                response = self.ollama_service.generate_deterministic(
                    prompt=user_prompt,
                    system=system_prompt,
                    max_tokens=self.config.max_tokens
                )
                
                elapsed = response.get('elapsed_time_seconds', 0)
                print(f"   ⏱️ Tiempo: {elapsed:.2f}s")
                
                # Procesar respuesta
                response_text = response.get('response', '')
                processed = process_deepseek_response(response_text)
                json_data = processed.get('json_data')
                
                if not json_data:
                    print(f"   ⚠️ No se extrajo JSON")
                    last_error = "No se pudo extraer JSON de la respuesta"
                    continue
                
                # Guardar para siguiente intento
                last_json = json_data
                
                # Forzar tipo_titular según clasificación de FASE 1
                # Esto asegura consistencia incluso si el LLM lo cambia
                json_data['tipo_titular'] = tipo_titular
                
                # Intentar validación estricta
                try:
                    EscrituraPublica.model_validate(json_data)
                    print(f"   ✅ Validación estricta EXITOSA")
                    return json_data, attempt + 1, True
                    
                except ValidationError as e:
                    last_error = str(e)
                    print(f"   ⚠️ Validación estricta falló")
                    
                    # Mostrar problemas específicos
                    analisis = analizar_json_parcial(json_data)
                    if analisis.get("problemas_detectados"):
                        for problema in analisis["problemas_detectados"][:2]:
                            print(f"      - {problema}")
                    
            except Exception as e:
                last_error = str(e)
                print(f"   ⚠️ Error: {e}")
        
        # Después de todos los intentos
        print(f"\n⚠️ Usando validación flexible (mejor JSON obtenido)")
        return json_data, self.config.max_retries, False
    
    def _step_ocr(self, pdf_path: str) -> Tuple[str, dict]:
        """Paso 1: OCR del PDF."""
        return self.ocr_service.extract_text(pdf_path)
    
    def _log_result(self, result: ExtractionResult):
        """Log del resultado final."""
        print("\n" + "=" * 50)
        
        if result.success:
            if result.validacion_estricta:
                print("✅ EXTRACCIÓN EXITOSA (validación estricta)")
            else:
                print("⚠️ EXTRACCIÓN PARCIAL (validación flexible)")
                print(f"   Campos encontrados: {result.campos_encontrados}/8")
                if result.campos_no_encontrados:
                    print(f"   Campos faltantes: {', '.join(result.campos_no_encontrados)}")
        else:
            print(f"❌ EXTRACCIÓN FALLIDA: {result.error}")
        
        print(f"📋 Tipo detectado: {result.tipo_detectado}")
        print(f"⏱️ Tiempo total: {result.processing_time:.2f}s")
        print(f"🔄 Intentos: {result.intentos_realizados}")
        print(f"🎲 Seed: {result.seed_used}")
        print("=" * 50)
    
    def health_check(self) -> Dict[str, bool]:
        """Verifica servicios."""
        return {
            'ollama': self.ollama_service.health_check(),
            'azure_ocr': self.ocr_service is not None
        }


# === FUNCIÓN DE CONVENIENCIA ===

def extract_escritura(pdf_path: str, **kwargs) -> ExtractionResult:
    """
    Función simple para extraer escritura.
    
    Uso:
        result = extract_escritura("documento.pdf")
        if result.success:
            print(result.data)
            print(f"Tipo: {result.tipo_detectado}")
            print(f"Campos: {result.campos_encontrados}")
    """
    config = ExtractionConfig(**kwargs)
    extractor = EscrituraExtractor(config=config)
    return extractor.extract(pdf_path)


# === CÓDIGO DE PRUEBA ===

if __name__ == "__main__":
    print("=" * 60)
    print("EXTRACTOR DE ESCRITURAS PÚBLICAS")
    print("Estrategia: Divide y Vencerás")
    print("=" * 60)
    
    extractor = EscrituraExtractor()
    
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
    print("       print(f'Tipo: {result.tipo_detectado}')")
