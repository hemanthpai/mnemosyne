import logging
from typing import List, Dict, Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Simple service for embeddings generation"""

    def __init__(self):
        self.session = requests.Session()

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
                embeddings.append(data["embedding"])

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

            # Extract embeddings in order
            embeddings = [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]

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
