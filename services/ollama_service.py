"""
services/ollama_service.py - Servicio para comunicarse con Ollama/DeepSeek

EXPLICACIÓN:
============
Este módulo maneja toda la comunicación con el servidor Ollama donde
está corriendo DeepSeek R1 32B. Usa la API REST de Ollama para enviar
prompts y recibir respuestas.

ARQUITECTURA DE COMUNICACIÓN:
=============================
    
    [Tu Laptop - Desarrollo]
            │
            ▼ HTTP POST via VPN
    [Servidor Ollama - IP configurada en .env]
            │
            ▼ Modelo cargado
    [DeepSeek R1 32B]
            │
            ▼ Genera respuesta con <think>
    [JSON con datos extraídos]

CONFIGURACIÓN:
==============
Las variables se leen del archivo .env:
    - OLLAMA_HOST: IP del servidor con Ollama
    - OLLAMA_PORT: Puerto de Ollama (default 11434)
    - OLLAMA_MODEL: Modelo a usar (default deepseek-r1:32b)
    - OLLAMA_TIMEOUT: Timeout en segundos (default 300)

La API de Ollama expone el endpoint /api/generate para generar texto.
"""

import os
import requests
import json
import time
from typing import Optional, Dict, Any, Generator
from dataclasses import dataclass, field
from dotenv import load_dotenv

# ============================================================================
# CARGAR VARIABLES DE ENTORNO
# ============================================================================
# load_dotenv() busca un archivo .env en el directorio actual y sus padres,
# y carga las variables definidas ahí como variables de entorno.
#
# Esto permite que cada desarrollador tenga su propia configuración
# sin modificar el código fuente.
# ============================================================================
load_dotenv()


@dataclass
class OllamaConfig:
    """
    Configuración para conectar con Ollama.
    
    ¿Qué es @dataclass?
    ===================
    Es un decorador que genera automáticamente __init__, __repr__, etc.
    Es como una clase normal pero más concisa para almacenar datos.
    
    ¿Cómo funciona con variables de entorno?
    =========================================
    Usamos field(default_factory=...) para que el valor por defecto
    se calcule al momento de crear la instancia, no cuando se define la clase.
    
    os.getenv("VARIABLE", "valor_default") busca la variable de entorno,
    si no existe, usa el valor por defecto.
    
    IMPORTANTE:
    ===========
    Crea un archivo .env en la raíz del proyecto con tus valores:
    
        OLLAMA_HOST=192.168.200.11
        OLLAMA_PORT=11434
        OLLAMA_MODEL=deepseek-r1:32b
        OLLAMA_TIMEOUT=300
    """
    # Lee del .env, si no existe usa el valor por defecto
    host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("OLLAMA_PORT", "11434")))
    model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "deepseek-r1:32b"))
    timeout: int = field(default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT", "300")))
    
    @property
    def base_url(self) -> str:
        """
        Construye la URL base de la API de Ollama.
        
        @property permite acceder a este método como si fuera un atributo:
            config.base_url  (en lugar de config.base_url())
        """
        return f"http://{self.host}:{self.port}"
    
    @property
    def generate_url(self) -> str:
        """URL del endpoint de generación."""
        return f"{self.base_url}/api/generate"
    
    @property
    def chat_url(self) -> str:
        """URL del endpoint de chat (alternativo)."""
        return f"{self.base_url}/api/chat"


class OllamaService:
    """
    Servicio para interactuar con Ollama.
    
    MÉTODOS PRINCIPALES:
    ====================
    - generate(): Genera texto con el modelo (método simple)
    - generate_stream(): Genera texto en streaming (para mostrar progreso)
    - extract_json(): Genera y parsea JSON automáticamente
    
    EJEMPLO DE USO:
    ===============
    >>> service = OllamaService()
    >>> response = service.generate("¿Cuál es la capital de México?")
    >>> print(response['response'])
    """
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        """
        Inicializa el servicio con la configuración dada.
        
        Args:
            config: Configuración de Ollama. Si es None, usa valores por defecto.
        """
        self.config = config or OllamaConfig()
        self._session = requests.Session()  # Reutiliza conexiones HTTP
    
    def health_check(self) -> bool:
        """
        Verifica si Ollama está disponible y el modelo está cargado.
        
        ¿Para qué sirve?
        ================
        Antes de procesar documentos, verificamos que el servidor
        esté activo. Esto evita esperar largos timeouts si hay problemas.
        
        Returns:
            True si Ollama responde correctamente, False en caso contrario.
        """
        try:
            # El endpoint /api/tags lista los modelos disponibles
            response = self._session.get(
                f"{self.config.base_url}/api/tags",
                timeout=10  # 10 segundos para health check
            )
            
            if response.status_code == 200:
                data = response.json()
                # Verificar que nuestro modelo esté en la lista
                models = [m['name'] for m in data.get('models', [])]
                model_base = self.config.model.split(':')[0]
                return any(model_base in m for m in models)
            return False
            
        except requests.exceptions.RequestException as e:
            print(f"Error en health check: {e}")
            return False
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera texto usando el modelo de Ollama.
        
        PARÁMETROS EXPLICADOS:
        ======================
        
        prompt (str):
            El texto/pregunta que enviamos al modelo.
            Ejemplo: "Extrae los datos de esta escritura: ..."
        
        system (str, opcional):
            Instrucciones del sistema que definen el comportamiento del modelo.
            Ejemplo: "Eres un experto en análisis de documentos legales..."
        
        temperature (float, default=0.1):
            Controla la "creatividad" del modelo.
            - 0.0 = Respuestas muy determinísticas (siempre iguales)
            - 0.1-0.3 = Respuestas consistentes (recomendado para extracción)
            - 0.7-1.0 = Respuestas más variadas/creativas
            
            Para extracción de datos, usamos 0.1 porque queremos
            respuestas precisas y reproducibles.
        
        max_tokens (int, default=4096):
            Número máximo de tokens en la respuesta.
            Un token ≈ 4 caracteres en español.
            4096 tokens ≈ 16,000 caracteres ≈ 8 páginas de texto.
        
        **kwargs:
            Parámetros adicionales de Ollama (num_ctx, top_p, etc.)
        
        Returns:
            Dict con la respuesta de Ollama incluyendo:
            - response: El texto generado
            - eval_count: Número de tokens generados
            - total_duration: Tiempo total en nanosegundos
        """
        
        # Construir el payload para la API
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,  # Esperar respuesta completa
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                **kwargs  # Parámetros adicionales
            }
        }
        
        # Agregar system prompt si se proporciona
        if system:
            payload["system"] = system
        
        try:
            # Medir tiempo de inicio
            start_time = time.time()
            
            # Hacer la petición POST a Ollama
            response = self._session.post(
                self.config.generate_url,
                json=payload,
                timeout=self.config.timeout
            )
            
            # Calcular tiempo transcurrido
            elapsed_time = time.time() - start_time
            
            # Verificar respuesta exitosa
            response.raise_for_status()
            
            # Parsear respuesta JSON
            result = response.json()
            result['elapsed_time_seconds'] = elapsed_time
            
            return result
            
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Timeout después de {self.config.timeout} segundos. "
                "El documento puede ser muy largo o el servidor está sobrecargado."
            )
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"No se pudo conectar a Ollama en {self.config.base_url}. "
                "Verifica que el servidor esté corriendo."
            )
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Error en la petición a Ollama: {e}")
    
    def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.1,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Genera texto en modo streaming (token por token).
        
        ¿Qué es streaming?
        ==================
        En lugar de esperar a que se genere toda la respuesta,
        recibimos los tokens conforme se van generando. Esto permite:
        
        1. Mostrar progreso al usuario en tiempo real
        2. Cancelar la generación si es necesario
        3. Mejor experiencia de usuario (no parece "colgado")
        
        ¿Qué es un Generator?
        =====================
        Un generator es una función que "produce" valores uno a uno
        en lugar de devolver una lista completa. Usa 'yield' en lugar
        de 'return'.
        
        Ejemplo de uso:
        ===============
        >>> for token in service.generate_stream("Hola"):
        ...     print(token, end='', flush=True)
        
        Yields:
            str: Cada fragmento de texto conforme se genera.
        """
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": True,  # Activar streaming
            "options": {
                "temperature": temperature,
                **kwargs
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            # iter_lines() procesa la respuesta línea por línea
            response = self._session.post(
                self.config.generate_url,
                json=payload,
                stream=True,  # Importante: stream=True en requests
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            # Procesar cada línea del stream
            for line in response.iter_lines():
                if line:
                    # Cada línea es un JSON con el token generado
                    data = json.loads(line)
                    if 'response' in data:
                        yield data['response']
                    
                    # Si 'done' es True, terminó la generación
                    if data.get('done', False):
                        break
                        
        except Exception as e:
            yield f"\n[Error en streaming: {e}]"
    
    def extract_json(
        self,
        prompt: str,
        system: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Genera texto y extrae el JSON de la respuesta.
        
        DeepSeek R1 genera su razonamiento en bloques <think>...</think>
        y luego produce el JSON. Este método:
        
        1. Genera la respuesta completa
        2. Elimina el bloque <think>
        3. Busca y parsea el JSON
        
        Returns:
            Dict con el JSON parseado, o None si no se encontró JSON válido.
        """
        
        result = self.generate(prompt, system, **kwargs)
        response_text = result.get('response', '')
        
        # Importar la función de limpieza (la crearemos después)
        from utils.text_processing import extract_json_from_response
        
        return extract_json_from_response(response_text)


# === INSTANCIA SINGLETON (PATRÓN DE DISEÑO) ===

_service_instance: Optional[OllamaService] = None


def get_ollama_service(config: Optional[OllamaConfig] = None) -> OllamaService:
    """
    Obtiene una instancia del servicio Ollama (patrón Singleton).
    
    ¿Qué es el patrón Singleton?
    ============================
    Asegura que solo exista UNA instancia de una clase en toda la aplicación.
    
    ¿Por qué usarlo aquí?
    - Reutilizar la conexión HTTP (más eficiente)
    - Evitar crear múltiples configuraciones
    - Centralizar la gestión del servicio
    
    Uso:
        service = get_ollama_service()  # Primera vez: crea instancia
        service = get_ollama_service()  # Segunda vez: devuelve la misma
    """
    global _service_instance
    
    if _service_instance is None or config is not None:
        _service_instance = OllamaService(config)
    
    return _service_instance


# === CÓDIGO DE PRUEBA ===

if __name__ == "__main__":
    """
    Código que se ejecuta solo si corres este archivo directamente:
        python services/ollama_service.py
    
    No se ejecuta si importas el módulo desde otro archivo.
    """
    
    print("=" * 60)
    print("PRUEBA DEL SERVICIO OLLAMA")
    print("=" * 60)
    
    # Crear servicio con configuración por defecto
    service = get_ollama_service()
    
    print(f"\n📡 Conectando a: {service.config.base_url}")
    print(f"🤖 Modelo: {service.config.model}")
    
    # Health check
    print("\n🔍 Verificando conexión...")
    if service.health_check():
        print("✅ Ollama está disponible y el modelo está cargado")
        
        # Prueba simple
        print("\n📝 Enviando prompt de prueba...")
        result = service.generate(
            prompt="Di 'Hola, estoy funcionando correctamente' en una línea.",
            temperature=0.1
        )
        print(f"\n🤖 Respuesta: {result['response']}")
        print(f"⏱️  Tiempo: {result['elapsed_time_seconds']:.2f} segundos")
    else:
        print("❌ No se pudo conectar a Ollama")
        print("   Verifica que el servidor esté corriendo en la IP correcta")
