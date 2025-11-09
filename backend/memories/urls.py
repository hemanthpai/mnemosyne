from django.urls import path
from .views import (
    StoreConversationTurnView,
    SearchConversationsView,
    ListConversationsView,
    GetSettingsView,
    UpdateSettingsView,
    ValidateEndpointView,
    FetchModelsView
)
from .import_views import (
    StartImportView,
    ImportProgressView,
    CancelImportView
)
from .views_notes import (
    ListAtomicNotesView,
    GetAtomicNoteView,
    DeleteAtomicNoteView,
    GetNoteTypesView,
    GetAvailableUsersView,
    TriggerExtractionView,
    KnowledgeGraphView
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

    # Settings endpoints
    path('settings/', GetSettingsView.as_view(), name='get_settings'),
    path('settings/update/', UpdateSettingsView.as_view(), name='update_settings'),
    path('settings/validate-endpoint/', ValidateEndpointView.as_view(), name='validate_endpoint'),
    path('settings/fetch-models/', FetchModelsView.as_view(), name='fetch_models'),

    # Atomic notes endpoints
    path('notes/list/', ListAtomicNotesView.as_view(), name='list_atomic_notes'),
    path('notes/get/', GetAtomicNoteView.as_view(), name='get_atomic_note'),
    path('notes/delete/', DeleteAtomicNoteView.as_view(), name='delete_atomic_note'),
    path('notes/types/', GetNoteTypesView.as_view(), name='get_note_types'),
    path('notes/users/', GetAvailableUsersView.as_view(), name='get_available_users'),
    path('notes/extract/', TriggerExtractionView.as_view(), name='trigger_extraction'),
    path('notes/graph/', KnowledgeGraphView.as_view(), name='knowledge_graph'),
]
