#!/usr/bin/env python3
"""
tests/test_02_text_processing.py - Prueba de procesamiento de texto

OBJETIVO:
=========
Verificar que las funciones de limpieza de texto OCR y
procesamiento de respuestas de DeepSeek funcionan correctamente.

CÓMO EJECUTAR:
==============
Desde la raíz del proyecto (con el entorno virtual activado):

    cd extract_info_project
    source venv/bin/activate
    python -m tests.test_02_text_processing

REQUISITOS:
===========
- No necesita conexión a servicios externos
- Solo usa librerías estándar de Python
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.text_processing import (
    clean_ocr_text,
    truncate_text,
    format_for_prompt,
    extract_think_block,
    extract_json_from_response,
    process_deepseek_response
)


def test_clean_ocr_text():
    """
    Prueba 1: Limpiar texto OCR con ruido.
    
    El OCR de documentos notariales genera mucho ruido:
    - Sellos de COTEJADO
    - Watermarks de notarías
    - Números de página
    - Encabezados repetidos
    """
    print("\n" + "="*60)
    print("PRUEBA 1: Limpieza de texto OCR (clean_ocr_text)")
    print("="*60)
    
    # Texto con ruido típico de OCR
    texto_sucio = """
COTEJADO
ESTADOS UNIDOS MEXICANOS
NOTARIA 45
1/5

ESCRITURA PÚBLICA NÚMERO 3125

En la Ciudad de México, siendo las diez horas del día quince de mayo
del año dos mil veinticuatro, ante mí, Licenciado Roberto Martínez
González, Notario Público número cuarenta y cinco, comparecen:

COTEJADO
NAYARIT
Day F4CA

Como VENDEDOR: JUAN CARLOS PÉREZ LÓPEZ, mexicano, mayor de edad,
con domicilio en Avenida Reforma número 123.

2/5
NOTARIA 45

Como COMPRADOR: MARÍA GARCÍA HERNÁNDEZ, mexicana, casada, con
RFC: GAHM900515XYZ.

COTEJADO
3/5
"""
    
    print("\n📄 Texto original (con ruido):")
    print("-" * 40)
    print(texto_sucio[:300] + "...")
    print(f"\nLongitud original: {len(texto_sucio)} caracteres")
    
    # Limpiar
    texto_limpio = clean_ocr_text(texto_sucio)
    
    print("\n🧹 Texto limpio:")
    print("-" * 40)
    print(texto_limpio[:500] + "..." if len(texto_limpio) > 500 else texto_limpio)
    print(f"\nLongitud limpia: {len(texto_limpio)} caracteres")
    
    # Verificaciones
    assert "COTEJADO" not in texto_limpio, "COTEJADO debería haberse eliminado"
    assert "1/5" not in texto_limpio, "Número de página debería haberse eliminado"
    assert "Day F4CA" not in texto_limpio, "Artefacto debería haberse eliminado"
    assert "ESCRITURA" in texto_limpio, "El contenido real debería conservarse"
    # Nota: Algunos textos cortos en mayúsculas pueden eliminarse por el filtro de ruido
    # Lo importante es que el contenido principal se conserve
    
    print("\n✅ Verificaciones pasadas:")
    print("   - COTEJADO eliminado")
    print("   - Números de página eliminados")
    print("   - Contenido real conservado")


def test_truncate_text():
    """
    Prueba 2: Truncar texto largo.
    
    Los modelos LLM tienen límite de contexto.
    Esta función trunca textos muy largos preservando
    inicio y final del documento.
    """
    print("\n" + "="*60)
    print("PRUEBA 2: Truncar texto (truncate_text)")
    print("="*60)
    
    # Crear texto largo (simular documento de muchas páginas)
    texto_largo = "Inicio del documento. " + ("Contenido intermedio. " * 1000) + "Final del documento."
    
    print(f"\n📄 Texto largo creado:")
    print(f"   Longitud: {len(texto_largo)} caracteres")
    print(f"   Tokens estimados: ~{len(texto_largo) // 4}")
    
    # Truncar a 500 tokens (2000 caracteres aprox)
    texto_truncado = truncate_text(texto_largo, max_tokens=500)
    
    print(f"\n✂️ Texto truncado:")
    print(f"   Longitud: {len(texto_truncado)} caracteres")
    
    # Verificar que preserva inicio y final
    assert texto_truncado.startswith("Inicio del documento"), "Debería preservar el inicio"
    assert "Final del documento" in texto_truncado, "Debería preservar el final"
    assert "TRUNCADO" in texto_truncado, "Debería indicar que fue truncado"
    
    print("\n✅ Verificaciones pasadas:")
    print("   - Inicio preservado")
    print("   - Final preservado")
    print("   - Indicador de truncado presente")
    
    # Probar que texto corto no se trunca
    texto_corto = "Este es un texto corto."
    texto_no_truncado = truncate_text(texto_corto, max_tokens=1000)
    assert texto_no_truncado == texto_corto, "Texto corto no debería modificarse"
    print("   - Texto corto no se modifica")


def test_format_for_prompt():
    """
    Prueba 3: Formatear texto para el prompt.
    
    Combina limpieza + truncado + envoltura en delimitadores.
    """
    print("\n" + "="*60)
    print("PRUEBA 3: Formatear para prompt (format_for_prompt)")
    print("="*60)
    
    texto = """
COTEJADO
ESCRITURA 3125
Vendedor: Juan Pérez
Comprador: María García
Precio: $1,000,000 MXN
"""
    
    formatted = format_for_prompt(texto, max_tokens=1000)
    
    print("\n📄 Texto formateado:")
    print("-" * 40)
    print(formatted)
    
    # Verificar delimitadores
    assert "<documento>" in formatted, "Debería tener delimitador de inicio"
    assert "</documento>" in formatted, "Debería tener delimitador de cierre"
    assert "COTEJADO" not in formatted, "Debería haber limpiado el ruido"
    
    print("\n✅ Verificaciones pasadas:")
    print("   - Delimitadores presentes")
    print("   - Ruido eliminado")


def test_extract_think_block():
    """
    Prueba 4: Extraer bloque <think> de DeepSeek R1.
    
    DeepSeek R1 "piensa en voz alta" en bloques <think>...</think>
    antes de dar su respuesta final.
    """
    print("\n" + "="*60)
    print("PRUEBA 4: Extraer bloque <think> (extract_think_block)")
    print("="*60)
    
    respuesta_con_think = """
<think>
El usuario me pide extraer datos de una escritura.
Veo que el número es 3125.
El vendedor es Juan Pérez.
Debo estructurar esto en JSON.
</think>

Aquí está el resultado en JSON:
```json
{"numero_escritura": 3125}
```
"""
    
    thinking, clean = extract_think_block(respuesta_con_think)
    
    print("\n💭 Pensamiento extraído:")
    print("-" * 40)
    print(thinking[:200] + "..." if thinking and len(thinking) > 200 else thinking)
    
    print("\n📄 Texto limpio (sin think):")
    print("-" * 40)
    print(clean[:200] + "..." if len(clean) > 200 else clean)
    
    # Verificaciones
    assert thinking is not None, "Debería extraer el pensamiento"
    assert "El usuario me pide" in thinking, "Pensamiento debería tener contenido"
    assert "<think>" not in clean, "Texto limpio no debería tener tags"
    assert "JSON" in clean, "Texto limpio debería tener la respuesta"
    
    print("\n✅ Verificaciones pasadas:")
    print("   - Pensamiento extraído")
    print("   - Tags eliminados del texto limpio")
    
    # Probar texto sin <think>
    respuesta_sin_think = "Respuesta directa sin pensar"
    thinking2, clean2 = extract_think_block(respuesta_sin_think)
    assert thinking2 is None, "No debería haber pensamiento"
    assert clean2 == respuesta_sin_think.strip(), "Texto debería quedar igual"
    print("   - Maneja correctamente texto sin <think>")


def test_extract_json():
    """
    Prueba 5: Extraer JSON de una respuesta.
    
    El JSON puede venir en bloques de código markdown
    o directamente en el texto.
    """
    print("\n" + "="*60)
    print("PRUEBA 5: Extraer JSON (extract_json_from_response)")
    print("="*60)
    
    # Caso 1: JSON en bloque de código markdown
    respuesta1 = """
Aquí está la información extraída:

```json
{
    "numero_escritura": 3125,
    "vendedor": "Juan Pérez",
    "comprador": "María García"
}
```

Espero que sea útil.
"""
    
    json1 = extract_json_from_response(respuesta1)
    print("\n📄 Caso 1 - JSON en bloque markdown:")
    print(f"   Resultado: {json1}")
    assert json1 is not None, "Debería extraer el JSON"
    assert json1["numero_escritura"] == 3125, "Debería tener el número correcto"
    
    # Caso 2: JSON directo
    respuesta2 = '{"nombre": "Test", "valor": 100}'
    json2 = extract_json_from_response(respuesta2)
    print("\n📄 Caso 2 - JSON directo:")
    print(f"   Resultado: {json2}")
    assert json2 is not None, "Debería extraer el JSON"
    assert json2["nombre"] == "Test", "Debería tener el nombre"
    
    # Caso 3: JSON con <think>
    respuesta3 = """
<think>
Procesando el documento...
</think>

```json
{"exito": true}
```
"""
    json3 = extract_json_from_response(respuesta3)
    print("\n📄 Caso 3 - JSON con <think>:")
    print(f"   Resultado: {json3}")
    assert json3 is not None, "Debería extraer el JSON"
    assert json3["exito"] == True, "Debería tener exito=true"
    
    print("\n✅ Todos los casos de extracción funcionan")


def test_process_deepseek_response():
    """
    Prueba 6: Procesar respuesta completa de DeepSeek.
    
    Esta función combina:
    - Extracción de <think>
    - Extracción de JSON
    - Metadatos del procesamiento
    """
    print("\n" + "="*60)
    print("PRUEBA 6: Procesar respuesta completa (process_deepseek_response)")
    print("="*60)
    
    respuesta_completa = """
<think>
Analizando el documento de escritura...
El número de escritura es 3125.
Es una operación de compraventa.
</think>

```json
{
    "numero_escritura": 3125,
    "tipo_operacion": "Compraventa",
    "vendedores": [
        {"nombre_completo": "Juan Pérez López"}
    ]
}
```
"""
    
    resultado = process_deepseek_response(respuesta_completa)
    
    print("\n📊 Resultado del procesamiento:")
    print(f"   success: {resultado['success']}")
    print(f"   thinking: {'Sí' if resultado['thinking'] else 'No'} ({len(resultado['thinking'] or '')} chars)")
    print(f"   json_data: {resultado['json_data']}")
    
    # Verificaciones
    assert resultado['success'] == True, "Debería ser exitoso"
    assert resultado['thinking'] is not None, "Debería tener pensamiento"
    assert resultado['json_data'] is not None, "Debería tener JSON"
    assert resultado['json_data']['numero_escritura'] == 3125, "JSON debería estar correcto"
    
    print("\n✅ Procesamiento completo funciona correctamente")


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "#"*60)
    print("# PRUEBAS DE PROCESAMIENTO DE TEXTO (utils/text_processing.py)")
    print("#"*60)
    
    try:
        test_clean_ocr_text()
        test_truncate_text()
        test_format_for_prompt()
        test_extract_think_block()
        test_extract_json()
        test_process_deepseek_response()
        
        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS PASARON EXITOSAMENTE")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ PRUEBA FALLIDA: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ ERROR EN LAS PRUEBAS: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
