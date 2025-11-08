from django.contrib import admin
from .models import ConversationTurn


@admin.register(ConversationTurn)
class ConversationTurnAdmin(admin.ModelAdmin):
    list_display = ('id', 'user_id', 'session_id', 'turn_number', 'timestamp', 'extracted')
    list_filter = ('extracted', 'timestamp')
    search_fields = ('user_id', 'session_id', 'user_message', 'assistant_message')
    readonly_fields = ('id', 'timestamp', 'vector_id')
    ordering = ('-timestamp',)
