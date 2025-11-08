from django.urls import path
from .views import (
    StoreConversationTurnView,
    SearchConversationsView,
    ListConversationsView,
    GetSettingsView
)

urlpatterns = [
    # Conversation endpoints
    path('conversations/store/', StoreConversationTurnView.as_view(), name='store_conversation_turn'),
    path('conversations/search/', SearchConversationsView.as_view(), name='search_conversations'),
    path('conversations/list/', ListConversationsView.as_view(), name='list_conversations'),

    # Settings endpoint (read-only)
    path('settings/', GetSettingsView.as_view(), name='get_settings'),
]
