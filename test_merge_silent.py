#!/usr/bin/env python3
"""
test_merge_silent.py - Test silencioso del merge

Verifica el merge sin prints que causen encoding errors.
"""

import json
import sys
import os
from pathlib import Path

# Suprimir prints del extractor
os.environ["PYTHONIOENCODING"] = "utf-8"

def test_merge_silent():
    """Test del merge sin prints problemáticos."""

    # Simular datos de DeepSeek
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

    # Cargar datos de Gemini
    gemini_file = Path("test_response_gemini_parsed.json")
    with open(gemini_file, "r", encoding="utf-8") as f:
        gemini_data = json.load(f)

    # Importar extractor y redirigir stdout a null temporalmente
    import io
    import contextlib

    # Capturar output para evitar encoding errors
    f = io.StringIO()

    with contextlib.redirect_stdout(f):
        from app.extractor import EscrituraExtractor
        extractor = EscrituraExtractor()
        resultado = extractor._merge_deepseek_gemini(deepseek_data, gemini_data)

    # Verificar campos
    adq = resultado["adquirientes"][0]

    # Test 1: RFC
    rfc_ok = adq.get("rfc") == "QUFA670718TK2"

    # Test 2: CURP
    curp_ok = adq.get("curp") == "QUFA670718HJCNLN04"

    # Test 3: Edad
    edad_ok = adq.get("edad") == 56

    # Test 4: Estado civil
    estado_civil_ok = "casado" in str(adq.get("estado_civil", "")).lower()

    # Resultado
    print("="*80)
    print("RESULTADO DEL TEST")
    print("="*80)

    print(f"\nRFC:          {'OK' if rfc_ok else 'FALLO'} - {adq.get('rfc')}")
    print(f"CURP:         {'OK' if curp_ok else 'FALLO'} - {adq.get('curp')}")
    print(f"Edad:         {'OK' if edad_ok else 'FALLO'} - {adq.get('edad')}")
    print(f"Estado civil: {'OK' if estado_civil_ok else 'FALLO'} - {adq.get('estado_civil')}")

    # JSON completo
    print(f"\nJSON completo del adquiriente mergeado:")
    print(json.dumps(adq, indent=2, ensure_ascii=False))

    # Resultado final
    all_ok = rfc_ok and curp_ok and edad_ok and estado_civil_ok

    print("\n" + "="*80)
    if all_ok:
        print("EXITO: Todos los campos se mergearon correctamente")
        print("="*80)
        return 0
    else:
        print("FALLO: Algunos campos no se mergearon")
        print("="*80)
        return 1


if __name__ == "__main__":
    sys.exit(test_merge_silent())
