from django.urls import path

from . import views

urlpatterns = [
    path("api/settings/", views.llm_settings, name="llm-settings"),
]
