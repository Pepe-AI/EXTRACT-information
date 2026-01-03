"""
app/extractor.py - Extractor con retry inteligente y validación flexible

FLUJO:
======
1. OCR del PDF
2. Limpieza de texto
3. Primera extracción con DeepSeek
4. Validación ESTRICTA
   ├─ Si pasa → Éxito completo
   └─ Si falla → Retry con feedback (hasta 3 veces)
5. Después de 3 intentos fallidos → Validación FLEXIBLE
   ├─ Acepta lo que hay
   ├─ Marca campos faltantes
   └─ Genera reporte

CARACTERÍSTICAS:
================
- Retry con feedback: Envía el error a DeepSeek para que corrija
- Validación flexible: No falla, acepta datos parciales
- Reporte detallado: Muestra qué se encontró y qué no
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
    format_for_prompt
)
from utils.prompt_builder import build_extraction_prompt

# Modelos
from models.escritura import (
    EscrituraPublica,
    EscrituraPublicaFlexible,
    ExtractionResponse,
    validar_json_flexible,
    generar_feedback_error
)


@dataclass
class ExtractionConfig:
    """Configuración del extractor."""
    
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_RETRIES", "3"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.getenv("TEMPERATURE", "0.1"))
    )
    max_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOKENS", "4096"))
    )
    max_context_tokens: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONTEXT_TOKENS", "8000"))
    )
    include_examples: bool = True
    save_thinking: bool = True


@dataclass
class ExtractionResult:
    """Resultado de la extracción."""
    
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


class EscrituraExtractor:
    """
    Extractor de escrituras públicas con validación flexible.
    
    Características:
    - Retry con feedback cuando falla validación
    - Validación flexible si no se logra estricta
    - Reporte de campos encontrados/no encontrados
    """
    
    def __init__(
        self,
        config: Optional[ExtractionConfig] = None,
        ollama_config: Optional[OllamaConfig] = None,
        azure_config: Optional[AzureConfig] = None
    ):
        self.config = config or ExtractionConfig()
        self.ollama_service = get_ollama_service(ollama_config)
        self.ocr_service = get_ocr_service(azure_config)
        
        print(f"🔧 Extractor inicializado")
        print(f"   - Modelo: {self.ollama_service.config.model}")
        print(f"   - Max reintentos: {self.config.max_retries}")
    
    def extract(self, pdf_path: str) -> ExtractionResult:
        """
        Extrae información de una escritura pública.
        
        Flujo:
        1. OCR
        2. Limpieza
        3. Extracción con reintentos
        4. Validación estricta o flexible
        """
        
        start_time = time.time()
        result = ExtractionResult(success=False)
        
        try:
            # === PASO 1: OCR ===
            print(f"\n📄 Procesando: {pdf_path}")
            ocr_text, ocr_meta = self._step_ocr(pdf_path)
            result.ocr_metadata = ocr_meta
            print(f"   ✅ OCR completado: {ocr_meta.get('pages', '?')} páginas")
            
            # === PASO 2: Limpiar texto ===
            clean_content = self._step_clean_text(ocr_text)
            print(f"   ✅ Texto limpiado: {len(clean_content)} caracteres")
            
            # === PASO 3-4: Extracción con reintentos ===
            json_data, intentos, validacion_estricta = self._extract_with_retries(clean_content)
            
            result.intentos_realizados = intentos
            result.raw_json = json_data
            result.model_used = self.ollama_service.config.model
            
            if json_data:
                # === PASO 5: Validación final ===
                if validacion_estricta:
                    # Pasó validación estricta
                    result.validacion_estricta = True
                    result.data = json_data
                    result.success = True
                    result.campos_encontrados = 8
                    result.campos_no_encontrados = []
                    print(f"\n✅ Validación ESTRICTA exitosa")
                else:
                    # Usar validación flexible
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
                    print(f"   ❌ Campos faltantes: {result.campos_no_encontrados}")
            else:
                result.error = "No se pudo extraer JSON del documento"
        
        except FileNotFoundError as e:
            result.error = f"Archivo no encontrado: {e}"
        except Exception as e:
            result.error = f"Error: {e}"
        
        result.processing_time = time.time() - start_time
        
        # Log final
        self._log_result(result)
        
        return result
    
    def _extract_with_retries(self, document: str) -> Tuple[Optional[Dict], int, bool]:
        """
        Intenta extraer con reintentos y feedback INTELIGENTE.
        
        MEJORA: Envía el JSON del intento anterior para que DeepSeek
        CORRIJA en lugar de empezar desde cero.
        
        Returns:
            (json_data, intentos_usados, paso_validacion_estricta)
        """
        
        last_error = None
        last_json = None  # JSON del intento anterior
        json_data = None
        
        for attempt in range(self.config.max_retries):
            print(f"\n🤖 Intento {attempt + 1}/{self.config.max_retries}")
            
            try:
                # Construir prompt
                if attempt == 0:
                    # Primer intento: prompt normal
                    system_prompt, user_prompt = build_extraction_prompt(
                        document,
                        include_examples=self.config.include_examples
                    )
                else:
                    # Reintentos: agregar feedback CON el JSON anterior
                    system_prompt, user_prompt = build_extraction_prompt(
                        document,
                        include_examples=self.config.include_examples
                    )
                    
                    # Generar feedback inteligente con el JSON anterior
                    feedback = generar_feedback_error(
                        error_validacion=str(last_error),
                        json_anterior=last_json  # ← NUEVO: enviamos el JSON anterior
                    )
                    user_prompt = user_prompt + "\n\n" + feedback
                    
                    print(f"   📝 Enviando feedback con JSON anterior")
                    if last_json:
                        # Mostrar resumen de lo que tiene el JSON anterior
                        from models.escritura import analizar_json_parcial
                        analisis = analizar_json_parcial(last_json)
                        print(f"   📊 JSON anterior: {analisis['porcentaje']}% completo")
                        print(f"      ✅ Tiene: {', '.join(analisis['campos_encontrados'][:3])}...")
                        print(f"      ❌ Falta: {', '.join(analisis['campos_faltantes'][:3])}...")
                
                # Llamar a DeepSeek
                response = self._step_inference(system_prompt, user_prompt)
                
                # Procesar respuesta
                processed = process_deepseek_response(response)
                json_data = processed.get('json_data')
                
                if not json_data:
                    print(f"   ⚠️ No se extrajo JSON")
                    last_error = "No se pudo extraer JSON de la respuesta"
                    # No actualizamos last_json porque no hay JSON nuevo
                    continue
                
                # Guardar JSON para el siguiente intento (si falla)
                last_json = json_data
                
                # Intentar validación ESTRICTA
                try:
                    EscrituraPublica.model_validate(json_data)
                    print(f"   ✅ Validación estricta EXITOSA")
                    return json_data, attempt + 1, True
                    
                except ValidationError as e:
                    last_error = str(e)
                    print(f"   ⚠️ Validación estricta falló")
                    
                    # Mostrar qué campos faltan
                    from models.escritura import analizar_json_parcial
                    analisis = analizar_json_parcial(json_data)
                    if analisis['problemas_detectados']:
                        print(f"   🔍 Problemas detectados:")
                        for problema in analisis['problemas_detectados'][:3]:
                            print(f"      - {problema}")
                    
            except Exception as e:
                last_error = str(e)
                print(f"   ⚠️ Error: {e}")
        
        # Después de todos los intentos, devolver lo que tengamos
        print(f"\n⚠️ Validación estricta falló después de {self.config.max_retries} intentos")
        print(f"   Usando validación flexible con el mejor JSON obtenido")
        return json_data, self.config.max_retries, False
    
    def _step_ocr(self, pdf_path: str) -> Tuple[str, dict]:
        """Paso 1: OCR del PDF."""
        return self.ocr_service.extract_text(pdf_path)
    
    def _step_clean_text(self, text: str) -> str:
        """Paso 2: Limpiar texto."""
        clean = clean_ocr_text(text)
        return format_for_prompt(clean, self.config.max_context_tokens)
    
    def _step_inference(self, system: str, prompt: str) -> str:
        """Paso 3: Ejecutar inferencia."""
        result = self.ollama_service.generate(
            prompt=prompt,
            system=system,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )
        
        elapsed = result.get('elapsed_time_seconds', 0)
        print(f"   ⏱️ Tiempo inferencia: {elapsed:.2f}s")
        
        return result.get('response', '')
    
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
        
        print(f"⏱️ Tiempo total: {result.processing_time:.2f}s")
        print(f"🔄 Intentos: {result.intentos_realizados}")
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
            print(f"Campos encontrados: {result.campos_encontrados}")
    """
    config = ExtractionConfig(**kwargs)
    extractor = EscrituraExtractor(config=config)
    return extractor.extract(pdf_path)


# === CÓDIGO DE PRUEBA ===

if __name__ == "__main__":
    print("=" * 60)
    print("EXTRACTOR DE ESCRITURAS PÚBLICAS")
    print("Con retry inteligente y validación flexible")
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
    print("       print(result.data)  # Datos encontrados")
    print("       print(result.campos_no_encontrados)  # Campos faltantes")
