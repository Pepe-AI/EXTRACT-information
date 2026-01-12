"""
services/ollama_service.py - Servicio para comunicarse con Ollama/DeepSeek

Este módulo maneja la comunicación con el servidor Ollama
que ejecuta el modelo DeepSeek R1 para extracción de datos.
"""

import os
import requests
import json
import time
from typing import Optional, Dict, Any, Generator
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


# =============================================================================
# CONSTANTES PARA REPRODUCIBILIDAD
# =============================================================================

DEFAULT_SEED = 42
EXTRACTION_TEMPERATURE = 0.0


@dataclass
class OllamaConfig:
    """
    Configuración para conectar con Ollama.
    
    Lee valores de variables de entorno o usa defaults.
    """
    host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("OLLAMA_PORT", "11434")))
    model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "deepseek-r1:32b"))
    timeout: int = field(default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT", "300")))
    default_seed: int = field(default_factory=lambda: int(os.getenv("OLLAMA_SEED", str(DEFAULT_SEED))))
    deterministic: bool = True
    
    @property
    def base_url(self) -> str:
        """Construye la URL base de Ollama."""
        # Si el host ya incluye http://, usarlo directamente
        if self.host.startswith("http://") or self.host.startswith("https://"):
            return self.host.rstrip("/")
        return f"http://{self.host}:{self.port}"
    
    @property
    def generate_url(self) -> str:
        """URL del endpoint de generación."""
        return f"{self.base_url}/api/generate"


class OllamaService:
    """
    Servicio para interactuar con Ollama.
    
    Métodos principales:
    - generate(): Genera texto con el modelo
    - health_check(): Verifica si el servidor está disponible
    - list_models(): Lista modelos disponibles
    """
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        """Inicializa el servicio."""
        self.config = config or OllamaConfig()
        self._session = requests.Session()
    
    def health_check(self) -> bool:
        """
        Verifica si Ollama está disponible.
        
        Returns:
            True si el servidor responde, False en caso contrario.
        """
        try:
            response = self._session.get(
                f"{self.config.base_url}/api/tags",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]
                model_base = self.config.model.split(':')[0]
                return any(model_base in m for m in models)
            return False
            
        except requests.exceptions.RequestException as e:
            print(f"Error en health check: {e}")
            return False
    
    def list_models(self) -> list:
        """Lista los modelos disponibles en Ollama."""
        try:
            response = self._session.get(
                f"{self.config.base_url}/api/tags",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return [m['name'] for m in data.get('models', [])]
            return []
            
        except requests.exceptions.RequestException:
            return []
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = 4096,
        seed: int = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera texto usando el modelo de Ollama.
        
        Args:
            prompt: El texto/pregunta para el modelo
            system: Instrucciones del sistema (opcional)
            temperature: Control de aleatoriedad (0.0 = determinístico)
            max_tokens: Máximo de tokens a generar
            seed: Semilla para reproducibilidad
            
        Returns:
            Dict con la respuesta de Ollama
        """
        
        # Usar valores determinísticos por defecto
        if self.config.deterministic:
            temperature = temperature if temperature is not None else EXTRACTION_TEMPERATURE
            seed = seed if seed is not None else self.config.default_seed
        else:
            temperature = temperature if temperature is not None else 0.1
        
        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "top_k": 1,
            "top_p": 1.0,
            **kwargs
        }
        
        if seed is not None:
            options["seed"] = seed
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
            "options": options
        }
        
        if system:
            payload["system"] = system
        
        try:
            start_time = time.time()
            
            response = self._session.post(
                self.config.generate_url,
                json=payload,
                timeout=self.config.timeout
            )
            
            elapsed_time = time.time() - start_time
            response.raise_for_status()
            
            result = response.json()
            result['elapsed_time_seconds'] = elapsed_time
            result['seed_used'] = seed
            result['temperature_used'] = temperature
            
            return result
            
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Timeout después de {self.config.timeout} segundos."
            )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"No se pudo conectar a Ollama en {self.config.base_url}."
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error en la petición a Ollama: {e}")


# === INSTANCIA SINGLETON ===

_service_instance: Optional[OllamaService] = None


def get_ollama_service(config: Optional[OllamaConfig] = None) -> OllamaService:
    """
    Obtiene una instancia del servicio Ollama (patrón Singleton).
    """
    global _service_instance
    
    if _service_instance is None or config is not None:
        _service_instance = OllamaService(config)
    
    return _service_instance


if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DEL SERVICIO OLLAMA")
    print("=" * 60)
    
    service = get_ollama_service()
    
    print(f"\n📡 URL: {service.config.base_url}")
    print(f"🤖 Modelo: {service.config.model}")
    
    if service.health_check():
        print("\n✅ Ollama está disponible")
    else:
        print("\n❌ No se pudo conectar a Ollama")
