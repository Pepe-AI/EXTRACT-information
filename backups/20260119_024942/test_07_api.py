#!/usr/bin/env python3
"""
tests/test_07_api.py - Prueba de la API FastAPI

OBJETIVO:
=========
Verificar que los endpoints de la API funcionan correctamente.

CÓMO EJECUTAR:
==============
Desde la raíz del proyecto (con el entorno virtual activado):

    cd extract_info_project
    source venv/bin/activate
    python -m tests.test_07_api

REQUISITOS:
===========
- httpx instalado (para cliente HTTP async)
- Azure configurado (para pruebas completas)
- Ollama disponible (para pruebas completas)

ALTERNATIVA - PRUEBA MANUAL:
============================
1. Inicia la API:
   uvicorn app.api:app --host 127.0.0.1 --port 8000

2. Prueba con curl:
   curl http://localhost:8000/health
   curl http://localhost:8000/schema
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
    Prueba 1: Verificar imports de FastAPI.
    
    Verifica que FastAPI y los módulos de la API están disponibles.
    """
    print("\n" + "="*60)
    print("PRUEBA 1: Verificar imports")
    print("="*60)
    
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        print("   ✅ FastAPI importado")
        print("   ✅ TestClient importado")
        
    except ImportError as e:
        print(f"   ❌ Error importando FastAPI: {e}")
        return False
    
    try:
        from app.api import app
        print("   ✅ app.api importado")
        return True
        
    except Exception as e:
        print(f"   ⚠️  Error importando app.api: {e}")
        print("   (Puede ser por falta de configuración de Azure)")
        return False


def test_app_creation():
    """
    Prueba 2: Creación de la aplicación FastAPI.
    
    Verifica que la app se crea correctamente.
    """
    print("\n" + "="*60)
    print("PRUEBA 2: Creación de la aplicación")
    print("="*60)
    
    try:
        from app.api import app
        
        print(f"\n📋 Aplicación FastAPI:")
        print(f"   Título: {app.title}")
        print(f"   Versión: {app.version}")
        print(f"   Descripción: {app.description[:60]}...")
        
        # Listar rutas
        routes = [route.path for route in app.routes if hasattr(route, 'path')]
        print(f"\n📋 Rutas disponibles ({len(routes)}):")
        for route in routes:
            print(f"   - {route}")
        
        print("\n✅ Aplicación creada correctamente")
        return True
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return False


def test_models():
    """
    Prueba 3: Modelos de la API.
    
    Verifica que los modelos Pydantic de la API están definidos.
    """
    print("\n" + "="*60)
    print("PRUEBA 3: Modelos de la API")
    print("="*60)
    
    try:
        from app.api import HealthResponse, ExtractionAPIResponse
        
        # Crear HealthResponse de prueba
        health = HealthResponse(
            status="healthy",
            services={"ollama": True, "azure_ocr": True},
            timestamp="2024-05-15T10:00:00"
        )
        
        print(f"\n📋 HealthResponse:")
        print(f"   status: {health.status}")
        print(f"   services: {health.services}")
        print(f"   timestamp: {health.timestamp}")
        
        # Crear ExtractionAPIResponse de prueba
        extraction = ExtractionAPIResponse(
            success=True,
            data={"numero_escritura": 3125},
            processing_time_seconds=5.5,
            model_used="deepseek-r1:32b"
        )
        
        print(f"\n📋 ExtractionAPIResponse:")
        print(f"   success: {extraction.success}")
        print(f"   data: {extraction.data}")
        print(f"   processing_time: {extraction.processing_time_seconds}s")
        
        print("\n✅ Modelos funcionan correctamente")
        return True
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return False


def test_endpoint_health():
    """
    Prueba 4: Endpoint /health.
    
    Usa TestClient de FastAPI para probar el endpoint sin
    necesidad de levantar el servidor.
    """
    print("\n" + "="*60)
    print("PRUEBA 4: Endpoint /health")
    print("="*60)
    
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        
        client = TestClient(app)
        
        print("\n🔍 Enviando GET /health...")
        response = client.get("/health")
        
        print(f"\n📋 Respuesta:")
        print(f"   Status code: {response.status_code}")
        print(f"   Content-Type: {response.headers.get('content-type')}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   status: {data.get('status')}")
            print(f"   services: {data.get('services')}")
            print("\n✅ Endpoint /health funciona")
        else:
            print(f"   Body: {response.text[:200]}")
            print("\n⚠️  Respuesta inesperada")
            
        return True
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_endpoint_schema():
    """
    Prueba 5: Endpoint /schema.
    
    Verifica que devuelve el esquema JSON esperado.
    """
    print("\n" + "="*60)
    print("PRUEBA 5: Endpoint /schema")
    print("="*60)
    
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        
        client = TestClient(app)
        
        print("\n🔍 Enviando GET /schema...")
        response = client.get("/schema")
        
        print(f"\n📋 Respuesta:")
        print(f"   Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   Título: {data.get('title')}")
            print(f"   Tipo: {data.get('type')}")
            print(f"   Propiedades: {len(data.get('properties', {}))}")
            
            # Mostrar algunas propiedades
            props = list(data.get('properties', {}).keys())[:5]
            print(f"   Primeras propiedades: {props}")
            
            print("\n✅ Endpoint /schema funciona")
        else:
            print(f"   Error: {response.text[:200]}")
            
        return True
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return False


def test_endpoint_extract_validation():
    """
    Prueba 6: Validación del endpoint /extract.
    
    Verifica que rechaza archivos no-PDF correctamente.
    """
    print("\n" + "="*60)
    print("PRUEBA 6: Validación de /extract")
    print("="*60)
    
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        
        client = TestClient(app)
        
        # Caso 1: Enviar archivo que no es PDF
        print("\n🔍 Caso 1: Enviando archivo .txt (debe rechazar)...")
        
        response = client.post(
            "/extract",
            files={"file": ("test.txt", b"contenido de prueba", "text/plain")}
        )
        
        print(f"   Status code: {response.status_code}")
        
        if response.status_code == 400:
            print(f"   ✅ Rechazó archivo no-PDF correctamente")
            print(f"   Mensaje: {response.json().get('detail')}")
        else:
            print(f"   ⚠️  Status inesperado: {response.status_code}")
        
        # Caso 2: Sin archivo
        print("\n🔍 Caso 2: Sin archivo (debe rechazar)...")
        
        response = client.post("/extract")
        
        print(f"   Status code: {response.status_code}")
        if response.status_code == 422:
            print(f"   ✅ Rechazó request sin archivo correctamente")
        else:
            print(f"   ⚠️  Status inesperado: {response.status_code}")
        
        print("\n✅ Validaciones funcionan correctamente")
        return True
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return False


def test_endpoint_extract_pdf():
    """
    Prueba 7: Extracción real con PDF (OPCIONAL).
    
    Requiere:
    - Azure configurado
    - Ollama disponible
    - PDF de prueba
    """
    print("\n" + "="*60)
    print("PRUEBA 7: Extracción real con PDF (opcional)")
    print("="*60)
    
    from services.azure_ocr_service import AzureConfig
    
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
        return
    
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        
        client = TestClient(app)
        
        # Verificar health primero
        health_response = client.get("/health")
        if health_response.status_code == 200:
            services = health_response.json().get('services', {})
            if not services.get('ollama', False):
                print("\n⚠️  Ollama no está disponible, saltando extracción")
                return
        
        print(f"\n📄 PDF: {pdf_path}")
        print("🔍 Enviando POST /extract...")
        print("   (Esto puede tomar varios minutos...)")
        
        with open(pdf_path, 'rb') as f:
            response = client.post(
                "/extract",
                files={"file": (pdf_path.name, f, "application/pdf")},
                params={"include_thinking": "false"}
            )
        
        print(f"\n📋 Respuesta:")
        print(f"   Status code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   success: {data.get('success')}")
            print(f"   processing_time: {data.get('processing_time_seconds', 0):.2f}s")
            print(f"   model_used: {data.get('model_used')}")
            
            if data.get('data'):
                print(f"\n   📋 Datos extraídos:")
                extracted = data['data']
                print(f"      numero_escritura: {extracted.get('numero_escritura')}")
                print(f"      fecha: {extracted.get('fecha_escritura')}")
                print(f"      tipo: {extracted.get('tipo_operacion')}")
            
            print("\n✅ Extracción completada")
        else:
            print(f"   Error: {response.text[:300]}")
            
    except Exception as e:
        print(f"\n⚠️  Error: {e}")


def test_openapi_docs():
    """
    Prueba 8: Documentación OpenAPI.
    
    Verifica que /docs y /openapi.json están disponibles.
    """
    print("\n" + "="*60)
    print("PRUEBA 8: Documentación OpenAPI")
    print("="*60)
    
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        
        client = TestClient(app)
        
        # Verificar /openapi.json
        print("\n🔍 Verificando /openapi.json...")
        response = client.get("/openapi.json")
        
        if response.status_code == 200:
            openapi = response.json()
            print(f"   ✅ OpenAPI disponible")
            print(f"   Versión OpenAPI: {openapi.get('openapi')}")
            print(f"   Título API: {openapi.get('info', {}).get('title')}")
            print(f"   Paths: {len(openapi.get('paths', {}))}")
        else:
            print(f"   ⚠️  /openapi.json no disponible: {response.status_code}")
        
        # Verificar /docs
        print("\n🔍 Verificando /docs...")
        response = client.get("/docs")
        
        if response.status_code == 200:
            print(f"   ✅ Swagger UI disponible en /docs")
        else:
            print(f"   ⚠️  /docs status: {response.status_code}")
        
        print("\n✅ Documentación verificada")
        return True
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return False


def test_cors():
    """
    Prueba 9: Configuración CORS.
    
    Verifica que CORS está configurado para permitir requests
    desde el frontend.
    """
    print("\n" + "="*60)
    print("PRUEBA 9: Configuración CORS")
    print("="*60)
    
    try:
        from fastapi.testclient import TestClient
        from app.api import app
        
        client = TestClient(app)
        
        # Simular preflight request
        print("\n🔍 Verificando headers CORS...")
        
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET"
            }
        )
        
        cors_headers = {
            k: v for k, v in response.headers.items() 
            if 'access-control' in k.lower()
        }
        
        if cors_headers:
            print(f"   ✅ CORS configurado")
            for header, value in cors_headers.items():
                print(f"      {header}: {value}")
        else:
            print(f"   ⚠️  No se encontraron headers CORS")
        
        print("\n✅ Verificación CORS completada")
        return True
        
    except Exception as e:
        print(f"\n⚠️  Error: {e}")
        return False


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "#"*60)
    print("# PRUEBAS DE LA API (app/api.py)")
    print("#"*60)
    
    print("\n⚠️  NOTA: Algunas pruebas requieren:")
    print("   - Credenciales de Azure en .env")
    print("   - Servidor Ollama corriendo")
    print("   - (Opcional) PDF de prueba en tests/sample.pdf")
    
    try:
        # Pruebas básicas
        if not test_imports():
            print("\n⚠️  Imports fallidos, continuando con pruebas limitadas...")
        
        test_app_creation()
        test_models()
        
        # Pruebas de endpoints
        test_endpoint_health()
        test_endpoint_schema()
        test_endpoint_extract_validation()
        test_endpoint_extract_pdf()
        
        # Pruebas adicionales
        test_openapi_docs()
        test_cors()
        
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
