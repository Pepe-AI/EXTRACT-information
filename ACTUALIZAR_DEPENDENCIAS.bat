@echo off
REM Script para actualizar dependencias de Gemini en el directorio principal

echo ========================================
echo   ACTUALIZAR DEPENDENCIAS GEMINI
echo ========================================
echo.

echo [1/3] Desinstalando google-generativeai antigua...
pip uninstall google-generativeai -y

echo.
echo [2/3] Instalando google-genai nueva...
pip install google-genai

echo.
echo [3/3] Verificando instalacion...
python -c "from google import genai; print('✅ google-genai instalado correctamente')"

echo.
echo ========================================
echo   INSTALACION COMPLETA
echo ========================================
echo.
echo Ahora reinicia el servidor con:
echo   uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
echo.
pause
