#!/usr/bin/env python3
"""
extraer_ocr_simple.py - Script simple para extraer OCR de un PDF

USO:
====
python extraer_ocr_simple.py ruta/al/archivo.pdf

SALIDA:
=======
- Imprime el texto OCR en consola
- Guarda el texto en: ocr_output.txt

REQUISITOS:
===========
- Credenciales de Azure configuradas en .env
- PDF en la ruta especificada
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def extraer_ocr(pdf_path: str):
    """
    Extrae texto OCR de un PDF usando Azure Document Intelligence.

    Args:
        pdf_path: Ruta al archivo PDF
    """
    print("\n" + "="*60)
    print("EXTRACCIÓN DE OCR")
    print("="*60)

    # Importar servicio Azure OCR
    from services.azure_ocr_service import (
        AzureConfig,
        AzureOCRService,
        OCRServiceError
    )

    # Verificar que el PDF existe
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"\n❌ ERROR: No se encontró el archivo: {pdf_path}")
        return

    print(f"\n📄 Archivo: {pdf_file.name}")
    print(f"📍 Ruta: {pdf_file.absolute()}")

    # Verificar configuración
    config = AzureConfig()
    if not config.is_configured:
        print("\n❌ ERROR: Azure no está configurado")
        print("\nConfigura las credenciales en .env:")
        print("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://tu-recurso.cognitiveservices.azure.com/")
        print("AZURE_DOCUMENT_INTELLIGENCE_KEY=tu-clave-aqui")
        return

    print(f"\n🔧 Endpoint: {config.endpoint[:50]}...")
    print(f"🔑 Key: {config.key[:8]}****")

    # Crear servicio y extraer texto
    print("\n🔍 Enviando a Azure Document Intelligence...")
    print("   (Esto puede tomar varios segundos...)\n")

    try:
        service = AzureOCRService(config)
        text, metadata = service.extract_text(str(pdf_file.absolute()))

        print(f"✅ Extracción exitosa!")
        print(f"   📄 Páginas: {metadata.get('pages', 'N/A')}")
        print(f"   🔤 Caracteres: {len(text):,}")
        print(f"   📏 Palabras (aprox): {len(text.split()):,}")

        # Guardar en archivo
        output_file = Path("ocr_output.txt")
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("="*60 + "\n")
            f.write(f"EXTRACCIÓN OCR - {pdf_file.name}\n")
            f.write("="*60 + "\n\n")
            f.write(text)

        print(f"\n💾 Texto guardado en: {output_file.absolute()}")

        # Mostrar muestra del texto
        print(f"\n📝 MUESTRA DEL TEXTO EXTRAÍDO:")
        print("-" * 60)
        muestra = text[:1000] if len(text) > 1000 else text
        print(muestra)
        if len(text) > 1000:
            print("\n... (texto truncado, ver archivo completo en ocr_output.txt)")
        print("-" * 60)

        print(f"\n✅ LISTO! Revisa el archivo: {output_file.absolute()}")

    except OCRServiceError as e:
        print(f"\n❌ Error de OCR: {type(e).__name__}")
        print(f"   {str(e)}")
    except Exception as e:
        print(f"\n❌ Error inesperado: {type(e).__name__}")
        print(f"   {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """Punto de entrada principal."""
    print("\n" + "#"*60)
    print("# EXTRACTOR DE OCR - Azure Document Intelligence")
    print("#"*60)

    # Verificar argumentos
    if len(sys.argv) < 2:
        print("\n❌ ERROR: Falta la ruta del PDF")
        print("\nUSO:")
        print(f"  python {Path(__file__).name} ruta/al/archivo.pdf")
        print("\nEJEMPLOS:")
        print(f'  python {Path(__file__).name} tests/sample.pdf')
        print(f'  python {Path(__file__).name} "C:/Users/Usuari/Documents/mi_documento.pdf"')
        return 1

    pdf_path = sys.argv[1]
    extraer_ocr(pdf_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
