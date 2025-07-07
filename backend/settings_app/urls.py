from django.urls import path

from . import views

urlpatterns = [
    path("api/settings/", views.llm_settings, name="llm-settings"),
    path(
        "api/settings/prompt-token-counts/",
        views.get_prompt_token_counts,
        name="prompt_token_counts",
    ),
    path(
        "api/settings/validate-endpoint/",
        views.validate_endpoint,
        name="validate_endpoint",
    ),
    path(
        "api/settings/fetch-models/",
        views.fetch_models,
        name="fetch_models",
    ),
]
