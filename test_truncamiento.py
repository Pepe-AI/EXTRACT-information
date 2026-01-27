#!/usr/bin/env python3
"""Test para verificar que el truncamiento fue eliminado."""

from utils.gemini_prompts import build_gemini_prompt_expandido

# Crear texto de prueba de 50,000 caracteres
texto_test = 'A' * 50000

# Generar prompt
prompt = build_gemini_prompt_expandido(texto_test)

# Verificar
print(f"Longitud del prompt: {len(prompt):,}")
print(f"Longitud esperada: ~50,000 (si NO trunca)")

if len(prompt) > 40000:
    print(f"Test: PASS - NO trunca")
else:
    print(f"Test: FAIL - TODAVIA TRUNCA")
