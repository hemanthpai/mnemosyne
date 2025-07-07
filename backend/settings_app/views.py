import json
import logging
import requests
from memories.token_utils import get_token_counts_for_prompts
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import LLMSettings
from .serializers import LLMSettingsSerializer

logger = logging.getLogger(__name__)


@api_view(["GET", "PUT"])
def llm_settings(request):
    """
    Get or update LLM settings
    """
    settings = LLMSettings.get_settings()

    if request.method == "GET":
        serializer = LLMSettingsSerializer(settings)
        return Response(serializer.data)

    elif request.method == "PUT":
        serializer = LLMSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def get_prompt_token_counts(request):
    """Get token counts for all prompts"""
    try:
        settings = LLMSettings.get_settings()
        token_counts = get_token_counts_for_prompts(settings)

        return Response(
            {
                "success": True,
                "token_counts": token_counts,
                "model_name": settings.extraction_model,
            }
        )
    except Exception as e:
        return Response({"success": False, "error": str(e)}, status=500)


@api_view(["POST"])
def validate_endpoint(request):
    """
    Validate an LLM/Embeddings endpoint by making a test request
    """
    try:
        data = request.data
        url = data.get("url", "").strip()
        provider_type = data.get("provider_type", "").strip()
        api_key = data.get("api_key", "").strip()

        if not url:
            return Response(
                {"success": False, "error": "URL is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not provider_type:
            return Response(
                {"success": False, "error": "Provider type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Construct the appropriate endpoint
        if provider_type == "ollama":
            test_endpoint = f"{url.rstrip('/')}/api/tags"
        else:  # openai_compatible or openai
            test_endpoint = f"{url.rstrip('/')}/v1/models"

        # Set up headers
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        logger.info(f"Validating endpoint: {test_endpoint}")

        # Make the test request with timeout
        response = requests.get(test_endpoint, headers=headers, timeout=10)
        response.raise_for_status()

        logger.info(f"Endpoint validation successful: {test_endpoint}")
        return Response({"success": True})

    except requests.exceptions.Timeout:
        logger.warning(f"Endpoint validation timeout: {test_endpoint}")
        return Response(
            {"success": False, "error": "Request timed out"},
            status=status.HTTP_408_REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        logger.warning(f"Endpoint validation connection error: {test_endpoint}")
        return Response(
            {"success": False, "error": "Could not connect to endpoint"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Endpoint validation HTTP error: {test_endpoint} - {e}")
        if e.response.status_code == 401:
            error_msg = "Authentication failed - check your API key"
        elif e.response.status_code == 403:
            error_msg = "Access forbidden - check your API key permissions"
        elif e.response.status_code == 404:
            error_msg = "Endpoint not found - check your URL and provider type"
        else:
            error_msg = f"HTTP {e.response.status_code}: {e.response.reason}"
        
        return Response(
            {"success": False, "error": error_msg},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception as e:
        logger.error(f"Unexpected error validating endpoint: {test_endpoint} - {e}")
        return Response(
            {"success": False, "error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
def fetch_models(request):
    """
    Fetch available models from an LLM/Embeddings endpoint
    """
    try:
        data = request.data
        url = data.get("url", "").strip()
        provider_type = data.get("provider_type", "").strip()
        api_key = data.get("api_key", "").strip()

        if not url:
            return Response(
                {"success": False, "error": "URL is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not provider_type:
            return Response(
                {"success": False, "error": "Provider type is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Construct the appropriate endpoint
        if provider_type == "ollama":
            models_endpoint = f"{url.rstrip('/')}/api/tags"
        else:  # openai_compatible or openai
            models_endpoint = f"{url.rstrip('/')}/v1/models"

        # Set up headers
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        logger.info(f"Fetching models from: {models_endpoint}")

        # Make the request with timeout
        response = requests.get(models_endpoint, headers=headers, timeout=15)
        response.raise_for_status()

        response_data = response.json()
        models = []

        if provider_type == "ollama":
            # Ollama format: { "models": [{ "name": "model-name", ... }, ...] }
            if "models" in response_data and isinstance(response_data["models"], list):
                models = [
                    model.get("name")
                    for model in response_data["models"]
                    if model.get("name")
                ]
        else:
            # OpenAI compatible format: { "data": [{ "id": "model-id", ... }, ...] }
            if "data" in response_data and isinstance(response_data["data"], list):
                models = [
                    model.get("id")
                    for model in response_data["data"]
                    if model.get("id")
                ]

        models.sort()
        logger.info(f"Fetched {len(models)} models from {models_endpoint}")

        return Response({"success": True, "models": models})

    except requests.exceptions.Timeout:
        logger.warning(f"Model fetching timeout: {models_endpoint}")
        return Response(
            {"success": False, "error": "Request timed out"},
            status=status.HTTP_408_REQUEST_TIMEOUT,
        )
    except requests.exceptions.ConnectionError:
        logger.warning(f"Model fetching connection error: {models_endpoint}")
        return Response(
            {"success": False, "error": "Could not connect to endpoint"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except requests.exceptions.HTTPError as e:
        logger.warning(f"Model fetching HTTP error: {models_endpoint} - {e}")
        if e.response.status_code == 401:
            error_msg = "Authentication failed - check your API key"
        elif e.response.status_code == 403:
            error_msg = "Access forbidden - check your API key permissions"
        elif e.response.status_code == 404:
            error_msg = "Endpoint not found - check your URL and provider type"
        else:
            error_msg = f"HTTP {e.response.status_code}: {e.response.reason}"
        
        return Response(
            {"success": False, "error": error_msg},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON response from: {models_endpoint}")
        return Response(
            {"success": False, "error": "Invalid JSON response from endpoint"},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching models: {models_endpoint} - {e}")
        return Response(
            {"success": False, "error": f"Unexpected error: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
