import mimetypes
import os

from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.generic import TemplateView

from .health import health_check


def serve_react_static(request, path):
    """Serve static files from React build with correct MIME types"""
    # For assets/* requests, look in the assets subdirectory
    if path.startswith("assets/"):
        # Remove 'assets/' prefix since we're already in the assets directory
        actual_path = path[7:]  # Remove 'assets/' prefix
        file_path = os.path.join(
            os.path.abspath(
                os.path.join(settings.BASE_DIR, "../frontend/build/assets", actual_path)
            )
        )
    else:
        # For other files (like vite.svg), look in the build root
        file_path = os.path.abspath(
            os.path.join(settings.BASE_DIR, "../frontend/build", path)
        )

    print(f"DEBUG: Looking for file: {file_path}")
    print(f"DEBUG: File exists: {os.path.exists(file_path)}")

    if os.path.exists(file_path) and os.path.isfile(file_path):
        # Get the correct MIME type
        content_type, _ = mimetypes.guess_type(file_path)
        print(f"DEBUG: Serving file with content type: {content_type}")
        response = FileResponse(open(file_path, "rb"), content_type=content_type)
        return response

    print(f"DEBUG: File not found: {file_path}")
    raise Http404("File not found")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("settings_app.urls")),
    path("api/memories/", include("memories.urls")),
    path("health/", health_check, name="health_check"),
    # Serve React static files - note the updated regex
    re_path(r"^(?P<path>assets/.*)$", serve_react_static),
    re_path(r"^(?P<path>vite\.svg)$", serve_react_static),
    # React app catch-all route MUST be last
    re_path(r"^.*$", TemplateView.as_view(template_name="index.html")),
]
