from rest_framework import serializers

from .models import LLMSettings


class LLMSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMSettings
        fields = [
            "extraction_endpoint_url",
            "extraction_model",
            "extraction_provider_type",
            "embeddings_endpoint_url",
            "embeddings_model",
            "embeddings_provider_type",
            "memory_extraction_prompt",
            "memory_search_prompt",
            "extraction_endpoint_api_key",
            "embeddings_endpoint_api_key",
            "extraction_timeout",
            "embeddings_timeout",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]
