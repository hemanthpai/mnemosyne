from django.contrib import admin
from django.urls import include, path

from .health import health_check

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("settings_app.urls")),
    path("api/memories/", include("memories.urls")),
    path("health/", health_check, name="health_check"),
]
