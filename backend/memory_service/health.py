import requests
from django.conf import settings
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

    # Check Qdrant
    try:
        qdrant_url = f"http://{settings.QDRANT_HOST}:{settings.QDRANT_PORT}/health"
        response = requests.get(qdrant_url, timeout=5)
        if response.status_code == 200:
            status["services"]["qdrant"] = "healthy"
        else:
            status["services"]["qdrant"] = f"unhealthy: status {response.status_code}"
            status["status"] = "unhealthy"
    except Exception as e:
        status["services"]["qdrant"] = f"unhealthy: {str(e)}"
        status["status"] = "unhealthy"

    # # Check Redis (if configured)
    # try:
    #     if hasattr(settings, "REDIS_URL"):
    #         r = redis.from_url(settings.REDIS_URL)
    #         r.ping()
    #         status["services"]["redis"] = "healthy"
    # except Exception as e:
    #     status["services"]["redis"] = f"unhealthy: {str(e)}"

    status_code = 200 if status["status"] == "healthy" else 503
    return JsonResponse(status, status=status_code)
