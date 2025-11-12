import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "your-secret-key")

# DEBUG = os.environ.get("DJANGO_DEBUG", "False") == "True"
DEBUG = True  # Set to False in production

# Get ALLOWED_HOSTS from environment variable
allowed_hosts_env = os.environ.get("ALLOWED_HOSTS", "")
env_hosts = (
    [host.strip() for host in allowed_hosts_env.split(",")] if allowed_hosts_env else []
)

# Combine with default hosts
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "localhost:8000", "127.0.0.1:8000"]
ALLOWED_HOSTS.extend([host for host in env_hosts if host and host not in ALLOWED_HOSTS])

# Qdrant Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)  # Optional
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "memories")

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

STATICFILES_DIRS = [
    (BASE_DIR / "../frontend/build/assets").resolve(),  # Vite builds assets here
]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_q",  # Background job processing
    "memories",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "memory_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "../frontend/build")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "memory_service.wsgi.application"

DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", "sqlite:///db.sqlite3")
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    # Disable authentication and CSRF for all API endpoints (KISS - we're an API service)
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# CORS settings - clean up the duplicates and fix the typo
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Embeddings Configuration
EMBEDDINGS_ENDPOINT_URL = os.getenv("EMBEDDINGS_ENDPOINT_URL", "http://localhost:11434")
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "mxbai-embed-large")
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "ollama")  # ollama, openai, openai_compatible
EMBEDDINGS_API_KEY = os.getenv("EMBEDDINGS_API_KEY", None)
EMBEDDINGS_TIMEOUT = int(os.getenv("EMBEDDINGS_TIMEOUT", "30"))

# Redis Cache Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Django Cache Configuration (use Redis for shared cache between app and worker)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
        "KEY_PREFIX": "mnemosyne",
        "TIMEOUT": 3600,  # 1 hour default timeout
    }
}

# Django-Q Background Job Configuration
Q_CLUSTER = {
    "name": "mnemosyne",
    "workers": 2,
    "timeout": 7200,  # 2 hours max per task (benchmarks can take a long time)
    "retry": 10800,  # Retry failed tasks after 3 hours (must be > timeout)
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",  # Use Django ORM (PostgreSQL) for task queue
    "save_limit": 250,  # Keep last 250 successful tasks
    "max_attempts": 3,  # Retry failed tasks up to 3 times
    "ack_failures": True,  # Acknowledge failed tasks
    "poll": 0.5,  # Poll for new tasks every 0.5 seconds
}

# Security headers and HTTPS settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# For production with HTTPS, uncomment these:
# SECURE_SSL_REDIRECT = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
