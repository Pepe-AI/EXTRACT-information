#!/usr/bin/env python3
"""
test_gemini_extraction.py - Test para ver exactamente qué retorna Gemini

OBJETIVO:
=========
Ver la respuesta cruda de Gemini cuando se le pide extraer rfc, curp, edad
del texto OCR que ya tenemos.

USO:
====
python test_gemini_extraction.py

SALIDA:
=======
- Muestra el prompt enviado a Gemini
- Muestra la respuesta RAW de Gemini
- Muestra el JSON parseado
- Verifica si rfc, curp, edad están presentes
"""

import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

def test_gemini_raw_response():
    """
    Prueba la extracción de Gemini y muestra la respuesta cruda.
    """
    print("\n" + "="*80)
    print("TEST: ¿Qué está retornando Gemini para rfc, curp, edad?")
    print("="*80)

    # =========================================================================
    # PASO 1: Leer el OCR que ya tenemos
    # =========================================================================
    ocr_file = Path("ocr_output.txt")

    if not ocr_file.exists():
        print(f"\n[ERROR] ERROR: No se encontró {ocr_file}")
        print("   Ejecuta primero: python extraer_ocr_simple.py <archivo.pdf>")
        return 1

    print(f"\n[*] Leyendo OCR de: {ocr_file}")
    with open(ocr_file, "r", encoding="utf-8") as f:
        ocr_text = f.read()

    print(f"   [OK] OCR leido: {len(ocr_text):,} caracteres")

    # =========================================================================
    # PASO 2: Generar prompt "expandido" de Gemini
    # =========================================================================
    print(f"\n[*] Generando prompt 'expandido' de Gemini...")

    from utils.gemini_prompts import build_gemini_prompt_expandido

    prompt = build_gemini_prompt_expandido(ocr_text)

    print(f"   [OK] Prompt generado: {len(prompt):,} caracteres")

    # Guardar prompt para inspección
    prompt_file = Path("test_prompt_gemini.txt")
    with open(prompt_file, "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"   [SAVE] Prompt guardado en: {prompt_file}")

    # =========================================================================
    # PASO 3: Llamar a Gemini
    # =========================================================================
    print(f"\n[*] Llamando a Gemini 2.5 Flash...")
    print(f"   (Esto puede tomar 5-10 segundos...)")

    try:
        from services.gemini_service import get_gemini_fallback_service

        gemini_service = get_gemini_fallback_service()

        # Llamar a Gemini
        raw_response = gemini_service.generate_content(prompt)

        if not raw_response:
            print(f"\n[ERROR] ERROR: Gemini no devolvió respuesta")
            return 1

        print(f"\n[OK] Respuesta recibida: {len(raw_response):,} caracteres")

        # Guardar respuesta cruda
        response_file = Path("test_response_gemini_raw.txt")
        with open(response_file, "w", encoding="utf-8") as f:
            f.write(raw_response)
        print(f"   [SAVE] Respuesta RAW guardada en: {response_file}")

    except Exception as e:
        print(f"\n[ERROR] Error llamando a Gemini: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # =========================================================================
    # PASO 4: Parsear respuesta JSON
    # =========================================================================
    print(f"\n[*] Parseando respuesta JSON...")

    from utils.gemini_prompts import parse_gemini_response

    json_data = parse_gemini_response(raw_response)

    if not json_data:
        print(f"\n[ERROR] ERROR: No se pudo parsear JSON de la respuesta")
        print(f"\n[*] Respuesta RAW (primeros 500 caracteres):")
        print("-" * 80)
        print(raw_response[:500])
        print("-" * 80)
        return 1

    print(f"   [OK] JSON parseado exitosamente")

    # Guardar JSON parseado
    json_file = Path("test_response_gemini_parsed.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)
    print(f"   [SAVE] JSON parseado guardado en: {json_file}")

    # =========================================================================
    # PASO 5: Analizar campos de adquiriente
    # =========================================================================
    print(f"\n" + "="*80)
    print("ANÁLISIS DE CAMPOS EXTRAÍDOS POR GEMINI")
    print("="*80)

    # Gemini puede retornar "adquiriente" o "adquirientes"
    adquiriente_data = None

    if "adquiriente" in json_data and json_data["adquiriente"]:
        adquiriente_data = json_data["adquiriente"]
        print(f"\n[OK] Gemini retornó 'adquiriente' (singular)")
    elif "adquirientes" in json_data and json_data["adquirientes"]:
        adquirientes_list = json_data["adquirientes"]
        if isinstance(adquirientes_list, list) and len(adquirientes_list) > 0:
            adquiriente_data = adquirientes_list[0]  # Tomar el primero
            print(f"\n[OK] Gemini retornó 'adquirientes' (plural): {len(adquirientes_list)} elementos")
            print(f"   Analizando el primer adquiriente...")
        else:
            print(f"\n[WARN] 'adquirientes' existe pero está vacío o no es lista")
    else:
        print(f"\n[ERROR] ERROR: Gemini NO retornó 'adquiriente' ni 'adquirientes'")
        print(f"\n[*] Estructura JSON recibida:")
        print(json.dumps(json_data, indent=2, ensure_ascii=False)[:500])
        return 1

    if not adquiriente_data:
        print(f"\n[ERROR] No se pudo obtener datos del adquiriente")
        return 1

    # =========================================================================
    # PASO 6: Verificar campos críticos
    # =========================================================================
    print(f"\n" + "-"*80)
    print("VERIFICACIÓN DE CAMPOS: rfc, curp, edad")
    print("-"*80)

    campos_criticos = ["rfc", "curp", "edad", "estado_civil", "tipo_sociedad", "nombre", "tipo"]

    for campo in campos_criticos:
        valor = adquiriente_data.get(campo)

        # Determinar estado
        if campo not in adquiriente_data:
            estado = "[ERROR] AUSENTE"
            detalle = "El campo NO está presente en el JSON"
        elif valor is None:
            estado = "[WARN] NULL"
            detalle = "El campo existe pero tiene valor null"
        elif valor is False or valor == "false":
            estado = "[WARN] FALSE"
            detalle = "El campo existe pero tiene valor false"
        elif valor == "" or valor == []:
            estado = "[WARN] VACÍO"
            detalle = "El campo existe pero está vacío"
        else:
            estado = "[OK] EXTRAÍDO"
            detalle = f"Valor: {valor}"

        print(f"\n{campo:20} → {estado}")
        print(f"{'':20}    {detalle}")

    # =========================================================================
    # PASO 7: Mostrar JSON completo del adquiriente
    # =========================================================================
    print(f"\n" + "="*80)
    print("JSON COMPLETO DEL ADQUIRIENTE (según Gemini)")
    print("="*80)
    print(json.dumps(adquiriente_data, indent=2, ensure_ascii=False))

    # =========================================================================
    # PASO 8: Verificar si los datos EXISTEN en el OCR
    # =========================================================================
    print(f"\n" + "="*80)
    print("VERIFICACIÓN: ¿Los datos existen en el OCR?")
    print("="*80)

    # Buscar RFC en el OCR
    import re

    rfc_pattern = r'\b([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})\b'
    curp_pattern = r'\b([A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d)\b'

    rfcs_found = re.findall(rfc_pattern, ocr_text.upper())
    curps_found = re.findall(curp_pattern, ocr_text.upper())

    print(f"\n[*] RFC encontrados en OCR (regex): {len(rfcs_found)}")
    for i, rfc in enumerate(rfcs_found[:5], 1):  # Mostrar primeros 5
        print(f"   {i}. {rfc}")

    print(f"\n[*] CURP encontrados en OCR (regex): {len(curps_found)}")
    for i, curp in enumerate(curps_found[:5], 1):  # Mostrar primeros 5
        print(f"   {i}. {curp}")

    # =========================================================================
    # PASO 9: Comparar lo que Gemini extrajo vs lo que existe
    # =========================================================================
    print(f"\n" + "="*80)
    print("CONCLUSIÓN")
    print("="*80)

    rfc_gemini = adquiriente_data.get("rfc")
    curp_gemini = adquiriente_data.get("curp")
    edad_gemini = adquiriente_data.get("edad")

    print(f"\n[*] RFC:")
    if rfc_gemini and rfc_gemini not in [False, "false", None, ""]:
        print(f"   [OK] Gemini SÍ extrajo RFC: {rfc_gemini}")
        if rfc_gemini in rfcs_found:
            print(f"   [OK] El RFC extraído EXISTE en el OCR")
        else:
            print(f"   [WARN] El RFC extraído NO coincide con los encontrados en OCR")
    else:
        print(f"   [ERROR] Gemini NO extrajo RFC (valor: {rfc_gemini})")
        if rfcs_found:
            print(f"   [WARN] PERO el OCR SÍ contiene {len(rfcs_found)} RFC(s)")
            print(f"   [TIP] Gemini DEBERÍA haber extraído: {rfcs_found[0]}")

    print(f"\n[*] CURP:")
    if curp_gemini and curp_gemini not in [False, "false", None, ""]:
        print(f"   [OK] Gemini SÍ extrajo CURP: {curp_gemini}")
        if curp_gemini in curps_found:
            print(f"   [OK] El CURP extraído EXISTE en el OCR")
        else:
            print(f"   [WARN] El CURP extraído NO coincide con los encontrados en OCR")
    else:
        print(f"   [ERROR] Gemini NO extrajo CURP (valor: {curp_gemini})")
        if curps_found:
            print(f"   [WARN] PERO el OCR SÍ contiene {len(curps_found)} CURP(s)")
            print(f"   [TIP] Gemini DEBERÍA haber extraído: {curps_found[0]}")

    print(f"\n[*] EDAD:")
    if edad_gemini and edad_gemini not in [False, "false", None, ""]:
        print(f"   [OK] Gemini SÍ extrajo edad: {edad_gemini}")
    else:
        print(f"   [ERROR] Gemini NO extrajo edad (valor: {edad_gemini})")

    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================
    print(f"\n" + "="*80)
    print("RESUMEN FINAL")
    print("="*80)

    if not rfc_gemini or rfc_gemini in [False, "false", None, ""]:
        if rfcs_found:
            print(f"\n[ERROR] PROBLEMA CONFIRMADO: Gemini NO está extrayendo RFC")
            print(f"   - Gemini retornó: {rfc_gemini}")
            print(f"   - OCR contiene: {rfcs_found[0]}")
            print(f"   - CAUSA PROBABLE: El prompt no es suficientemente específico")
        else:
            print(f"\n[WARN] RFC no extraído, pero tampoco existe en OCR")

    if not curp_gemini or curp_gemini in [False, "false", None, ""]:
        if curps_found:
            print(f"\n[ERROR] PROBLEMA CONFIRMADO: Gemini NO está extrayendo CURP")
            print(f"   - Gemini retornó: {curp_gemini}")
            print(f"   - OCR contiene: {curps_found[0]}")
            print(f"   - CAUSA PROBABLE: El prompt no es suficientemente específico")
        else:
            print(f"\n[WARN] CURP no extraído, pero tampoco existe en OCR")

    if not edad_gemini or edad_gemini in [False, "false", None, ""]:
        print(f"\n[WARN] Edad no extraída por Gemini")
        print(f"   - Gemini retornó: {edad_gemini}")

    print(f"\n" + "="*80)
    print("Archivos generados:")
    print(f"  - {prompt_file} (prompt enviado)")
    print(f"  - {response_file} (respuesta RAW)")
    print(f"  - {json_file} (JSON parseado)")
    print("="*80 + "\n")

    return 0


def main():
    """Punto de entrada principal."""
    print("\n" + "#"*80)
    print("# TEST: Verificar respuesta de Gemini para rfc, curp, edad")
    print("#"*80)

    try:
        return test_gemini_raw_response()
    except Exception as e:
        print(f"\n[ERROR] ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
