"""
services/ollama_service.py - Servicio para comunicarse con Ollama/DeepSeek

CAMBIOS PARA REDUCIR VARIABILIDAD:
===================================
1. temperature=0.0 (antes era 0.1) → Respuestas 100% determinísticas
2. seed fija (nuevo) → Misma semilla = mismos resultados
3. top_p=1.0, top_k=1 → Siempre elige el token más probable

¿Por qué estos cambios?
=======================
Los LLMs generan texto eligiendo el siguiente token basándose en probabilidades.
- temperature > 0: Introduce aleatoriedad en la selección
- temperature = 0: SIEMPRE elige el token más probable (greedy decoding)
- seed: Controla el generador de números aleatorios

Con temperature=0 y seed fija, el mismo prompt SIEMPRE genera la misma respuesta.
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

# Seed fija para resultados reproducibles
# Usamos un número arbitrario pero consistente
DEFAULT_SEED = 42

# Temperatura para extracción de datos (0 = determinístico)
EXTRACTION_TEMPERATURE = 0.0

# Temperatura para clasificación (también determinística)
CLASSIFICATION_TEMPERATURE = 0.0


@dataclass
class OllamaConfig:
    """
    Configuración para conectar con Ollama.
    
    NUEVOS PARÁMETROS:
    ==================
    - default_seed: Semilla por defecto para reproducibilidad
    - deterministic: Si es True, usa configuración 100% determinística
    """
    host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("OLLAMA_PORT", "11434")))
    model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "deepseek-r1:32b"))
    timeout: int = field(default_factory=lambda: int(os.getenv("OLLAMA_TIMEOUT", "300")))
    default_seed: int = field(default_factory=lambda: int(os.getenv("OLLAMA_SEED", str(DEFAULT_SEED))))
    deterministic: bool = True  # Por defecto, queremos resultados reproducibles
    
    @property
    def base_url(self) -> str:
        """Construye la URL base de la API de Ollama."""
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
    - generate(): Genera texto con el modelo
    - generate_deterministic(): Genera texto de forma 100% reproducible (NUEVO)
    - classify_document(): Clasifica documento como empresa/persona (NUEVO)
    """
    
    def __init__(self, config: Optional[OllamaConfig] = None):
        """Inicializa el servicio con la configuración dada."""
        self.config = config or OllamaConfig()
        self._session = requests.Session()
    
    def health_check(self) -> bool:
        """
        Verifica si Ollama está disponible y el modelo está cargado.
        
        Returns:
            True si Ollama responde correctamente, False en caso contrario.
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
        """
        Lista los modelos disponibles en Ollama.
        
        Returns:
            Lista de nombres de modelos disponibles.
        """
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
        
        PARÁMETROS IMPORTANTES PARA REPRODUCIBILIDAD:
        ==============================================
        
        temperature (float):
            Controla la aleatoriedad en la selección de tokens.
            - 0.0 = Determinístico (siempre elige el token más probable)
            - 0.1-0.3 = Muy poca variación (bueno para extracción)
            - 0.7-1.0 = Mucha variación (bueno para creatividad)
            
            ANTES: default=0.1 (permitía variación)
            AHORA: default=0.0 (100% determinístico)
        
        seed (int):
            Semilla para el generador de números aleatorios.
            Si usas la misma seed + mismo prompt = misma respuesta.
            
            ANTES: No se usaba (cada ejecución era diferente)
            AHORA: default=42 (resultados reproducibles)
        
        top_k (int): NUEVO
            Limita la selección a los K tokens más probables.
            top_k=1 significa: SIEMPRE elegir el más probable.
        
        top_p (float): NUEVO
            Nucleus sampling. top_p=1.0 con temperature=0 = determinístico.
        
        Returns:
            Dict con la respuesta de Ollama incluyendo:
            - response: El texto generado
            - eval_count: Número de tokens generados
            - total_duration: Tiempo total en nanosegundos
        """
        
        # Usar valores determinísticos por defecto si está habilitado
        if self.config.deterministic:
            temperature = temperature if temperature is not None else EXTRACTION_TEMPERATURE
            seed = seed if seed is not None else self.config.default_seed
        else:
            temperature = temperature if temperature is not None else 0.1
        
        # Construir opciones con parámetros para reproducibilidad
        options = {
            "temperature": temperature,
            "num_predict": max_tokens,
            "top_k": 1,      # NUEVO: Solo considerar el token más probable
            "top_p": 1.0,    # NUEVO: No usar nucleus sampling
            **kwargs
        }
        
        # Agregar seed si está definida
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
            result['seed_used'] = seed  # Para debugging
            result['temperature_used'] = temperature  # Para debugging
            
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
    
    def generate_deterministic(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Genera texto de forma 100% determinística.
        
        NUEVO MÉTODO - Wrapper para garantizar reproducibilidad.
        
        Usa:
        - temperature = 0.0
        - seed = DEFAULT_SEED (42)
        - top_k = 1
        - top_p = 1.0
        
        Esto garantiza que el mismo prompt SIEMPRE produzca
        la misma respuesta, eliminando la variabilidad.
        
        Args:
            prompt: El texto/pregunta para el modelo
            system: Instrucciones del sistema (opcional)
            max_tokens: Máximo de tokens a generar
            
        Returns:
            Dict con la respuesta de Ollama
        """
        return self.generate(
            prompt=prompt,
            system=system,
            temperature=0.0,
            max_tokens=max_tokens,
            seed=self.config.default_seed
        )
    
    def classify_document(
        self,
        document_text: str,
        max_tokens: int = 100
    ) -> Dict[str, Any]:
        """
        NUEVO MÉTODO - Clasifica un documento como empresa o persona.
        
        Esta es la FASE 1 del enfoque "divide y vencerás".
        
        ¿Por qué un método separado?
        ============================
        1. Prompt muy simple y específico = alta precisión
        2. Respuesta corta = rápido (~2-5 segundos)
        3. Solo necesita determinar UN dato: empresa o persona
        
        Args:
            document_text: Texto del documento a clasificar
            max_tokens: Máximo de tokens (100 es suficiente)
            
        Returns:
            Dict con:
            - tipo: "empresa" o "persona"
            - confianza: alta/media/baja
            - indicadores: lista de palabras clave encontradas
        """
        
        # Prompt ultra-específico para clasificación
        system_prompt = """Eres un clasificador de documentos legales mexicanos.
Tu ÚNICA tarea es determinar si el VENDEDOR/ENAJENANTE es una EMPRESA o una PERSONA FÍSICA.

REGLAS:
- Si ves "S.A.", "S.A. de C.V.", "S. de R.L.", "SOCIEDAD", "CAPITAL VARIABLE" → es EMPRESA
- Si el vendedor es un nombre de persona sin denominación social → es PERSONA

Responde SOLO con un JSON así:
{"tipo": "empresa", "indicadores": ["S.A. de C.V.", "SOCIEDAD"]}
o
{"tipo": "persona", "indicadores": ["nombre personal"]}"""

        user_prompt = f"""Analiza este fragmento del documento y clasifica al VENDEDOR/ENAJENANTE:

<documento>
{document_text[:3000]}
</documento>

¿El vendedor es EMPRESA o PERSONA FÍSICA? Responde solo con JSON."""

        result = self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.0,  # 100% determinístico
            max_tokens=max_tokens,
            seed=self.config.default_seed
        )
        
        # Parsear resultado
        response_text = result.get('response', '')
        
        try:
            # Intentar extraer JSON de la respuesta
            import re
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                classification = json.loads(json_match.group())
                return {
                    'tipo': classification.get('tipo', 'empresa').lower(),
                    'indicadores': classification.get('indicadores', []),
                    'raw_response': response_text,
                    'success': True
                }
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Fallback: detectar por palabras clave
        texto_upper = document_text.upper()
        indicadores_empresa = ['S.A.', 'S.A. DE C.V.', 'SOCIEDAD', 'CAPITAL VARIABLE', 'S. DE R.L.']
        
        encontrados = [ind for ind in indicadores_empresa if ind in texto_upper]
        
        if encontrados:
            return {
                'tipo': 'empresa',
                'indicadores': encontrados,
                'raw_response': response_text,
                'success': True,
                'metodo': 'fallback_keywords'
            }
        
        return {
            'tipo': 'persona',
            'indicadores': ['No se encontraron indicadores de empresa'],
            'raw_response': response_text,
            'success': True,
            'metodo': 'fallback_default'
        }
    
    def generate_stream(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        **kwargs
    ) -> Generator[str, None, None]:
        """
        Genera texto en modo streaming (token por token).
        
        Yields:
            str: Cada fragmento de texto conforme se genera.
        """
        
        payload = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "seed": self.config.default_seed,
                **kwargs
            }
        }
        
        if system:
            payload["system"] = system
        
        try:
            response = self._session.post(
                self.config.generate_url,
                json=payload,
                stream=True,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if 'response' in data:
                        yield data['response']
                    
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
        
        Returns:
            Dict con el JSON parseado, o None si no se encontró JSON válido.
        """
        
        result = self.generate(prompt, system, **kwargs)
        response_text = result.get('response', '')
        
        from utils.text_processing import extract_json_from_response
        
        return extract_json_from_response(response_text)


# === INSTANCIA SINGLETON ===

_service_instance: Optional[OllamaService] = None


def get_ollama_service(config: Optional[OllamaConfig] = None) -> OllamaService:
    """
    Obtiene una instancia del servicio Ollama (patrón Singleton).
    
    Uso:
        service = get_ollama_service()
        service = get_ollama_service()  # Devuelve la misma instancia
    """
    global _service_instance
    
    if _service_instance is None or config is not None:
        _service_instance = OllamaService(config)
    
    return _service_instance


# === CÓDIGO DE PRUEBA ===

if __name__ == "__main__":
    print("=" * 60)
    print("PRUEBA DEL SERVICIO OLLAMA (CON REPRODUCIBILIDAD)")
    print("=" * 60)
    
    service = get_ollama_service()
    
    print(f"\n📡 Conectando a: {service.config.base_url}")
    print(f"🤖 Modelo: {service.config.model}")
    print(f"🎲 Seed por defecto: {service.config.default_seed}")
    print(f"🌡️ Modo determinístico: {service.config.deterministic}")
    
    if service.health_check():
        print("\n✅ Ollama está disponible")
        
        # Prueba de reproducibilidad
        print("\n🔬 Probando reproducibilidad...")
        prompt = "Responde solo con 'OK' si puedes leer esto."
        
        result1 = service.generate_deterministic(prompt)
        result2 = service.generate_deterministic(prompt)
        
        print(f"   Respuesta 1: {result1['response'][:50]}")
        print(f"   Respuesta 2: {result2['response'][:50]}")
        print(f"   ¿Iguales?: {result1['response'] == result2['response']}")
    else:
        print("\n❌ No se pudo conectar a Ollama")
