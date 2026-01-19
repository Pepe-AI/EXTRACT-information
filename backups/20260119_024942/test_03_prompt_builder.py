#!/usr/bin/env python3
"""
tests/test_03_prompt_builder.py - Prueba del constructor de prompts
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.prompt_builder import (
    build_extraction_prompt,
    build_validation_prompt,
    estimate_tokens,
    SYSTEM_PROMPT_EXTRACCION
)


def test_system_prompt():
    """Prueba 1: System Prompt existe y tiene contenido."""
    print("\n" + "="*60)
    print("PRUEBA 1: System Prompt")
    print("="*60)
    
    assert len(SYSTEM_PROMPT_EXTRACCION) > 100
    assert "JSON" in SYSTEM_PROMPT_EXTRACCION
    
    print(f"\n✅ System prompt: {len(SYSTEM_PROMPT_EXTRACCION)} chars")


def test_extraction_prompt():
    """Prueba 2: Prompt de extracción."""
    print("\n" + "="*60)
    print("PRUEBA 2: Prompt de extracción")
    print("="*60)
    
    documento = "ESCRITURA 3125\nNotario: Lic. García"
    
    system, user = build_extraction_prompt(documento, include_examples=True)
    
    assert len(system) > 0
    assert len(user) > 0
    assert "PLANTILLA" in user or "plantilla" in user.lower()
    assert documento in user
    
    print(f"\n✅ Prompt generado:")
    print(f"   System: {len(system)} chars")
    print(f"   User: {len(user)} chars")


def test_prompt_sin_ejemplos():
    """Prueba 3: Prompt sin ejemplos."""
    print("\n" + "="*60)
    print("PRUEBA 3: Prompt sin ejemplos")
    print("="*60)
    
    _, con_ejemplos = build_extraction_prompt("Doc", include_examples=True)
    _, sin_ejemplos = build_extraction_prompt("Doc", include_examples=False)
    
    print(f"\n✅ Con ejemplos: {len(con_ejemplos)} chars")
    print(f"   Sin ejemplos: {len(sin_ejemplos)} chars")
    
    assert len(con_ejemplos) > len(sin_ejemplos)


def test_campos_en_prompt():
    """Prueba 4: Campos obligatorios en el prompt."""
    print("\n" + "="*60)
    print("PRUEBA 4: Campos en prompt")
    print("="*60)
    
    _, user = build_extraction_prompt("Doc")
    
    campos = ["notario", "numero_escritura", "titulares", "adquirientes"]
    
    for campo in campos:
        assert campo in user, f"Falta: {campo}"
        print(f"   ✅ {campo}")


def test_validation_prompt():
    """Prueba 5: Prompt de validación."""
    print("\n" + "="*60)
    print("PRUEBA 5: Prompt de validación")
    print("="*60)
    
    json_data = {"notario": "Test"}
    system, user = build_validation_prompt(json_data, "Documento")
    
    assert len(system) > 0
    assert len(user) > 0
    
    print(f"\n✅ Validation prompt generado")


def test_estimate_tokens():
    """Prueba 6: Estimación de tokens."""
    print("\n" + "="*60)
    print("PRUEBA 6: Estimación de tokens")
    print("="*60)
    
    texto = "Hola mundo esto es una prueba"  # ~30 chars
    tokens = estimate_tokens(texto)
    
    print(f"\n✅ '{texto}' → {tokens} tokens")
    
    assert tokens > 0
    assert tokens < len(texto)


def test_tamaño_prompt():
    """Prueba 7: Tamaño del prompt."""
    print("\n" + "="*60)
    print("PRUEBA 7: Tamaño total")
    print("="*60)
    
    documento = "Texto legal. " * 100
    system, user = build_extraction_prompt(documento)
    
    total_tokens = estimate_tokens(system + user)
    
    print(f"\n   Total: ~{total_tokens} tokens")
    
    assert total_tokens < 32000


def main():
    print("\n" + "#"*60)
    print("# PRUEBAS DE PROMPT BUILDER")
    print("#"*60)
    
    try:
        test_system_prompt()
        test_extraction_prompt()
        test_prompt_sin_ejemplos()
        test_campos_en_prompt()
        test_validation_prompt()
        test_estimate_tokens()
        test_tamaño_prompt()
        
        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS PASARON (7/7)")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
