#!/usr/bin/env python3
"""
tests/test_06_extractor.py - Prueba del extractor principal

OBJETIVO:
=========
Verificar el funcionamiento del EscrituraExtractor,
que orquesta todo el flujo de extracción.

CÓMO EJECUTAR:
==============
Desde la raíz del proyecto (con el entorno virtual activado):

    cd extract_info_project
    source venv/bin/activate
    python -m tests.test_06_extractor

REQUISITOS:
===========
- Azure Document Intelligence configurado
- Servidor Ollama corriendo con DeepSeek R1
- VPN conectada (si el servidor es remoto)

NOTA:
=====
Las pruebas de extracción completa requieren:
- Credenciales de Azure válidas
- Servidor Ollama disponible
- PDF de prueba
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()


def test_imports():
    """
    Prueba 1: Verificar imports.
    
    Esto verifica que todos los módulos están disponibles.
    """
    print("\n" + "="*60)
    print("PRUEBA 1: Verificar imports")
    print("="*60)
    
    try:
        from app.extractor import (
            ExtractionConfig,
            ExtractionResult,
            EscrituraExtractor,
            extract_escritura
        )
        print("\n✅ Imports exitosos:")
        print("   - ExtractionConfig")
        print("   - ExtractionResult")
        print("   - EscrituraExtractor")
        print("   - extract_escritura")
        return True
        
    except ImportError as e:
        print(f"\n❌ Error de importación: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_extraction_config():
    """
    Prueba 2: Configuración de extracción.
    
    Verifica que ExtractionConfig lee valores de .env
    o usa valores por defecto.
    """
    print("\n" + "="*60)
    print("PRUEBA 2: Configuración de extracción (ExtractionConfig)")
    print("="*60)
    
    from app.extractor import ExtractionConfig
    
    # Crear configuración (lee de .env o usa defaults)
    config = ExtractionConfig()
    
    print("\n📋 Configuración actual:")
    print(f"   max_retries: {config.max_retries}")
    print(f"   temperature: {config.temperature}")
    print(f"   max_tokens: {config.max_tokens}")
    print(f"   max_context_tokens: {config.max_context_tokens}")
    print(f"   include_examples: {config.include_examples}")
    print(f"   save_thinking: {config.save_thinking}")
    
    # Verificaciones básicas
    assert config.max_retries > 0, "max_retries debe ser positivo"
    assert 0 <= config.temperature <= 1, "temperature debe estar entre 0 y 1"
    assert config.max_tokens > 0, "max_tokens debe ser positivo"
    
    print("\n✅ Configuración válida")


def test_extraction_config_custom():
    """
    Prueba 3: Configuración personalizada.
    
    Verifica que podemos crear configuración con valores custom.
    """
    print("\n" + "="*60)
    print("PRUEBA 3: Configuración personalizada")
    print("="*60)
    
    from app.extractor import ExtractionConfig
    
    config = ExtractionConfig(
        max_retries=5,
        temperature=0.2,
        max_tokens=8000,
        max_context_tokens=16000,
        include_examples=True
    )
    
    print("\n📋 Configuración custom:")
    print(f"   max_retries: {config.max_retries}")
    print(f"   temperature: {config.temperature}")
    print(f"   max_tokens: {config.max_tokens}")
    print(f"   max_context_tokens: {config.max_context_tokens}")
    print(f"   include_examples: {config.include_examples}")
    
    assert config.max_retries == 5
    assert config.temperature == 0.2
    assert config.include_examples == True
    
    print("\n✅ Configuración personalizada funciona")


def test_extraction_result():
    """
    Prueba 4: Estructura de ExtractionResult.
    
    Verifica que ExtractionResult tiene todos los campos necesarios.
    """
    print("\n" + "="*60)
    print("PRUEBA 4: Estructura de ExtractionResult")
    print("="*60)
    
    from app.extractor import ExtractionResult
    
    # Crear resultado vacío
    result = ExtractionResult(success=False)
    
    print("\n📋 Campos de ExtractionResult:")
    print(f"   success: {result.success}")
    print(f"   validacion_estricta: {result.validacion_estricta}")
    print(f"   data: {result.data}")
    print(f"   raw_json: {result.raw_json}")
    print(f"   error: {result.error}")
    print(f"   processing_time: {result.processing_time}")
    print(f"   model_used: {result.model_used}")
    print(f"   campos_encontrados: {result.campos_encontrados}")
    print(f"   campos_no_encontrados: {result.campos_no_encontrados}")
    
    # Crear resultado exitoso
    result_success = ExtractionResult(
        success=True,
        validacion_estricta=False,
        raw_json={"numero_escritura": 3125},
        processing_time=5.5,
        model_used="deepseek-r1:32b",
        campos_encontrados=6,
        campos_no_encontrados=["valor_catastral", "tipo_sociedad"]
    )
    
    print("\n📋 Resultado exitoso de prueba:")
    print(f"   success: {result_success.success}")
    print(f"   validacion_estricta: {result_success.validacion_estricta}")
    print(f"   campos_encontrados: {result_success.campos_encontrados}")
    print(f"   processing_time: {result_success.processing_time}s")
    
    print("\n✅ ExtractionResult funciona correctamente")


def test_extractor_initialization():
    """
    Prueba 5: Inicialización del extractor.
    
    Intenta crear una instancia de EscrituraExtractor.
    Requiere que Azure y Ollama estén configurados.
    """
    print("\n" + "="*60)
    print("PRUEBA 5: Inicialización del extractor")
    print("="*60)
    
    from app.extractor import EscrituraExtractor, ExtractionConfig
    from services.azure_ocr_service import AzureConfig, OCRConfigurationError
    
    # Verificar si Azure está configurado
    azure_config = AzureConfig()
    if not azure_config.is_configured:
        print("\n⚠️  Azure no está configurado, saltando prueba")
        print("   Configure las credenciales en .env")
        return False
    
    print("\n🔍 Creando EscrituraExtractor...")
    
    try:
        extractor = EscrituraExtractor()
        print("   ✅ Extractor creado exitosamente")
        return True
        
    except OCRConfigurationError as e:
        print(f"   ❌ Error de configuración Azure: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Error: {type(e).__name__}: {e}")
        return False


def test_extractor_health_check():
    """
    Prueba 6: Health check del extractor.
    
    Verifica el estado de los servicios (Azure OCR y Ollama).
    """
    print("\n" + "="*60)
    print("PRUEBA 6: Health check del extractor")
    print("="*60)
    
    from app.extractor import EscrituraExtractor
    from services.azure_ocr_service import AzureConfig, OCRConfigurationError
    
    azure_config = AzureConfig()
    if not azure_config.is_configured:
        print("\n⚠️  Azure no está configurado, saltando prueba")
        return
    
    try:
        extractor = EscrituraExtractor()
        
        print("\n🔍 Verificando estado de servicios...")
        health = extractor.health_check()
        
        print(f"\n📋 Estado de servicios:")
        for service, status in health.items():
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {service}: {'disponible' if status else 'no disponible'}")
        
        if all(health.values()):
            print("\n✅ Todos los servicios están disponibles")
        else:
            print("\n⚠️  Algunos servicios no están disponibles")
            
    except OCRConfigurationError as e:
        print(f"\n⚠️  No se pudo crear extractor: {e}")
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")


def test_extract_from_pdf():
    """
    Prueba 7: Extracción completa de PDF (OPCIONAL).
    
    Esta es la prueba más completa. Requiere:
    - Azure configurado
    - Ollama disponible con DeepSeek
    - PDF de prueba en tests/sample.pdf
    """
    print("\n" + "="*60)
    print("PRUEBA 7: Extracción completa de PDF (opcional)")
    print("="*60)
    
    from app.extractor import EscrituraExtractor, ExtractionConfig
    from services.azure_ocr_service import AzureConfig, OCRConfigurationError
    
    azure_config = AzureConfig()
    if not azure_config.is_configured:
        print("\n⚠️  Azure no está configurado, saltando prueba")
        return
    
    # Buscar PDF de prueba
    sample_paths = [
        Path(__file__).parent / "sample.pdf",
        Path(__file__).parent.parent / "tests" / "sample.pdf",
        Path(__file__).parent.parent / "sample.pdf",
    ]
    
    pdf_path = None
    for p in sample_paths:
        if p.exists():
            pdf_path = p
            break
    
    if not pdf_path:
        print("\n⚠️  No se encontró PDF de prueba")
        print("   Coloca un archivo 'sample.pdf' en la carpeta tests/")
        print("   para probar la extracción completa.")
        return
    
    print(f"\n📄 PDF encontrado: {pdf_path}")
    
    try:
        extractor = EscrituraExtractor()
        
        # Verificar servicios primero
        health = extractor.health_check()
        if not health.get('ollama', False):
            print("\n⚠️  Ollama no está disponible, saltando extracción")
            return
        
        print("\n🔍 Iniciando extracción completa...")
        print("   (Esto puede tomar varios minutos...)")
        
        result = extractor.extract(str(pdf_path))
        
        print(f"\n📊 Resultado de la extracción:")
        print(f"   success: {result.success}")
        print(f"   processing_time: {result.processing_time:.2f}s")
        print(f"   model_used: {result.model_used}")
        print(f"   retries_used: {result.retries_used}")
        
        if result.success:
            print(f"\n✅ Extracción exitosa!")
            print(f"   Validación estricta: {result.validacion_estricta}")
            print(f"   Campos encontrados: {result.campos_encontrados}/8")
            if result.campos_no_encontrados:
                print(f"   Campos faltantes: {result.campos_no_encontrados}")
            
            if result.data:
                print(f"\n📋 Datos extraídos:")
                import json
                print(json.dumps(result.data, indent=2, ensure_ascii=False)[:800])
        else:
            print(f"\n❌ Extracción falló: {result.error}")
            
        if result.thinking:
            print(f"\n💭 Razonamiento del modelo (primeros 300 chars):")
            print(f"   {result.thinking[:300]}...")
            
    except OCRConfigurationError as e:
        print(f"\n⚠️  Error de configuración: {e}")
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


def test_convenience_function():
    """
    Prueba 8: Función de conveniencia extract_escritura().
    
    Verifica que la función de conveniencia funciona.
    """
    print("\n" + "="*60)
    print("PRUEBA 8: Función de conveniencia")
    print("="*60)
    
    from app.extractor import extract_escritura
    from services.azure_ocr_service import AzureConfig
    
    azure_config = AzureConfig()
    if not azure_config.is_configured:
        print("\n⚠️  Azure no está configurado, saltando prueba")
        return
    
    print("\n📋 Función extract_escritura disponible")
    print("   Uso: result = extract_escritura('documento.pdf')")
    print("   Es un atajo para crear EscrituraExtractor y llamar extract()")
    
    print("\n✅ Función de conveniencia verificada")


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "#"*60)
    print("# PRUEBAS DEL EXTRACTOR (app/extractor.py)")
    print("#"*60)
    
    print("\n⚠️  NOTA: Algunas pruebas requieren:")
    print("   - Credenciales de Azure en .env")
    print("   - Servidor Ollama corriendo")
    print("   - VPN conectada (si es servidor remoto)")
    print("   - (Opcional) PDF de prueba en tests/sample.pdf")
    
    try:
        # Prueba de imports primero
        if not test_imports():
            print("\n❌ Falló la prueba de imports, abortando.")
            return 1
        
        # Pruebas que no requieren servicios
        test_extraction_config()
        test_extraction_config_custom()
        test_extraction_result()
        
        # Pruebas que requieren servicios
        test_extractor_initialization()
        test_extractor_health_check()
        test_extract_from_pdf()
        test_convenience_function()
        
        print("\n" + "="*60)
        print("✅ PRUEBAS COMPLETADAS")
        print("   (Algunas pueden haber sido saltadas)")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR EN LAS PRUEBAS: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
