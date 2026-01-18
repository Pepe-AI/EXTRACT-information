"""
app/api.py - API REST con FastAPI

EXPLICACIÓN:
============
FastAPI es un framework moderno para crear APIs en Python.

¿Por qué FastAPI?
=================
1. Rápido: Uno de los frameworks más rápidos (comparable a Node.js)
2. Tipado: Usa type hints de Python para validación automática
3. Documentación automática: Genera Swagger UI automáticamente
4. Asíncrono: Soporta async/await para mejor rendimiento
5. Pydantic: Integración nativa con nuestros modelos

ENDPOINTS DISPONIBLES:
======================
- GET  /health  → Verificar estado de servicios
- POST /extract → Subir PDF y extraer información
- GET  /schema  → Obtener esquema JSON esperado

CÓMO CORRER LA API:
==================
    uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload

Luego acceder a:
    - API: http://localhost:8000
    - Docs: http://localhost:8000/docs (Swagger UI)
    - ReDoc: http://localhost:8000/redoc
"""

import os
import time
import tempfile
from pathlib import Path
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ============================================================================
# CARGAR VARIABLES DE ENTORNO
# ============================================================================
# Esto debe hacerse ANTES de importar otros módulos del proyecto
# para que las configuraciones estén disponibles.
# ============================================================================
load_dotenv()

# Importar el extractor y modelos
from app.extractor import EscrituraExtractor, ExtractionConfig
from models.escritura import (
    EscrituraPublica, 
    EscrituraPublicaFlexible,
    ExtractionResponse,
    get_campos_obligatorios,
    get_campos_no_obligatorios
)

# Importar excepciones de OCR para manejar errores específicos
from services.azure_ocr_service import (
    OCRServiceError,
    OCRConfigurationError,
    OCRConnectionError,
    OCRAuthenticationError,
    OCRQuotaExceededError,
    OCRProcessingError
)


# === CONFIGURACIÓN DE LA APLICACIÓN ===

app = FastAPI(
    title="API de Extracción de Escrituras Públicas",
    description="""
    API para extraer información estructurada de escrituras públicas
    usando OCR y LLM (DeepSeek R1).
    
    ## Flujo de Procesamiento
    
    1. **Carga del PDF** - Sube el documento
    2. **OCR** - Extrae texto del PDF
    3. **Limpieza** - Elimina ruido (sellos, watermarks, encabezados)
    4. **Inferencia** - DeepSeek R1 analiza y estructura
    5. **Validación** - Pydantic verifica el resultado
    
    ## Uso
    
    Sube un PDF al endpoint `/extract` y recibe JSON estructurado.
    """,
    version="1.0.0",
    contact={
        "name": "Soporte",
        "email": "soporte@ejemplo.com"
    }
)


# === CORS (Cross-Origin Resource Sharing) ===
# Permite que el frontend (en otro dominio) acceda a la API

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos los headers
)

# === CONFIGURACIÓN DE TEMPLATES Y ARCHIVOS ESTÁTICOS ===
# Esto permite servir el frontend HTML

# Obtener la ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Configurar templates (HTML)
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Configurar archivos estáticos (CSS, JS)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

"""
¿Qué es CORS?
=============
Por seguridad, los navegadores bloquean peticiones a dominios diferentes
al que sirve la página web. CORS permite especificar qué dominios
pueden acceder a tu API.

En desarrollo usamos "*" (todos), pero en producción deberías
especificar solo tu dominio frontend:
    allow_origins=["https://tu-app.com"]
"""


# === INSTANCIA GLOBAL DEL EXTRACTOR ===
# Se inicializa al arrancar la aplicación

extractor: Optional[EscrituraExtractor] = None


@app.on_event("startup")
async def startup_event():
    """
    Se ejecuta cuando la aplicación inicia.
    
    ¿Por qué inicializar aquí?
    ==========================
    Inicializar el extractor una sola vez al inicio es más eficiente
    que crearlo en cada petición. Reutilizamos conexiones y recursos.
    
    MANEJO DE ERRORES:
    ==================
    Si Azure OCR no está configurado, el extractor lanzará 
    OCRConfigurationError y la API no podrá iniciar correctamente.
    """
    global extractor
    print("🚀 Iniciando API de Extracción...")
    
    try:
        # Crear configuración desde variables de entorno (si existen)
        config = ExtractionConfig(
            max_retries=int(os.getenv('MAX_RETRIES', 3)),
            temperature=float(os.getenv('TEMPERATURE', 0.1))
        )
        
        extractor = EscrituraExtractor(config=config)
        print("✅ Extractor inicializado")
        
    except OCRConfigurationError as e:
        print(f"❌ Error de configuración de Azure OCR: {e}")
        print("   Verifique las variables de entorno:")
        print("   - AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        print("   - AZURE_DOCUMENT_INTELLIGENCE_KEY")
        # extractor queda como None, los endpoints devolverán error 503


@app.on_event("shutdown")
async def shutdown_event():
    """Se ejecuta cuando la aplicación se detiene."""
    print("👋 Cerrando API de Extracción...")


# === MODELOS DE ENTRADA/SALIDA PARA LA API ===

class HealthResponse(BaseModel):
    """Respuesta del endpoint de salud."""
    status: str
    services: dict
    timestamp: str


class ExtractionAPIResponse(BaseModel):
    """
    Respuesta estándar de la API de extracción.
    
    Incluye tanto los datos extraídos como metadatos del proceso.
    
    NUEVOS CAMPOS (v4):
    - validacion_estricta: Si pasó validación estricta (100% campos)
    - campos_encontrados: Número de campos extraídos
    - campos_no_encontrados: Lista de campos que no se encontraron
    - reporte: Reporte detallado de la extracción
    """
    success: bool
    validacion_estricta: bool = False  # Nuevo
    data: Optional[dict] = None
    campos_encontrados: int = 0  # Nuevo
    campos_no_encontrados: list = []  # Nuevo
    reporte: Optional[dict] = None  # Nuevo
    error: Optional[str] = None
    processing_time_seconds: float
    model_used: str
    intentos_realizados: int = 0  # Nuevo
    thinking: Optional[str] = None  # Para debug
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "validacion_estricta": False,
                "data": {
                    "notario": "Lic. Roberto García",
                    "numero_escritura": 3125,
                    "titulares": [{"nombre": "..."}]
                },
                "campos_encontrados": 6,
                "campos_no_encontrados": ["valor_catastral", "edad"],
                "processing_time_seconds": 45.2,
                "model_used": "deepseek-r1:32b",
                "intentos_realizados": 2
            }
        }


# === ENDPOINTS ===

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def root(request: Request):
    """
    Sirve la página principal (frontend).
    
    Esta página permite subir PDFs y ver los resultados de extracción.
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/info", tags=["General"])
async def api_info():
    """
    Información básica de la API.
    
    Útil para verificar que la API está corriendo.
    """
    return {
        "name": "API de Extracción de Escrituras Públicas",
        "version": "2.0.0",
        "docs_url": "/docs",
        "health_url": "/health",
        "features": [
            "Retry inteligente con feedback",
            "Validación flexible",
            "Reporte de campos encontrados/faltantes"
        ]
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """
    Verifica el estado de todos los servicios.
    
    RESPONSE:
    =========
    - status: "healthy" si todo está bien, "degraded" si hay problemas
    - services: Estado individual de cada servicio
    - timestamp: Hora de la verificación
    
    EJEMPLO DE USO:
    ===============
    ```bash
    curl http://localhost:8000/health
    ```
    """
    if extractor is None:
        raise HTTPException(status_code=503, detail="Extractor no inicializado")
    
    services = extractor.health_check()
    
    # Determinar estado general
    all_healthy = all(services.values())
    status = "healthy" if all_healthy else "degraded"
    
    return HealthResponse(
        status=status,
        services=services,
        timestamp=datetime.now().isoformat()
    )


@app.get("/schema", tags=["Información"])
async def get_schema():
    """
    Obtiene el esquema JSON que la API espera generar.
    
    Útil para entender la estructura de datos que se extrae.
    
    EJEMPLO DE USO:
    ===============
    ```bash
    curl http://localhost:8000/schema
    ```
    """
    return {
        "campos_obligatorios": get_campos_obligatorios(),
        "campos_opcionales": get_campos_no_obligatorios(),
        "estructura": {
            "notario": "string - Nombre del notario",
            "numero_escritura": "integer - Número de la escritura",
            "fecha_documento": "string - Fecha del documento",
            "tipo_titular": "string - 'empresa' o 'persona'",
            "titulares": [
                {
                    "nombre": "string - Nombre del titular",
                    "actua_por": "string - En qué calidad actúa",
                    "representante": {
                        "nombre": "string",
                        "en_calidad": "string",
                        "escritura": "string",
                        "bis": "boolean",
                        "fecha_poder": "string"
                    }
                }
            ],
            "adquirientes": [
                {
                    "nombre": "string - Nombre del adquiriente",
                    "estado_civil": "string",
                    "tipo_sociedad": "string | null",
                    "edad": "integer | null",
                    "rfc": "string | boolean",
                    "curp": "string | boolean"
                }
            ],
            "monto_operacion": "string - Monto de la operación",
            "valor_catastral": "string | null - Valor catastral"
        }
    }


@app.post("/extract", response_model=ExtractionAPIResponse, tags=["Extracción"])
async def extract_from_pdf(
    file: UploadFile = File(..., description="Archivo PDF de la escritura pública"),
    include_thinking: bool = False
):
    """
    Extrae información de un PDF de escritura pública.
    
    PROCESO:
    ========
    1. Recibe el archivo PDF
    2. Lo guarda temporalmente
    3. Ejecuta OCR con Azure Document Intelligence
    4. Envía a DeepSeek para extracción
    5. Valida y devuelve el resultado
    
    PARÁMETROS:
    ===========
    - file: Archivo PDF a procesar (multipart/form-data)
    - include_thinking: Si es True, incluye el razonamiento del modelo
    
    EJEMPLO CON CURL:
    =================
    ```bash
    curl -X POST "http://localhost:8000/extract" \\
         -F "file=@escritura.pdf" \\
         -F "include_thinking=false"
    ```
    
    EJEMPLO CON PYTHON:
    ===================
    ```python
    import requests
    
    with open('escritura.pdf', 'rb') as f:
        response = requests.post(
            'http://localhost:8000/extract',
            files={'file': f}
        )
    print(response.json())
    ```
    """
    
    # Verificar que el extractor esté disponible
    if extractor is None:
        raise HTTPException(
            status_code=503, 
            detail="El servicio de extracción no está disponible. "
                   "Verifique la configuración de Azure Document Intelligence."
        )
    
    # Validar tipo de archivo
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos PDF"
        )
    
    # Guardar archivo temporalmente
    temp_path = None
    try:
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Procesar el PDF
        result = extractor.extract(temp_path)
        
        # Construir respuesta con nuevos campos
        response_data = ExtractionAPIResponse(
            success=result.success,
            validacion_estricta=result.validacion_estricta,
            data=result.data,  # Ya es un dict, no necesita .model_dump()
            campos_encontrados=result.campos_encontrados,
            campos_no_encontrados=result.campos_no_encontrados,
            reporte=result.reporte,
            error=result.error,
            processing_time_seconds=result.processing_time,
            model_used=result.model_used,
            intentos_realizados=result.intentos_realizados,
            thinking=result.thinking if include_thinking else None
        )
        
        return response_data
    
    # =========================================================================
    # MANEJO DE ERRORES DE OCR
    # =========================================================================
    # Cada tipo de error tiene un mensaje específico para el usuario.
    # Los detalles técnicos se registran en los logs del servidor.
    # =========================================================================
    
    except OCRAuthenticationError:
        raise HTTPException(
            status_code=503,
            detail="Error de autenticación con el servicio OCR. "
                   "Por favor, contacte al administrador."
        )
    
    except OCRQuotaExceededError:
        raise HTTPException(
            status_code=503,
            detail="El servicio OCR ha excedido su límite de uso. "
                   "Por favor, intente más tarde."
        )
    
    except OCRConnectionError:
        raise HTTPException(
            status_code=503,
            detail="No se pudo conectar con el servicio OCR. "
                   "Por favor, intente más tarde."
        )
    
    except OCRProcessingError as e:
        raise HTTPException(
            status_code=422,
            detail=f"Error procesando el documento: {str(e)}"
        )
    
    except OCRServiceError as e:
        # Cualquier otro error de OCR no manejado específicamente
        raise HTTPException(
            status_code=503,
            detail="El servicio OCR no está disponible. "
                   "Por favor, intente más tarde."
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # Limpiar archivo temporal
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


# === MANEJO DE ERRORES ===

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """
    Manejador personalizado para excepciones HTTP.
    
    Asegura que todas las respuestas de error tengan un formato consistente.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Manejador para excepciones no esperadas.
    
    En producción, aquí se registraría el error en logs.
    """
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": f"Error interno del servidor: {str(exc)}",
            "status_code": 500
        }
    )


# === CÓDIGO DE PRUEBA LOCAL ===

if __name__ == "__main__":
    """
    Ejecutar directamente para desarrollo.
    
    En producción, usar:
        uvicorn app.api:app --host 0.0.0.0 --port 8000
    """
    import uvicorn
    
    print("=" * 60)
    print("INICIANDO API EN MODO DESARROLLO")
    print("=" * 60)
    print("\n📍 La API estará disponible en:")
    print("   - http://localhost:8000")
    print("   - http://localhost:8000/docs (Swagger UI)")
    print("\n🔧 Para detener: Ctrl+C\n")
    
    uvicorn.run(
        "app.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Auto-recarga al cambiar código
    )
