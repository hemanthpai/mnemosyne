import logging
import math
from typing import List, Dict, Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def normalize_vector(vector: List[float]) -> List[float]:
    """Normalize a vector to unit length for cosine similarity"""
    magnitude = math.sqrt(sum(x * x for x in vector))
    if magnitude == 0:
        return vector
    return [x / magnitude for x in vector]


class LLMService:
    """Service for LLM operations: embeddings and text generation"""

    def __init__(self):
        self.session = requests.Session()

    def _get_generation_config(self) -> Dict[str, Any]:
        """
        Get generation configuration from Settings (with environment fallback)

        Returns:
            Dict with generation configuration
        """
        try:
            from .settings_model import Settings
            db_settings = Settings.get_settings()

            return {
                'provider': db_settings.generation_provider or db_settings.embeddings_provider,
                'endpoint_url': db_settings.generation_endpoint_url or db_settings.embeddings_endpoint_url,
                'model': db_settings.generation_model or db_settings.embeddings_model,
                'api_key': db_settings.generation_api_key or db_settings.embeddings_api_key,
                'temperature': db_settings.generation_temperature,
                'max_tokens': db_settings.generation_max_tokens,
                'timeout': db_settings.generation_timeout,
            }
        except Exception as e:
            # Fallback to environment variables
            logger.warning(f"Failed to get Settings from database, using environment: {e}")
            return {
                'provider': settings.EMBEDDINGS_PROVIDER,
                'endpoint_url': settings.EMBEDDINGS_ENDPOINT_URL,
                'model': getattr(settings, 'GENERATION_MODEL', settings.EMBEDDINGS_MODEL),
                'api_key': settings.EMBEDDINGS_API_KEY,
                'temperature': 0.3,
                'max_tokens': 1000,
                'timeout': settings.EMBEDDINGS_TIMEOUT * 2,
            }

    def generate_text(
        self,
        prompt: str,
        temperature: float = None,
        max_tokens: int = None
    ) -> Dict[str, Any]:
        """
        Generate text using LLM (for extraction, analysis, etc.)

        Args:
            prompt: The prompt to send to the LLM
            temperature: Sampling temperature (0.0-1.0), uses config default if None
            max_tokens: Maximum tokens to generate, uses config default if None

        Returns:
            Dict with 'success', 'text' (generated text), 'error' (if failed)
        """
        try:
            config = self._get_generation_config()
            provider = config['provider'].lower()

            # Use config defaults if not provided
            if temperature is None:
                temperature = config['temperature']
            if max_tokens is None:
                max_tokens = config['max_tokens']

            if provider == "ollama":
                return self._generate_text_ollama(prompt, temperature, max_tokens, config)
            elif provider in ["openai", "openai_compatible"]:
                return self._generate_text_openai(prompt, temperature, max_tokens, config)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported provider: {provider}"
                }

        except Exception as e:
            logger.error(f"Failed to generate text: {e}")
            return {"success": False, "error": str(e)}

    def _generate_text_ollama(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate text using Ollama with JSON mode for structured output"""
        endpoint = f"{config['endpoint_url']}/api/generate"
        model = config['model']

        try:
            response = self.session.post(
                endpoint,
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",  # Enable JSON mode for constrained generation
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens
                    }
                },
                timeout=config['timeout']
            )
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "text": data["response"],
                "model": model
            }

        except Exception as e:
            logger.error(f"Ollama text generation failed: {e}")
            return {"success": False, "error": str(e)}

    def _generate_text_openai(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate text using OpenAI or compatible API with JSON mode"""
        endpoint = f"{config['endpoint_url']}/v1/chat/completions"
        model = config['model']

        headers = {}
        if config['api_key']:
            headers["Authorization"] = f"Bearer {config['api_key']}"

        try:
            # Note: response_format removed for compatibility
            # The prompt already requests JSON format
            response = self.session.post(
                endpoint,
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                headers=headers,
                timeout=config['timeout']
            )
            response.raise_for_status()
            data = response.json()

            return {
                "success": True,
                "text": data["choices"][0]["message"]["content"],
                "model": data.get("model", model)
            }

        except requests.exceptions.HTTPError as e:
            error_detail = ""
            try:
                error_detail = e.response.json() if e.response else {}
            except:
                error_detail = e.response.text if e.response else ""
            logger.error(f"OpenAI text generation failed: {e}. Response: {error_detail}")
            return {"success": False, "error": f"{str(e)}. Response: {error_detail}"}
        except Exception as e:
            logger.error(f"OpenAI text generation failed: {e}")
            return {"success": False, "error": str(e)}

    def get_embeddings(self, texts: List[str]) -> Dict[str, Any]:
        """
        Generate embeddings for a list of texts

        Args:
            texts: List of text strings to embed

        Returns:
            Dict with 'success', 'embeddings' (list of vectors), 'error' (if failed)
        """
        if not texts:
            return {"success": False, "error": "No texts provided"}

        try:
            provider = settings.EMBEDDINGS_PROVIDER.lower()

            if provider == "ollama":
                return self._get_embeddings_ollama(texts)
            elif provider in ["openai", "openai_compatible"]:
                return self._get_embeddings_openai(texts)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported provider: {provider}"
                }

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return {"success": False, "error": str(e)}

    def _get_embeddings_ollama(self, texts: List[str]) -> Dict[str, Any]:
        """Get embeddings from Ollama"""
        endpoint = f"{settings.EMBEDDINGS_ENDPOINT_URL}/api/embeddings"

        embeddings = []
        for text in texts:
            try:
                response = self.session.post(
                    endpoint,
                    json={
                        "model": settings.EMBEDDINGS_MODEL,
                        "prompt": text,
                    },
                    timeout=settings.EMBEDDINGS_TIMEOUT,
                )
                response.raise_for_status()
                data = response.json()
                # Normalize embedding for proper cosine similarity
                raw_embedding = data["embedding"]
                normalized_embedding = normalize_vector(raw_embedding)
                embeddings.append(normalized_embedding)

            except Exception as e:
                logger.error(f"Ollama embedding failed: {e}")
                return {"success": False, "error": str(e)}

        return {
            "success": True,
            "embeddings": embeddings,
            "model": settings.EMBEDDINGS_MODEL,
        }

    def _get_embeddings_openai(self, texts: List[str]) -> Dict[str, Any]:
        """Get embeddings from OpenAI or compatible API"""
        endpoint = f"{settings.EMBEDDINGS_ENDPOINT_URL}/v1/embeddings"

        headers = {}
        if settings.EMBEDDINGS_API_KEY:
            headers["Authorization"] = f"Bearer {settings.EMBEDDINGS_API_KEY}"

        try:
            response = self.session.post(
                endpoint,
                json={
                    "model": settings.EMBEDDINGS_MODEL,
                    "input": texts,
                },
                headers=headers,
                timeout=settings.EMBEDDINGS_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()

            # Extract and normalize embeddings in order
            raw_embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]
            embeddings = [normalize_vector(emb) for emb in raw_embeddings]

            return {
                "success": True,
                "embeddings": embeddings,
                "model": data.get("model", settings.EMBEDDINGS_MODEL),
            }

        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            return {"success": False, "error": str(e)}


# Global instance
llm_service = LLMService()
