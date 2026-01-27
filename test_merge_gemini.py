#!/usr/bin/env python3
"""
test_merge_gemini.py - Test del merge entre DeepSeek y Gemini

Verifica que los campos rfc, curp, edad de Gemini se mergean correctamente
con los datos de DeepSeek.
"""

import json
import sys
from pathlib import Path

def test_merge():
    """Test del merge DeepSeek + Gemini."""

    print("\n" + "="*80)
    print("TEST: Merge DeepSeek + Gemini (rfc, curp, edad)")
    print("="*80)

    # Simular datos de DeepSeek (sin rfc/curp/edad)
    deepseek_data = {
        "adquirientes": [
            {
                "nombre": "ANTONIO QUINTERO FLORES",
                "tipo": "persona",
                "actua_por": "derecho propio",
                "estado_civil": False,
                "rfc": False,
                "curp": False,
                "edad": False,
                "tipo_sociedad": False,
                "representante": None
            }
        ]
    }

    # Datos de Gemini (CON rfc/curp/edad extraidos)
    gemini_file = Path("test_response_gemini_parsed.json")

    if not gemini_file.exists():
        print(f"\n[ERROR] No se encontro: {gemini_file}")
        return 1

    with open(gemini_file, "r", encoding="utf-8") as f:
        gemini_data = json.load(f)

    print(f"\n[*] Datos de DeepSeek (simulados):")
    print(json.dumps(deepseek_data["adquirientes"][0], indent=2, ensure_ascii=False))

    print(f"\n[*] Datos de Gemini (reales):")
    print(json.dumps(gemini_data.get("adquiriente"), indent=2, ensure_ascii=False))

    # Importar función de merge
    print(f"\n[*] Ejecutando merge...")

    from app.extractor import EscrituraExtractor

    extractor = EscrituraExtractor()

    # Simular el merge
    resultado = extractor._merge_deepseek_gemini(deepseek_data, gemini_data)

    print(f"\n[*] Resultado del merge:")
    print(json.dumps(resultado["adquirientes"][0], indent=2, ensure_ascii=False))

    # Verificar campos
    print(f"\n" + "="*80)
    print("VERIFICACION DE CAMPOS")
    print("="*80)

    adq = resultado["adquirientes"][0]

    campos_a_verificar = {
        "rfc": "QUFA670718TK2",
        "curp": "QUFA670718HJCNLN04",
        "edad": 56,
        "estado_civil": "casado bajo el régimen de sociedad legal"
    }

    errores = 0

    for campo, valor_esperado in campos_a_verificar.items():
        valor_actual = adq.get(campo)

        if valor_actual == valor_esperado:
            print(f"\n{campo:20} [OK]")
            print(f"{'':20} Esperado: {valor_esperado}")
            print(f"{'':20} Actual:   {valor_actual}")
        else:
            print(f"\n{campo:20} [ERROR]")
            print(f"{'':20} Esperado: {valor_esperado}")
            print(f"{'':20} Actual:   {valor_actual}")
            errores += 1

    # Resumen
    print(f"\n" + "="*80)
    print("RESUMEN")
    print("="*80)

    if errores == 0:
        print(f"\n[OK] MERGE EXITOSO: Todos los campos se mergearon correctamente")
        print(f"     - RFC extraido y mergeado")
        print(f"     - CURP extraido y mergeado")
        print(f"     - Edad extraida y mergeada")
        print(f"     - Estado civil extraido y mergeado")
        return 0
    else:
        print(f"\n[ERROR] MERGE FALLIDO: {errores} campos no se mergearon correctamente")
        return 1


if __name__ == "__main__":
    sys.exit(test_merge())
