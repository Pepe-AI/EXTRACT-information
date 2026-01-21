"""
Script de diagnóstico para detectar problemas con nombre_notario
"""

import sys
import re
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from utils.text_processing import extraer_nombre_notario


def test_patrones():
    """Prueba los patrones regex con ejemplos conocidos."""

    ejemplos = [
        # Formato: (texto, nombre_esperado)
        (
            "ante mí, Lic. RIGOBERTO OCHOA TORRES, Notario Público número 45",
            "RIGOBERTO OCHOA TORRES"
        ),
        (
            "FERNANDO CASTRO RUBIO, Notario Público número 123",
            "FERNANDO CASTRO RUBIO"
        ),
        (
            "ante mí, GUILLERMO LOZA RAMÍREZ, Notario",
            "GUILLERMO LOZA RAMÍREZ"
        ),
        (
            """
            ESCRITURA NÚMERO 2307

            En la ciudad de Tepic, Nayarit, a cinco de mayo de 2023

            Ante mí, RIGOBERTO OCHOA TORRES, Notario Público número 45
            del Estado de Nayarit, comparecen...
            """,
            "RIGOBERTO OCHOA TORRES"
        ),
    ]

    print("=" * 70)
    print("PRUEBA DE PATRONES REGEX PARA NOMBRE DE NOTARIO")
    print("=" * 70)

    for i, (texto, esperado) in enumerate(ejemplos, 1):
        print(f"\n[TEST {i}]")
        print(f"   Texto: {texto[:80].replace(chr(10), ' ')}...")
        print(f"   Esperado: {esperado}")

        resultado = extraer_nombre_notario(texto)

        if resultado:
            print(f"   [OK] Detectado: {resultado}")
            if resultado.upper() == esperado.upper():
                print(f"   [OK] CORRECTO")
            else:
                print(f"   [ERROR] DIFERENTE DEL ESPERADO")
        else:
            print(f"   [ERROR] NO DETECTADO")

    print("\n" + "=" * 70)


def test_documento_real():
    """
    Pega aquí el texto OCR de tu documento real para diagnosticar.
    """

    # INSTRUCCIONES:
    # 1. Ejecuta el script y copia el texto OCR del documento que falla
    # 2. Pégalo aquí entre las comillas triple
    # 3. Vuelve a ejecutar

    texto_real = """
    PEGA AQUÍ EL TEXTO OCR DEL DOCUMENTO REAL
    """

    if "PEGA AQUÍ" not in texto_real:
        print("\n" + "=" * 70)
        print("DIAGNÓSTICO DE DOCUMENTO REAL")
        print("=" * 70)

        resultado = extraer_nombre_notario(texto_real)

        if resultado:
            print(f"\n[OK] Nombre detectado: {resultado}")
        else:
            print(f"\n[ERROR] NO se detecto el nombre del notario")
            print(f"\nBuscando patrones en el texto...")

            # Buscar posibles ubicaciones
            patrones_comunes = [
                r'ante\s+m[ií]',
                r'[Nn]otario\s+[Pp][uú]blico',
                r'[Tt]itular\s+de\s+la\s+[Nn]otar[ií]a',
            ]

            for patron in patrones_comunes:
                matches = list(re.finditer(patron, texto_real, re.IGNORECASE))
                if matches:
                    print(f"\n   Patrón '{patron}' encontrado {len(matches)} vez/veces:")
                    for match in matches:
                        inicio = max(0, match.start() - 50)
                        fin = min(len(texto_real), match.end() + 50)
                        contexto = texto_real[inicio:fin].replace('\n', ' ')
                        print(f"      ...{contexto}...")


def mostrar_patrones_actuales():
    """Muestra los patrones regex que se están usando."""

    print("\n" + "=" * 70)
    print("PATRONES REGEX ACTUALES")
    print("=" * 70)

    # Extraer patrones del código fuente
    from utils.text_processing import extraer_nombre_notario
    import inspect

    source = inspect.getsource(extraer_nombre_notario)

    # Buscar los patrones
    patron_busqueda = r"r'([^']+)'"
    patrones = re.findall(patron_busqueda, source)

    print("\nPatrones definidos:")
    for i, patron in enumerate(patrones[:3], 1):  # Solo los primeros 3
        print(f"\n{i}. {patron}")


if __name__ == "__main__":
    # Ejecutar todas las pruebas
    test_patrones()
    mostrar_patrones_actuales()
    test_documento_real()

    print("\n" + "=" * 70)
    print("RECOMENDACIONES:")
    print("=" * 70)
    print("""
1. Si los ejemplos de prueba pasan pero el documento real falla:
   - Copia el texto OCR del documento real
   - Pégalo en la función test_documento_real()
   - Vuelve a ejecutar este script

2. Si ningún patrón funciona:
   - Revisa el formato del nombre en el documento
   - Puede que necesitemos agregar un nuevo patrón regex

3. Para ejecutar este script:
   python test_nombre_notario.py
""")
