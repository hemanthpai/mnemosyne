# Create scripts/start-server.sh
#!/bin/bash
set -e

echo "=== Mnemosyne AI Memory Service Startup ==="
echo "Timestamp: $(date)"

# Wait for database connection (basic connectivity only)
echo "Waiting for database connection..."
until pg_isready -h ${DATABASE_HOST:-db} -p ${DATABASE_PORT:-5432} -U ${DATABASE_USER:-postgres}; do
    echo "Database unavailable - sleeping"
    sleep 2
done
echo "Database connected successfully"

# Run migrations FIRST (before any Django operations that might access models)
echo "Running database migrations..."
python manage.py migrate --noinput

# Now we can safely do Django operations that access the database
echo "Checking Django database configuration..."
python manage.py check --database default

# Wait for Qdrant
echo "Waiting for Qdrant connection..."
until python manage.py test_qdrant; do
    echo "Qdrant unavailable - sleeping"
    sleep 2
done
echo "Qdrant connected successfully"

# Initialize Qdrant collection
echo "Initializing Qdrant collection..."
python manage.py init_qdrant

# Create default settings if they don't exist (now safe after migrations)
echo "Ensuring default settings exist..."
python manage.py shell -c "
from settings_app.models import LLMSettings
if not LLMSettings.objects.exists():
    LLMSettings.objects.create()
    print('Created default settings')
else:
    print('Settings already exist')
"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput --clear || echo "Static files collection skipped"

echo "=== Starting Gunicorn Server ==="
# Minimal but production-ready gunicorn config
exec gunicorn memory_service.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --timeout ${GUNICORN_TIMEOUT:-120} \
    --access-logfile - \
    --error-logfile - \
    --log-level info

echo "=== Mnemosyne AI Memory Service Started Successfully ==="