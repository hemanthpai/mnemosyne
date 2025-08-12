from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BuildMemoryGraphView,
    DeleteAllMemoriesView,
    ExtractMemoriesView,
    GraphHealthView,
    GraphQueryView,
    GraphStatsView,
    GraphStatusView,
    MemoryClustersView,
    MemoryStatsView,
    MemoryViewSet,
    RetrieveMemoriesView,
    TestConnectionView,
    TextToGraphView,
    TraverseMemoryGraphView,
)

router = DefaultRouter()
router.register(r"", MemoryViewSet, basename="memories")

urlpatterns = [
    path("extract/", ExtractMemoriesView.as_view(), name="extract-memories"),
    path("retrieve/", RetrieveMemoriesView.as_view(), name="retrieve-memories"),
    path("test-connection/", TestConnectionView.as_view(), name="test-connection"),
    path("stats/", MemoryStatsView.as_view(), name="memory-stats"),
    path("delete-all/", DeleteAllMemoriesView.as_view(), name="delete_all_memories"),
    path("text-to-graph/", TextToGraphView.as_view(), name="text-to-graph"),
    path("graph-stats/", GraphStatsView.as_view(), name="graph-stats"),
    path("graph-health/", GraphHealthView.as_view(), name="graph-health"),
    path("graph-query/", GraphQueryView.as_view(), name="graph-query"),
    path("build-graph/", BuildMemoryGraphView.as_view(), name="build-memory-graph"),
    path("traverse-graph/", TraverseMemoryGraphView.as_view(), name="traverse-memory-graph"),
    path("memory-clusters/", MemoryClustersView.as_view(), name="memory-clusters"),
    path("graph-status/", GraphStatusView.as_view(), name="graph-status"),
    path("", include(router.urls)),
]
