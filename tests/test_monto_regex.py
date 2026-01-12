#!/usr/bin/env python3
"""
tests/test_monto_regex.py - Prueba de extracción de monto por regex

OBJETIVO:
=========
Verificar que la función extraer_monto_operacion() detecta correctamente
montos en diferentes formatos usados en escrituras públicas mexicanas.

CÓMO EJECUTAR:
==============
    cd extract_info_project
    python -m tests.test_monto_regex

O con un PDF real:
    python -m tests.test_monto_regex ruta/a/tu/documento.pdf
"""

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.text_processing import (
    extraer_monto_operacion,
    extraer_numero_escritura,
    extraer_fecha_documento,
    extraer_datos_con_regex,
)


def test_patrones_monto():
    """
    Prueba la extracción de monto con diferentes formatos.
    """
    print("\n" + "="*60)
    print("PRUEBA: Extracción de monto_operacion con regex")
    print("="*60)
    
    # Casos de prueba con diferentes formatos de monto
    casos = [
        # Formato 1: "precio de esta operación"
        (
            "El precio de esta operación fue la cantidad de $1,500,000.00 (UN MILLÓN QUINIENTOS MIL PESOS)",
            "$1,500,000.00"
        ),
        
        # Formato 2: "la cantidad de"
        (
            "Se pacta como precio la cantidad de $850,000.00 M.N.",
            "$850,000.00"
        ),
        
        # Formato 3: "por la suma de"
        (
            "El inmueble se enajena por la suma de $2,300,000.00 (DOS MILLONES TRESCIENTOS MIL PESOS)",
            "$2,300,000.00"
        ),
        
        # Formato 4: "monto de la operación"
        (
            "El monto de la operación es de $750,000.00",
            "$750,000.00"
        ),
        
        # Formato 5: Sin centavos
        (
            "Precio de venta: $1,200,000 PESOS",
            "$1,200,000.00"
        ),
        
        # Formato 6: Con M.N.
        (
            "Valor total M.N. $3,500,000.00",
            "$3,500,000.00"
        ),
        
        # Formato 7: Monto pequeño
        (
            "El precio acordado fue de $95,000.00 (NOVENTA Y CINCO MIL PESOS)",
            "$95,000.00"
        ),
        
        # Formato 8: Sin comas
        (
            "Precio: $1500000.00 pesos",
            "$1,500,000.00"
        ),
        
        # Formato 9: Texto legal complejo
        (
            """SÉPTIMA.- PRECIO.- Las partes convienen que el precio de la presente 
            compraventa es la cantidad de $600,000.00 (SEISCIENTOS MIL PESOS 00/100 
            MONEDA NACIONAL), misma que el COMPRADOR paga al VENDEDOR en este acto.""",
            "$600,000.00"
        ),
        
        # Formato 10: Con variante de escritura
        (
            "El valor de esta enajenación asciende a la suma de $4,250,000.00 M.N.",
            "$4,250,000.00"
        ),
    ]
    
    exitosos = 0
    fallidos = 0
    
    for i, (texto, esperado) in enumerate(casos, 1):
        resultado = extraer_monto_operacion(texto)
        
        # Normalizar para comparación
        if resultado:
            resultado_num = float(resultado.replace('$', '').replace(',', ''))
            esperado_num = float(esperado.replace('$', '').replace(',', ''))
            match = abs(resultado_num - esperado_num) < 0.01
        else:
            match = False
        
        status = "✅" if match else "❌"
        
        if match:
            exitosos += 1
        else:
            fallidos += 1
        
        print(f"\n{status} Caso {i}:")
        print(f"   Texto: {texto[:60]}...")
        print(f"   Esperado: {esperado}")
        print(f"   Obtenido: {resultado}")
    
    print(f"\n{'='*60}")
    print(f"RESULTADO: {exitosos}/{len(casos)} casos exitosos")
    if fallidos > 0:
        print(f"⚠️  {fallidos} casos fallaron")
    else:
        print("✅ Todos los casos pasaron")
    print("="*60)
    
    return fallidos == 0


def test_extraccion_completa():
    """
    Prueba la extracción de todos los campos con regex.
    """
    print("\n" + "="*60)
    print("PRUEBA: Extracción completa con regex")
    print("="*60)
    
    texto_ejemplo = """
    ESCRITURA PÚBLICA NÚMERO 18,226
    
    En la ciudad de Guadalajara, Jalisco, a los veintidós días del mes de marzo 
    del año dos mil veinticuatro, ante mí, Licenciado GUILLERMO LOZA RAMÍREZ, 
    Notario Público número 10, comparecen:
    
    Como VENDEDOR: DESARROLLO TURÍSTICO LOS COCOS, S.A. DE C.V., representada 
    por el señor HÉCTOR RAMÓN FLORES IBARRA, en su calidad de apoderado general.
    
    Como COMPRADOR: ANTONIO QUINTERO FLORES, mexicano, casado.
    
    El precio de esta operación fue la cantidad de $600,000.00 (SEISCIENTOS MIL 
    PESOS 00/100 MONEDA NACIONAL), que el comprador paga al vendedor en este acto.
    """
    
    datos = extraer_datos_con_regex(texto_ejemplo)
    
    print("\n📊 Datos extraídos:")
    for campo, valor in datos.items():
        status = "✅" if valor else "❌"
        print(f"   {status} {campo}: {valor}")
    
    # Verificaciones
    assert datos['numero_escritura'] == 18226, f"Número esperado 18226, obtenido {datos['numero_escritura']}"
    assert datos['monto_operacion'] == "$600,000.00", f"Monto esperado $600,000.00, obtenido {datos['monto_operacion']}"
    assert datos['fecha_documento'] is not None, "Fecha no detectada"
    
    print("\n✅ Extracción completa exitosa")
    return True


def test_con_pdf_real(pdf_path: str):
    """
    Prueba la extracción con un PDF real.
    """
    print("\n" + "="*60)
    print(f"PRUEBA: Extracción de PDF real")
    print(f"Archivo: {pdf_path}")
    print("="*60)
    
    from services.azure_ocr_service import get_ocr_service
    
    try:
        ocr = get_ocr_service()
        text, meta = ocr.extract_text(pdf_path)
        
        print(f"\n📄 OCR completado: {meta.get('pages', '?')} páginas, {len(text)} caracteres")
        
        # Extraer datos con regex
        datos = extraer_datos_con_regex(text)
        
        print("\n📊 Datos extraídos por REGEX:")
        for campo, valor in datos.items():
            status = "✅" if valor else "❌"
            print(f"   {status} {campo}: {valor}")
        
        # Mostrar contexto donde se encontró el monto
        if datos['monto_operacion']:
            import re
            monto = datos['monto_operacion'].replace('$', r'\$').replace(',', ',?')
            patron = rf'.{{0,100}}{monto}.{{0,100}}'
            matches = re.findall(patron, text, re.IGNORECASE)
            if matches:
                print(f"\n📝 Contexto del monto encontrado:")
                print(f"   \"{matches[0].strip()}\"")
        else:
            # Buscar patrones de precio en el documento
            print("\n🔍 Buscando patrones de precio en el documento...")
            import re
            patrones_busqueda = [
                r'.{0,50}precio.{0,100}',
                r'.{0,50}cantidad de.{0,100}',
                r'.{0,50}\$[\d,\.]+.{0,50}',
            ]
            
            for patron in patrones_busqueda:
                matches = re.findall(patron, text, re.IGNORECASE)
                for match in matches[:2]:
                    print(f"   📝 {match.strip()[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Ejecuta las pruebas."""
    print("\n" + "#"*60)
    print("# PRUEBAS DE EXTRACCIÓN DE MONTO POR REGEX")
    print("#"*60)
    
    # Si se proporciona un PDF como argumento, probarlo
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        if Path(pdf_path).exists():
            test_con_pdf_real(pdf_path)
        else:
            print(f"❌ Archivo no encontrado: {pdf_path}")
        return
    
    # Pruebas con textos de ejemplo
    try:
        test_patrones_monto()
        test_extraccion_completa()
        
        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS")
        print("="*60)
        print("\n💡 Para probar con un PDF real:")
        print("   python -m tests.test_monto_regex tu_documento.pdf")
        
    except AssertionError as e:
        print(f"\n❌ Prueba fallida: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
