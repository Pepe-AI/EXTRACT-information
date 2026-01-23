#!/usr/bin/env python3
"""
tests/test_05_azure_ocr_service.py - Prueba del servicio OCR de Azure

OBJETIVO:
=========
Verificar la configuración y funcionamiento del servicio
Azure Document Intelligence para OCR.

CÓMO EJECUTAR:
==============
Desde la raíz del proyecto (con el entorno virtual activado):

    cd extract_info_project
    source venv/bin/activate
    python -m tests.test_05_azure_ocr_service

REQUISITOS:
===========
- Credenciales de Azure configuradas en .env:
  - AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
  - AZURE_DOCUMENT_INTELLIGENCE_KEY
- azure-ai-documentintelligence instalado

NOTA:
=====
Las pruebas de extracción real requieren un PDF de prueba
y credenciales válidas de Azure.
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
    Prueba 1: Verificar que los imports funcionan.
    
    Esto verifica que el SDK de Azure está instalado.
    """
    print("\n" + "="*60)
    print("PRUEBA 1: Verificar imports")
    print("="*60)
    
    try:
        from services.azure_ocr_service import (
            AzureConfig,
            AzureOCRService,
            get_ocr_service,
            OCRServiceError,
            OCRConfigurationError,
            OCRConnectionError,
            OCRAuthenticationError,
            OCRQuotaExceededError,
            OCRProcessingError
        )
        print("\n✅ Todos los imports exitosos")
        print("   - AzureConfig")
        print("   - AzureOCRService")
        print("   - get_ocr_service")
        print("   - Excepciones personalizadas (5)")
        
    except ImportError as e:
        print(f"\n❌ Error de importación: {e}")
        print("   Puede que falte instalar: pip install azure-ai-documentintelligence")
        return False
    
    return True


def test_azure_config():
    """
    Prueba 2: Configuración de Azure.
    
    Verifica que la configuración lee las variables de entorno.
    """
    print("\n" + "="*60)
    print("PRUEBA 2: Configuración de Azure (AzureConfig)")
    print("="*60)
    
    from services.azure_ocr_service import AzureConfig
    
    config = AzureConfig()
    
    print("\n📋 Configuración actual:")
    
    # Mostrar endpoint (parcialmente oculto por seguridad)
    if config.endpoint:
        endpoint_display = config.endpoint[:30] + "..." if len(config.endpoint) > 30 else config.endpoint
        print(f"   Endpoint: {endpoint_display}")
    else:
        print("   Endpoint: ❌ NO CONFIGURADO")
    
    # Mostrar key (oculta por seguridad)
    if config.key:
        key_display = config.key[:8] + "****" + config.key[-4:] if len(config.key) > 12 else "****"
        print(f"   Key: {key_display}")
    else:
        print("   Key: ❌ NO CONFIGURADA")
    
    print(f"   is_configured: {config.is_configured}")
    
    if config.is_configured:
        print("\n✅ Azure está configurado correctamente")
    else:
        print("\n⚠️  Azure NO está configurado")
        print("   Configure en .env:")
        print("   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://tu-recurso.cognitiveservices.azure.com/")
        print("   AZURE_DOCUMENT_INTELLIGENCE_KEY=tu-clave-aqui")
    
    return config.is_configured


def test_azure_config_custom():
    """
    Prueba 3: Configuración personalizada.
    
    Verifica que podemos crear configuración con valores custom.
    """
    print("\n" + "="*60)
    print("PRUEBA 3: Configuración personalizada")
    print("="*60)
    
    from services.azure_ocr_service import AzureConfig
    
    config = AzureConfig(
        endpoint="https://test-resource.cognitiveservices.azure.com/",
        key="test-key-12345"
    )
    
    print(f"\n📋 Configuración custom:")
    print(f"   Endpoint: {config.endpoint}")
    print(f"   Key: {config.key[:8]}****")
    print(f"   is_configured: {config.is_configured}")
    
    assert config.endpoint == "https://test-resource.cognitiveservices.azure.com/"
    assert config.key == "test-key-12345"
    assert config.is_configured == True
    
    print("\n✅ Configuración personalizada funciona")


def test_exceptions_hierarchy():
    """
    Prueba 4: Jerarquía de excepciones.
    
    Verifica que las excepciones están bien definidas
    y heredan de OCRServiceError.
    """
    print("\n" + "="*60)
    print("PRUEBA 4: Jerarquía de excepciones")
    print("="*60)
    
    from services.azure_ocr_service import (
        OCRServiceError,
        OCRConfigurationError,
        OCRConnectionError,
        OCRAuthenticationError,
        OCRQuotaExceededError,
        OCRProcessingError
    )
    
    # Verificar herencia
    exceptions = [
        ("OCRConfigurationError", OCRConfigurationError),
        ("OCRConnectionError", OCRConnectionError),
        ("OCRAuthenticationError", OCRAuthenticationError),
        ("OCRQuotaExceededError", OCRQuotaExceededError),
        ("OCRProcessingError", OCRProcessingError),
    ]
    
    print("\n📋 Jerarquía de excepciones:")
    print(f"   OCRServiceError (base)")
    
    for name, exc_class in exceptions:
        is_subclass = issubclass(exc_class, OCRServiceError)
        status = "✅" if is_subclass else "❌"
        print(f"   {status} └── {name}")
        assert is_subclass, f"{name} debe heredar de OCRServiceError"
    
    # Probar que se pueden lanzar y capturar
    print("\n🔍 Probando captura de excepciones:")
    
    try:
        raise OCRAuthenticationError("Credenciales inválidas")
    except OCRServiceError as e:
        print(f"   ✅ OCRAuthenticationError capturada como OCRServiceError")
        print(f"      Mensaje: {e}")
    
    print("\n✅ Jerarquía de excepciones correcta")


def test_service_without_config():
    """
    Prueba 5: Servicio sin configuración.
    
    Verifica que se lanza OCRConfigurationError
    cuando no hay credenciales.
    """
    print("\n" + "="*60)
    print("PRUEBA 5: Servicio sin configuración")
    print("="*60)
    
    from services.azure_ocr_service import (
        AzureOCRService,
        AzureConfig,
        OCRConfigurationError
    )
    
    # Crear config vacía
    config = AzureConfig(endpoint=None, key=None)
    
    print("\n🔍 Intentando crear servicio sin credenciales...")
    
    try:
        service = AzureOCRService(config)
        print("   ❌ ERROR: Debería haber lanzado OCRConfigurationError")
    except OCRConfigurationError as e:
        print(f"   ✅ Correcto: Se lanzó OCRConfigurationError")
        print(f"      Mensaje: {str(e)[:80]}...")
    except Exception as e:
        print(f"   ⚠️ Se lanzó otra excepción: {type(e).__name__}: {e}")


def test_service_initialization():
    """
    Prueba 6: Inicialización del servicio.
    
    Intenta crear el servicio con las credenciales del .env.
    Si no están configuradas, la prueba se salta.
    """
    print("\n" + "="*60)
    print("PRUEBA 6: Inicialización del servicio")
    print("="*60)
    
    from services.azure_ocr_service import (
        AzureConfig,
        AzureOCRService,
        OCRConfigurationError
    )
    
    config = AzureConfig()
    
    if not config.is_configured:
        print("\n⚠️  Azure no está configurado, saltando prueba")
        print("   Configure las credenciales en .env para probar")
        return
    
    print("\n🔍 Creando servicio con credenciales del .env...")
    
    try:
        service = AzureOCRService(config)
        print("   ✅ Servicio creado exitosamente")
        print(f"      Endpoint: {config.endpoint[:40]}...")
        
    except OCRConfigurationError as e:
        print(f"   ❌ Error de configuración: {e}")
    except Exception as e:
        print(f"   ❌ Error inesperado: {type(e).__name__}: {e}")


def test_singleton_pattern():
    """
    Prueba 7: Patrón Singleton.
    
    Verifica que get_ocr_service() devuelve la misma instancia.
    """
    print("\n" + "="*60)
    print("PRUEBA 7: Patrón Singleton (get_ocr_service)")
    print("="*60)
    
    from services.azure_ocr_service import (
        AzureConfig,
        get_ocr_service,
        OCRConfigurationError
    )
    
    config = AzureConfig()
    
    if not config.is_configured:
        print("\n⚠️  Azure no está configurado, saltando prueba")
        return
    
    print("\n🔍 Obteniendo instancias del servicio...")
    
    try:
        service1 = get_ocr_service()
        service2 = get_ocr_service()
        
        same_instance = service1 is service2
        
        print(f"   service1 id: {id(service1)}")
        print(f"   service2 id: {id(service2)}")
        print(f"   ¿Misma instancia?: {same_instance}")
        
        if same_instance:
            print("\n✅ Patrón Singleton funciona correctamente")
        else:
            print("\n⚠️  No son la misma instancia (puede ser intencional)")
            
    except OCRConfigurationError as e:
        print(f"\n⚠️  No se pudo crear servicio: {e}")


def test_file_not_found():
    """
    Prueba 8: Archivo no encontrado.
    
    Verifica que se lanza FileNotFoundError correctamente.
    """
    print("\n" + "="*60)
    print("PRUEBA 8: Archivo no encontrado")
    print("="*60)
    
    from services.azure_ocr_service import (
        AzureConfig,
        AzureOCRService,
        OCRConfigurationError
    )
    
    config = AzureConfig()
    
    if not config.is_configured:
        print("\n⚠️  Azure no está configurado, saltando prueba")
        return
    
    try:
        service = AzureOCRService(config)
        
        print("\n🔍 Intentando procesar archivo inexistente...")
        
        try:
            service.extract_text("/ruta/inexistente/documento.pdf")
            print("   ❌ ERROR: Debería haber lanzado FileNotFoundError")
        except FileNotFoundError as e:
            print(f"   ✅ Correcto: Se lanzó FileNotFoundError")
            print(f"      Mensaje: {e}")
            
    except OCRConfigurationError as e:
        print(f"\n⚠️  No se pudo crear servicio: {e}")


def test_extract_real_pdf():
    """
    Prueba 9: Extracción de PDF real (OPCIONAL).
    
    Esta prueba requiere:
    - Credenciales de Azure válidas
    - Un archivo PDF en tests/sample.pdf
    
    Si no existe el PDF, la prueba se salta.
    """
    print("\n" + "="*60)
    print("PRUEBA 9: Extracción de PDF real (opcional)")
    print("="*60)
    
    from services.azure_ocr_service import (
        AzureConfig,
        AzureOCRService,
        OCRConfigurationError,
        OCRServiceError
    )
    
    config = AzureConfig()
    
    if not config.is_configured:
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
        print("   para probar la extracción real.")
        return
    
    print(f"\n📄 PDF encontrado: {pdf_path}")
    print("🔍 Enviando a Azure Document Intelligence...")
    print("   (Esto puede tomar varios segundos...)")
    
    try:
        service = AzureOCRService(config)
        text, metadata = service.extract_text(str(pdf_path))
        
        print(f"\n✅ Extracción exitosa!")
        print(f"   Páginas: {metadata.get('pages', 'N/A')}")
        print(f"   Método: {metadata.get('method', 'N/A')}")
        print(f"   Caracteres extraídos: {len(text)}")
        
        # Guardar extracción en archivo de texto
        output_file = Path(__file__).parent / "extraction_result.txt"
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"\n💾 Extracción guardada en: {output_file}")
        except Exception as e:
            print(f"\n⚠️  No se pudo guardar el archivo de texto: {e}")
        
        print(f"\n📝 Primeros 500 caracteres del texto:")
        print("-" * 40)
        print(text[:500] + "..." if len(text) > 500 else text)
        print("-" * 40)
        
    except OCRServiceError as e:
        print(f"\n❌ Error de OCR: {type(e).__name__}: {e}")
    except Exception as e:
        print(f"\n❌ Error inesperado: {type(e).__name__}: {e}")


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "#"*60)
    print("# PRUEBAS DEL SERVICIO AZURE OCR (services/azure_ocr_service.py)")
    print("#"*60)
    
    print("\n⚠️  NOTA: Algunas pruebas requieren:")
    print("   - Credenciales de Azure en .env")
    print("   - SDK de Azure instalado")
    print("   - (Opcional) PDF de prueba en tests/sample.pdf")
    
    try:
        # Prueba de imports primero
        if not test_imports():
            print("\n❌ Falló la prueba de imports, abortando.")
            return 1
        
        # Pruebas que no requieren credenciales
        test_azure_config()
        test_azure_config_custom()
        test_exceptions_hierarchy()
        test_service_without_config()
        
        # Pruebas que requieren credenciales
        test_service_initialization()
        test_singleton_pattern()
        test_file_not_found()
        test_extract_real_pdf()
        
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
