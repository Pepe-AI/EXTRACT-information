#!/bin/bash
# ============================================
# install.sh - Script de instalación
# ============================================
# 
# USO:
#   chmod +x install.sh
#   ./install.sh
#
# ============================================

set -e  # Salir si hay error

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Sin color

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  INSTALACIÓN DEL PROYECTO${NC}"
echo -e "${BLUE}  Sistema de Extracción de Escrituras${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Verificar Python
echo -e "${YELLOW}[1/5] Verificando Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo -e "${GREEN}✓ $PYTHON_VERSION encontrado${NC}"
else
    echo -e "${RED}✗ Python 3 no encontrado${NC}"
    echo "  Instala Python 3.10 o superior"
    exit 1
fi

# Crear entorno virtual
echo ""
echo -e "${YELLOW}[2/5] Creando entorno virtual...${NC}"
if [ -d "venv" ]; then
    echo -e "${GREEN}✓ Entorno virtual ya existe${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}✓ Entorno virtual creado${NC}"
fi

# Activar entorno virtual
echo ""
echo -e "${YELLOW}[3/5] Activando entorno virtual...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Entorno virtual activado${NC}"

# Instalar dependencias
echo ""
echo -e "${YELLOW}[4/5] Instalando dependencias...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "${GREEN}✓ Dependencias instaladas${NC}"

# Crear archivo .env si no existe
echo ""
echo -e "${YELLOW}[5/5] Configurando archivo .env...${NC}"
if [ -f ".env" ]; then
    echo -e "${GREEN}✓ Archivo .env ya existe${NC}"
else
    cp .env.example .env
    echo -e "${GREEN}✓ Archivo .env creado desde .env.example${NC}"
    echo -e "${YELLOW}  ⚠ IMPORTANTE: Edita .env con tus credenciales${NC}"
fi

# Ejecutar tests básicos
echo ""
echo -e "${YELLOW}Ejecutando tests de verificación...${NC}"
echo ""

# Test de modelos
python -m tests.test_01_escritura > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test de modelos: PASÓ${NC}"
else
    echo -e "${RED}✗ Test de modelos: FALLÓ${NC}"
fi

# Test de prompt builder
python -m tests.test_03_prompt_builder > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Test de prompts: PASÓ${NC}"
else
    echo -e "${RED}✗ Test de prompts: FALLÓ${NC}"
fi

# Resumen final
echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}  ✓ INSTALACIÓN COMPLETADA${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "Próximos pasos:"
echo ""
echo -e "  1. ${YELLOW}Editar .env con tus credenciales:${NC}"
echo -e "     nano .env"
echo ""
echo -e "  2. ${YELLOW}Iniciar el servidor:${NC}"
echo -e "     ./start.sh"
echo ""
echo -e "  3. ${YELLOW}Abrir en el navegador:${NC}"
echo -e "     http://localhost:8000"
echo ""
