"""
Reranking Service

Provides cross-encoder reranking for improving search precision.
Supports multiple providers:
- remote: GPU server endpoint (e.g., TEI or custom FastAPI server)
- ollama: LLM-based relevance scoring
- sentence_transformers: Local cross-encoder models
"""

import logging
import requests
from typing import List, Tuple
from .settings_model import Settings

logger = logging.getLogger(__name__)


class RerankingService:
    """
    Service for reranking search results using cross-encoder models or LLM scoring.

    The reranker takes a query and a list of documents, and returns them sorted by
    relevance with scores.
    """

    def __init__(self, settings: Settings = None):
        """
        Initialize the reranking service with the specified provider

        Args:
            settings: Settings object (if None, will fetch from database)
        """
        self.settings = settings or Settings.get_settings()
        self.provider = self.settings.reranking_provider
        self.model = None

        logger.info(f"Initializing RerankingService with provider: {self.provider}")

        if self.provider == 'sentence_transformers':
            self._init_sentence_transformers()
        elif self.provider == 'remote':
            self._init_remote()
        elif self.provider == 'ollama':
            self._init_ollama()
        else:
            logger.warning(f"Unknown reranking provider: {self.provider}, falling back to ollama")
            self.provider = 'ollama'
            self._init_ollama()

    def _init_sentence_transformers(self):
        """Initialize sentence-transformers cross-encoder"""
        try:
            from sentence_transformers import CrossEncoder
            import torch

            device = self.settings.reranking_device
            if device == 'auto':
                device = 'cuda' if torch.cuda.is_available() else 'cpu'

            logger.info(f"Loading cross-encoder model: {self.settings.reranking_model_name} on {device}")

            self.model = CrossEncoder(
                self.settings.reranking_model_name,
                device=device,
                max_length=512  # Standard length for most rerankers
            )

            logger.info(f"Cross-encoder model loaded successfully on {device}")

        except ImportError as e:
            logger.error(f"sentence-transformers not installed: {e}")
            logger.error("Install with: pip install sentence-transformers torch")
            raise
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            raise

    def _init_remote(self):
        """Initialize remote reranking endpoint"""
        endpoint = self.settings.reranking_endpoint_url
        logger.info(f"Using remote reranking endpoint: {endpoint}")

        # Test connectivity
        try:
            response = requests.get(f"{endpoint.rstrip('/')}/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"Remote reranking endpoint is healthy: {response.json()}")
            else:
                logger.warning(f"Remote endpoint returned status {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not verify remote endpoint health: {e}")

    def _init_ollama(self):
        """Initialize Ollama for LLM-based reranking"""
        endpoint = self.settings.ollama_reranking_base_url
        model = self.settings.ollama_reranking_model
        logger.info(f"Using Ollama reranking with model: {model} at {endpoint}")

    def rerank(self, query: str, documents: List[str], top_k: int = None) -> List[Tuple[int, float]]:
        """
        Rerank documents by relevance to query

        Args:
            query: Search query
            documents: List of document texts to rerank
            top_k: Optional, return only top k results (default: return all)

        Returns:
            List of (index, score) tuples sorted by relevance (descending)
            Index refers to the original position in the documents list
        """
        if not documents:
            return []

        try:
            if self.provider == 'sentence_transformers':
                return self._rerank_sentence_transformers(query, documents, top_k)
            elif self.provider == 'remote':
                return self._rerank_remote(query, documents, top_k)
            elif self.provider == 'ollama':
                return self._rerank_ollama(query, documents, top_k)
            else:
                logger.error(f"Unknown provider: {self.provider}")
                # Fallback: return original order
                return [(i, 1.0) for i in range(len(documents))]

        except Exception as e:
            logger.error(f"Reranking failed with {self.provider}: {e}")
            logger.warning("Falling back to original order")
            # Return original order on error
            return [(i, 1.0) for i in range(len(documents))]

    def _rerank_sentence_transformers(self, query: str, documents: List[str], top_k: int = None) -> List[Tuple[int, float]]:
        """Rerank using local cross-encoder model"""
        # Create query-document pairs
        pairs = [[query, doc] for doc in documents]

        # Get scores
        scores = self.model.predict(
            pairs,
            batch_size=self.settings.reranking_batch_size,
            show_progress_bar=False
        )

        # Create results with original indices
        results = [(i, float(score)) for i, score in enumerate(scores)]

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Return top_k if specified
        if top_k:
            results = results[:top_k]

        return results

    def _rerank_remote(self, query: str, documents: List[str], top_k: int = None) -> List[Tuple[int, float]]:
        """Rerank using remote endpoint (TEI or custom FastAPI server)"""
        endpoint = self.settings.reranking_endpoint_url.rstrip('/')

        try:
            response = requests.post(
                f"{endpoint}/rerank",
                json={
                    "query": query,
                    "texts": documents,
                    "top_k": top_k  # Let server handle top_k if it supports it
                },
                timeout=30
            )
            response.raise_for_status()

            results = response.json()

            # Handle different response formats
            if isinstance(results, list):
                # Format: [{"index": 0, "score": 0.98}, ...]
                if results and isinstance(results[0], dict) and 'index' in results[0]:
                    return [(r['index'], r['score']) for r in results[:top_k] if top_k else results]
                # Format: [0.98, 0.45, ...] (scores in original order)
                elif results and isinstance(results[0], (int, float)):
                    indexed = [(i, float(score)) for i, score in enumerate(results)]
                    indexed.sort(key=lambda x: x[1], reverse=True)
                    return indexed[:top_k] if top_k else indexed

            logger.error(f"Unexpected response format from remote endpoint: {results}")
            return [(i, 1.0) for i in range(len(documents))]

        except Exception as e:
            logger.error(f"Remote reranking request failed: {e}")
            raise

    def _rerank_ollama(self, query: str, documents: List[str], top_k: int = None) -> List[Tuple[int, float]]:
        """Rerank using Ollama LLM-based scoring"""
        endpoint = self.settings.ollama_reranking_base_url.rstrip('/')
        model = self.settings.ollama_reranking_model
        temperature = self.settings.ollama_reranking_temperature

        scores = []

        for i, doc in enumerate(documents):
            try:
                # Prompt for relevance scoring
                prompt = f"""Rate the relevance of this document to the query on a scale of 0-10.
Only respond with a single number between 0 and 10.

Query: {query}

Document: {doc}

Relevance score (0-10):"""

                response = requests.post(
                    f"{endpoint}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "temperature": temperature,
                        "stream": False
                    },
                    timeout=30
                )
                response.raise_for_status()

                result = response.json()
                score_text = result.get('response', '').strip()

                # Extract number from response
                try:
                    # Try to parse as float directly
                    score = float(score_text)
                    # Normalize to 0-1 range
                    score = max(0, min(10, score)) / 10.0
                except ValueError:
                    # Try to extract first number
                    import re
                    numbers = re.findall(r'\d+(?:\.\d+)?', score_text)
                    if numbers:
                        score = float(numbers[0])
                        score = max(0, min(10, score)) / 10.0
                    else:
                        logger.warning(f"Could not parse score from: {score_text}")
                        score = 0.5  # Default middle score

                scores.append((i, score))

            except Exception as e:
                logger.warning(f"Failed to score document {i} with Ollama: {e}")
                scores.append((i, 0.0))  # Assign lowest score on error

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        # Return top_k if specified
        if top_k:
            scores = scores[:top_k]

        return scores


# Singleton instance
_reranking_service = None


def get_reranking_service() -> RerankingService:
    """
    Get or create singleton reranking service instance

    Returns:
        RerankingService instance
    """
    global _reranking_service

    if _reranking_service is None:
        _reranking_service = RerankingService()

    return _reranking_service


def reset_reranking_service():
    """
    Reset the singleton reranking service (for testing or settings changes)
    """
    global _reranking_service
    _reranking_service = None
