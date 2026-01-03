#!/usr/bin/env python3
"""
tests/run_all.py - Ejecuta todas las pruebas en orden

CÓMO EJECUTAR:
==============
Desde la raíz del proyecto (con el entorno virtual activado):

    cd extract_info_project
    source venv/bin/activate
    python -m tests.run_all

O directamente:
    python tests/run_all.py

OPCIONES:
=========
Las pruebas están ordenadas de menor a mayor dependencia:
1-3: No requieren servicios externos (siempre pasan)
4-7: Requieren Ollama y/o Azure (pueden fallar si no están configurados)
"""

import sys
import subprocess
from pathlib import Path

# Lista de pruebas en orden
TESTS = [
    ("test_01_escritura", "Modelos Pydantic", False),
    ("test_02_text_processing", "Procesamiento de texto", False),
    ("test_03_prompt_builder", "Constructor de prompts", False),
    ("test_04_ollama_service", "Servicio Ollama", True),
    ("test_05_azure_ocr_service", "Servicio Azure OCR", True),
    ("test_06_extractor", "Extractor principal", True),
    ("test_07_api", "API FastAPI", True),
]


def run_test(test_name: str) -> bool:
    """
    Ejecuta una prueba individual.
    
    Args:
        test_name: Nombre del módulo de prueba (sin .py)
        
    Returns:
        True si la prueba pasó, False si falló
    """
    result = subprocess.run(
        [sys.executable, "-m", f"tests.{test_name}"],
        cwd=Path(__file__).parent.parent
    )
    return result.returncode == 0


def main():
    """Ejecuta todas las pruebas."""
    print("\n" + "="*70)
    print("║" + " "*20 + "EJECUTANDO TODAS LAS PRUEBAS" + " "*20 + "║")
    print("="*70)
    
    results = []
    
    for test_name, description, requires_services in TESTS:
        print(f"\n{'─'*70}")
        print(f"▶ Ejecutando: {description}")
        print(f"  Módulo: tests.{test_name}")
        if requires_services:
            print(f"  ⚠️  Requiere servicios externos (Ollama/Azure)")
        print(f"{'─'*70}")
        
        success = run_test(test_name)
        results.append((test_name, description, success))
    
    # Resumen final
    print("\n" + "="*70)
    print("║" + " "*25 + "RESUMEN DE PRUEBAS" + " "*25 + "║")
    print("="*70)
    
    passed = 0
    failed = 0
    
    for test_name, description, success in results:
        status = "✅ PASÓ" if success else "❌ FALLÓ"
        print(f"  {status}  {description} ({test_name})")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("─"*70)
    print(f"  Total: {passed} pasaron, {failed} fallaron de {len(results)}")
    print("="*70 + "\n")
    
    # Retornar código de error si hubo fallos
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
