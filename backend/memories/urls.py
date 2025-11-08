from django.urls import path
from .views import (
    StoreConversationTurnView,
    SearchConversationsView,
    ListConversationsView,
    GetSettingsView
)
from .import_views import (
    StartImportView,
    ImportProgressView,
    CancelImportView
)

urlpatterns = [
    # Conversation endpoints
    path('conversations/store/', StoreConversationTurnView.as_view(), name='store_conversation_turn'),
    path('conversations/search/', SearchConversationsView.as_view(), name='search_conversations'),
    path('conversations/list/', ListConversationsView.as_view(), name='list_conversations'),

    # Import endpoints
    path('import/start/', StartImportView.as_view(), name='start_import'),
    path('import/progress/', ImportProgressView.as_view(), name='import_progress'),
    path('import/cancel/', CancelImportView.as_view(), name='cancel_import'),

    # Settings endpoint (read-only)
    path('settings/', GetSettingsView.as_view(), name='get_settings'),
]
