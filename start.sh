#!/bin/bash
# ============================================
# start.sh - Inicia el servidor
# ============================================
#
# USO:
#   chmod +x start.sh
#   ./start.sh
#
# ============================================

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  INICIANDO SERVIDOR${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Verificar entorno virtual
if [ ! -d "venv" ]; then
    echo -e "${RED}✗ Entorno virtual no encontrado${NC}"
    echo "  Ejecuta primero: ./install.sh"
    exit 1
fi

# Activar entorno virtual
echo -e "${YELLOW}Activando entorno virtual...${NC}"
source venv/bin/activate
echo -e "${GREEN}✓ Entorno virtual activado${NC}"

# Verificar .env
if [ ! -f ".env" ]; then
    echo -e "${RED}✗ Archivo .env no encontrado${NC}"
    echo "  Copia .env.example a .env y configura tus credenciales"
    exit 1
fi
echo -e "${GREEN}✓ Archivo .env encontrado${NC}"

# Cargar variables de .env
export $(grep -v '^#' .env | xargs)

# Verificar conexión a Ollama (opcional)
echo -e "${YELLOW}Verificando conexión a Ollama...${NC}"
OLLAMA_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${OLLAMA_HOST}/api/tags" 2>/dev/null || echo "000")

if [ "$OLLAMA_RESPONSE" == "200" ]; then
    echo -e "${GREEN}✓ Ollama disponible en ${OLLAMA_HOST}${NC}"
else
    echo -e "${YELLOW}⚠ No se pudo conectar a Ollama (${OLLAMA_HOST})${NC}"
    echo -e "  El servidor iniciará, pero la extracción no funcionará"
    echo -e "  Verifica que Ollama esté corriendo"
fi

# Obtener puerto
PORT=${PORT:-8000}
HOST=${HOST:-0.0.0.0}

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Servidor iniciando en:${NC}"
echo -e "${GREEN}  http://localhost:${PORT}${NC}"
echo -e "${GREEN}  http://$(hostname -I | awk '{print $1}'):${PORT}${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "Presiona ${YELLOW}Ctrl+C${NC} para detener"
echo ""

# Iniciar servidor
uvicorn app.api:app --host $HOST --port $PORT --reload
