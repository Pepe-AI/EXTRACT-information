#!/usr/bin/env python3
"""
test_extractor_completo.py - Test end-to-end del extractor

Ejecuta el extractor completo para verificar que RFC, CURP, edad
se extraen correctamente después del fix de truncamiento.
"""

import sys
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def test_extractor_completo():
    """Test end-to-end del extractor."""

    print("\n" + "="*80)
    print("TEST END-TO-END: Extractor completo con fix de truncamiento")
    print("="*80)

    # Archivo PDF
    pdf_file = Path("ESCRITURA 18226 ANTONIO QUINTERO FLORES NOTARIA 10 NUEVO NAYARIT, NAYARIT_20240611140357 (2).pdf")

    if not pdf_file.exists():
        print(f"\n[ERROR] No se encontro el PDF: {pdf_file}")
        return 1

    print(f"\n[*] PDF a procesar: {pdf_file.name}")
    print(f"    Tamano: {pdf_file.stat().st_size:,} bytes")

    # Importar extractor
    print(f"\n[*] Importando extractor...")
    from app.extractor import EscrituraExtractor

    # Crear instancia
    print(f"[*] Creando instancia del extractor...")
    extractor = EscrituraExtractor()

    # Procesar documento
    print(f"\n[*] Procesando documento (esto puede tomar 30-60 segundos)...")
    print(f"    - Azure OCR")
    print(f"    - DeepSeek extraction")
    print(f"    - Gemini extraction (expandido)")
    print(f"    - Merge + validacion")

    try:
        resultado = extractor.extract(str(pdf_file.absolute()))

        if not resultado:
            print(f"\n[ERROR] El extractor no retorno resultado")
            return 1

        print(f"\n[OK] Documento procesado exitosamente")

        # Guardar JSON completo
        output_file = Path("test_extractor_output.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(resultado, f, indent=2, ensure_ascii=False)

        print(f"[SAVE] JSON completo guardado en: {output_file}")

        # Analizar adquirientes
        print(f"\n" + "="*80)
        print("ANALISIS DE ADQUIRIENTES")
        print("="*80)

        adquirientes = resultado.get("adquirientes", [])

        if not adquirientes:
            print(f"\n[WARN] No se encontraron adquirientes en el resultado")
            return 1

        print(f"\n[*] Total de adquirientes: {len(adquirientes)}")

        for i, adq in enumerate(adquirientes, 1):
            print(f"\n{'─'*80}")
            print(f"ADQUIRIENTE {i}")
            print(f"{'─'*80}")

            # Campos basicos
            print(f"\nnombre:          {adq.get('nombre', 'N/A')}")
            print(f"tipo:            {adq.get('tipo', 'N/A')}")

            # CAMPOS CRITICOS (los que queremos verificar)
            rfc = adq.get("rfc")
            curp = adq.get("curp")
            edad = adq.get("edad")
            estado_civil = adq.get("estado_civil")
            tipo_sociedad = adq.get("tipo_sociedad")

            # Verificar RFC
            if rfc and rfc not in [False, "false", None, ""]:
                print(f"rfc:             [OK] {rfc}")
            else:
                print(f"rfc:             [ERROR] {rfc} (no extraido)")

            # Verificar CURP
            if curp and curp not in [False, "false", None, ""]:
                print(f"curp:            [OK] {curp}")
            else:
                print(f"curp:            [ERROR] {curp} (no extraido)")

            # Verificar edad
            if edad and edad not in [False, "false", None, ""]:
                print(f"edad:            [OK] {edad}")
            else:
                print(f"edad:            [ERROR] {edad} (no extraido)")

            # Verificar estado_civil
            if estado_civil and estado_civil not in [False, "false", None, ""]:
                print(f"estado_civil:    [OK] {estado_civil}")
            else:
                print(f"estado_civil:    [ERROR] {estado_civil} (no extraido)")

            # Verificar tipo_sociedad
            if tipo_sociedad and tipo_sociedad not in [False, "false", None, ""]:
                print(f"tipo_sociedad:   [OK] {tipo_sociedad}")
            else:
                print(f"tipo_sociedad:   [INFO] {tipo_sociedad} (puede ser false si no existe)")

        # Resumen final
        print(f"\n" + "="*80)
        print("RESUMEN FINAL")
        print("="*80)

        # Contar campos extraidos
        total_adq = len(adquirientes)
        rfc_ok = sum(1 for adq in adquirientes if adq.get("rfc") not in [False, "false", None, ""])
        curp_ok = sum(1 for adq in adquirientes if adq.get("curp") not in [False, "false", None, ""])
        edad_ok = sum(1 for adq in adquirientes if adq.get("edad") not in [False, "false", None, ""])
        estado_civil_ok = sum(1 for adq in adquirientes if adq.get("estado_civil") not in [False, "false", None, ""])

        print(f"\nAdquirientes con RFC extraido:         {rfc_ok}/{total_adq}")
        print(f"Adquirientes con CURP extraido:        {curp_ok}/{total_adq}")
        print(f"Adquirientes con edad extraida:        {edad_ok}/{total_adq}")
        print(f"Adquirientes con estado_civil extraido: {estado_civil_ok}/{total_adq}")

        if rfc_ok == 0 and curp_ok == 0:
            print(f"\n[ERROR] FIX NO FUNCIONO: RFC y CURP siguen sin extraerse")
            print(f"[TIP] Verifica que el cambio en utils/gemini_prompts.py este aplicado")
            return 1
        elif rfc_ok > 0 or curp_ok > 0:
            print(f"\n[OK] FIX FUNCIONA: Al menos algunos campos se extrajeron correctamente")
            return 0

    except Exception as e:
        print(f"\n[ERROR] Error durante procesamiento: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_extractor_completo())
