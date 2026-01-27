#!/usr/bin/env python3
"""
test_gemini_adquirientes_array.py - Test que Gemini separa adquirientes multiples

Verifica que Gemini retorna "adquirientes" como array cuando hay multiples personas.
"""

import json
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def test_gemini_adquirientes_array():
    """Test que Gemini separa adquirientes multiples."""

    print("\n" + "="*80)
    print("TEST: Gemini retorna adquirientes como array (separados)")
    print("="*80)

    # Leer OCR
    ocr_file = Path("ocr_output.txt")

    if not ocr_file.exists():
        print(f"\n[ERROR] No se encontro: {ocr_file}")
        print(f"[TIP] Ejecuta primero: python extraer_ocr_simple.py 'ESCRITURA 18226...pdf'")
        return 1

    with open(ocr_file, "r", encoding="utf-8") as f:
        ocr_text = f.read()

    print(f"\n[*] OCR leido: {len(ocr_text):,} caracteres")

    # Generar prompt expandido con el fix de adquirientes array
    print(f"\n[*] Generando prompt expandido (con fix de adquirientes array)...")

    from utils.gemini_prompts import build_gemini_prompt_expandido

    prompt = build_gemini_prompt_expandido(ocr_text)

    print(f"[*] Longitud del prompt: {len(prompt):,} caracteres")

    # Guardar prompt
    with open("test_prompt_gemini_array.txt", "w", encoding="utf-8") as f:
        f.write(prompt)
    print(f"[SAVE] Prompt guardado: test_prompt_gemini_array.txt")

    # Importar Gemini service
    print(f"\n[*] Inicializando Gemini service...")

    try:
        from services.gemini_service import get_gemini_fallback_service
        gemini = get_gemini_fallback_service()
    except ImportError as e:
        print(f"\n[ERROR] No se pudo importar gemini_service: {e}")
        print(f"[TIP] Verifica que google-genai este instalado: python -m pip install google-genai")
        return 1
    except Exception as e:
        print(f"\n[ERROR] No se pudo inicializar Gemini: {e}")
        return 1

    # Llamar a Gemini
    print(f"\n[*] Llamando a Gemini 2.5 Flash...")
    print(f"    (esto puede tomar 10-30 segundos)")

    try:
        raw_response = gemini.generate_content(prompt)

        if not raw_response:
            print(f"\n[ERROR] Gemini no retorno respuesta")
            return 1

        # Guardar respuesta raw
        with open("test_response_gemini_array_raw.txt", "w", encoding="utf-8") as f:
            f.write(raw_response)
        print(f"\n[SAVE] Respuesta raw guardada: test_response_gemini_array_raw.txt")

    except Exception as e:
        print(f"\n[ERROR] Error al llamar a Gemini: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Parsear JSON
    print(f"\n[*] Parseando respuesta JSON...")

    try:
        # Limpiar respuesta (quitar markdown si existe)
        json_str = raw_response.strip()
        if json_str.startswith("```json"):
            json_str = json_str.replace("```json", "").replace("```", "").strip()
        elif json_str.startswith("```"):
            json_str = json_str.replace("```", "").strip()

        data = json.loads(json_str)

        # Guardar JSON parseado
        with open("test_response_gemini_array_parsed.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[SAVE] JSON parseado guardado: test_response_gemini_array_parsed.json")

    except json.JSONDecodeError as e:
        print(f"\n[ERROR] No se pudo parsear JSON: {e}")
        print(f"[DEBUG] Respuesta raw:")
        print(raw_response[:500])
        return 1

    # Analizar resultado
    print(f"\n" + "="*80)
    print("ANALISIS DE RESULTADO")
    print("="*80)

    # Verificar estructura
    print(f"\n[*] Campos en respuesta: {list(data.keys())}")

    # Verificar adquirientes
    if "adquirientes" in data:
        adquirientes = data["adquirientes"]

        if isinstance(adquirientes, list):
            print(f"\n[OK] Gemini retorno 'adquirientes' como ARRAY")
            print(f"[OK] Total de adquirientes: {len(adquirientes)}")

            # Mostrar cada adquiriente
            for i, adq in enumerate(adquirientes, 1):
                print(f"\n{'─'*80}")
                print(f"ADQUIRIENTE {i}")
                print(f"{'─'*80}")
                print(f"nombre:       {adq.get('nombre', 'N/A')}")
                print(f"rfc:          {adq.get('rfc', 'N/A')}")
                print(f"curp:         {adq.get('curp', 'N/A')}")
                print(f"edad:         {adq.get('edad', 'N/A')}")
                print(f"estado_civil: {adq.get('estado_civil', 'N/A')}")

            # Verificar si se separaron correctamente
            if len(adquirientes) >= 2:
                print(f"\n" + "="*80)
                print("VERIFICACION DE SEPARACION")
                print("="*80)

                adq1 = adquirientes[0]
                adq2 = adquirientes[1]

                # Verificar que nombres estan separados
                nombre1 = adq1.get("nombre", "")
                nombre2 = adq2.get("nombre", "")

                if "y" not in nombre1 and "y" not in nombre2:
                    print(f"\n[OK] Nombres estan SEPARADOS (no hay 'y' en los nombres)")
                    print(f"     Adquiriente 1: {nombre1}")
                    print(f"     Adquiriente 2: {nombre2}")
                else:
                    print(f"\n[ERROR] Nombres TODAVIA concatenados (contienen 'y')")
                    print(f"     Adquiriente 1: {nombre1}")
                    print(f"     Adquiriente 2: {nombre2}")

                # Verificar RFC/CURP individuales
                rfc1 = adq1.get("rfc")
                rfc2 = adq2.get("rfc")
                curp1 = adq1.get("curp")
                curp2 = adq2.get("curp")

                print(f"\n[*] RFC/CURP extraidos:")
                print(f"    Adquiriente 1: RFC={rfc1}, CURP={curp1}")
                print(f"    Adquiriente 2: RFC={rfc2}, CURP={curp2}")

                # Valores esperados
                print(f"\n[*] Valores esperados:")
                print(f"    Antonio: RFC=QUFA670718TK2, CURP=QUFA670718HJCNLN04")
                print(f"    Silvia:  RFC=SASS680104FB7, CURP=SASS680104MJCNNL03")

                # Verificar coincidencias
                antonio_ok = (rfc1 == "QUFA670718TK2" and curp1 == "QUFA670718HJCNLN04") or \
                             (rfc2 == "QUFA670718TK2" and curp2 == "QUFA670718HJCNLN04")

                silvia_ok = (rfc1 == "SASS680104FB7" and curp1 == "SASS680104MJCNNL03") or \
                            (rfc2 == "SASS680104FB7" and curp2 == "SASS680104MJCNNL03")

                print(f"\n" + "="*80)
                print("RESULTADO FINAL")
                print("="*80)

                if antonio_ok and silvia_ok:
                    print(f"\n[OK] FIX EXITOSO:")
                    print(f"     - Adquirientes separados en array")
                    print(f"     - RFC/CURP de Antonio extraidos correctamente")
                    print(f"     - RFC/CURP de Silvia extraidos correctamente")
                    return 0
                else:
                    print(f"\n[WARN] FIX PARCIAL:")
                    print(f"     - Adquirientes separados: OK")
                    print(f"     - RFC/CURP Antonio: {'OK' if antonio_ok else 'FALLO'}")
                    print(f"     - RFC/CURP Silvia:  {'OK' if silvia_ok else 'FALLO'}")
                    return 1
            else:
                print(f"\n[WARN] Solo se encontro {len(adquirientes)} adquiriente(s)")
                print(f"[TIP] Se esperaban 2 adquirientes (Antonio y Silvia)")
                return 1

        else:
            print(f"\n[ERROR] 'adquirientes' NO es una lista: {type(adquirientes)}")
            return 1

    elif "adquiriente" in data:
        print(f"\n[ERROR] Gemini todavia retorna 'adquiriente' (singular)")
        print(f"[TIP] El prompt debe especificar 'adquirientes' como array")

        adq = data["adquiriente"]
        print(f"\nDatos del adquiriente singular:")
        print(json.dumps(adq, indent=2, ensure_ascii=False))
        return 1

    else:
        print(f"\n[ERROR] No se encontro 'adquirientes' ni 'adquiriente' en respuesta")
        return 1


if __name__ == "__main__":
    sys.exit(test_gemini_adquirientes_array())
