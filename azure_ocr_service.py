"""
services/azure_ocr_service.py - Servicio de OCR con Azure Document Intelligence

Este módulo maneja la extracción de texto de documentos PDF
usando Azure Document Intelligence.
"""

import os
import base64
import logging
from typing import Optional, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# EXCEPCIONES PERSONALIZADAS
# =============================================================================

class OCRServiceError(Exception):
    """Clase base para errores del servicio OCR."""
    pass


class OCRConfigurationError(OCRServiceError):
    """Error: Credenciales de Azure no configuradas."""
    pass


class OCRConnectionError(OCRServiceError):
    """Error: No se pudo conectar con Azure."""
    pass


class OCRAuthenticationError(OCRServiceError):
    """Error: Credenciales inválidas."""
    pass


class OCRQuotaExceededError(OCRServiceError):
    """Error: Cuota de Azure excedida."""
    pass


class OCRProcessingError(OCRServiceError):
    """Error: Fallo al procesar el documento."""
    pass


# =============================================================================
# CONFIGURACIÓN DE AZURE
# =============================================================================

@dataclass
class AzureConfig:
    """
    Configuración para Azure Document Intelligence.
    
    Lee credenciales de variables de entorno.
    """
    endpoint: Optional[str] = None
    key: Optional[str] = None
    
    def __post_init__(self):
        if not self.endpoint:
            self.endpoint = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT')
        if not self.key:
            self.key = os.getenv('AZURE_DOCUMENT_INTELLIGENCE_KEY')
    
    @property
    def is_configured(self) -> bool:
        """Verifica si las credenciales están configuradas."""
        return bool(self.endpoint and self.key)


# =============================================================================
# SERVICIO OCR
# =============================================================================

class AzureOCRService:
    """
    Servicio para extraer texto de PDFs usando Azure Document Intelligence.
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
        
        if not self.config.is_configured:
            raise OCRConfigurationError(
                "Azure Document Intelligence no está configurado. "
                "Configure AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT y "
                "AZURE_DOCUMENT_INTELLIGENCE_KEY en .env"
            )
        
        self._init_azure_client()
    
    def _init_azure_client(self):
        """Inicializa el cliente de Azure."""
        try:
            from azure.ai.documentintelligence import DocumentIntelligenceClient
            from azure.core.credentials import AzureKeyCredential
            
            self._azure_client = DocumentIntelligenceClient(
                endpoint=self.config.endpoint,
                credential=AzureKeyCredential(self.config.key)
            )
            
        except ImportError as e:
            raise OCRConfigurationError(
                "SDK de Azure no instalado. "
                "Ejecutar: pip install azure-ai-documentintelligence"
            )
        except Exception as e:
            raise OCRConfigurationError(f"Error inicializando Azure: {e}")
    
    def extract_text(self, pdf_path: str) -> Tuple[str, dict]:
        """
        Extrae el contenido de texto de un PDF.
        
        Args:
            pdf_path: Ruta al archivo PDF
            
        Returns:
            Tupla de (texto, metadata)
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            OCRServiceError: Si hay error procesando
        """
        
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"No se encontró el archivo: {pdf_path}")
        
        try:
            from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
            
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            
            pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
            
            poller = self._azure_client.begin_analyze_document(
                model_id="prebuilt-layout",
                body=AnalyzeDocumentRequest(
                    bytes_source=pdf_base64
                )
            )
            
            result = poller.result()
            
            metadata = {
                'source_file': pdf_path,
                'pages': len(result.pages) if result.pages else 0,
                'method': 'azure'
            }
            
            text_content = result.content if result.content else ""
            
            return text_content, metadata
            
        except Exception as e:
            error_str = str(e).lower()
            
            if 'unauthorized' in error_str or '401' in error_str:
                raise OCRAuthenticationError(
                    "Credenciales de Azure inválidas."
                )
            
            if 'quota' in error_str or '429' in error_str:
                raise OCRQuotaExceededError(
                    "Cuota de Azure excedida."
                )
            
            if 'connection' in error_str or 'timeout' in error_str:
                raise OCRConnectionError(
                    "No se pudo conectar con Azure."
                )
            
            raise OCRProcessingError(f"Error procesando documento: {e}")


# === INSTANCIA SINGLETON ===

_ocr_service_instance: Optional[AzureOCRService] = None


def get_ocr_service(config: Optional[AzureConfig] = None) -> AzureOCRService:
    """
    Obtiene una instancia del servicio OCR (patrón Singleton).
    """
    global _ocr_service_instance
    
    if _ocr_service_instance is None or config is not None:
        _ocr_service_instance = AzureOCRService(config)
    
    return _ocr_service_instance


if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DEL SERVICIO AZURE OCR")
    print("=" * 60)
    
    config = AzureConfig()
    
    if config.is_configured:
        print("✅ Azure está configurado")
    else:
        print("❌ Azure NO está configurado")
        print("   Configure en .env:")
        print("   AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=...")
        print("   AZURE_DOCUMENT_INTELLIGENCE_KEY=...")
