#!/usr/bin/env python3
"""
tests/test_04_ollama_service.py - Prueba del servicio Ollama

OBJETIVO:
=========
Verificar la conexión y comunicación con el servidor Ollama
donde corre DeepSeek R1.

CÓMO EJECUTAR:
==============
Desde la raíz del proyecto (con el entorno virtual activado):

    cd extract_info_project
    source venv/bin/activate
    python -m tests.test_04_ollama_service

REQUISITOS:
===========
- Servidor Ollama corriendo (local o remoto)
- VPN activa si el servidor es remoto
- Configurar OLLAMA_HOST en .env

NOTA:
=====
Si el servidor no está disponible, las pruebas mostrarán
errores informativos pero no fallarán completamente.
"""

import sys
import os
from pathlib import Path

# Agregar el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Cargar variables de entorno
from dotenv import load_dotenv
load_dotenv()

from services.ollama_service import (
    OllamaConfig,
    OllamaService,
    get_ollama_service
)


def test_ollama_config():
    """
    Prueba 1: Configuración de Ollama.
    
    Verifica que la configuración se carga correctamente
    desde variables de entorno o valores por defecto.
    """
    print("\n" + "="*60)
    print("PRUEBA 1: Configuración de Ollama (OllamaConfig)")
    print("="*60)
    
    # Crear configuración (lee de .env o usa defaults)
    config = OllamaConfig()
    
    print("\n📋 Configuración actual:")
    print(f"   Host: {config.host}")
    print(f"   Puerto: {config.port}")
    print(f"   Modelo: {config.model}")
    print(f"   Timeout: {config.timeout} segundos")
    print(f"   URL base: {config.base_url}")
    
    # Verificaciones básicas
    assert config.host is not None, "Host no puede ser None"
    assert config.port > 0, "Puerto debe ser positivo"
    assert config.model is not None, "Modelo no puede ser None"
    assert config.timeout > 0, "Timeout debe ser positivo"
    
    print("\n✅ Configuración válida")


def test_ollama_config_custom():
    """
    Prueba 2: Configuración personalizada.
    
    Verifica que podemos crear configuración con valores custom.
    """
    print("\n" + "="*60)
    print("PRUEBA 2: Configuración personalizada")
    print("="*60)
    
    config = OllamaConfig(
        host="192.168.1.100",
        port=11434,
        model="deepseek-r1:14b",
        timeout=600
    )
    
    print(f"\n📋 Configuración custom:")
    print(f"   Host: {config.host}")
    print(f"   Puerto: {config.port}")
    print(f"   Modelo: {config.model}")
    print(f"   Timeout: {config.timeout}")
    print(f"   URL: {config.base_url}")
    
    assert config.host == "192.168.1.100", "Host debería ser custom"
    assert config.model == "deepseek-r1:14b", "Modelo debería ser custom"
    assert config.base_url == "http://192.168.1.100:11434", "URL debería formarse correctamente"
    
    print("\n✅ Configuración personalizada funciona")


def test_ollama_service_init():
    """
    Prueba 3: Inicializar servicio Ollama.
    
    Crea una instancia del servicio (sin conectar aún).
    """
    print("\n" + "="*60)
    print("PRUEBA 3: Inicializar servicio Ollama")
    print("="*60)
    
    service = OllamaService()
    
    print(f"\n📋 Servicio creado:")
    print(f"   Config host: {service.config.host}")
    print(f"   Config modelo: {service.config.model}")
    print(f"   URL base: {service.config.base_url}")
    
    print("\n✅ Servicio inicializado")


def test_ollama_health_check():
    """
    Prueba 4: Health check del servidor.
    
    Verifica si el servidor Ollama está disponible.
    Esta prueba requiere conexión al servidor.
    """
    print("\n" + "="*60)
    print("PRUEBA 4: Health check del servidor")
    print("="*60)
    
    service = get_ollama_service()
    
    print(f"\n🔍 Verificando conexión a {service.config.base_url}...")
    
    is_healthy = service.health_check()
    
    if is_healthy:
        print("\n✅ Servidor Ollama disponible y respondiendo")
    else:
        print("\n⚠️  Servidor Ollama no disponible")
        print("   Posibles causas:")
        print("   - El servidor no está corriendo")
        print("   - La VPN no está conectada")
        print(f"   - Host/puerto incorrectos ({service.config.host}:{service.config.port})")
        print("\n   Esta prueba requiere el servidor para continuar.")


def test_ollama_list_models():
    """
    Prueba 5: Listar modelos disponibles.
    
    Obtiene la lista de modelos instalados en el servidor.
    Requiere conexión al servidor.
    """
    print("\n" + "="*60)
    print("PRUEBA 5: Listar modelos disponibles")
    print("="*60)
    
    service = get_ollama_service()
    
    print(f"\n🔍 Obteniendo lista de modelos de {service.config.base_url}...")
    
    try:
        models = service.list_models()
        
        if models:
            print(f"\n✅ Modelos disponibles ({len(models)}):")
            for model in models:
                print(f"   - {model}")
            
            # Verificar si el modelo configurado está disponible
            if service.config.model in models:
                print(f"\n✅ Modelo configurado '{service.config.model}' está disponible")
            else:
                print(f"\n⚠️  Modelo configurado '{service.config.model}' NO está en la lista")
                print("   Puede que necesites descargar el modelo con:")
                print(f"   ollama pull {service.config.model}")
        else:
            print("\n⚠️  No se encontraron modelos o el servidor no respondió")
            
    except Exception as e:
        print(f"\n⚠️  Error al listar modelos: {e}")
        print("   El servidor puede no estar disponible.")


def test_ollama_generate_simple():
    """
    Prueba 6: Generar respuesta simple.
    
    Envía un prompt simple al modelo y verifica la respuesta.
    Requiere conexión al servidor Y el modelo descargado.
    """
    print("\n" + "="*60)
    print("PRUEBA 6: Generar respuesta simple")
    print("="*60)
    
    service = get_ollama_service()
    
    # Verificar disponibilidad primero
    if not service.health_check():
        print("\n⚠️  Servidor no disponible, saltando prueba de generación")
        return
    
    print(f"\n🤖 Enviando prompt simple al modelo {service.config.model}...")
    print("   (Esto puede tomar varios segundos...)")
    
    try:
        response = service.generate(
            prompt="Responde solo con 'OK' si puedes leer este mensaje.",
            temperature=0.1,
            max_tokens=50
        )
        
        print(f"\n📄 Respuesta recibida:")
        print("-" * 40)
        print(response[:200] if response else "(vacía)")
        print("-" * 40)
        
        if response:
            print("\n✅ El modelo respondió correctamente")
        else:
            print("\n⚠️  Respuesta vacía del modelo")
            
    except Exception as e:
        print(f"\n⚠️  Error en la generación: {e}")
        print("   Posibles causas:")
        print("   - Modelo no descargado")
        print("   - Timeout (documento muy largo)")
        print("   - Error de memoria en el servidor")


def test_ollama_generate_with_system():
    """
    Prueba 7: Generar con system prompt.
    
    Envía un prompt con system message (define el rol del modelo).
    """
    print("\n" + "="*60)
    print("PRUEBA 7: Generar con system prompt")
    print("="*60)
    
    service = get_ollama_service()
    
    if not service.health_check():
        print("\n⚠️  Servidor no disponible, saltando prueba")
        return
    
    system = "Eres un asistente que responde en español de forma muy breve."
    prompt = "¿Cuál es la capital de México?"
    
    print(f"\n📋 System: {system[:60]}...")
    print(f"📝 Prompt: {prompt}")
    print("\n🤖 Generando respuesta...")
    
    try:
        response = service.generate(
            prompt=prompt,
            system=system,
            temperature=0.1,
            max_tokens=100
        )
        
        print(f"\n📄 Respuesta:")
        print("-" * 40)
        print(response[:300] if response else "(vacía)")
        print("-" * 40)
        
        if response and ("México" in response or "Ciudad" in response or "CDMX" in response):
            print("\n✅ Respuesta correcta y coherente")
        else:
            print("\n⚠️  Respuesta inesperada")
            
    except Exception as e:
        print(f"\n⚠️  Error: {e}")


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "#"*60)
    print("# PRUEBAS DEL SERVICIO OLLAMA (services/ollama_service.py)")
    print("#"*60)
    
    print("\n⚠️  NOTA: Algunas pruebas requieren:")
    print("   - Servidor Ollama corriendo")
    print("   - VPN conectada (si es servidor remoto)")
    print("   - Modelo descargado en el servidor")
    
    try:
        # Pruebas que no requieren servidor
        test_ollama_config()
        test_ollama_config_custom()
        test_ollama_service_init()
        
        # Pruebas que requieren servidor
        test_ollama_health_check()
        test_ollama_list_models()
        test_ollama_generate_simple()
        test_ollama_generate_with_system()
        
        print("\n" + "="*60)
        print("✅ PRUEBAS COMPLETADAS")
        print("   (Algunas pueden haber sido saltadas por falta de servidor)")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR EN LAS PRUEBAS: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
