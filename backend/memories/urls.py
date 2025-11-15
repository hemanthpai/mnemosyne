from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from .views import (
    StoreConversationTurnView,
    SearchConversationsView,
    ListConversationsView,
    GetSettingsView,
    UpdateSettingsView,
    ValidateEndpointView,
    FetchModelsView,
    QueueStatusView,
    ClearStuckTasksView,
    QueueHealthDiagnosticsView,
    RunBenchmarkView,
    BenchmarkStatusView,
    BenchmarkResultsView,
    ListDatasetsView,
    UploadDatasetView,
    ActiveTasksView,
    RecentTasksView,
    ClearAllDataView,
    CancelBenchmarkView
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

    # Queue monitoring endpoints
    path('queue/status/', QueueStatusView.as_view(), name='queue_status'),
    path('queue/clear-stuck/', ClearStuckTasksView.as_view(), name='clear_stuck_tasks'),
    path('queue/health/', QueueHealthDiagnosticsView.as_view(), name='queue_health'),

    # Benchmark endpoints
    path('benchmarks/run/', RunBenchmarkView.as_view(), name='run_benchmark'),
    path('benchmarks/status/<str:task_id>/', BenchmarkStatusView.as_view(), name='benchmark_status'),
    path('benchmarks/results/<str:task_id>/', BenchmarkResultsView.as_view(), name='benchmark_results'),
    path('benchmarks/datasets/', ListDatasetsView.as_view(), name='list_datasets'),
    path('benchmarks/datasets/upload/', csrf_exempt(UploadDatasetView.as_view()), name='upload_dataset'),
    path('benchmarks/cancel/', csrf_exempt(CancelBenchmarkView.as_view()), name='cancel_benchmark'),

    # Activity Monitor endpoints
    path('tasks/active/', ActiveTasksView.as_view(), name='active_tasks'),
    path('tasks/recent/', RecentTasksView.as_view(), name='recent_tasks'),

    # Data Management endpoints
    path('data/clear-all/', ClearAllDataView.as_view(), name='clear_all_data'),
]
