"""
tests/ - Directorio de pruebas

ARCHIVOS DE PRUEBA:
===================
- test_01_escritura.py      → Modelos Pydantic (models/escritura.py)
- test_02_text_processing.py → Limpieza de texto (utils/text_processing.py)
- test_03_prompt_builder.py  → Constructor de prompts (utils/prompt_builder.py)
- test_04_ollama_service.py  → Servicio Ollama (services/ollama_service.py)
- test_05_azure_ocr_service.py → Servicio OCR (services/azure_ocr_service.py)
- test_06_extractor.py       → Extractor principal (app/extractor.py)
- test_07_api.py            → API FastAPI (app/api.py)

CÓMO EJECUTAR:
==============
Individual:
    python -m tests.test_01_escritura
    python -m tests.test_02_text_processing
    ...

Todas las pruebas:
    python -m tests.run_all

REQUISITOS:
===========
Las primeras 3 pruebas no requieren servicios externos.
Las pruebas 4-7 pueden requerir:
- Servidor Ollama corriendo
- Credenciales de Azure configuradas
- VPN conectada (si es servidor remoto)
"""
