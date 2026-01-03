"""
services/azure_ocr_service.py - Servicio de OCR con Azure Document Intelligence

EXPLICACIÓN:
============
Este módulo maneja la extracción de texto de documentos PDF usando
Azure Document Intelligence.

¿Por qué Azure Document Intelligence?
=====================================
1. OCR de alta calidad para documentos escaneados
2. Detecta automáticamente el layout del documento
3. Soporte para documentos en español
4. Alta precisión en documentos notariales

CONFIGURACIÓN:
==============
Las variables se leen del archivo .env:
    - AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: URL del servicio Azure
    - AZURE_DOCUMENT_INTELLIGENCE_KEY: Clave de acceso

MANEJO DE ERRORES:
==================
Este módulo define excepciones específicas para cada tipo de error:
    - OCRConfigurationError: Credenciales no configuradas
    - OCRConnectionError: Error de conexión con Azure
    - OCRQuotaExceededError: Cuota de Azure excedida
    - OCRAuthenticationError: Credenciales inválidas
    - OCRProcessingError: Error procesando el documento

Estas excepciones son capturadas en api.py para enviar mensajes
apropiados al usuario.
"""

import os
import base64
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
load_dotenv()

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================
# logging es el módulo estándar de Python para registrar eventos.
# 
# Niveles de log (de menor a mayor severidad):
#   - DEBUG: Información detallada para debugging
#   - INFO: Confirmación de que las cosas funcionan
#   - WARNING: Algo inesperado, pero el programa sigue funcionando
#   - ERROR: Error serio, el programa no pudo hacer algo
#   - CRITICAL: Error muy serio, el programa puede no continuar
#
# Los logs se muestran en consola y pueden redirigirse a archivo.
# ============================================================================

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Crear handler para consola si no existe
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Formato del log: timestamp - nivel - mensaje
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================
# Definir excepciones específicas permite:
# 1. Identificar exactamente qué tipo de error ocurrió
# 2. Manejar cada error de forma diferente en api.py
# 3. Dar mensajes más útiles al usuario
#
# Todas heredan de OCRServiceError para poder capturarlas como grupo.
# ============================================================================

class OCRServiceError(Exception):
    """
    Clase base para errores del servicio OCR.
    
    Todas las excepciones específicas heredan de esta clase.
    Esto permite capturar cualquier error del servicio con:
    
        except OCRServiceError as e:
            # Manejar cualquier error de OCR
    """
    pass


class OCRConfigurationError(OCRServiceError):
    """
    Error: Credenciales de Azure no configuradas.
    
    Se lanza cuando:
    - AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT no está definido
    - AZURE_DOCUMENT_INTELLIGENCE_KEY no está definido
    - El SDK de Azure no está instalado
    """
    pass


class OCRConnectionError(OCRServiceError):
    """
    Error: No se pudo conectar con Azure.
    
    Se lanza cuando:
    - No hay conexión a internet
    - El endpoint de Azure no responde
    - Timeout en la conexión
    """
    pass


class OCRAuthenticationError(OCRServiceError):
    """
    Error: Credenciales inválidas.
    
    Se lanza cuando:
    - La API key es incorrecta
    - El endpoint no corresponde a la key
    - Las credenciales han expirado
    """
    pass


class OCRQuotaExceededError(OCRServiceError):
    """
    Error: Cuota de Azure excedida.
    
    Se lanza cuando:
    - Se superó el límite de requests por minuto
    - Se superó el límite mensual de procesamiento
    - La suscripción está suspendida por falta de pago
    """
    pass


class OCRProcessingError(OCRServiceError):
    """
    Error: Fallo al procesar el documento.
    
    Se lanza cuando:
    - El PDF está corrupto
    - El formato no es soportado
    - El documento es demasiado grande
    - Error interno de Azure
    """
    pass


# ============================================================================
# CONFIGURACIÓN DE AZURE
# ============================================================================

@dataclass
class AzureConfig:
    """
    Configuración para Azure Document Intelligence.
    
    CÓMO OBTENER LAS CREDENCIALES:
    ==============================
    1. Ve a portal.azure.com
    2. Crea un recurso "Document Intelligence"
    3. En "Keys and Endpoint" encontrarás:
       - KEY1 o KEY2 → AZURE_DOCUMENT_INTELLIGENCE_KEY
       - Endpoint → AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
    
    VARIABLES DE ENTORNO (.env):
    ============================
    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://tu-recurso.cognitiveservices.azure.com/
    AZURE_DOCUMENT_INTELLIGENCE_KEY=tu-clave-aquí
    """
    endpoint: Optional[str] = None
    key: Optional[str] = None
    
    def __post_init__(self):
        """
        Se ejecuta automáticamente después de __init__.
        Carga credenciales de variables de entorno si no se proporcionaron.
        """
        if not self.endpoint:
            self.endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
        if not self.key:
            self.key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    @property
    def is_configured(self) -> bool:
        """Verifica si las credenciales están configuradas."""
        return bool(self.endpoint and self.key)


# ============================================================================
# SERVICIO OCR
# ============================================================================

class AzureOCRService:
    """
    Servicio para extraer texto de PDFs usando Azure Document Intelligence.
    
    EJEMPLO DE USO:
    ===============
    >>> service = AzureOCRService()
    >>> texto, meta = service.extract_text("documento.pdf")
    >>> print(texto)
    
    MANEJO DE ERRORES:
    ==================
    El servicio lanza excepciones específicas que deben ser
    capturadas por el llamador (api.py):
    
    >>> try:
    ...     texto, meta = service.extract_text("documento.pdf")
    ... except OCRConfigurationError:
    ...     print("Azure no está configurado")
    ... except OCRConnectionError:
    ...     print("No se pudo conectar a Azure")
    """
    
    def __init__(self, config: Optional[AzureConfig] = None):
        """
        Inicializa el servicio.
        
        Args:
            config: Configuración de Azure. Si es None, carga de .env
            
        Raises:
            OCRConfigurationError: Si las credenciales no están configuradas
        """
        self.config = config or AzureConfig()
        self._azure_client = None
        
        # Verificar configuración
        if not self.config.is_configured:
            logger.error(
                "Credenciales de Azure no configuradas. "
                "Verificar AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT y "
                "AZURE_DOCUMENT_INTELLIGENCE_KEY en .env"
            )
            raise OCRConfigurationError(
                "Azure Document Intelligence no está configurado. "
                "Configure las variables de entorno en el archivo .env"
            )
        
        # Inicializar cliente
        self._init_azure_client()
    
    def _init_azure_client(self):
        """
        Inicializa el cliente de Azure Document Intelligence.
        
        Raises:
            OCRConfigurationError: Si el SDK no está instalado
        """
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential
            
            self._azure_client = DocumentIntelligenceClient(
                endpoint=self.config.endpoint,
                credential=AzureKeyCredential(self.config.key)
            )
            
            logger.info("Cliente Azure Document Intelligence inicializado correctamente")
            
        except ImportError as e:
            logger.error(f"SDK de Azure no instalado: {e}")
            raise OCRConfigurationError(
                "El SDK de Azure no está instalado. "
                "Ejecutar: pip install azure-ai-documentintelligence"
            )
        except Exception as e:
            logger.error(f"Error inicializando cliente Azure: {e}")
            raise OCRConfigurationError(f"Error inicializando Azure: {e}")
    
    def extract_text(self, pdf_path: str) -> Tuple[str, dict]:
        """
        Extrae el contenido de texto de un PDF usando Azure.
        
        Args:
            pdf_path: Ruta al archivo PDF
            
        Returns:
            Tuple de (texto, metadata)
            - texto: Contenido de texto extraído
            - metadata: Información adicional (páginas, etc.)
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            OCRConnectionError: Si no se puede conectar a Azure
            OCRAuthenticationError: Si las credenciales son inválidas
            OCRQuotaExceededError: Si se excedió la cuota
            OCRProcessingError: Si hay error procesando el documento
        """
        
        # Verificar que el archivo existe
        if not os.path.exists(pdf_path):
            logger.error(f"Archivo no encontrado: {pdf_path}")
            raise FileNotFoundError(f"No se encontró el archivo: {pdf_path}")
        
        logger.info(f"Iniciando extracción OCR de: {pdf_path}")
        
        try:
            # Importar modelos de Azure
            from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
            
            # Leer el PDF como bytes
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            
            logger.debug(f"Archivo leído: {len(pdf_bytes)} bytes")
            
            # Codificar en base64 para enviar a Azure
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            # Analizar el documento
            logger.info("Enviando documento a Azure Document Intelligence...")
            
            poller = self._azure_client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(
                    bytes_source=pdf_base64
                )
            )
            
            # Esperar resultado
            result = poller.result()
            
            # Extraer metadatos
            metadata = {
                'source_file': pdf_path,
                'pages': len(result.pages) if result.pages else 0,
                'method': 'azure'
            }
            
            # Extraer texto
            text_content = result.content if result.content else ""
            
            logger.info(
                f"Extracción exitosa: {metadata['pages']} páginas, "
                f"{len(text_content)} caracteres"
            )
            
            return text_content, metadata
            
        except ImportError as e:
            logger.error(f"Error de importación: {e}")
            raise OCRConfigurationError(f"Módulo de Azure no disponible: {e}")
            
        except Exception as e:
            # Analizar el tipo de error para dar mensaje específico
            error_str = str(e).lower()
            
            # Error de autenticación
            if 'unauthorized' in error_str or '401' in error_str or 'authentication' in error_str:
                logger.error(f"Error de autenticación con Azure: {e}")
                raise OCRAuthenticationError(
                    "Credenciales de Azure inválidas. "
                    "Verifique AZURE_DOCUMENT_INTELLIGENCE_KEY en .env"
                )
            
            # Error de cuota
            if 'quota' in error_str or '429' in error_str or 'rate limit' in error_str:
                logger.error(f"Cuota de Azure excedida: {e}")
                raise OCRQuotaExceededError(
                    "Se ha excedido la cuota de Azure. "
                    "Intente más tarde o verifique su plan de suscripción."
                )
            
            # Error de conexión
            if 'connection' in error_str or 'timeout' in error_str or 'network' in error_str:
                logger.error(f"Error de conexión con Azure: {e}")
                raise OCRConnectionError(
                    "No se pudo conectar con Azure. "
                    "Verifique su conexión a internet y el endpoint configurado."
                )
            
            # Error de endpoint inválido
            if 'not found' in error_str or '404' in error_str:
                logger.error(f"Endpoint de Azure no encontrado: {e}")
                raise OCRConfigurationError(
                    "El endpoint de Azure no es válido. "
                    "Verifique AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT en .env"
                )
            
            # Cualquier otro error
            logger.error(f"Error procesando documento: {e}")
            raise OCRProcessingError(f"Error al procesar el documento: {e}")


# ============================================================================
# INSTANCIA SINGLETON
# ============================================================================

_ocr_service_instance: Optional[AzureOCRService] = None


def get_ocr_service(config: Optional[AzureConfig] = None) -> AzureOCRService:
    """
    Obtiene una instancia del servicio OCR (patrón Singleton).
    
    El patrón Singleton asegura que solo exista una instancia
    del servicio en toda la aplicación, reutilizando la conexión.
    
    Uso:
        service = get_ocr_service()
        texto, meta = service.extract_text("documento.pdf")
        
    Raises:
        OCRConfigurationError: Si Azure no está configurado
    """
    global _ocr_service_instance
    
    if _ocr_service_instance is None or config is not None:
        _ocr_service_instance = AzureOCRService(config)
    
    return _ocr_service_instance


# ============================================================================
# CÓDIGO DE PRUEBA
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DEL SERVICIO OCR")
    print("=" * 60)
    
    try:
        service = get_ocr_service()
        print("✅ Servicio Azure OCR inicializado correctamente")
        print(f"   Endpoint: {service.config.endpoint[:50]}...")
        
    except OCRConfigurationError as e:
        print(f"❌ Error de configuración: {e}")
        print("\nPara configurar Azure, crear archivo .env con:")
        print("  AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://...")
        print("  AZURE_DOCUMENT_INTELLIGENCE_KEY=tu-clave")
