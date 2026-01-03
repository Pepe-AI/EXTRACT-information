# 📄 Sistema de Extracción de Escrituras Públicas

Sistema para extraer información estructurada de escrituras públicas mexicanas usando OCR (Azure Document Intelligence) e IA (DeepSeek R1).

## ✨ Características

- **OCR Inteligente**: Extrae texto de PDFs escaneados usando Azure Document Intelligence
- **IA Avanzada**: Usa DeepSeek R1 32B para analizar y estructurar la información
- **Retry Inteligente**: Si falla la extracción, reintenta con feedback del error anterior
- **Validación Flexible**: Siempre devuelve resultados, indicando campos encontrados y faltantes
- **Interfaz Web**: Frontend moderno para subir PDFs y ver resultados
- **API REST**: Endpoints documentados con Swagger UI

---

## 📦 Requisitos

### Software

| Software | Versión | Descripción |
|----------|---------|-------------|
| Python | 3.10+ | Lenguaje de programación |
| Ollama | Última | Servidor para modelos de IA |
| DeepSeek R1 | 32B | Modelo de IA para extracción |

### Servicios Externos

| Servicio | Descripción |
|----------|-------------|
| Azure Document Intelligence | OCR para extraer texto de PDFs |

### Hardware Recomendado (servidor con Ollama)

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| GPU | RTX 3090 (24GB) | RTX 4090/5090 (24-32GB) |
| RAM | 32GB | 64GB |
| Almacenamiento | 50GB SSD | 100GB NVMe |

---

## 🚀 Instalación

### Windows (PowerShell)

```powershell
# 1. Navegar al directorio del proyecto
cd "C:\ruta\al\proyecto"

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar entorno virtual
.\venv\Scripts\Activate

# 4. (Si hay error de permisos, ejecutar primero):
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 5. Actualizar pip
pip install --upgrade pip

# 6. Instalar dependencias
pip install -r requirements.txt

# 7. Crear archivo de configuración
Copy-Item .env.example .env

# 8. Editar .env con tus credenciales (usar Notepad, VS Code, etc.)
notepad .env
```

### Linux / Mac

```bash
# 1. Navegar al directorio del proyecto
cd /ruta/al/proyecto

# 2. Crear entorno virtual
python3 -m venv venv

# 3. Activar entorno virtual
source venv/bin/activate

# 4. Actualizar pip
pip install --upgrade pip

# 5. Instalar dependencias
pip install -r requirements.txt

# 6. Crear archivo de configuración
cp .env.example .env

# 7. Editar .env con tus credenciales
nano .env
```

---

## ⚙️ Configuración

### Archivo `.env`

Edita el archivo `.env` con tus credenciales:

```bash
# ============================================
# AZURE DOCUMENT INTELLIGENCE (OCR)
# ============================================
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://TU-RECURSO.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_KEY=tu_clave_aqui

# ============================================
# OLLAMA (DeepSeek R1)
# ============================================
# Si Ollama está en la misma máquina:
OLLAMA_HOST=http://localhost:11434

# Si Ollama está en un servidor remoto:
# OLLAMA_HOST=http://192.168.200.11:11434

# Modelo a usar
OLLAMA_MODEL=deepseek-r1:32b

# ============================================
# CONFIGURACIÓN DE EXTRACCIÓN
# ============================================
MAX_CONTEXT_TOKENS=8000
TEMPERATURE=0.1
MAX_RETRIES=3
```

### Configurar Ollama

```bash
# Instalar Ollama (Linux/Mac)
curl -fsSL https://ollama.com/install.sh | sh

# Descargar modelo DeepSeek R1
ollama pull deepseek-r1:32b

# Iniciar servidor (escuchando en todas las interfaces)
OLLAMA_HOST=0.0.0.0:11434 ollama serve
```

---

## ▶️ Ejecución

### Windows (PowerShell)

```powershell
# Activar entorno virtual
.\venv\Scripts\Activate

# Iniciar servidor (con auto-reload para desarrollo)
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

### Linux / Mac

```bash
# Activar entorno virtual
source venv/bin/activate

# Iniciar servidor (con auto-reload para desarrollo)
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

### Acceder a la aplicación

| URL | Descripción |
|-----|-------------|
| http://localhost:8000 | Interfaz web (subir PDFs) |
| http://localhost:8000/docs | Documentación API (Swagger) |
| http://localhost:8000/health | Estado de los servicios |

---

## 🔄 Flujo de Extracción

```
PDF → OCR (Azure) → Limpiar texto → DeepSeek R1 → Validación → Resultado JSON
```

### Sistema de Retry Inteligente

El sistema intenta extraer con validación estricta. Si falla:

1. **Intento 1**: Prompt normal
2. **Intento 2**: Prompt + feedback del error + JSON anterior
3. **Intento 3**: Prompt + feedback del error + JSON anterior
4. **Si todo falla**: Validación flexible (acepta datos parciales)

### Validación Flexible

Cuando la validación estricta falla, el sistema:
- ✅ Acepta los datos que SÍ se encontraron
- ❌ Marca los campos faltantes como "NO SE ENCONTRÓ DATO"
- 📊 Genera un reporte con porcentaje de éxito

**Ejemplo de respuesta:**
```json
{
  "success": true,
  "validacion_estricta": false,
  "campos_encontrados": 6,
  "campos_no_encontrados": ["valor_catastral", "edad"],
  "data": {
    "notario": "Lic. Roberto García",
    "numero_escritura": 3125,
    "titulares": [...]
  },
  "intentos_realizados": 3,
  "processing_time_seconds": 45.2
}
```

---

## 📁 Estructura del Proyecto

```
extract_info_project/
├── app/
│   ├── __init__.py
│   ├── api.py              # Endpoints FastAPI + Frontend
│   └── extractor.py        # Lógica de extracción con retry
├── models/
│   ├── __init__.py
│   └── escritura.py        # Modelos Pydantic (estricto + flexible)
├── services/
│   ├── __init__.py
│   ├── azure_ocr_service.py    # Servicio OCR Azure
│   └── ollama_service.py       # Servicio Ollama/DeepSeek
├── utils/
│   ├── __init__.py
│   ├── prompt_builder.py   # Constructor de prompts
│   └── text_processing.py  # Limpieza de texto OCR
├── tests/
│   ├── test_01_escritura.py
│   ├── test_02_text_processing.py
│   └── ...
├── templates/
│   └── index.html          # Interfaz web
├── static/
│   ├── css/
│   └── js/
├── .env.example            # Ejemplo de configuración
├── requirements.txt        # Dependencias Python
└── README.md               # Este archivo
```

---

## 🔌 API Endpoints

### POST `/extract`

Extrae información de un PDF.

**Ejemplo con curl:**
```bash
curl -X POST "http://localhost:8000/extract" \
  -F "file=@escritura.pdf"
```

**Ejemplo con Python:**
```python
import requests

with open('escritura.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/extract',
        files={'file': f}
    )
print(response.json())
```

### GET `/health`

Verifica el estado de los servicios.

```bash
curl http://localhost:8000/health
```

**Respuesta:**
```json
{
  "status": "healthy",
  "services": {
    "ollama": true,
    "azure_ocr": true
  }
}
```

### GET `/schema`

Obtiene el esquema de campos esperados.

```bash
curl http://localhost:8000/schema
```

---

## 🧪 Tests

### Ejecutar todos los tests

```bash
python -m tests.run_all
```

### Ejecutar tests individuales

```bash
# Modelos Pydantic (no requiere servicios externos)
python -m tests.test_01_escritura

# Procesamiento de texto
python -m tests.test_02_text_processing

# Constructor de prompts
python -m tests.test_03_prompt_builder

# Servicio Ollama (requiere servidor Ollama)
python -m tests.test_04_ollama_service

# Servicio Azure OCR (requiere credenciales)
python -m tests.test_05_azure_ocr_service
```

---

## 📊 Estructura de Datos de Salida

### Campos Extraídos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `notario` | string | Nombre completo del notario |
| `numero_escritura` | integer | Número de la escritura |
| `fecha_documento` | string | Fecha del documento |
| `tipo_titular` | string | "empresa" o "persona" |
| `titulares` | array | Lista de titulares/vendedores |
| `adquirientes` | array | Lista de compradores |
| `monto_operacion` | string | Monto de la operación |
| `tipo_moneda` | string | Tipo de moneda (MXN, USD) |
| `valor_catastral` | string | Valor catastral (opcional) |

### Ejemplo JSON Completo

```json
{
  "notario": "Lic. Roberto García Mendoza",
  "numero_escritura": 3125,
  "fecha_documento": "15 de mayo de 2024",
  "tipo_titular": "empresa",
  "titulares": [
    {
      "nombre": "Inmobiliaria del Norte S.A. de C.V.",
      "actua_por": "derecho propio",
      "representante": {
        "nombre": "Juan Carlos Pérez López",
        "en_calidad": "apoderado legal",
        "escritura": "1234",
        "bis": false,
        "fecha_poder": "10 de enero de 2020"
      }
    }
  ],
  "adquirientes": [
    {
      "nombre": "Carlos Rodríguez Martínez",
      "estado_civil": "casado",
      "tipo_sociedad": "sociedad conyugal",
      "edad": 45,
      "rfc": "ROMC790515ABC",
      "curp": "ROMC790515HDFRRL09"
    }
  ],
  "monto_operacion": "$1,500,000.00",
  "tipo_moneda": "MXN",
  "valor_catastral": "$800,000.00"
}
```

---

## ❓ Solución de Problemas

### Error: "No se puede conectar a Ollama"

```bash
# Verificar que Ollama está corriendo
curl http://localhost:11434/api/tags

# Si está en servidor remoto
curl http://IP_SERVIDOR:11434/api/tags
```

### Error: "Azure credentials invalid"

1. Verificar que el endpoint termina en `/`
2. Verificar que la key es correcta
3. Verificar que el recurso está activo en Azure Portal

### Error: "begin_analyze_document() missing argument 'body'"

Actualizar el archivo `services/azure_ocr_service.py`:
- Cambiar `analyze_request=` por `body=`

### Error: Puerto en uso (Windows)

```powershell
# Encontrar proceso usando el puerto
netstat -ano | findstr :8000

# Matar el proceso (reemplazar PID)
taskkill /PID 12345 /F

# O usar otro puerto
uvicorn app.api:app --host 0.0.0.0 --port 8001 --reload
```

### Error: "Execution Policy" en Windows

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Error: GPU sin memoria

```bash
# Verificar uso de GPU
nvidia-smi

# Usar modelo más pequeño en .env
OLLAMA_MODEL=deepseek-r1:14b
```

---

## 📝 Notas de Desarrollo

### Auto-reload durante desarrollo

El flag `--reload` reinicia automáticamente el servidor cuando cambias archivos:

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

### Logs detallados

Los logs muestran el progreso de cada extracción:
- 📄 Archivo recibido
- 🔍 OCR ejecutándose
- 🧹 Texto limpiado
- 🤖 DeepSeek analizando
- ✅/⚠️ Resultado de validación

---

## 📄 Licencia

Proyecto de uso interno.

---

## 👥 Contacto

Para soporte técnico, contactar al equipo de desarrollo.
