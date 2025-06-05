from rest_framework import serializers

from .models import LLMSettings


class LLMSettingsSerializer(serializers.ModelSerializer):
    memory_categories_list = serializers.SerializerMethodField()

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
            "memory_categories_list",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_memory_categories_list(self, obj):
        """Return memory categories as a list for frontend"""
        return obj.get_memory_categories_list()

    def update(self, instance, validated_data):
        # Handle memory categories list if provided in initial data
        if (
            hasattr(self, "initial_data")
            and isinstance(self.initial_data, dict)
            and "memory_categories_list" in self.initial_data
        ):
            categories_list = self.initial_data["memory_categories_list"]
            if isinstance(categories_list, list):
                instance.set_memory_categories_list(categories_list)

        # Update other fields normally
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        return instance
