import logging
import urllib.request
import urllib.error

from django.conf import settings
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)


def health_check(request):
    """Health check endpoint for load balancers and monitoring"""
    status = {"status": "healthy", "services": {}}
    logger.info("Health check started")

    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        status["services"]["database"] = "healthy"
    except Exception as e:
        status["services"]["database"] = f"unhealthy: {str(e)}"
        status["status"] = "unhealthy"

    # Check Qdrant using urllib (no external dependency)
    try:
        qdrant_url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}"
        logger.info(f"Checking Qdrant at {qdrant_url}")
        req = urllib.request.Request(qdrant_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                status["services"]["qdrant"] = "healthy"
                logger.info("Qdrant is healthy")
            else:
                status["services"]["qdrant"] = f"unhealthy: status {response.status}"
                status["status"] = "unhealthy"
    except urllib.error.URLError as e:
        logger.error(f"Qdrant URLError: {e}")
        status["services"]["qdrant"] = f"unhealthy: {str(e)}"
        status["status"] = "unhealthy"
    except Exception as e:
        logger.error(f"Qdrant error: {type(e).__name__}: {e}")
        status["services"]["qdrant"] = f"unhealthy: {str(e)}"
        status["status"] = "unhealthy"

    # Check Redis (if configured)
    try:
        # Simple Redis check using Django cache
        from django.core.cache import cache

        logger.info("Checking Redis")
        cache.set("health_check", "test", 1)
        test_value = cache.get("health_check")
        if test_value == "test":
            status["services"]["redis"] = "healthy"
            logger.info("Redis is healthy")
        else:
            status["services"]["redis"] = "unhealthy: cache test failed"
            status["status"] = "unhealthy"
    except Exception as e:
        logger.error(f"Redis error: {type(e).__name__}: {e}")
        status["services"]["redis"] = f"unhealthy: {str(e)}"
        status["status"] = "unhealthy"

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
    logger.info(f"Health check complete: {status}")
    return JsonResponse(status, status=status_code)
