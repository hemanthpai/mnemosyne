import logging
import os
import time
from typing import Any, Dict, List, Optional, Union  # Add Tuple import

import requests
from django.utils import timezone

from .token_utils import TokenCounter  # Add this import

logger = logging.getLogger(__name__)

# Define format schemas
MEMORY_EXTRACTION_FORMAT = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "context": {"type": "string"},
            "connections": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["content", "tags", "confidence"],
    },
}

MEMORY_SEARCH_FORMAT = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "search_query": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "search_type": {
                "type": "string",
                "enum": [
                    "direct",
                    "semantic",
                    "experiential",
                    "contextual",
                    "interest",
                ],
            },
            "rationale": {
                "type": "string",
            },
        },
        "required": ["search_query", "confidence"],
    },
}

SEMANTIC_CONNECTION_FORMAT = {
    "type": "object",
    "properties": {
        "has_connections": {"type": "boolean"},
        "additional_searches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "search_query": {"type": "string"},
                    "rationale": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                },
                "required": ["search_query", "rationale", "confidence"],
            },
        },
        "reasoning": {"type": "string"},
    },
    "required": ["has_connections", "additional_searches", "reasoning"],
}

MEMORY_SUMMARY_FORMAT = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "key_points": {"type": "array", "items": {"type": "string"}},
        "relevant_context": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "memory_usage": {
            "type": "object",
            "properties": {
                "total_memories": {"type": "integer"},
                "highly_relevant": {"type": "integer"},
                "moderately_relevant": {"type": "integer"},
                "context_relevant": {"type": "integer"},
            },
        },
    },
    "required": [
        "summary",
        "key_points",
        "relevant_context",
        "confidence",
        "memory_usage",
    ],
}


class LLMService:
    """
    Service class for making calls to LLM and embedding APIs
    """

    def __init__(self):
        self.session = requests.Session()
        self._settings = None
        self._settings_loaded = False

    @property
    def settings(self):
        """Lazy load settings when first accessed"""
        if not self._settings_loaded:
            self._load_settings()
        return self._settings

    def _load_settings(self):
        """Load settings from database with proper error handling"""
        try:
            from django.db import connection

            # Check if we can connect to database
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            # Check if the table exists
            from django.db import transaction

            with transaction.atomic():
                from settings_app.models import LLMSettings

                self._settings = LLMSettings.get_settings()
                self._settings_loaded = True
                print("LLM settings loaded from database")

        except Exception as e:
            print(f"Could not load LLM settings from database: {e}")
            print("Using environment variables and defaults")

            # Create a fallback settings object from environment variables
            from types import SimpleNamespace

            self._settings = SimpleNamespace(
                base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                model=os.getenv("LLM_MODEL", "llama3.1:8b"),
                embedding_model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4000")),
                timeout=int(os.getenv("LLM_TIMEOUT", "120")),
            )
            self._settings_loaded = True

    def refresh_settings(self):
        """Refresh settings from database"""
        self._settings_loaded = False  # Force reload
        self._load_settings()

    def get_formatted_datetime(self):
        """Get current datetime with timezone"""
        return timezone.now()

    def query_llm(
        self,
        prompt: str,
        user_input: str = "",
        system_prompt: str = "",
        response_format: Union[str, Dict[str, Any], None] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        temperature: Optional[float] = None,  # Make optional
        max_tokens: Optional[int] = None,  # Make optional
    ) -> Dict[str, Any]:
        """Query LLM with settings from database"""
        if not self.settings:
            return {
                "success": False,
                "error": "LLM settings not loaded",
                "response": "",
                "model": "unknown",
            }

        # Use settings values if not provided
        if temperature is None or not isinstance(temperature, (float, int)):
            temperature = float(self.settings.llm_temperature)
        if max_tokens is None or not isinstance(max_tokens, int):
            max_tokens = int(self.settings.llm_max_tokens)

        provider_type = self.settings.extraction_provider_type
        model = self.settings.extraction_model
        api_url = self.settings.extraction_endpoint_url

        logger.info(
            "LLM Query: Provider=%s, Model=%s, URL=%s", provider_type, model, api_url
        )

        # Construct full prompt
        full_prompt = prompt
        if user_input:
            full_prompt = f"User Input: {user_input}\n\nTask: {prompt}"

        # Add current datetime to system prompt for time awareness
        system_prompt_with_date = system_prompt
        try:
            now = self.get_formatted_datetime()
            tzname = now.tzname() or "UTC"
            system_prompt_with_date = f"{system_prompt}\n\nCurrent date and time: {now.strftime('%Y-%m-%d %H:%M:%S')} {tzname}"
        except Exception as e:
            logger.warning("Could not add date to system prompt: %s", e)

        headers = {"Content-Type": "application/json"}

        # Add API key if needed (for OpenAI-compatible APIs)
        if provider_type == "openai_compatible":
            if (
                hasattr(self.settings, "extraction_endpoint_api_key")
                and self.settings.extraction_endpoint_api_key
            ):
                headers["Authorization"] = (
                    f"Bearer {self.settings.extraction_endpoint_api_key}"
                )

        for attempt in range(1, max_retries + 2):
            logger.debug("LLM query attempt %d/%d", attempt, max_retries + 1)

            try:
                # Prepare request data based on provider type
                if provider_type == "ollama":
                    data = self._prepare_ollama_request(
                        model,
                        system_prompt_with_date,
                        full_prompt,
                        temperature,
                        max_tokens,
                        response_format,  # Pass response_format instead of force_json
                    )
                    endpoint = f"{api_url.rstrip('/')}/api/chat"
                elif provider_type in ["openai", "openai_compatible"]:
                    data = self._prepare_openai_request(
                        model,
                        system_prompt_with_date,
                        full_prompt,
                        temperature,
                        max_tokens,
                        response_format,  # Pass response_format instead of force_json
                    )
                    endpoint = f"{api_url.rstrip('/')}/v1/chat/completions"
                else:
                    error_msg = f"Unsupported provider type: {provider_type}"
                    logger.error(error_msg)
                    return {
                        "success": False,
                        "error": error_msg,
                        "response": "",
                        "model": model,
                    }

                logger.info(
                    "Making API request to %s (attempt %d/%d)",
                    endpoint,
                    attempt,
                    max_retries + 1,
                )

                # Make the API call
                response = requests.post(
                    endpoint,
                    json=data,
                    headers=headers,
                    timeout=self.settings.extraction_timeout,
                )

                logger.info("API response status: %s", response.status_code)

                if response.status_code == 200:
                    # Parse response based on provider type
                    result = self._parse_response(response, provider_type)

                    if result["success"]:
                        return {
                            "success": True,
                            "response": result["content"],
                            "model": model,
                            "metadata": result.get("metadata", {}),
                        }
                    else:
                        error_msg = result["error"]
                        logger.error(error_msg)
                        if attempt > max_retries:
                            return {
                                "success": False,
                                "error": error_msg,
                                "response": "",
                                "model": model,
                            }
                else:
                    # Handle error response
                    error_msg = f"LLM API ({provider_type}) returned {response.status_code}: {response.text}"
                    logger.warning("API error: %s", error_msg)

                    # Determine if we should retry
                    is_retryable = response.status_code in [429, 500, 502, 503, 504]

                    if is_retryable and attempt <= max_retries:
                        sleep_time = retry_delay * (2 ** (attempt - 1))
                        logger.warning("Retrying in %.2f seconds...", sleep_time)
                        time.sleep(sleep_time)
                        continue
                    else:
                        return {
                            "success": False,
                            "error": error_msg,
                            "response": "",
                            "model": model,
                        }

            except requests.exceptions.Timeout:
                logger.warning("Attempt %d failed: LLM API request timed out", attempt)
                if attempt <= max_retries:
                    sleep_time = retry_delay * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
                    continue
                else:
                    return {
                        "success": False,
                        "error": "LLM API request timed out after multiple retries",
                        "response": "",
                        "model": model,
                    }
            except Exception as e:
                logger.error(
                    "Attempt %d failed: Unexpected error during LLM query: %s",
                    attempt,
                    e,
                )
                if attempt <= max_retries:
                    sleep_time = retry_delay * (2 ** (attempt - 1))
                    time.sleep(sleep_time)
                    continue
                else:
                    return {
                        "success": False,
                        "error": f"Unexpected error after {max_retries} attempts: {str(e)}",
                        "response": "",
                        "model": model,
                    }

        return {
            "success": False,
            "error": f"LLM query failed after {max_retries} attempts",
            "response": "",
            "model": model,
        }

    def _prepare_ollama_request(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        response_format: Union[str, Dict[str, Any], None] = None,
    ) -> Dict[str, Any]:
        """Prepare request data for Ollama API with settings"""

        # Calculate required context size
        required_context = TokenCounter.calculate_required_context(
            prompt=system_prompt,
            user_input=user_prompt,
            model_name=model,
            safety_margin=max_tokens + 512,  # Add extra margin for response
        )

        logger.info(
            "Token analysis - System prompt: %d tokens, User prompt: %d tokens, Required context: %d",
            TokenCounter.estimate_tokens(system_prompt, model),
            TokenCounter.estimate_tokens(user_prompt, model),
            required_context,
        )

        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "options": {
                "temperature": temperature,
                "top_p": float(self.settings.llm_top_p),
                "top_k": int(self.settings.llm_top_k),
                "num_predict": max_tokens,
                "num_ctx": required_context,  # Set context size dynamically
            },
            "stream": False,
        }

        # Handle response_format parameter
        if response_format is not None:
            if isinstance(response_format, dict):
                data["format"] = response_format
            elif response_format == "json":
                data["format"] = {"type": "object"}

        logger.info(
            "Prepared Ollama request data with context size %d: %s",
            required_context,
            data,
        )
        return data

    def _prepare_openai_request(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        response_format: Union[str, Dict[str, Any], None],
    ) -> Dict[str, Any]:
        """Prepare request data for OpenAI-compatible API with settings"""
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "top_p": float(self.settings.llm_top_p),
            "top_k": int(self.settings.llm_top_k),
            "stream": False,
        }

        if max_tokens:
            data["max_tokens"] = max_tokens

        if response_format:
            if isinstance(response_format, dict):
                data["response_format"] = response_format
            elif response_format == "json":
                data["response_format"] = {"type": "json_object"}

        return data

    def _parse_response(self, response, provider_type: str) -> Dict[str, Any]:
        """Parse API response based on provider type"""
        try:
            data = response.json()

            logger.info("Raw response data: %s", data)

            # Extract content based on provider type
            content = None
            metadata = {}

            if provider_type in ["openai", "openai_compatible"]:
                if (
                    data.get("choices")
                    and data["choices"][0].get("message")
                    and data["choices"][0]["message"].get("content")
                ):
                    content = data["choices"][0]["message"]["content"]
                    metadata = {
                        "usage": data.get("usage", {}),
                        "finish_reason": data["choices"][0].get("finish_reason"),
                    }
            elif provider_type == "ollama":
                if data.get("message") and data["message"].get("content"):
                    content = data["message"]["content"]
                    metadata = {
                        "total_duration": data.get("total_duration"),
                        "load_duration": data.get("load_duration"),
                        "prompt_eval_count": data.get("prompt_eval_count"),
                        "eval_count": data.get("eval_count"),
                        "eval_duration": data.get("eval_duration"),
                    }

            if content:
                return {"success": True, "content": content, "metadata": metadata}
            else:
                return {
                    "success": False,
                    "error": f"Could not extract content from {provider_type} response format",
                }

        except Exception as e:
            return {"success": False, "error": f"Error parsing response: {str(e)}"}

    def get_embeddings(
        self, texts: List[str], normalize: bool = True
    ) -> Dict[str, Any]:
        """
        Get embeddings for the provided texts (synchronous)
        """
        if not self.settings:
            return {
                "success": False,
                "error": "LLM settings not loaded",
                "embeddings": [],
                "model": "unknown",
            }

        try:
            if self.settings.embeddings_provider_type == "ollama":
                return self._get_ollama_embeddings(texts, normalize)
            elif self.settings.embeddings_provider_type == "openai_compatible":
                return self._get_openai_compatible_embeddings(texts, normalize)
            else:
                raise ValueError(
                    f"Unsupported embeddings provider: {self.settings.embeddings_provider_type}"
                )
        except Exception as e:
            logger.error("Error getting embeddings: %s", e)
            return {
                "success": False,
                "error": str(e),
                "embeddings": [],
                "model": self.settings.embeddings_model,
            }

    def _get_ollama_embeddings(
        self, texts: List[str], normalize: bool
    ) -> Dict[str, Any]:
        """Get embeddings from Ollama (synchronous)"""
        if not self.settings or not getattr(
            self.settings, "embeddings_endpoint_url", None
        ):
            return {
                "success": False,
                "error": "Embeddings settings not loaded or missing embeddings_endpoint_url",
                "embeddings": [],
                "model": getattr(self.settings, "embeddings_model", "unknown"),
            }

        url = f"{self.settings.embeddings_endpoint_url.rstrip('/')}/api/embeddings"
        all_embeddings = []

        for text in texts:
            payload = {"model": self.settings.embeddings_model, "prompt": text}

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            response.raise_for_status()

            result = response.json()
            embedding = result.get("embedding", [])

            if normalize and embedding:
                import math

                magnitude = math.sqrt(sum(x * x for x in embedding))
                if magnitude > 0:
                    embedding = [x / magnitude for x in embedding]

            all_embeddings.append(embedding)

        return {
            "success": True,
            "embeddings": all_embeddings,
            "model": self.settings.embeddings_model,
            "metadata": {
                "count": len(all_embeddings),
                "dimension": len(all_embeddings[0])
                if all_embeddings and all_embeddings[0]
                else 0,
            },
        }

    def _get_openai_compatible_embeddings(
        self, texts: List[str], normalize: bool
    ) -> Dict[str, Any]:
        """Get embeddings from OpenAI-compatible API (synchronous)"""
        if not self.settings or not getattr(
            self.settings, "embeddings_endpoint_url", None
        ):
            return {
                "success": False,
                "error": "Embeddings settings not loaded or missing embeddings_endpoint_url",
                "embeddings": [],
                "model": getattr(self.settings, "embeddings_model", "unknown"),
            }

        url = f"{self.settings.embeddings_endpoint_url.rstrip('/')}/v1/embeddings"

        payload = {"model": self.settings.embeddings_model, "input": texts}
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        result = response.json()

        embeddings = []
        for item in sorted(result["data"], key=lambda x: x["index"]):
            embedding = item["embedding"]

            if normalize:
                import math

                magnitude = math.sqrt(sum(x * x for x in embedding))
                if magnitude > 0:
                    embedding = [x / magnitude for x in embedding]

            embeddings.append(embedding)

        return {
            "success": True,
            "embeddings": embeddings,
            "model": self.settings.embeddings_model,
            "metadata": {
                "usage": result.get("usage", {}),
                "count": len(embeddings),
                "dimension": len(embeddings[0]) if embeddings else 0,
            },
        }

    def test_connection(self) -> Dict[str, Any]:
        """Test connection to both LLM and embeddings endpoints"""
        results = {
            "llm_connection": False,
            "embeddings_connection": False,
            "llm_error": None,
            "embeddings_error": None,
        }

        # Test LLM connection
        try:
            llm_result = self.query_llm(
                prompt="Respond with just 'Hello' to test the connection.",
                temperature=0.1,
            )
            results["llm_connection"] = llm_result.get("success", False)
            if not results["llm_connection"]:
                results["llm_error"] = llm_result.get("error", "Unknown error")
        except Exception as e:
            results["llm_error"] = str(e)

        # Test embeddings connection
        try:
            embeddings_result = self.get_embeddings(["test connection"])
            results["embeddings_connection"] = embeddings_result.get("success", False)
            if not results["embeddings_connection"]:
                results["embeddings_error"] = embeddings_result.get(
                    "error", "Unknown error"
                )
        except Exception as e:
            results["embeddings_error"] = str(e)

        return results

    def get_prompt_token_info(
        self, prompt: str, user_input: str = ""
    ) -> Dict[str, Any]:
        """
        Get token information for a given prompt and user input.

        Returns:
            Dictionary containing token counts and context requirements
        """
        model_name = self.settings.extraction_model if self.settings else ""

        prompt_tokens = TokenCounter.estimate_tokens(prompt, model_name)
        input_tokens = TokenCounter.estimate_tokens(user_input, model_name)
        total_tokens = prompt_tokens + input_tokens
        required_context = TokenCounter.calculate_required_context(
            prompt, user_input, model_name
        )

        return {
            "prompt_tokens": prompt_tokens,
            "input_tokens": input_tokens,
            "total_input_tokens": total_tokens,
            "required_context": required_context,
            "model_family": TokenCounter._get_model_family(model_name.lower()),
        }


# Global instance
llm_service = LLMService()
