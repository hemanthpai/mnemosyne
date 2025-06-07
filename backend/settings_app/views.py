from memories.token_utils import get_token_counts_for_prompts
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import LLMSettings
from .serializers import LLMSettingsSerializer


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
