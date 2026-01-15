"""
tests/test_integracion_plan_z.py - Prueba de integración del Plan Z

Este script prueba el flujo completo con un PDF real.

Uso:
    python -m tests.test_integracion_plan_z ruta/al/documento.pdf
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.extractor import EscrituraExtractor


def test_con_pdf(pdf_path: str):
    """Prueba el extractor completo con un PDF."""
    
    print("\n" + "=" * 70)
    print("TEST DE INTEGRACIÓN - PLAN Z (ABDF + E)")
    print("=" * 70)
    print(f"\n📄 Archivo: {pdf_path}")
    
    # Crear extractor
    extractor = EscrituraExtractor()
    
    # Ejecutar extracción
    resultado = extractor.extract(pdf_path)
    
    # Mostrar resultado
    print("\n" + "=" * 70)
    print("RESULTADO FINAL")
    print("=" * 70)
    
    if resultado.success:
        print(f"\n✅ ÉXITO")
        print(f"   Calidad: {resultado.calidad_general}%")
        print(f"   Campos encontrados: {resultado.campos_encontrados}/8")
        print(f"   Plan E activado: {'Sí' if resultado.plan_e_activado else 'No'}")
        
        if resultado.campos_mejorados_plan_e:
            print(f"   Campos mejorados por Plan E: {resultado.campos_mejorados_plan_e}")
        
        print(f"\n📋 DATOS EXTRAÍDOS:")
        print(json.dumps(resultado.data, indent=2, ensure_ascii=False, default=str))
        
        print(f"\n📊 CONFIANZA POR CAMPO:")
        for campo, confianza in resultado.confianza.items():
            emoji = "✅" if confianza == "alta" else ("⚠️" if confianza == "media" else "❌")
            origen = resultado.origen.get(campo, "N/A")
            print(f"   {emoji} {campo}: {confianza} (origen: {origen})")
        
        if resultado.requiere_revision:
            print(f"\n🔍 REQUIEREN REVISIÓN: {resultado.requiere_revision}")
        
        if resultado.campos_no_encontrados:
            print(f"\n❌ NO ENCONTRADOS: {resultado.campos_no_encontrados}")
    
    else:
        print(f"\n❌ FALLO: {resultado.error}")
        
        if resultado.detalles_fallo:
            print(f"\n📋 DETALLES:")
            print(json.dumps(resultado.detalles_fallo, indent=2, ensure_ascii=False))
    
    print(f"\n⏱️ Tiempo: {resultado.processing_time:.2f} segundos")
    print("=" * 70)
    
    return resultado


def main():
    if len(sys.argv) < 2:
        print("Uso: python -m tests.test_integracion_plan_z <ruta_pdf>")
        print("\nEjemplo:")
        print("  python -m tests.test_integracion_plan_z documento.pdf")
        return 1
    
    pdf_path = sys.argv[1]
    
    if not Path(pdf_path).exists():
        print(f"❌ Archivo no encontrado: {pdf_path}")
        return 1
    
    resultado = test_con_pdf(pdf_path)
    
    return 0 if resultado.success else 1


if __name__ == "__main__":
    sys.exit(main())