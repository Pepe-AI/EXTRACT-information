"""
Script de prueba para validar la extracción de RFC, CURP, edad y tipo_sociedad
"""

import json
import sys
import os

# Fix encoding for Windows
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")

from app.extractor import EscrituraExtractor, ExtractionConfig

def print_resultado(result):
    """Imprime el resultado de forma legible"""
    print("\n" + "="*80)
    print("RESULTADO DE LA EXTRACCIÓN")
    print("="*80)

    if not result.success:
        print(f"❌ Extracción fallida: {result.error}")
        return

    print(f"✅ Extracción exitosa")
    print(f"   Calidad: {result.calidad_general}%")
    print(f"   Campos encontrados: {result.campos_encontrados}/8")
    print(f"   Plan E activado: {result.plan_e_activado}")

    # Mostrar adquirientes con RFC, CURP, edad, tipo_sociedad
    if result.data and "adquirientes" in result.data:
        print("\n" + "-"*80)
        print("ADQUIRIENTES (COMPRADORES)")
        print("-"*80)

        for i, adq in enumerate(result.data["adquirientes"], 1):
            print(f"\nAdquiriente {i}:")
            print(f"  Nombre: {adq.get('nombre', 'N/A')}")
            print(f"  Tipo: {adq.get('tipo', 'N/A')}")
            print(f"  Estado civil: {adq.get('estado_civil', 'N/A')}")
            print(f"  RFC: {adq.get('rfc', 'N/A')}")
            print(f"  CURP: {adq.get('curp', 'N/A')}")
            print(f"  Edad: {adq.get('edad', 'N/A')}")
            print(f"  Tipo sociedad: {adq.get('tipo_sociedad', 'N/A')}")

    # Mostrar origen de cada campo
    if result.origen:
        print("\n" + "-"*80)
        print("ORIGEN DE LOS DATOS")
        print("-"*80)
        for campo, origen in result.origen.items():
            if campo in ["rfc", "curp", "edad", "tipo_sociedad", "estado_civil"]:
                print(f"  {campo}: {origen}")

    # Mostrar confianza
    if result.confianza:
        print("\n" + "-"*80)
        print("NIVEL DE CONFIANZA")
        print("-"*80)
        for campo, nivel in result.confianza.items():
            if campo in ["rfc", "curp", "edad", "tipo_sociedad", "estado_civil"]:
                print(f"  {campo}: {nivel}")

    # Mostrar JSON completo
    print("\n" + "-"*80)
    print("JSON COMPLETO")
    print("-"*80)
    print(json.dumps(result.data, indent=2, ensure_ascii=False))

def main():
    pdf_path = "ESCRITURA 18226 ANTONIO QUINTERO FLORES NOTARIA 10 NUEVO NAYARIT, NAYARIT_20240611140357 (2).pdf"

    print(f"\n{'='*80}")
    print(f"PRUEBA DE EXTRACCIÓN DE CAMPOS PROBLEMÁTICOS")
    print(f"{'='*80}")
    print(f"PDF: {pdf_path}")
    print(f"\nCampos a validar:")
    print(f"  - RFC")
    print(f"  - CURP")
    print(f"  - edad")
    print(f"  - tipo_sociedad")
    print(f"  - estado_civil")

    # Crear configuración
    config = ExtractionConfig(
        use_classification=True,
        use_plan_e=True,
        max_retries=3,
        temperature=0.0
    )

    # Crear extractor
    extractor = EscrituraExtractor(config=config)

    # Extraer
    result = extractor.extract(pdf_path)

    # Mostrar resultado
    print_resultado(result)

    # Validar campos específicos
    print("\n" + "="*80)
    print("VALIDACIÓN DE CAMPOS PROBLEMÁTICOS")
    print("="*80)

    campos_validar = ["rfc", "curp", "edad", "tipo_sociedad", "estado_civil"]

    if result.data and "adquirientes" in result.data:
        for campo in campos_validar:
            encontrado = False
            for adq in result.data["adquirientes"]:
                valor = adq.get(campo)
                if valor not in [None, False, "", "N/A", "no encontrado"]:
                    print(f"✅ {campo}: ENCONTRADO ({valor})")
                    encontrado = True
                    break

            if not encontrado:
                print(f"❌ {campo}: NO ENCONTRADO")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
