from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DeleteAllMemoriesView,
    ExtractMemoriesView,
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
    path("", include(router.urls)),
]
