from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint for load balancers and monitoring"""
    status = {"status": "healthy", "services": {}}

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status["services"]["database"] = "healthy"
    except Exception as e:
        status["services"]["database"] = f"unhealthy: {str(e)}"
        status["status"] = "unhealthy"

    # # Check Qdrant using urllib (no external dependency)
    # try:
    #     qdrant_url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}/health"
    #     req = urllib.request.Request(qdrant_url)
    #     with urllib.request.urlopen(req, timeout=5) as response:
    #         if response.status == 200:
    #             status["services"]["qdrant"] = "healthy"
    #         else:
    #             status["services"]["qdrant"] = f"unhealthy: status {response.status}"
    #             status["status"] = "unhealthy"
    # except urllib.error.URLError as e:
    #     status["services"]["qdrant"] = f"unhealthy: {str(e)}"
    #     status["status"] = "unhealthy"
    # except Exception as e:
    #     status["services"]["qdrant"] = f"unhealthy: {str(e)}"
    #     status["status"] = "unhealthy"

    # # Check Redis (if configured)
    # try:
    #     if hasattr(settings, "REDIS_URL") and settings.REDIS_URL:
    #         # Simple Redis check using Django cache if configured
    #         from django.core.cache import cache

    #         cache.set("health_check", "test", 1)
    #         test_value = cache.get("health_check")
    #         if test_value == "test":
    #             status["services"]["redis"] = "healthy"
    #         else:
    #             status["services"]["redis"] = "unhealthy: cache test failed"
    #             status["status"] = "unhealthy"
    # except Exception as e:
    #     status["services"]["redis"] = f"unhealthy: {str(e)}"

    # Check Ollama connection (if configured)
    # try:
    #     if hasattr(settings, "OLLAMA_BASE_URL") and settings.OLLAMA_BASE_URL:
    #         ollama_url = f"{settings.OLLAMA_BASE_URL}/api/tags"
    #         req = urllib.request.Request(ollama_url)
    #         with urllib.request.urlopen(req, timeout=5) as response:
    #             if response.status == 200:
    #                 status["services"]["ollama"] = "healthy"
    #             else:
    #                 status["services"]["ollama"] = (
    #                     f"unhealthy: status {response.status}"
    #                 )
    # except Exception as e:
    #     # Ollama is optional, so don't fail the overall health check
    #     status["services"]["ollama"] = f"unavailable: {str(e)}"

    status_code = 200 if status["status"] == "healthy" else 503
    return JsonResponse(status, status=status_code)
