from rest_framework import serializers

from .models import LLMSettings


class LLMSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = LLMSettings
        fields = [
            # LLM Endpoints
            "extraction_endpoint_url",
            "extraction_model",
            "extraction_provider_type",
            "extraction_endpoint_api_key",
            "extraction_timeout",
            # Embeddings
            "embeddings_endpoint_url",
            "embeddings_model",
            "embeddings_provider_type",
            "embeddings_endpoint_api_key",
            "embeddings_timeout",
            # LLM Parameters
            "llm_temperature",
            "llm_top_p",
            "llm_top_k",
            "llm_max_tokens",
            # Search Configuration
            "enable_semantic_connections",
            "semantic_enhancement_threshold",
            "search_threshold_direct",
            "search_threshold_semantic",
            "search_threshold_experiential",
            "search_threshold_contextual",
            "search_threshold_interest",
            # Memory Consolidation
            "enable_memory_consolidation",
            "consolidation_similarity_threshold",
            "consolidation_auto_threshold",
            "consolidation_strategy",
            "consolidation_max_group_size",
            "consolidation_batch_size",
            # Graph-Enhanced Retrieval
            "enable_graph_enhanced_retrieval",
            "graph_build_status",
            # Prompts
            "memory_extraction_prompt",
            "memory_search_prompt",
            "semantic_connection_prompt",
            "memory_summarization_prompt",
            # Metadata
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_llm_temperature(self, value):
        if not 0.0 <= value <= 2.0:
            raise serializers.ValidationError("Temperature must be between 0.0 and 2.0")
        return value

    def validate_llm_top_p(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError("Top P must be between 0.0 and 1.0")
        return value

    def validate_llm_top_k(self, value):
        if value < 1:
            raise serializers.ValidationError("Top K must be at least 1")
        return value

    def validate_consolidation_similarity_threshold(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError("Consolidation similarity threshold must be between 0.0 and 1.0")
        return value

    def validate_consolidation_auto_threshold(self, value):
        if not 0.0 <= value <= 1.0:
            raise serializers.ValidationError("Consolidation auto threshold must be between 0.0 and 1.0")
        return value

    def validate_consolidation_max_group_size(self, value):
        if value < 2:
            raise serializers.ValidationError("Max group size must be at least 2")
        return value

    def validate_consolidation_batch_size(self, value):
        if value < 1:
            raise serializers.ValidationError("Batch size must be at least 1")
        return value
