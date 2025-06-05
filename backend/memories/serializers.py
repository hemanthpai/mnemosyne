import uuid

from rest_framework import serializers

from .models import Memory


class MemorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Memory
        fields = ["id", "user_id", "content", "metadata", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_user_id(self, value):
        """Validate that user_id is a valid UUID"""
        try:
            uuid.UUID(str(value))
            return value
        except ValueError as exc:
            raise serializers.ValidationError("user_id must be a valid UUID") from exc

    def validate_content(self, value):
        """Validate that content is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Content cannot be empty")
        return value.strip()
