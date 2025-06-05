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
