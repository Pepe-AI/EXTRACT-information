"""
app/extractor.py - Extractor con Sistema Híbrido (Plan A + C)

ARQUITECTURA HÍBRIDA:
=====================

┌─────────────────────────────────────────────────────────────────────┐
│                         FLUJO COMPLETO                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐      ┌──────────────┐      ┌─────────────────────┐   │
│  │   PDF    │ ───> │  Azure OCR   │ ───> │   Texto limpio      │   │
│  └──────────┘      └──────────────┘      └──────────┬──────────┘   │
│                                                     │               │
│                                                     ▼               │
│                                          ┌──────────────────────┐   │
│                                          │  FASE 1: CLASIFICAR  │   │
│                                          │  (Prompt ligero)     │   │
│                                          │  ~5-10 segundos      │   │
│                                          └──────────┬───────────┘   │
│                                                     │               │
│                              ┌──────────────────────┼───────────┐   │
│                              │                      │           │   │
│                              ▼                      ▼           │   │
│                    ┌─────────────────┐   ┌─────────────────┐    │   │
│                    │ Validar con     │   │ Validar con     │    │   │
│                    │ regex (Python)  │   │ regex (Python)  │    │   │
│                    └────────┬────────┘   └────────┬────────┘    │   │
│                             │                     │             │   │
│                             └──────────┬──────────┘             │   │
│                                        │                        │   │
│                                        ▼                        │   │
│                             ┌──────────────────────┐            │   │
│                             │  FASE 2: EXTRAER     │            │   │
│                             │  (Prompt específico) │            │   │
│                             │  Con clasificación   │            │   │
│                             └──────────┬───────────┘            │   │
│                                        │                        │   │
│                                        ▼                        │   │
│                             ┌──────────────────────┐            │   │
│                             │  Validación Pydantic │            │   │
│                             │  + Retry si falla    │            │   │
│                             └──────────────────────┘            │   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

VENTAJAS DEL SISTEMA HÍBRIDO:
=============================
1. Clasificación previa reduce errores de confusión titular/representante
2. Prompt específico por tipo (empresa vs persona) = menos ambigüedad
3. Validación con regex como "segunda opinión"
4. Retry inteligente mantiene la clasificación original
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
)
from utils.prompt_builder import (
    build_extraction_prompt,
    build_validation_prompt,
    estimate_tokens,
    limpiar_json_extra,  # NUEVO: Limpia campos extra del JSON
)
from utils.clasificador import (
    clasificar_documento,
    ResultadoClasificacion,
    detectar_tipo_por_nombre,
    validar_representante_no_es_institucion,
)

# Modelos
from models.escritura import (
    EscrituraPublica,
    EscrituraPublicaFlexible,
    validar_json_flexible,
    generar_feedback_error,
    analizar_json_parcial,
)


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
    use_classification: bool = True  # Habilitar sistema híbrido


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
    
    Atributos de clasificación (NUEVOS):
    ====================================
    - clasificacion: Resultado de la Fase 1
    - tipo_detectado: "empresa" o "persona"
    - metodo_clasificacion: Cómo se determinó el tipo
    
    Atributos de debug:
    ===================
    - thinking: Contenido del bloque <think> de DeepSeek
    - raw_json: JSON crudo antes de validación
    - intentos_realizados: Número de intentos de extracción
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
    retries_used: int = 0  # Alias para compatibilidad
    campos_encontrados: int = 0
    campos_no_encontrados: list = field(default_factory=list)
    
    # Nuevos campos para sistema híbrido
    clasificacion: Optional[Dict[str, Any]] = None
    tipo_detectado: str = ""
    metodo_clasificacion: str = ""


# =============================================================================
# EXTRACTOR PRINCIPAL
# =============================================================================

class EscrituraExtractor:
    """
    Extractor de escrituras públicas con Sistema Híbrido.
    
    FLUJO:
    ======
    1. OCR del PDF (Azure Document Intelligence)
    2. Limpieza del texto (eliminar ruido, watermarks, etc.)
    3. FASE 1: Clasificación ligera (determinar tipo de titular)
    4. FASE 2: Extracción con prompt específico según clasificación
    5. Validación con Pydantic + retry si falla
    
    Ejemplo de uso:
    ===============
    >>> extractor = EscrituraExtractor()
    >>> result = extractor.extract("escritura.pdf")
    >>> if result.success:
    ...     print(result.data)
    ...     print(f"Tipo: {result.tipo_detectado}")
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
        
        print(f"🔧 Extractor inicializado (Sistema Híbrido)")
        print(f"   - Modelo: {self.ollama_service.config.model}")
        print(f"   - Clasificación previa: {'✅ Habilitada' if self.config.use_classification else '❌ Deshabilitada'}")
        print(f"   - Max reintentos: {self.config.max_retries}")
        print(f"   - Temperature: {self.config.temperature}")
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extrae información de una escritura pública.
        
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
            # PASO 3: FASE 1 - Clasificación (si está habilitada)
            # =================================================================
            clasificacion = None
            tipo_titular = None
            nombre_titular = None
            nombre_representante = None
            
            if self.config.use_classification:
                print(f"\n🔍 Paso 3: FASE 1 - Clasificando documento...")
                clasificacion = clasificar_documento(
                    texto_documento=clean_text,
                    ollama_service=self.ollama_service
                )
                
                tipo_titular = clasificacion.tipo_titular
                nombre_titular = clasificacion.nombre_titular
                nombre_representante = clasificacion.nombre_representante
                
                result.clasificacion = clasificacion.to_dict()
                result.tipo_detectado = tipo_titular
                result.metodo_clasificacion = clasificacion.metodo
                
                print(f"   ✅ Tipo detectado: {tipo_titular.upper()}")
                print(f"   📋 Confianza: {clasificacion.confianza}")
                if nombre_titular:
                    print(f"   👤 Titular: {nombre_titular[:50]}...")
                if nombre_representante:
                    print(f"   👔 Representante: {nombre_representante}")
            else:
                print(f"\n⚠️ Paso 3: Clasificación deshabilitada, usando prompt genérico")
            
            # =================================================================
            # PASO 4: FASE 2 - Extracción con prompt específico
            # =================================================================
            print(f"\n🤖 Paso 4: FASE 2 - Extrayendo datos...")
            
            json_data, intentos, validacion_estricta, thinking = self._fase2_extraer(
                document_text=formatted_text,
                tipo_titular=tipo_titular,
                nombre_titular=nombre_titular,
                nombre_representante=nombre_representante
            )
            
            result.intentos_realizados = intentos
            result.retries_used = intentos  # Alias
            result.raw_json = json_data
            result.thinking = thinking
            result.model_used = self.ollama_service.config.model
            
            # =================================================================
            # PASO 5: Validación post-extracción
            # =================================================================
            if json_data:
                # Validar consistencia del tipo_titular con regex
                json_data = self._validar_y_corregir_tipo(json_data, tipo_titular)
                
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
                    result.data = reporte["datos_completos"]
                    result.reporte = reporte
                    result.success = True
                    result.campos_encontrados = reporte["resumen"]["campos_encontrados"]
                    result.campos_no_encontrados = reporte["campos_faltantes"]
                    
                    print(f"\n⚠️ Validación FLEXIBLE aplicada")
                    print(f"   📊 Campos encontrados: {result.campos_encontrados}/8")
                    if result.campos_no_encontrados:
                        print(f"   ❌ Faltantes: {', '.join(result.campos_no_encontrados)}")
            else:
                result.error = "No se pudo extraer JSON del documento"
                print(f"\n❌ Error: No se extrajo JSON válido")
        
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
        document_text: str,
        tipo_titular: str = None,
        nombre_titular: str = None,
        nombre_representante: str = None
    ) -> Tuple[Optional[Dict], int, bool, Optional[str]]:
        """
        FASE 2: Extracción con prompt específico y sistema de retry.
        
        Esta función:
        1. Construye el prompt con la clasificación previa
        2. Envía a DeepSeek para extracción
        3. Valida la respuesta
        4. Si falla, reintenta con feedback
        
        Args:
            document_text: Texto del documento (ya formateado)
            tipo_titular: "empresa" o "persona" (de Fase 1)
            nombre_titular: Nombre del titular identificado
            nombre_representante: Nombre del representante identificado
            
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
                    # Primer intento: prompt con clasificación
                    system_prompt, user_prompt = build_extraction_prompt(
                        document_text=document_text,
                        tipo_titular=tipo_titular,
                        nombre_titular=nombre_titular,
                        nombre_representante=nombre_representante,
                        include_examples=self.config.include_examples
                    )
                    print(f"      📝 Prompt específico para: {tipo_titular or 'genérico'}")
                else:
                    # Retry: prompt de corrección
                    system_prompt, user_prompt = build_validation_prompt(
                        json_anterior=last_json,
                        error_validacion=str(last_error),
                        document_text=document_text[:2000],  # Truncar para retry
                        tipo_titular=tipo_titular,
                        nombre_titular=nombre_titular,
                        nombre_representante=nombre_representante
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
                
                if not json_data:
                    print(f"      ⚠️ No se extrajo JSON de la respuesta")
                    last_error = "No se pudo parsear JSON de la respuesta"
                    continue
                
                # ============================================================
                # LIMPIEZA DE CAMPOS EXTRA (CRÍTICO)
                # ============================================================
                # El LLM a veces agrega campos no solicitados como:
                # - "documento", "inmueble", "firmas"
                # - "representante_legal" (debe estar dentro de representante)
                # Esta función los elimina y corrige la estructura.
                # ============================================================
                print(f"      🧹 Limpiando campos extra del JSON...")
                json_data = limpiar_json_extra(json_data)
                
                # Guardar para siguiente intento
                last_json = json_data
                
                # Forzar tipo_titular de la clasificación si existe
                if tipo_titular:
                    if json_data.get('tipo_titular') != tipo_titular:
                        print(f"      🔧 Corrigiendo tipo_titular: {json_data.get('tipo_titular')} → {tipo_titular}")
                    json_data['tipo_titular'] = tipo_titular
                
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
                    
                    # Mostrar análisis del JSON
                    analisis = analizar_json_parcial(json_data, tipo_titular)
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
    
    def _validar_y_corregir_tipo(
        self,
        json_data: Dict[str, Any],
        tipo_clasificado: str = None
    ) -> Dict[str, Any]:
        """
        Valida y corrige inconsistencias en el tipo_titular.
        
        Esta función actúa como "última línea de defensa" usando
        regex para detectar y corregir errores que el LLM pudo cometer.
        
        Args:
            json_data: JSON extraído
            tipo_clasificado: Tipo de la clasificación previa
            
        Returns:
            JSON corregido (si hubo correcciones)
        """
        
        tipo_json = json_data.get('tipo_titular', '')
        titulares = json_data.get('titulares', [])
        
        for i, titular in enumerate(titulares):
            if not isinstance(titular, dict):
                continue
            
            nombre = titular.get('nombre', '')
            representante = titular.get('representante')
            
            # Verificar si el nombre del titular es una institución
            tipo_detectado, patrones = detectar_tipo_por_nombre(nombre)
            
            if tipo_detectado == "empresa" and tipo_json == "persona":
                print(f"\n   🔧 POST-CORRECCIÓN: Cambiando tipo_titular a 'empresa'")
                print(f"      Razón: '{nombre[:40]}...' parece empresa ({', '.join(patrones[:2])})")
                json_data['tipo_titular'] = "empresa"
            
            # Verificar si el representante es una institución (error grave)
            if representante and isinstance(representante, dict):
                nombre_rep = representante.get('nombre', '')
                tipo_rep, patrones_rep = detectar_tipo_por_nombre(nombre_rep)
                
                if tipo_rep == "empresa":
                    print(f"\n   🔧 POST-CORRECCIÓN: Intercambiando titular ↔ representante")
                    print(f"      Razón: El representante '{nombre_rep[:30]}...' parece institución")
                    
                    # Intercambiar: el "representante" es el titular real
                    titular['nombre'], representante['nombre'] = representante['nombre'], titular['nombre']
                    json_data['tipo_titular'] = "empresa"
        
        return json_data
    
    def _log_resultado_final(self, result: ExtractionResult):
        """
        Imprime el resumen final de la extracción.
        """
        print(f"\n{'='*60}")
        print(f"📊 RESULTADO FINAL")
        print(f"{'='*60}")
        
        if result.success:
            if result.validacion_estricta:
                print(f"✅ EXTRACCIÓN EXITOSA (validación estricta)")
            else:
                print(f"⚠️ EXTRACCIÓN PARCIAL (validación flexible)")
                print(f"   Campos encontrados: {result.campos_encontrados}/8")
                if result.campos_no_encontrados:
                    print(f"   Campos faltantes: {', '.join(result.campos_no_encontrados)}")
        else:
            print(f"❌ EXTRACCIÓN FALLIDA")
            print(f"   Error: {result.error}")
        
        if result.tipo_detectado:
            print(f"\n📋 Clasificación:")
            print(f"   Tipo: {result.tipo_detectado}")
            print(f"   Método: {result.metodo_clasificacion}")
        
        print(f"\n⏱️ Tiempo total: {result.processing_time:.2f}s")
        print(f"🔄 Intentos: {result.intentos_realizados}")
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
    print("Sistema Híbrido (Plan A + C)")
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
    print("       print(f'Tipo: {result.tipo_detectado}')")
    print("       print(f'Campos: {result.campos_encontrados}/8')")
