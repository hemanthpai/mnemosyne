# Create scripts/start-server.sh
#!/bin/bash
set -e

echo "=== Mnemosyne AI Memory Service Startup ==="
echo "Timestamp: $(date)"

# Wait for database
echo "Waiting for database connection..."
until python manage.py check --database default; do
    echo "Database unavailable - sleeping"
    sleep 2
done
echo "Database connected successfully"

# Wait for Qdrant
echo "Waiting for Qdrant connection..."
until python manage.py test_qdrant_connection; do
    echo "Qdrant unavailable - sleeping"
    sleep 2
done
echo "Qdrant connected successfully"

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Initialize Qdrant collection
echo "Initializing Qdrant collection..."
python manage.py init_qdrant

# Create default settings if they don't exist
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
python manage.py collectstatic --noinput

echo "=== Starting Gunicorn Server ==="
exec gunicorn memory_service.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --worker-class gevent \
    --worker-connections 1000 \
    --timeout 120 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --preload \
    --access-logfile - \
    --error-logfile - \
    --log-level info