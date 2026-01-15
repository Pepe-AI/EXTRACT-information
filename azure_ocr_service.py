"""
test_ocr_output.py - Extraer y guardar texto OCR para debug
"""

import sys
from pathlib import Path

# Agregar el proyecto al path
sys.path.insert(0, str(Path(__file__).parent))

from services.azure_ocr_service import get_ocr_service
from utils.text_processing import clean_ocr_text

def extraer_texto_ocr(pdf_path: str, output_file: str = "texto_ocr.txt"):
    """Extrae el texto OCR y lo guarda en un archivo."""
    
    print(f"📄 Procesando: {pdf_path}")
    
    # Obtener servicio OCR
    ocr_service = get_ocr_service()
    
    # Extraer texto
    print("🔍 Extrayendo texto con OCR...")
    texto_raw, metadata = ocr_service.extract_text(pdf_path)
    
    print(f"   ✅ Páginas: {metadata.get('pages', '?')}")
    print(f"   ✅ Caracteres raw: {len(texto_raw)}")
    
    # Limpiar texto
    texto_limpio = clean_ocr_text(texto_raw)
    print(f"   ✅ Caracteres limpios: {len(texto_limpio)}")
    
    # Guardar en archivo
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("TEXTO OCR RAW\n")
        f.write("=" * 80 + "\n\n")
        f.write(texto_raw)
        f.write("\n\n")
        f.write("=" * 80 + "\n")
        f.write("TEXTO OCR LIMPIO\n")
        f.write("=" * 80 + "\n\n")
        f.write(texto_limpio)
    
    print(f"\n✅ Texto guardado en: {output_file}")
    print(f"\n📋 Texto limpio completo:\n")
    print("-" * 80)
    print(texto_limpio)
    print("-" * 80)
    
    return texto_limpio

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python test_ocr_output.py <ruta_pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    extraer_texto_ocr(pdf_path)