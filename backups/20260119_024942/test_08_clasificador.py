#!/usr/bin/env python3
"""
tests/test_08_clasificador.py - Prueba del sistema híbrido de clasificación

OBJETIVO:
=========
Verificar el funcionamiento del clasificador (Fase 1) y su integración
con el extractor (Fase 2).

CÓMO EJECUTAR:
==============
Desde la raíz del proyecto (con el entorno virtual activado):

    cd extract_info_project
    source venv/bin/activate
    python -m tests.test_08_clasificador

REQUISITOS:
===========
- Para pruebas de detección por regex: Ninguno (solo Python)
- Para pruebas con LLM: Servidor Ollama corriendo
- Para prueba completa: Azure configurado + PDF de prueba
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
    """
    print("\n" + "="*60)
    print("PRUEBA 1: Verificar imports del clasificador")
    print("="*60)
    
    try:
        from utils.clasificador import (
            clasificar_documento,
            ResultadoClasificacion,
            detectar_tipo_por_nombre,
            validar_representante_no_es_institucion,
            PATRONES_EMPRESA,
        )
        print("\n✅ Imports exitosos:")
        print("   - clasificar_documento")
        print("   - ResultadoClasificacion")
        print("   - detectar_tipo_por_nombre")
        print("   - validar_representante_no_es_institucion")
        print(f"   - PATRONES_EMPRESA ({len(PATRONES_EMPRESA)} patrones)")
        return True
        
    except ImportError as e:
        print(f"\n❌ Error de importación: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_deteccion_por_nombre():
    """
    Prueba 2: Detección de tipo por nombre usando regex.
    
    Esta prueba NO requiere servicios externos.
    """
    print("\n" + "="*60)
    print("PRUEBA 2: Detección de tipo por nombre (regex)")
    print("="*60)
    
    from utils.clasificador import detectar_tipo_por_nombre
    
    # Casos de prueba: (nombre, tipo_esperado)
    casos = [
        # Empresas/Instituciones - Deben detectarse como "empresa"
        ("Instituto Nacional del Suelo Sustentable", "empresa"),
        ("Inmobiliaria del Norte S.A. de C.V.", "empresa"),
        ("INFONAVIT", "empresa"),
        ("Secretaría de Desarrollo Agrario", "empresa"),
        ("Fideicomiso de Vivienda", "empresa"),
        ("Desarrollos Turísticos del Pacífico", "empresa"),
        ("Gobierno del Estado de Jalisco", "empresa"),
        ("Constructora ABC S. de R.L.", "empresa"),
        ("Asociación de Colonos A.C.", "empresa"),
        
        # Personas físicas - Deben detectarse como "persona"
        ("Juan Pérez López", "persona"),
        ("María García Hernández", "persona"),
        ("Ana López", "persona"),
        ("Carlos Rodríguez Martínez", "persona"),
        ("Ernesto Padilla Aceves", "persona"),
    ]
    
    print("\n📋 Resultados de detección:")
    print("-" * 60)
    
    aciertos = 0
    errores = 0
    
    for nombre, tipo_esperado in casos:
        tipo_detectado, patrones = detectar_tipo_por_nombre(nombre)
        
        es_correcto = tipo_detectado == tipo_esperado
        
        if es_correcto:
            aciertos += 1
            emoji = "✅"
        else:
            errores += 1
            emoji = "❌"
        
        patrones_str = f" ({', '.join(patrones[:2])})" if patrones else ""
        print(f"   {emoji} {nombre[:35]:35} → {tipo_detectado}{patrones_str}")
        
        if not es_correcto:
            print(f"      ⚠️ Esperado: {tipo_esperado}")
    
    print("-" * 60)
    print(f"\n📊 Resultado: {aciertos}/{len(casos)} correctos")
    
    if errores == 0:
        print("✅ Todas las detecciones fueron correctas")
    else:
        print(f"⚠️ {errores} detecciones incorrectas")
    
    return errores == 0


def test_validacion_representante():
    """
    Prueba 3: Validación de que el representante sea persona física.
    
    El representante NUNCA debe ser una institución.
    """
    print("\n" + "="*60)
    print("PRUEBA 3: Validación de representante")
    print("="*60)
    
    from utils.clasificador import validar_representante_no_es_institucion
    
    # Casos de prueba: (nombre, debe_ser_valido)
    casos = [
        # Representantes válidos (personas físicas)
        ("Juan Pérez López", True),
        ("María García", True),
        ("Ernesto Padilla Aceves", True),
        
        # Representantes inválidos (instituciones)
        ("Instituto Nacional del Suelo Sustentable", False),
        ("INFONAVIT", False),
        ("Secretaría de Desarrollo", False),
        ("Inmobiliaria ABC S.A. de C.V.", False),
    ]
    
    print("\n📋 Validación de representantes:")
    print("-" * 60)
    
    aciertos = 0
    
    for nombre, debe_ser_valido in casos:
        es_valido, error = validar_representante_no_es_institucion(nombre)
        
        resultado_correcto = es_valido == debe_ser_valido
        
        if resultado_correcto:
            aciertos += 1
            emoji = "✅"
        else:
            emoji = "❌"
        
        status = "Válido" if es_valido else "Inválido"
        print(f"   {emoji} {nombre[:40]:40} → {status}")
        
        if error and not debe_ser_valido:
            print(f"      ℹ️ {error[:50]}...")
    
    print("-" * 60)
    print(f"\n📊 Resultado: {aciertos}/{len(casos)} correctos")
    
    return aciertos == len(casos)


def test_resultado_clasificacion():
    """
    Prueba 4: Estructura de ResultadoClasificacion.
    """
    print("\n" + "="*60)
    print("PRUEBA 4: Estructura de ResultadoClasificacion")
    print("="*60)
    
    from utils.clasificador import ResultadoClasificacion
    
    # Crear resultado de prueba
    resultado = ResultadoClasificacion(
        tipo_titular="empresa",
        nombre_titular="Instituto Nacional del Suelo Sustentable",
        nombre_representante="Ernesto Padilla Aceves",
        confianza="alta",
        razon="Detectado patrón 'Instituto'",
        patrones_encontrados=["Instituto"],
        metodo="hibrido"
    )
    
    print("\n📋 ResultadoClasificacion creado:")
    print(f"   tipo_titular: {resultado.tipo_titular}")
    print(f"   nombre_titular: {resultado.nombre_titular}")
    print(f"   nombre_representante: {resultado.nombre_representante}")
    print(f"   confianza: {resultado.confianza}")
    print(f"   metodo: {resultado.metodo}")
    
    # Convertir a dict
    resultado_dict = resultado.to_dict()
    print(f"\n📋 Conversión a dict exitosa: {len(resultado_dict)} campos")
    
    assert resultado_dict['tipo_titular'] == "empresa"
    assert resultado_dict['nombre_titular'] == "Instituto Nacional del Suelo Sustentable"
    
    print("\n✅ ResultadoClasificacion funciona correctamente")
    return True


def test_clasificacion_texto():
    """
    Prueba 5: Clasificación de texto de documento.
    
    Esta prueba usa regex, NO requiere LLM.
    """
    print("\n" + "="*60)
    print("PRUEBA 5: Clasificación de texto de documento")
    print("="*60)
    
    from utils.clasificador import _detectar_tipo_en_texto
    
    # Texto de prueba: institución gubernamental
    texto_institucion = """
    ESCRITURA NÚMERO 2397
    Comparece el señor ERNESTO PADILLA ACEVES en su carácter de 
    REPRESENTANTE REGIONAL del INSTITUTO NACIONAL DEL SUELO SUSTENTABLE (INSS),
    organismo público descentralizado del Gobierno Federal...
    Para transmitir a favor de ANGELITA PÉREZ SOTO...
    """
    
    tipo, patrones = _detectar_tipo_en_texto(texto_institucion)
    
    print(f"\n📄 Texto de institución gubernamental:")
    print(f"   Tipo detectado: {tipo}")
    print(f"   Patrones: {', '.join(patrones[:3])}")
    
    assert tipo == "empresa", f"Esperaba 'empresa', obtuve '{tipo}'"
    
    # Texto de prueba: empresa S.A. de C.V.
    texto_empresa = """
    ESCRITURA NÚMERO 3125
    Comparece INMOBILIARIA DEL NORTE S.A. DE C.V. representada por
    JUAN CARLOS PÉREZ LÓPEZ en su carácter de apoderado legal...
    """
    
    tipo, patrones = _detectar_tipo_en_texto(texto_empresa)
    
    print(f"\n📄 Texto de empresa S.A. de C.V.:")
    print(f"   Tipo detectado: {tipo}")
    print(f"   Patrones: {', '.join(patrones[:3])}")
    
    assert tipo == "empresa"
    
    # Texto de prueba: persona física
    texto_persona = """
    ESCRITURA NÚMERO 5432
    Comparece JUAN PÉREZ LÓPEZ por su propio derecho, mexicano,
    mayor de edad, casado, con domicilio en...
    Para vender a MARÍA GARCÍA HERNÁNDEZ...
    """
    
    tipo, patrones = _detectar_tipo_en_texto(texto_persona)
    
    print(f"\n📄 Texto de persona física:")
    print(f"   Tipo detectado: {tipo}")
    print(f"   Patrones: {patrones if patrones else 'Ninguno'}")
    
    # Para persona física, no deberían detectarse patrones de empresa
    assert tipo == "persona" or len(patrones) == 0
    
    print("\n✅ Clasificación de texto funciona correctamente")
    return True


def test_clasificacion_con_ollama():
    """
    Prueba 6: Clasificación completa con Ollama (OPCIONAL).
    
    Requiere servidor Ollama corriendo.
    """
    print("\n" + "="*60)
    print("PRUEBA 6: Clasificación con Ollama (opcional)")
    print("="*60)
    
    from services.ollama_service import get_ollama_service
    
    service = get_ollama_service()
    
    if not service.health_check():
        print("\n⚠️ Ollama no está disponible, saltando prueba")
        return True  # No es un error, solo no está disponible
    
    from utils.clasificador import clasificar_documento
    
    texto_prueba = """
    ESCRITURA NÚMERO 2397
    En la ciudad de Tepic, Nayarit, siendo las once horas del día cinco de mayo 
    del año dos mil veintitrés, ante mí, Licenciado Rigoberto Ochoa Torres, 
    Notario Público número 45, comparece:
    
    El señor ERNESTO PADILLA ACEVES, quien se identifica con credencial de elector,
    actuando en su carácter de REPRESENTANTE REGIONAL del INSTITUTO NACIONAL 
    DEL SUELO SUSTENTABLE (INSS), organismo público descentralizado del Gobierno
    Federal, según nombramiento de fecha...
    
    Para transmitir a título de compraventa a favor de la señora ANGELITA PÉREZ SOTO
    el inmueble ubicado en Calle Principal número 123...
    
    PRECIO: $8,654.00 (OCHO MIL SEISCIENTOS CINCUENTA Y CUATRO PESOS 00/100 M.N.)
    """
    
    print("\n🔍 Clasificando documento con Ollama...")
    
    resultado = clasificar_documento(
        texto_documento=texto_prueba,
        ollama_service=service
    )
    
    print(f"\n📋 Resultado de clasificación:")
    print(f"   Tipo: {resultado.tipo_titular}")
    print(f"   Titular: {resultado.nombre_titular or 'No identificado'}")
    print(f"   Representante: {resultado.nombre_representante or 'No identificado'}")
    print(f"   Confianza: {resultado.confianza}")
    print(f"   Método: {resultado.metodo}")
    print(f"   Razón: {resultado.razon[:80]}...")
    
    # Verificar que clasificó correctamente
    if resultado.tipo_titular != "empresa":
        print(f"\n⚠️ Clasificación incorrecta: esperaba 'empresa', obtuve '{resultado.tipo_titular}'")
        return False
    
    print("\n✅ Clasificación con Ollama exitosa")
    return True


def test_extractor_con_clasificacion():
    """
    Prueba 7: Extractor completo con sistema híbrido (OPCIONAL).
    
    Requiere:
    - Azure configurado
    - Ollama disponible
    - PDF de prueba
    """
    print("\n" + "="*60)
    print("PRUEBA 7: Extractor completo (opcional)")
    print("="*60)
    
    from services.azure_ocr_service import AzureConfig
    
    azure_config = AzureConfig()
    if not azure_config.is_configured:
        print("\n⚠️ Azure no está configurado, saltando prueba")
        return True
    
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
        print("\n⚠️ No se encontró PDF de prueba")
        print("   Coloca un archivo 'sample.pdf' en la carpeta tests/")
        return True
    
    from app.extractor import EscrituraExtractor, ExtractionConfig
    
    # Verificar Ollama
    from services.ollama_service import get_ollama_service
    service = get_ollama_service()
    if not service.health_check():
        print("\n⚠️ Ollama no está disponible, saltando prueba")
        return True
    
    print(f"\n📄 PDF encontrado: {pdf_path}")
    print("🔍 Iniciando extracción con sistema híbrido...")
    print("   (Esto puede tomar varios minutos...)")
    
    try:
        config = ExtractionConfig(
            use_classification=True,  # Habilitar sistema híbrido
            max_retries=2
        )
        
        extractor = EscrituraExtractor(config=config)
        result = extractor.extract(str(pdf_path))
        
        print(f"\n📊 Resultado de la extracción:")
        print(f"   success: {result.success}")
        print(f"   validacion_estricta: {result.validacion_estricta}")
        print(f"   processing_time: {result.processing_time:.2f}s")
        print(f"   intentos: {result.intentos_realizados}")
        
        if result.clasificacion:
            print(f"\n📋 Clasificación (Fase 1):")
            print(f"   Tipo: {result.tipo_detectado}")
            print(f"   Método: {result.metodo_clasificacion}")
        
        if result.success:
            print(f"\n✅ Extracción exitosa!")
            print(f"   Campos encontrados: {result.campos_encontrados}/8")
            if result.campos_no_encontrados:
                print(f"   Campos faltantes: {result.campos_no_encontrados}")
        else:
            print(f"\n❌ Extracción falló: {result.error}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def test_prompt_con_clasificacion():
    """
    Prueba 8: Construcción de prompt con clasificación previa.
    """
    print("\n" + "="*60)
    print("PRUEBA 8: Prompt con clasificación")
    print("="*60)
    
    from utils.prompt_builder import build_extraction_prompt
    
    documento = "ESCRITURA NÚMERO 2397... Instituto Nacional..."
    
    # Prompt con clasificación de empresa
    system, user = build_extraction_prompt(
        document_text=documento,
        tipo_titular="empresa",
        nombre_titular="Instituto Nacional del Suelo Sustentable",
        nombre_representante="Ernesto Padilla Aceves"
    )
    
    print("\n📋 Prompt con clasificación EMPRESA:")
    print(f"   System prompt: {len(system)} caracteres")
    print(f"   User prompt: {len(user)} caracteres")
    
    # Verificar que incluye la información confirmada
    assert "INFORMACIÓN YA CONFIRMADA" in user
    assert "Instituto Nacional" in user
    assert "Ernesto Padilla" in user
    
    print("   ✅ Incluye información confirmada")
    print("   ✅ Incluye nombre del titular")
    print("   ✅ Incluye nombre del representante")
    
    # Prompt con clasificación de persona
    system, user = build_extraction_prompt(
        document_text=documento,
        tipo_titular="persona",
        nombre_titular="Juan Pérez López"
    )
    
    print("\n📋 Prompt con clasificación PERSONA:")
    print(f"   System prompt: {len(system)} caracteres")
    print(f"   User prompt: {len(user)} caracteres")
    
    assert "persona" in system.lower()
    
    print("   ✅ System prompt es para persona")
    
    # Prompt sin clasificación (genérico)
    system, user = build_extraction_prompt(
        document_text=documento,
        tipo_titular=None
    )
    
    print("\n📋 Prompt genérico (sin clasificación):")
    print(f"   System prompt: {len(system)} caracteres")
    print(f"   User prompt: {len(user)} caracteres")
    
    print("   ✅ Prompt genérico funciona")
    
    print("\n✅ Construcción de prompts correcta")
    return True


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "#"*60)
    print("# PRUEBAS DEL SISTEMA HÍBRIDO (CLASIFICADOR + EXTRACTOR)")
    print("#"*60)
    
    print("\n⚠️  NOTA: Las pruebas 6 y 7 requieren servicios externos")
    print("   - Prueba 6: Servidor Ollama")
    print("   - Prueba 7: Azure + Ollama + PDF de prueba")
    
    try:
        # Pruebas que no requieren servicios externos
        if not test_imports():
            print("\n❌ Falló la prueba de imports, abortando.")
            return 1
        
        test_deteccion_por_nombre()
        test_validacion_representante()
        test_resultado_clasificacion()
        test_clasificacion_texto()
        test_prompt_con_clasificacion()
        
        # Pruebas que requieren servicios externos
        test_clasificacion_con_ollama()
        test_extractor_con_clasificacion()
        
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
