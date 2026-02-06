"""
Script de prueba para validar el nuevo segmentador V2
"""

import sys
import codecs

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")

from extraction.segmentador_v2 import SegmentadorV2
from models.seccion_mapping import SeccionDocumento
from azure_ocr_service import AzureOCRService

def main():
    pdf_path = "ESCRITURA 18226 ANTONIO QUINTERO FLORES NOTARIA 10 NUEVO NAYARIT, NAYARIT_20240611140357 (2).pdf"

    print("="*80)
    print("PRUEBA DE SEGMENTACIÓN V2")
    print("="*80)
    print(f"\nPDF: {pdf_path}\n")

    # Extraer texto con OCR
    print("1. Extrayendo texto con OCR...")
    ocr_service = AzureOCRService()
    texto_raw = ocr_service.extract_text(pdf_path)
    print(f"   OK - {len(texto_raw)} caracteres\n")

    # Limpiar texto
    print("2. Limpiando texto...")
    from utils.text_cleaner import limpiar_texto_ocr
    texto_limpio = limpiar_texto_ocr(texto_raw)
    print(f"   OK - {len(texto_limpio)} caracteres después de limpieza\n")

    # Segmentar con SegmentadorV2
    print("3. Segmentando documento...")
    segmentador = SegmentadorV2(min_confianza=0.5)
    resultado = segmentador.segmentar(texto_limpio)

    print(f"   Usar fallback: {resultado.usar_fallback}")
    print(f"   Confianza general: {resultado.confianza_general:.2f}")
    print(f"   Secciones detectadas: {len(resultado.secciones)}\n")

    # Mostrar secciones detectadas
    print("="*80)
    print("SECCIONES DETECTADAS")
    print("="*80)

    for seccion_tipo, seccion in resultado.secciones.items():
        print(f"\n{seccion_tipo.value.upper()}")
        print("-"*80)
        print(f"  Posición: {seccion.inicio} - {seccion.fin}")
        print(f"  Longitud: {len(seccion.contenido)} caracteres")
        print(f"  Confianza: {seccion.confianza:.2f}")
        print(f"\n  Contenido (primeros 300 chars):")
        print(f"  {seccion.contenido[:300]}...")
        print()

    # Probar obtención de texto para campos específicos
    print("="*80)
    print("PRUEBA DE BÚSQUEDA DIRIGIDA")
    print("="*80)

    from extraction.segmentador_v2 import obtener_seccion_para_campo

    campos_prueba = [
        ("numero_escritura", "Introducción"),
        ("rfc", "Generales"),
        ("monto_operacion", "Cláusula Segunda"),
        ("titular.nombre", "Cláusula Primera"),
    ]

    for campo, seccion_esperada in campos_prueba:
        texto_seccion = obtener_seccion_para_campo(resultado, campo)
        if texto_seccion == resultado.texto_completo:
            origen = "texto completo (fallback)"
        else:
            origen = f"sección específica ({len(texto_seccion)} chars)"

        print(f"\n{campo}:")
        print(f"  Sección esperada: {seccion_esperada}")
        print(f"  Origen del texto: {origen}")

    print("\n" + "="*80)
    print("RESUMEN")
    print("="*80)

    if resultado.usar_fallback:
        print("\n⚠️  Segmentación no confiable - usando texto completo")
        print("    Razón: No se detectaron suficientes secciones o baja confianza")
    else:
        print(f"\n✅ Segmentación exitosa")
        print(f"    Secciones: {', '.join(s.value for s in resultado.secciones.keys())}")
        print(f"    Confianza: {resultado.confianza_general:.1%}")
        print("\n    Ventajas:")
        print("    - Búsqueda dirigida por sección")
        print("    - Menor ambigüedad en campos")
        print("    - Menos tokens enviados al LLM")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
