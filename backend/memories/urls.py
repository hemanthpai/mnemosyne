from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CancelImportView,
    DeleteAllMemoriesView,
    ExtractMemoriesView,
    ImportOpenWebUIHistoryView,
    ImportProgressView,
    MemoryStatsView,
    MemoryViewSet,
    RetrieveMemoriesView,
    TestConnectionView,
)

router = DefaultRouter()
router.register(r"", MemoryViewSet, basename="memories")

urlpatterns = [
    path("extract/", ExtractMemoriesView.as_view(), name="extract-memories"),
    path("retrieve/", RetrieveMemoriesView.as_view(), name="retrieve-memories"),
    path("test-connection/", TestConnectionView.as_view(), name="test-connection"),
    path("stats/", MemoryStatsView.as_view(), name="memory-stats"),
    path("delete-all/", DeleteAllMemoriesView.as_view(), name="delete_all_memories"),
    path("import/start/", ImportOpenWebUIHistoryView.as_view(), name="import_openwebui_history"),
    path("import/progress/", ImportProgressView.as_view(), name="import_progress"),
    path("import/cancel/", CancelImportView.as_view(), name="cancel_import"),
    path("", include(router.urls)),
]
